const HEADER = "X-Formcut-Window-Key";
const STORE = "formcut-window-key";

const nativeFetch = window.fetch.bind(window);
let key = "";

function remembered(): string {
  try { return sessionStorage.getItem(STORE) ?? ""; } catch { return ""; }
}

function remember(value: string): void {
  try { sessionStorage.setItem(STORE, value); } catch { return; }
}

async function ticketWith(value: string): Promise<string> {
  const res = await nativeFetch("/api/window/ticket", { method: "POST", headers: { [HEADER]: value, "x-formcut-local": "1" } });
  if (!res.ok) return "";
  const body = await res.json() as { ticket?: unknown };
  return typeof body.ticket === "string" ? body.ticket : "";
}

async function load(): Promise<string> {
  const holder = window as unknown as { __FORMCUT_WINDOW_KEY?: unknown };
  const given = holder.__FORMCUT_WINDOW_KEY;
  delete holder.__FORMCUT_WINDOW_KEY;
  if (typeof given === "string" && given) return given;
  const kept = remembered();
  if (kept && await ticketWith(kept).catch(() => "")) return kept;
  try {
    const res = await nativeFetch("/api/window/key", { method: "POST", headers: { "x-formcut-local": "1" } });
    const body = res.ok ? await res.json() as { key?: unknown } : {};
    if (typeof body.key === "string" && body.key) { remember(body.key); return body.key; }
  } catch { return kept; }
  return kept;
}

export const keyReady: Promise<string> = load().then((value) => { key = value; return value; });

export const windowKey = (): string => key;

export async function socketTicket(): Promise<string> {
  const value = await keyReady;
  return value ? ticketWith(value).catch(() => "") : "";
}

export { HEADER as WINDOW_KEY_HEADER };
