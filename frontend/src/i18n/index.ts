// Locale strings live in JSON files; the active locale is chosen once at
// boot from localStorage and applied at render time, so switching persists
// the choice and reloads (panes render their chrome once by design; live
// re-render machinery for a language switch is not worth its complexity).
import { languagePack } from "./language-pack";
import de from "./de.json";
import en from "./en.json";
import es from "./es.json";

const LOCALES: Record<string, Record<string, string>> = { ...languagePack(en), en, es, de };
export const LOCALE_NAMES: Array<{ code: string; name: string }> = [
  { code: "en", name: "English" },
  { code: "es", name: "Español" },
  { code: "de", name: "Deutsch" },
  { code: "fr", name: "Français" },
  { code: "it", name: "Italiano" },
  { code: "ja", name: "日本語" },
  { code: "ko", name: "한국어" },
  { code: "pt-BR", name: "Português (Brasil)" },
  { code: "ru", name: "Русский" },
  { code: "tr", name: "Türkçe" },
  { code: "zh-Hans", name: "简体中文" },
  { code: "zh-Hant", name: "繁體中文" },
];

const STORAGE_KEY = "formcut.locale";

function readLocale(): string {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored && LOCALES[stored]) return stored;
  } catch {
    /* storage unavailable: stay on english */
  }
  return "en";
}

export let locale = readLocale();

export function t(key: string): string {
  return LOCALES[locale]?.[key] ?? LOCALES.en[key] ?? key;
}

/**
 * P6: merge locale files dropped into the data directory's `locales/` folder.
 *
 * A dropped-in file wins over the built-in strings for the codes it carries, so
 * a corrected translation needs no release; it lists under its own
 * `language.name`, and keys it omits fall back to English through t().
 * Called once at start, before the first paint of translated text.
 */
export async function loadExtraLocales(): Promise<Array<{ code: string; name: string; missingCount: number }>> {
  try {
    const reply = await fetch("/api/locales").then((r) => (r.ok ? r.json() : { locales: [] }));
    const listed: Array<{ code: string; name: string; missingCount: number }> = [];
    for (const entry of reply.locales ?? []) {
      if (entry.error || !entry.strings) continue;
      LOCALES[entry.code] = { ...(LOCALES[entry.code] ?? {}), ...entry.strings };
      if (!LOCALE_NAMES.some((known) => known.code === entry.code)) {
        LOCALE_NAMES.push({ code: entry.code, name: entry.name });
      } else {
        const known = LOCALE_NAMES.find((item) => item.code === entry.code)!;
        known.name = entry.name;
      }
      listed.push({ code: entry.code, name: entry.name, missingCount: entry.missingCount ?? 0 });
      indexLocales();
    }
    return listed;
  } catch {
    return [];
  }
}

/** Every string of every locale, mapped back to its key. */
const REVERSE = new Map<string, string>();
function indexLocales(): void {
  REVERSE.clear();
  for (const table of Object.values(LOCALES)) {
    for (const [key, value] of Object.entries(table)) {
      if (typeof value === "string" && value && !REVERSE.has(value)) REVERSE.set(value, key);
    }
  }
}
indexLocales();

const SKIP = "input, textarea, [contenteditable], [data-no-i18n], .clip, .bin-card, .stock-credit";

/**
 * Re-translate what is already on screen.
 *
 * Switching language used to reload the page, which flashed the whole
 * interface away and threw out unsaved work. Instead every visible string is
 * looked up by the key it came from and rewritten in place, so the switch is
 * one repaint and the project stays exactly where it was. Anything holding
 * text a person typed, or a name that belongs to their media, is skipped, and
 * so is anything marked data-no-i18n, which is how the language list keeps its
 * own names in every language.
 */
export function relocalize(root: HTMLElement = document.body): void {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let node: Node | null;
  const pending: Array<[Node, string]> = [];
  while ((node = walker.nextNode())) {
    const parent = (node as Text).parentElement;
    if (!parent || parent.closest(SKIP)) continue;
    const raw = node.textContent ?? "";
    const trimmed = raw.trim();
    if (!trimmed) continue;
    const key = REVERSE.get(trimmed);
    if (!key) continue;
    const next = LOCALES[locale]?.[key] ?? LOCALES.en[key];
    if (next && next !== trimmed) pending.push([node, raw.replace(trimmed, next)]);
  }
  for (const [target, value] of pending) target.textContent = value;
  for (const element of root.querySelectorAll<HTMLElement>("[title],[placeholder],[aria-label]")) {
    if (element.closest("[data-no-i18n]")) continue;
    for (const attribute of ["title", "placeholder", "aria-label"]) {
      const current = element.getAttribute(attribute);
      if (!current) continue;
      const key = REVERSE.get(current.trim());
      if (!key) continue;
      const next = LOCALES[locale]?.[key] ?? LOCALES.en[key];
      if (next && next !== current) element.setAttribute(attribute, next);
    }
  }
}

export function setLocale(code: string): void {
  if (!LOCALES[code] || code === locale) return;
  try {
    localStorage.setItem(STORAGE_KEY, code);
  } catch {
    /* the choice simply does not survive the session */
  }
  locale = code;
  relocalize();
  document.dispatchEvent(new CustomEvent("formcut:locale", { detail: { locale: code } }));
}
