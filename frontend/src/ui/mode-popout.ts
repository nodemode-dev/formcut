import { t } from "../i18n";
import { icon } from "./icons";
import {
  activeProfile, allProfiles, exportProfile, KNOWN_FEATURES, onInterfaceMode, parseProfile, profileById,
  removeUserProfile, saveUserProfile, switchInterfaceMode, type InterfaceProfile,
} from "./interface-mode";

const GROUPS: Array<[string, string]> = [
  ["menu.", "Menus"], ["titlebar.", "Titlebar"], ["tab.", "Library"], ["group.", "Inspector"], ["subtab.", "Inspector"], ["section.", "Inspector"], ["insp.", "Inspector"],
  ["creator.", "Creator tools"], ["tool.", "Timeline"], ["act.", "Timeline"], ["chip.", "Timeline"], ["zoom.", "Timeline"], ["snap", "Timeline"], ["tl.", "Timeline"], ["kf.", "Timeline"], ["workarea", "Timeline"], ["set.", "Settings"],
];
const groupOf = (id: string) => GROUPS.find(([prefix]) => id.startsWith(prefix))?.[1] ?? "Other";

export function buildModePanel(): HTMLElement {
  const panel = document.createElement("div");
  panel.className = "mode-panel";
  panel.innerHTML = `
    <div class="mode-cards" data-cards></div>
    <div class="panel-section" data-user hidden><div class="panel-section-head"><span>${t("mode.profiles")}</span></div><div class="mode-user" data-user-list></div></div>
    <div class="mode-actions">
      <button class="tool-chip" data-customise aria-expanded="false">${icon("sliders")}${t("mode.customise")}</button>
      <label class="tool-chip mode-import">${icon("folder")}${t("mode.import")}<input type="file" accept=".fcui,application/json" data-import hidden></label>
      <button class="tool-chip" data-export>${icon("download")}${t("mode.export")}</button>
      <button class="tool-chip" data-reset>${icon("reset")}${t("mode.reset")}</button>
    </div>
    <p class="stock-note mode-note" data-note></p>
    <div class="panel-section mode-customise" data-customise-panel hidden><div class="panel-section-head"><span>${t("mode.customise")}</span></div><div class="mode-checklist" data-checklist></div></div>`;
  const q = <T extends HTMLElement = HTMLElement>(name: string) => panel.querySelector<T>(`[data-${name}]`)!;
  const cards = q("cards");
  const userList = q("user-list");
  const note = (text: string) => { const node = q("note"); if (node.textContent !== text) node.textContent = text; };
  const cardNodes = new Map<string, HTMLButtonElement>();

  const card = (profile: InterfaceProfile, builtIn: boolean) => {
    let node = cardNodes.get(profile.id);
    if (!node) {
      node = document.createElement("button");
      node.className = "mode-card";
      node.dataset.id = profile.id;
      node.innerHTML = `<strong></strong><span></span>${builtIn ? "" : `<b class="iconbtn mode-delete" role="button" tabindex="0" title="${t("mode.delete")}" data-delete>${icon("trash")}</b>`}`;
      node.addEventListener("click", (event) => {
        if ((event.target as HTMLElement).closest("[data-delete]")) { removeUserProfile(profile.id); return; }
        switchInterfaceMode(profile.id);
      });
      cardNodes.set(profile.id, node);
    }
    const title = builtIn ? t(profile.id === "easy" ? "mode.easy" : "mode.advanced") : profile.name;
    const desc = builtIn ? t(profile.id === "easy" ? "mode.easyDesc" : "mode.advancedDesc") : profile.description;
    const strong = node.querySelector("strong")!; if (strong.textContent !== title) strong.textContent = title;
    const span = node.querySelector("span")!; if (span.textContent !== desc) span.textContent = desc;
    return node;
  };

  const sync = () => {
    const active = activeProfile();
    const profiles = allProfiles();
    const seen = new Set<string>();
    for (const profile of profiles) {
      const builtIn = profile.id === "easy" || profile.id === "advanced";
      const node = card(profile, builtIn);
      const parent = builtIn ? cards : userList;
      if (node.parentElement !== parent) parent.append(node);
      node.classList.toggle("is-active", profile.id === active.id);
      node.setAttribute("aria-pressed", String(profile.id === active.id));
      seen.add(profile.id);
    }
    for (const [id, node] of cardNodes) if (!seen.has(id)) { node.remove(); cardNodes.delete(id); }
    const hasUser = userList.childElementCount > 0;
    if (q("user").hidden === hasUser) q("user").hidden = !hasUser;
    for (const box of panel.querySelectorAll<HTMLInputElement>("[data-checklist] input")) {
      const on = active.features[box.dataset.feature!] !== false;
      if (box.checked !== on) box.checked = on;
    }
  };

  const checklist = q("checklist");
  const groups = new Map<string, HTMLElement>();
  for (const id of [...KNOWN_FEATURES].sort()) {
    const name = groupOf(id);
    let group = groups.get(name);
    if (!group) {
      group = document.createElement("div"); group.className = "mode-group";
      group.innerHTML = `<p class="home-title">${name}</p>`;
      groups.set(name, group); checklist.append(group);
    }
    const label = document.createElement("label");
    label.className = "mode-check";
    label.innerHTML = `<input type="checkbox" data-feature="${id}"><span>${id}</span>`;
    group.append(label);
  }
  checklist.addEventListener("change", (event) => {
    const box = event.target as HTMLInputElement;
    if (!box.dataset.feature) return;
    const base = activeProfile();
    const custom: InterfaceProfile = base.id === "easy" || base.id === "advanced"
      ? { ...base, id: `${base.id}-custom`, name: `${t(base.id === "easy" ? "mode.easy" : "mode.advanced")} (${t("mode.customise").toLowerCase()})`, description: t("mode.customise"), features: { ...base.features } }
      : { ...base, features: { ...base.features } };
    custom.features[box.dataset.feature!] = box.checked;
    saveUserProfile(custom);
    switchInterfaceMode(custom.id);
  });
  q<HTMLButtonElement>("customise").addEventListener("click", () => {
    const open = q("customise-panel").hidden;
    q("customise-panel").hidden = !open;
    q("customise").setAttribute("aria-expanded", String(open));
  });
  q<HTMLInputElement>("import").addEventListener("change", async () => {
    const file = q<HTMLInputElement>("import").files?.[0];
    if (!file) return;
    const report = parseProfile(await file.text(), file.name.replace(/\.fcui$|\.json$/i, ""));
    q<HTMLInputElement>("import").value = "";
    if (!report.ok) { note(report.reason); return; }
    saveUserProfile(report.profile);
    switchInterfaceMode(report.profile.id);
    note(report.unknown.length ? `${t("mode.unknown")}: ${report.unknown.join(", ")}` : t("mode.imported"));
  });
  q("export").addEventListener("click", () => {
    const profile = activeProfile();
    const blob = new Blob([exportProfile(profile)], { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `${profile.id}.fcui`;
    link.click();
    URL.revokeObjectURL(link.href);
  });
  q("reset").addEventListener("click", () => {
    const active = activeProfile();
    for (const profile of allProfiles()) if (profile.id !== "easy" && profile.id !== "advanced") removeUserProfile(profile.id);
    switchInterfaceMode(active.id.startsWith("easy") ? "easy" : "advanced");
    note("");
  });
  onInterfaceMode(sync);
  sync();
  return panel;
}

export function askInterfaceModeOnce(host: HTMLElement): void {
  try {
    if (localStorage.getItem("formcut.interface")) return;
  } catch {
    return;
  }
  const ask = document.createElement("div");
  ask.className = "mode-ask";
  ask.innerHTML = `<div class="mode-ask-card"><strong>${t("mode.ask")}</strong><div class="mode-cards" data-cards></div><button class="tool-chip" data-later>${t("mode.later")}</button></div>`;
  const cards = ask.querySelector<HTMLElement>("[data-cards]")!;
  for (const id of ["easy", "advanced"]) {
    const profile = profileById(id)!;
    const node = document.createElement("button");
    node.className = `mode-card${id === "easy" ? " is-active" : ""}`;
    node.innerHTML = `<strong>${t(id === "easy" ? "mode.easy" : "mode.advanced")}</strong><span>${t(id === "easy" ? "mode.easyDesc" : "mode.advancedDesc")}</span>`;
    node.addEventListener("click", () => { switchInterfaceMode(profile.id); ask.hidden = true; });
    cards.append(node);
  }
  ask.querySelector("[data-later]")!.addEventListener("click", () => { ask.hidden = true; });
  host.append(ask);
}
