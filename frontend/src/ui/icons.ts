import { LUCIDE } from "./icons-lucide";

const wrap = (inner: string, vb = "0 0 16 16") =>
  `<svg viewBox="${vb}" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${inner}</svg>`;

export const icons: Record<string, string> = {
  logo: `<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true"><path d="M19.618 3.045C20.383 3.045 21.003 3.618 21.003 4.325L21.003 19.675C21.003 20.382 20.383 20.955 19.618 20.955L4.382 20.955C3.617 20.955 2.997 20.382 2.997 19.675L2.997 4.325C2.997 3.618 3.617 3.045 4.382 3.045ZM4.382 1.766C2.853 1.766 1.612 2.912 1.612 4.325L1.612 19.675C1.612 21.088 2.853 22.234 4.382 22.234L19.618 22.234C21.147 22.234 22.388 21.088 22.388 19.675L22.388 4.325C22.388 2.912 21.147 1.766 19.618 1.766Z"/><path d="M9.922 5.604C9.922 4.897 10.543 4.325 11.307 4.325L12.693 4.325C13.457 4.325 14.078 4.897 14.078 5.604L14.078 9.442C14.078 10.148 13.457 10.721 12.693 10.721L11.307 10.721C10.543 10.721 9.922 10.148 9.922 9.442ZM4.382 5.604C4.382 4.897 5.002 4.325 5.767 4.325L7.152 4.325C7.917 4.325 8.537 4.897 8.537 5.604L8.537 14.558C8.537 15.265 7.917 15.838 7.152 15.838L5.767 15.838C5.002 15.838 4.382 15.265 4.382 14.558ZM15.463 5.604C15.463 4.897 16.083 4.325 16.848 4.325L18.233 4.325C18.998 4.325 19.618 4.897 19.618 5.604L19.618 18.396C19.618 19.103 18.998 19.675 18.233 19.675L16.848 19.675C16.083 19.675 15.463 19.103 15.463 18.396Z"/></svg>`,
  play: `<svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor" aria-hidden="true"><path d="M4.5 2.8v10.4L13 8z"/></svg>`,
  pause: `<svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor" aria-hidden="true"><rect x="3.5" y="3" width="3" height="10" rx="1"/><rect x="9.5" y="3" width="3" height="10" rx="1"/></svg>`,
  stepBack: wrap('<path d="M10.5 3.5 6 8l4.5 4.5"/><path d="M5 3.5v9"/>'),
  stepFwd: wrap('<path d="M5.5 3.5 10 8l-4.5 4.5"/><path d="M11 3.5v9"/>'),
  toStart: wrap('<path d="M11 3.5 6.5 8 11 12.5"/><path d="M4.5 3.5v9"/>'),
  toEnd: wrap('<path d="M5 3.5 9.5 8 5 12.5"/><path d="M11.5 3.5v9"/>'),
  export: wrap('<path d="M8 10V2.8M5.2 5.4 8 2.6l2.8 2.8"/><path d="M3 9.5v3A1.5 1.5 0 0 0 4.5 14h7a1.5 1.5 0 0 0 1.5-1.5v-3"/>'),
  search: wrap('<circle cx="7" cy="7" r="4.2"/><path d="m13.5 13.5-3.4-3.4"/>'),
  chevD: wrap('<path d="m4 6.2 4 4 4-4"/>'),
  chevL: wrap('<path d="M9.8 4 6 8l3.8 4"/>'),
  chevR: wrap('<path d="M6.2 4 10 8l-3.8 4"/>'),
  diamond: wrap('<rect x="4.9" y="4.9" width="6.2" height="6.2" rx="1" transform="rotate(45 8 8)"/>'),
  phone: wrap('<rect x="4.6" y="1.8" width="6.8" height="12.4" rx="1.6"/><path d="M7 12.2h2"/>'),
  pointer: `<svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor" aria-hidden="true"><path d="M3.5 2.2 12.8 8l-4 .9-1.6 4.4z"/></svg>`,
  blade: wrap('<path d="M3 12.5 12.6 2.9"/><circle cx="4.6" cy="10.9" r="1.7"/><circle cx="8.2" cy="12.6" r="1.7"/><path d="m8.6 7 4 5.6"/>'),
  split: wrap('<rect x="2" y="4" width="4.6" height="8" rx="1"/><rect x="9.4" y="4" width="4.6" height="8" rx="1"/><path d="M8 2.5v11"/>'),
  hook: wrap('<path d="M8 2.5v6a3 3 0 1 0 6 0V7"/>'),
  trash: wrap('<path d="M3 4.5h10M6.4 4.5V3h3.2v1.5M4.4 4.5l.6 8.5h6l.6-8.5"/>'),
  magnet: wrap('<path d="M5 2.5v6a3 3 0 0 0 6 0v-6"/><path d="M5 2.5h2.4v3H5zM8.6 2.5H11v3H8.6z" fill="currentColor" stroke="none"/><path d="M8 11.5v2"/>'),
  captions: wrap('<rect x="2" y="3.5" width="12" height="9" rx="1.6"/><path d="M4.5 8h4M4.5 10.2h7"/>'),
  speak: wrap('<path d="M3 6.5v3h2.4L9 12.5v-9L5.4 6.5z"/><path d="M11 6a3 3 0 0 1 0 4"/>'),
  detach: wrap('<path d="M2.5 8h2m2 0h1.6m2 0H12m2 0h-.4"/><path d="M4.5 5.4v5.2M8 3.6v8.8M11.5 5.8v4.4"/>'),
  plus: wrap('<path d="M8 3.5v9M3.5 8h9"/>'),
  minus: wrap('<path d="M3.5 8h9"/>'),
  fullscreen: wrap('<path d="M6 2.5H2.5V6M10 2.5h3.5V6M6 13.5H2.5V10M10 13.5h3.5V10"/>'),
  layout: wrap('<rect x="2" y="2.5" width="12" height="11" rx="1.6"/><path d="M2 7h12M7.5 7v6.5"/>'),
  sliders: wrap('<path d="M3 5h10M3 11h10"/><circle cx="6" cy="5" r="1.6" fill="var(--panel)"/><circle cx="10" cy="11" r="1.6" fill="var(--panel)"/>'),
  pip: wrap('<rect x="2" y="3" width="12" height="10" rx="1.6"/><rect x="8" y="7.5" width="4.5" height="3.5" rx="0.8" fill="currentColor" stroke="none"/>'),
  menuLines: wrap('<path d="M3.5 5h9M3.5 8h9M3.5 11h9"/>'),
  lock: wrap('<rect x="4" y="7" width="8" height="6.5" rx="1.4"/><path d="M5.6 7V5.4a2.4 2.4 0 0 1 4.8 0V7"/>'),
  eye: wrap('<path d="M1.8 8s2.4-4 6.2-4 6.2 4 6.2 4-2.4 4-6.2 4S1.8 8 1.8 8z"/><circle cx="8" cy="8" r="1.8"/>'),
  speaker: wrap('<path d="M2.8 6.4v3.2h2.1L8 12.2V3.8L4.9 6.4z"/><path d="M10 6.2a2.6 2.6 0 0 1 0 3.6M11.8 4.6a5 5 0 0 1 0 6.8"/>'),
  grid: wrap('<rect x="2.5" y="2.5" width="4.6" height="4.6" rx="1"/><rect x="8.9" y="2.5" width="4.6" height="4.6" rx="1"/><rect x="2.5" y="8.9" width="4.6" height="4.6" rx="1"/><rect x="8.9" y="8.9" width="4.6" height="4.6" rx="1"/>'),
  reset: `<svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.6 8.5a4.5 4.5 0 1 0 1.2-3.6"/><path d="M3.2 2.6v2.9h2.9"/></svg>`,
  help: wrap('<circle cx="8" cy="8" r="6"/><path d="M6.3 6.2A1.8 1.8 0 1 1 8 9v1"/><circle cx="8" cy="11.6" r="0.5" fill="currentColor" stroke="none"/>'),
  text: wrap('<path d="M3.5 4.5V3h9v1.5M8 3v10M6.3 13h3.4"/>'),
};

export function icon(name: string): string {
  const body = LUCIDE[name];
  if (body) return `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true">${body}</svg>`;
  return icons[name] ?? "";
}
