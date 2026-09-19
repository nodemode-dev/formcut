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

export const locale = readLocale();

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
    }
    return listed;
  } catch {
    return [];
  }
}

export function setLocale(code: string): void {
  if (!LOCALES[code] || code === locale) return;
  try {
    localStorage.setItem(STORAGE_KEY, code);
  } catch {
    return;
  }
  location.reload();
}
