import { api, waitJob } from "../engine/api";
import type { ProjectEngine } from "../engine/project";
import type { MediaBin } from "../engine/media";

export function titleSpeech(root: HTMLElement, engine: ProjectEngine, bin: MediaBin): void {
  const voice = root.querySelector<HTMLSelectElement>('[data-ref="tts-voice"]')!;
  const status = root.querySelector<HTMLElement>('[data-ref="cap-status"]')!;
  const trackSelect = root.querySelector<HTMLSelectElement>('[data-ref="cap-track"]')!;
  const refreshTracks = () => {
    const tracks = engine.snapshot.timelines[engine.snapshot.activeTimeline].tracks;
    while (trackSelect.options.length > tracks.length) trackSelect.remove(trackSelect.options.length - 1);
    tracks.forEach((track, index) => { let option = trackSelect.options[index]; if (!option) { option = document.createElement("option"); trackSelect.append(option); } option.value = String(index); if (option.textContent !== track.name) option.textContent = track.name; option.disabled = Boolean(track.locked); });
    if (!trackSelect.selectedOptions[0] || trackSelect.selectedOptions[0].disabled) trackSelect.selectedIndex = tracks.findIndex(track => !track.locked);
  };
  engine.subscribe((_state, changed) => { if (["clips", "timeline", "project"].includes(changed)) refreshTracks(); });
  refreshTracks();
  const button = root.querySelector<HTMLButtonElement>('[data-ref="speak"]')!;
  const cancel = document.createElement("button"); cancel.type = "button"; cancel.className = "tool-chip"; cancel.textContent = "Cancel speech"; cancel.hidden = true; button.after(cancel);
  const say = (message: string) => { status.hidden = false; if (status.textContent !== message) status.textContent = message; };
  let controller: AbortController | undefined;
  cancel.addEventListener("click", () => controller?.abort());
  const load = async () => {
    try {
      const response = await api("/api/speech/voices");
      const known = new Set([...voice.options].map(option => option.value));
      for (const item of response.voices) if (!known.has(item.id)) { const option = document.createElement("option"); option.value = item.id; option.textContent = item.name; voice.append(option); }
    } catch (error) { say((error as Error).message); }
  };
  root.querySelector('[data-ref="tabs"]')!.addEventListener("click", event => { if ((event.target as HTMLElement).closest<HTMLElement>('[data-tab="Text"]')) void load(); });
  button.addEventListener("click", async () => {
    if (controller) return;
    const state = engine.snapshot, selected = state.selectedClipId ? engine.findClip(state.selectedClipId) : null;
    if (!selected || selected.clip.kind !== "text") { say("Select a title to generate local speech."); return; }
    const timelineId = state.timelines[state.activeTimeline].id, start = selected.clip.start;
    const text = selected.clip.textStyle?.content || selected.clip.label;
    controller = new AbortController(); cancel.hidden = false; button.disabled = true;
    const id = voice.value || "af_heart";
    const languages: Record<string, string> = { a: "en-us", b: "en-gb", e: "es", f: "fr-fr", h: "hi", i: "it", j: "ja", p: "pt-br", z: "cmn" };
    say("Generating speech locally...");
    try {
      const queued = await api("/api/speech", { text, voice: id, language: languages[id[0]] || "en-us", speed: 1 });
      const result = await waitJob(queued.job_id, undefined, controller.signal);
      await bin.load();
      const current = engine.snapshot.timelines[engine.snapshot.activeTimeline];
      if (current.id !== timelineId) throw new Error("Speech is in the media bin. The active timeline changed.");
      let trackIndex = current.tracks.findIndex(track => /audio/i.test(track.name) && !track.locked);
      if (trackIndex < 0) { engine.dispatch("track.add", { name: "Audio" }); trackIndex = engine.snapshot.timelines[engine.snapshot.activeTimeline].tracks.length - 1; }
      engine.dispatch("clip.add", { trackIndex, clip: { id: crypto.randomUUID(), kind: "audio", label: result.media.name, start, duration: result.media.duration, mediaId: result.media.id } });
      say("Local speech added to the timeline.");
    } catch (error) { say((error as Error).message); }
    finally { controller = undefined; cancel.hidden = true; button.disabled = false; }
  });
}
