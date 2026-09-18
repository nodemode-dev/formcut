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
  return LOCALES[locale][key] ?? LOCALES.en[key] ?? key;
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
