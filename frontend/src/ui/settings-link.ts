/**
 * Open Settings at a page, scrolled to a section, from anywhere. The Settings
 * popout listens for this event, so a dialog that needs something set up can
 * take people there directly without importing the popout.
 */
export function openSettings(page: string, section?: string): void {
  window.dispatchEvent(new CustomEvent("formcut:open-settings", { detail: { page, section } }));
}
