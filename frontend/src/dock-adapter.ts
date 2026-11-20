import type { ConsentChoice, ConsentRequest, DockAdapter, DockAgentStatus, DockChannel, DockErrorKind, DockProgramStatus, DockTerminal, PtyKind, StoredChoice, StoredChoiceState } from "./dock/adapter";
import { Dock } from "./dock/dock";
import "./dock/dock.css";
import "./styles/dock-tokens.css";
import { socketTicket, windowKey, WINDOW_KEY_HEADER } from "./engine/window-key";
import { t } from "./i18n";
import { text } from "./i18n/text";
import { compact } from "./ui/compact";
import { keyLabel } from "./ui/keymap";
import { openSettings } from "./ui/settings-link";

export const DOCK_KEY = "formcut.dock";
export const DOCK_SIZES = { minHeight: 120, defaultHeight: 260, maxHeightShare: 0.45, keepHeight: 440, minWidth: 320, defaultWidth: 400, maxWidthShare: 0.4, keepWidth: 940 };

type Kind = Exclude<PtyKind, "agent"> | "antigravity";
type Told = Partial<DockProgramStatus> & { finding?: string; said?: string };
type Row = { id: string; title: string; alive: boolean; kind: string; tip?: string };
type Frame = { type?: string; data?: string };
type Question = { id: string; action?: string; tool?: string; agent?: string; client?: string; what?: string; offers?: string[]; always?: string; expires?: number; notes?: string[] };
type Withdrawals = { seq: number; events: Array<{ type: string; id: string }> };

const KINDS: Kind[] = ["shell", "claude", "codex", "cursor", "antigravity"];
const CHOICES: ConsentChoice[] = ["deny", "once", "always"];
const COVERED = ".modal-scrim:not([hidden]),.set-scrim:not([hidden]),.start-overlay:not([hidden])";

class EngineError extends Error {
  constructor(message: string, readonly code: string, readonly status: number) { super(message); }
}

async function call<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, body === undefined ? { method } : { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  } catch {
    throw new EngineError("", "unreachable", 0);
  }
  if (response.ok) return (response.status === 204 ? undefined : await response.json()) as T;
  const detail = ((await response.json().catch(() => ({}))) as { detail?: unknown }).detail;
  const told = detail && typeof detail === "object" ? detail as { code?: unknown; message?: unknown } : null;
  const code = typeof told?.code === "string" ? told.code : response.status === 403 ? "refused" : response.status === 404 ? "missing" : "";
  throw new EngineError(typeof told?.message === "string" ? told.message : typeof detail === "string" ? detail : "", code, response.status);
}

function errorKind(err: unknown): DockErrorKind | null {
  if (!(err instanceof EngineError)) return null;
  if (err.code === "notInstalled" || err.code === "busy" || err.code === "refused" || err.code === "unreachable") return err.code;
  return err.code === "missing" ? "oldEngine" : null;
}

function terminal(row: Row): DockTerminal<"antigravity"> {
  const kind = KINDS.includes(row.kind as Kind) ? row.kind as Kind : "shell";
  return row.tip ? { id: row.id, title: row.title, alive: row.alive, kind, tip: row.tip } : { id: row.id, title: row.title, alive: row.alive, kind };
}

function channel(id: string): DockChannel {
  let data = (_chunk: string | Uint8Array): void => undefined;
  let exit = (): void => undefined;
  let lost = (): void => undefined;
  let socket: WebSocket | null = null;
  let shut = false;
  let attached = false;
  let tries = 0;
  let size: { cols: number; rows: number } | null = null;
  const send = (message: unknown): void => { if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify(message)); };
  const connect = async (): Promise<void> => {
    const ticket = await socketTicket();
    if (shut) return;
    if (!ticket) { lost(); return; }
    const made = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api/terminal/tabs/${encodeURIComponent(id)}/ws?ticket=${encodeURIComponent(ticket)}`);
    socket = made;
    made.addEventListener("open", () => { if (size) send({ type: "resize", cols: size.cols, rows: size.rows }); });
    made.addEventListener("message", (event) => {
      let frame: Frame;
      try { frame = JSON.parse(String(event.data)) as Frame; } catch { return; }
      if (frame.type === "replay") { tries = 0; data((attached ? "\x1bc" : "") + (frame.data ?? "")); attached = true; }
      else if (frame.type === "data") data(frame.data ?? "");
      else if (frame.type === "exit") exit();
      else if (frame.type === "restart") data("\x1bc");
      else if (frame.type === "gone") { shut = true; lost(); }
    });
    made.addEventListener("close", () => {
      if (socket !== made) return;
      socket = null;
      if (shut) return;
      if (tries < 5) { tries += 1; window.setTimeout(() => void connect(), 400 * tries); } else lost();
    });
  };
  void connect();
  return {
    send: (chunk) => send({ type: "input", data: chunk }),
    resize: (cols, rows) => { size = { cols, rows }; send({ type: "resize", cols, rows }); },
    onData: (handler) => { data = handler; },
    onExit: (handler) => { exit = handler; },
    onClose: (handler) => { lost = handler; },
    close: () => { shut = true; socket?.close(); },
  };
}

const program = (row: Told | undefined): DockProgramStatus => ({
  installed: row?.installed === true, version: row?.version ?? null, install: row?.install ?? "", signedIn: row?.signedIn ?? null,
  ...(row?.finding && row.finding !== "runs" && typeof row.said === "string" ? { note: row.said } : {}),
});

let add: ((request: ConsentRequest) => void) | null = null;
let withdraw: (id: string) => void = () => undefined;
const early: ConsentRequest[] = [];
const open = new Set<string>();
let seq = 0;
let watching = false;

async function watch(): Promise<void> {
  if (watching) return;
  watching = true;
  while (open.size) {
    try {
      const told = await call<Withdrawals>(`/api/agent-access/events?after=${seq}&wait=25`);
      seq = Math.max(seq, told.seq);
      for (const event of told.events) if (event.type === "withdrawn" && open.delete(event.id)) withdraw(event.id);
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 3000));
    }
  }
  watching = false;
}

/** One outside agent's question, as the engine sends it, shown by the family's dialog. */
export function agentQuestion(raw: Question): void {
  if (open.has(raw.id)) return;
  const offers = CHOICES.filter((choice) => (raw.offers ?? ["deny", "once"]).includes(choice));
  const request: ConsentRequest = { id: raw.id, agent: raw.client || raw.agent || "", what: raw.what || `run ${raw.tool ?? ""}`, offers, always: raw.always === "agent" ? "agent" : "all", escape: "deny", notes: raw.notes ?? [] };
  if (typeof raw.expires === "number") request.expires = raw.expires;
  open.add(raw.id);
  if (add) add(request); else early.push(request);
  void watch();
}

const available = (): boolean => !compact() && !document.querySelector(COVERED);

const adapter: DockAdapter<"antigravity"> = {
  words: { app: "formcut", noun: "video", lead: "Claude Code works on your {noun} in {app} with you: say what you want done.", example: "cut the pauses and add captions", start: "./formcut" },
  placement: { mode: "own", storage: { key: DOCK_KEY, legacy: [] }, sizes: DOCK_SIZES, canDockRight: () => !compact() },
  passKey: () => false,
  isDockChord: (event) => event.code === "KeyJ" && (event.metaKey || event.ctrlKey) && !event.shiftKey && !event.altKey && available(),
  chordLabel: () => keyLabel("mod+j"),
  tabs: () => ({ builtin: ["shell", "claude", "codex", "cursor", "antigravity"] }),
  classes: { iconButton: "iconbtn", button: "tool-chip", primaryButton: "is-primary", input: "", select: "", note: "fc-dock-note" },
  t: (key, english) => { const name = `dock.${key}`; const own = t(name); return own === name ? text(english) : own; },
  onTheme: () => undefined,
  keyHeaders: () => ({ [WINDOW_KEY_HEADER]: windowKey(), "x-formcut-local": "1" }),
  errors: { message: (err) => (err instanceof EngineError && err.message ? err.message : null), kind: errorKind },
  terminal: {
    list: async () => (await call<{ tabs: Row[] }>("/api/terminal/tabs")).tabs.map(terminal),
    open: async (kind, options) => terminal(await call<Row>("/api/terminal/tabs", "POST", { kind, ...options })),
    restart: async (id) => { await call(`/api/terminal/tabs/${encodeURIComponent(id)}/restart`, "POST", {}); },
    close: async (id) => { await call(`/api/terminal/tabs/${encodeURIComponent(id)}`, "DELETE"); },
    channel,
  },
  agentStatus: async (): Promise<DockAgentStatus<"antigravity"> | null> => {
    try {
      const told = await call<Partial<Record<"claude" | "codex" | "cursor" | "antigravity", Told>>>("/api/terminal/agents");
      return { claude: program(told.claude), codex: program(told.codex), cursor: program(told.cursor), antigravity: program(told.antigravity) };
    } catch { return null; }
  },
  consent: {
    subscribe: (onAdd, onWithdraw) => {
      add = onAdd;
      withdraw = onWithdraw;
      for (const request of early.splice(0)) onAdd(request);
      const read = (): void => {
        void call<{ seq: number; requests: Question[] }>("/api/agent-access/waiting").then((told) => {
          seq = Math.max(seq, told.seq);
          for (const raw of told.requests) agentQuestion(raw);
        }, () => undefined);
      };
      read();
      for (const later of [13000, 27000]) window.setTimeout(read, later);
    },
    answer: async (id: string, choice: ConsentChoice) => {
      open.delete(id);
      await call(`/api/extensions/agent/${encodeURIComponent(id)}`, "POST", { result: choice });
    },
  },
  storedChoice: {
    get: async (): Promise<StoredChoiceState> => {
      const told = await call<{ choice: string; sealBroken: boolean }>("/api/agent-access");
      return { value: told.choice === "allowed" || told.choice === "blocked" ? told.choice : "ask", changedOutside: told.sealBroken === true };
    },
    set: async (value: StoredChoice) => { await call("/api/agent-access", "PUT", { choice: value }); },
  },
  openSettings: () => openSettings("connections", "access"),
};

let dock: Dock<"antigravity"> | null = null;

/** The family's terminal panel, built once and placed after the workspace; it asks the engine nothing until it is opened. */
export function installDock(host: HTMLElement, before: Node | null = null): Dock<"antigravity"> {
  if (dock) return dock;
  dock = new Dock(adapter);
  dock.mount(host, before);
  return dock;
}

export function toggleDock(): void {
  if (available() || dock?.isOpen()) dock?.toggle();
}

export async function showDock(kind: "shell" | "claude" = "shell"): Promise<void> {
  if (!compact()) await dock?.show(kind);
}
