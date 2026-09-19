import { LUCIDE } from "./icons-lucide";

const wrap = (inner: string, vb = "0 0 16 16") =>
  `<svg viewBox="${vb}" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${inner}</svg>`;

export const icons: Record<string, string> = {
  // The supplied formcut mark, used for the titlebar home button and the
  // start screen. Drawn with currentColor so it takes the accent.
  logo: `<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true"><path d="M18.987 1.52L4.522 1.52C2.863 1.52 1.525 2.858 1.525 4.518L1.525 18.992C1.525 20.642 2.863 21.98 4.513 21.98L18.987 21.98C20.637 21.98 21.975 20.642 21.975 18.992L21.975 4.518C21.975 2.868 20.637 1.529 18.987 1.529ZM3.45 5.233C3.45 4.389 4.027 3.702 4.742 3.702L14.019 3.702C14.734 3.702 15.311 4.389 15.311 5.233L15.311 6.763C15.311 7.607 14.734 8.294 14.019 8.294L4.742 8.294C4.027 8.294 3.45 7.607 3.45 6.763L3.45 5.233ZM3.45 10.998C3.45 10.155 4.027 9.468 4.742 9.468L10.462 9.468C11.177 9.468 11.755 10.155 11.755 10.998L11.755 12.529C11.755 13.373 11.177 14.06 10.462 14.06L4.742 14.06C4.027 14.06 3.45 13.373 3.45 12.529L3.45 10.998ZM6.044 18.378C6.044 19.166 5.475 19.798 4.779 19.798L4.715 19.798C4.018 19.798 3.45 19.157 3.45 18.378L3.45 16.627C3.45 15.838 4.018 15.206 4.715 15.206L4.779 15.206C5.475 15.206 6.044 15.848 6.044 16.627L6.044 18.378ZM16.705 18.222C16.705 19.093 16.072 19.798 15.293 19.798L8.143 19.798C7.364 19.798 6.731 19.093 6.731 18.222L6.731 16.783C6.731 15.912 7.364 15.206 8.143 15.206L15.293 15.206C16.072 15.206 16.705 15.912 16.705 16.783L16.705 18.222ZM20.06 6.873C20.06 7.662 19.491 8.294 18.795 8.294L17.273 8.294C16.576 8.294 16.008 7.653 16.008 6.873L16.008 5.123C16.008 4.334 16.576 3.702 17.273 3.702L18.795 3.702C19.491 3.702 20.06 4.343 20.06 5.123L20.06 6.873Z"/> <path d="M19.487 2.02L5.022 2.02C3.363 2.02 2.025 3.358 2.025 5.018L2.025 19.492C2.025 21.142 3.363 22.48 5.013 22.48L19.487 22.48C21.137 22.48 22.475 21.142 22.475 19.492L22.475 5.018C22.475 3.368 21.137 2.029 19.487 2.029ZM3.95 5.733C3.95 4.889 4.527 4.202 5.242 4.202L14.519 4.202C15.234 4.202 15.811 4.889 15.811 5.733L15.811 7.263C15.811 8.107 15.234 8.794 14.519 8.794L5.242 8.794C4.527 8.794 3.95 8.107 3.95 7.263L3.95 5.733ZM3.95 11.498C3.95 10.655 4.527 9.968 5.242 9.968L10.962 9.968C11.677 9.968 12.255 10.655 12.255 11.498L12.255 13.029C12.255 13.873 11.677 14.56 10.962 14.56L5.242 14.56C4.527 14.56 3.95 13.873 3.95 13.029L3.95 11.498ZM6.544 18.878C6.544 19.666 5.975 20.298 5.279 20.298L5.215 20.298C4.518 20.298 3.95 19.657 3.95 18.878L3.95 17.127C3.95 16.338 4.518 15.706 5.215 15.706L5.279 15.706C5.975 15.706 6.544 16.347 6.544 17.127L6.544 18.878ZM17.205 18.722C17.205 19.593 16.572 20.298 15.793 20.298L8.643 20.298C7.864 20.298 7.231 19.593 7.231 18.722L7.231 17.283C7.231 16.412 7.864 15.706 8.643 15.706L15.793 15.706C16.572 15.706 17.205 16.412 17.205 17.283L17.205 18.722ZM20.56 7.373C20.56 8.162 19.991 8.794 19.295 8.794L17.773 8.794C17.076 8.794 16.508 8.153 16.508 7.373L16.508 5.623C16.508 4.834 17.076 4.202 17.773 4.202L19.295 4.202C19.991 4.202 20.56 4.843 20.56 5.623L20.56 7.373Z" opacity="0.19"/></svg>`,
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
  sliders: wrap('<path d="M3 5h10M3 11h10"/><circle cx="6" cy="5" r="1.6" fill="var(--pane)"/><circle cx="10" cy="11" r="1.6" fill="var(--pane)"/>'),
  pip: wrap('<rect x="2" y="3" width="12" height="10" rx="1.6"/><rect x="8" y="7.5" width="4.5" height="3.5" rx="0.8" fill="currentColor" stroke="none"/>'),
  menuLines: wrap('<path d="M3.5 5h9M3.5 8h9M3.5 11h9"/>'),
  lock: wrap('<rect x="4" y="7" width="8" height="6.5" rx="1.4"/><path d="M5.6 7V5.4a2.4 2.4 0 0 1 4.8 0V7"/>'),
  eye: wrap('<path d="M1.8 8s2.4-4 6.2-4 6.2 4 6.2 4-2.4 4-6.2 4S1.8 8 1.8 8z"/><circle cx="8" cy="8" r="1.8"/>'),
  speaker: wrap('<path d="M2.8 6.4v3.2h2.1L8 12.2V3.8L4.9 6.4z"/><path d="M10 6.2a2.6 2.6 0 0 1 0 3.6M11.8 4.6a5 5 0 0 1 0 6.8"/>'),
  grid: wrap('<rect x="2.5" y="2.5" width="4.6" height="4.6" rx="1"/><rect x="8.9" y="2.5" width="4.6" height="4.6" rx="1"/><rect x="2.5" y="8.9" width="4.6" height="4.6" rx="1"/><rect x="8.9" y="8.9" width="4.6" height="4.6" rx="1"/>'),
  reset: `<svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.6 8.5a4.5 4.5 0 1 0 1.2-3.6"/><path d="M3.2 2.6v2.9h2.9"/></svg>`,
  help: wrap('<circle cx="8" cy="8" r="6"/><path d="M6.3 6.2A1.8 1.8 0 1 1 8 9v1"/><circle cx="8" cy="11.6" r="0.5" fill="currentColor" stroke="none"/>'),
  text: wrap('<path d="M3.5 4.5V3h9v1.5M8 3v10M6.3 13h3.4"/>'),
  close: wrap('<path d="M4 4l8 8M12 4l-8 8"/>'),
};

export function icon(name: string): string {
  const body = LUCIDE[name];
  if (body) return `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true">${body}</svg>`;
  return icons[name] ?? "";
}
