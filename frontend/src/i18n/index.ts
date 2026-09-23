// Locale strings live in JSON files. The active locale is chosen at boot from
// localStorage and can be changed in place afterwards, without a reload and
// without losing unsaved work; see relocalize below.
import { PHRASES, languagePack } from "./language-pack";
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

/**
 * Languages written right to left.
 *
 * A locale being listed here is what turns the interface around; a dropped-in
 * locale file for one of these codes is enough, no build is needed. The
 * timeline is deliberately not mirrored, whatever the language: time runs from
 * earlier to later, and a person reading Arabic still expects a clip that
 * starts sooner to sit to the left of one that starts later.
 */
export const RTL_LOCALES = new Set(["ar", "he", "fa", "ur", "yi", "dv", "ps"]);

export function direction(code: string = locale): "rtl" | "ltr" {
  return RTL_LOCALES.has(code.split("-")[0]) ? "rtl" : "ltr";
}

export function storedLocale(): string {
  try {
    return localStorage.getItem(STORAGE_KEY) || locale;
  } catch {
    return locale;
  }
}

/**
 * Set the document's direction.
 *
 * At boot this must read the *stored* code rather than the resolved one: a
 * dropped-in language is not in the built-in table yet, so resolving would give
 * English, and the interface would turn from right to left and back again
 * before its locale file arrived.
 */
export function applyDirection(code: string = storedLocale()): void {
  const dir = direction(code);
  const root = document.documentElement;
  if (root.dir !== dir) root.dir = dir;
  if (root.lang !== code) root.lang = code;
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
      // A dropped-in locale the person had already chosen becomes active as
      // soon as its file loads. Without this, choosing a language that is not
      // built in would be forgotten on every restart, and an RTL language would
      // never turn the interface around at all.
      try {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored && stored === entry.code && stored !== locale) {
          locale = stored;
          applyDirection(stored);
          relocalize();
        }
      } catch {
        /* storage unavailable: stay where we are */
      }
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
  // Phrases the interface translates by their English wording (the language
  // pack, and phrase: entries in locale files) map back to that wording, so a
  // switch of language rewrites them too.
  for (const table of Object.values(PHRASES)) {
    for (const [source, value] of Object.entries(table)) {
      if (value && !REVERSE.has(value)) REVERSE.set(value, PHRASE + source);
      if (!REVERSE.has(source)) REVERSE.set(source, PHRASE + source);
    }
  }
}

/** A locale's own wording for an English phrase, from the pack or its file's phrase: entries. */
export const PHRASE = "phrase:";
export function phrase(source: string, code: string = locale): string | undefined {
  return PHRASES[code]?.[source] ?? LOCALES[code]?.[PHRASE + source];
}

function resolve(key: string): string | undefined {
  if (!key.startsWith(PHRASE)) return LOCALES[locale]?.[key] ?? LOCALES.en[key];
  const source = key.slice(PHRASE.length);
  return locale === "en" ? source : phrase(source) ?? source;
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
    const next = resolve(key);
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
      const next = resolve(key);
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
  applyDirection(code);
  relocalize();
  document.dispatchEvent(new CustomEvent("formcut:locale", { detail: { locale: code } }));
}
