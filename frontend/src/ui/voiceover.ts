import type { ProjectEngine } from "../engine/project";
import type { MediaBin } from "../engine/media";
import { t } from "../i18n";

/**
 * Voiceover recording (B7).
 *
 * The browser does the recording, because it is the only thing here with the
 * microphone, and the engine converts what comes back. A level meter runs while
 * recording rather than only a timer: the commonest failure is a muted or wrong
 * input, and a flat meter says so before a take is wasted.
 *
 * Nothing is placed on the timeline until the person asks. A take is kept as
 * media first, so an unwanted one costs a delete rather than an undo.
 */
export function buildVoiceover(engine: ProjectEngine, bin: MediaBin): HTMLElement {
  const root = document.createElement("div");
  root.className = "panel-section voiceover";
  root.innerHTML = `
    <div class="panel-section-head"><span>${t("voice.title")}</span><small>${t("voice.hint")}</small></div>
    <div class="panel-rows">
      <div class="stock-row">
        <button class="tool-chip is-primary" data-ref="vo-record">${t("voice.record")}</button>
        <button class="tool-chip" data-ref="vo-stop" hidden>${t("voice.stop")}</button>
        <span class="vo-time" data-ref="vo-time">0.0s</span>
      </div>
      <div class="vo-meter" aria-hidden="true"><span data-ref="vo-level"></span></div>
      <audio class="vo-preview" data-ref="vo-preview" controls hidden></audio>
      <div class="stock-row">
        <button class="tool-chip" data-ref="vo-place" hidden>${t("voice.place")}</button>
        <button class="tool-chip" data-ref="vo-discard" hidden>${t("voice.discard")}</button>
      </div>
      <p class="stock-note" data-ref="vo-note"></p>
    </div>`;

  const pick = <T extends HTMLElement>(ref: string) => root.querySelector<T>(`[data-ref="${ref}"]`)!;
  const recordButton = pick<HTMLButtonElement>("vo-record");
  const stopButton = pick<HTMLButtonElement>("vo-stop");
  const placeButton = pick<HTMLButtonElement>("vo-place");
  const discardButton = pick<HTMLButtonElement>("vo-discard");
  const level = pick<HTMLElement>("vo-level");
  const clock = pick<HTMLElement>("vo-time");
  const preview = pick<HTMLAudioElement>("vo-preview");
  const note = pick<HTMLElement>("vo-note");

  let recorder: MediaRecorder | null = null;
  let chunks: Blob[] = [];
  let stream: MediaStream | null = null;
  let context: AudioContext | null = null;
  let meterTimer = 0;
  let clockTimer = 0;
  let startedAt = 0;
  let take: Blob | null = null;
  let peak = 0;
  let heard = false;
  let placed: { id: string; duration: number } | null = null;

  const stopMeter = () => {
    window.clearInterval(meterTimer);
    window.clearInterval(clockTimer);
    level.style.width = "0%";
    void context?.close();
    context = null;
  };

  const startMeter = (source: MediaStream) => {
    context = new AudioContext();
    // A context created without a user gesture starts suspended, and a
    // suspended context hands back silence, so the meter reads dead while the
    // recording is working perfectly. Resuming is what makes it tell the truth.
    if (context.state === "suspended") void context.resume();
    const analyser = context.createAnalyser();
    analyser.fftSize = 512;
    context.createMediaStreamSource(source).connect(analyser);
    // An analyser with no route to the destination is not pulled, so it returns
    // silence however loud the input is: the meter read dead while the take
    // recorded a full-scale tone. A silent gain node keeps the graph running
    // without putting the microphone through the speakers, which would howl.
    const silence = context.createGain();
    silence.gain.value = 0;
    analyser.connect(silence).connect(context.destination);
    const buffer = new Float32Array(analyser.fftSize);
    meterTimer = window.setInterval(() => {
      analyser.getFloatTimeDomainData(buffer);
      let sum = 0;
      for (const sample of buffer) sum += sample * sample;
      const rms = Math.sqrt(sum / buffer.length);
      // A meter that only moves for loud speech is not much use, so the scale
      // is compressed toward the quiet end.
      const shown = Math.min(100, Math.round(Math.sqrt(rms) * 220));
      // The meter holds its peak and falls back slowly, the way a real one
      // does. Speech is mostly gaps, so an instantaneous reading spends most of
      // its time at zero and looks like a dead microphone.
      peak = Math.max(shown, peak - 4);
      if (peak > 2) heard = true;
      level.style.width = `${peak}%`;
      level.dataset.live = heard ? "yes" : "no";
    }, 80);
    clockTimer = window.setInterval(() => {
      clock.textContent = `${((performance.now() - startedAt) / 1000).toFixed(1)}s`;
    }, 100);
  };

  recordButton.addEventListener("click", () => void (async () => {
    note.textContent = "";
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (error) {
      note.textContent = `${t("voice.nomic")}: ${error instanceof Error ? error.message : "?"}`;
      return;
    }
    chunks = [];
    recorder = new MediaRecorder(stream);
    recorder.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data); };
    recorder.onstop = () => {
      take = new Blob(chunks, { type: chunks[0]?.type || "audio/webm" });
      preview.src = URL.createObjectURL(take);
      preview.hidden = false;
      placeButton.hidden = false;
      discardButton.hidden = false;
      note.textContent = heard
        ? `${t("voice.took")} ${((performance.now() - startedAt) / 1000).toFixed(1)}s`
        : `${t("voice.took")} ${((performance.now() - startedAt) / 1000).toFixed(1)}s — ${t("voice.silent")}`;
      stream?.getTracks().forEach((track) => track.stop());
      stopMeter();
    };
    peak = 0;
    heard = false;
    startedAt = performance.now();
    recorder.start();
    startMeter(stream);
    recordButton.hidden = true;
    stopButton.hidden = false;
    preview.hidden = true;
    placeButton.hidden = true;
    discardButton.hidden = true;
  })());

  stopButton.addEventListener("click", () => {
    recorder?.stop();
    recordButton.hidden = false;
    stopButton.hidden = true;
  });

  discardButton.addEventListener("click", () => {
    take = null;
    placed = null;
    preview.hidden = true;
    placeButton.hidden = true;
    discardButton.hidden = true;
    note.textContent = t("voice.discarded");
  });

  placeButton.addEventListener("click", () => void (async () => {
    if (!take) return;
    note.textContent = t("voice.saving");
    const body = new FormData();
    body.append("file", take, "voiceover.webm");
    try {
      const item = await fetch("/api/media/voiceover", {
        method: "POST", body, headers: { "x-formcut-local": "1" },
      }).then((response) => (response.ok ? response.json() : Promise.reject(new Error(String(response.status)))));
      await bin.load();
      placed = { id: item.id, duration: item.duration ?? 0 };
      const state = engine.snapshot;
      const timeline = state.timelines[state.activeTimeline];
      const audioTrack = timeline.tracks.findIndex((track) => /audio/i.test(track.name));
      engine.dispatch("clip.add", {
        trackIndex: audioTrack >= 0 ? audioTrack : timeline.tracks.length - 1,
        clip: {
          id: crypto.randomUUID(), kind: "audio", label: item.name,
          mediaId: item.id, start: state.playhead, duration: item.duration || 1,
        },
      });
      note.textContent = `${t("voice.placed")} ${(item.duration ?? 0).toFixed(1)}s`;
      placeButton.hidden = true;
      discardButton.hidden = true;
    } catch (error) {
      note.textContent = `${t("voice.failed")}: ${error instanceof Error ? error.message : "?"}`;
    }
  })());

  Object.defineProperty(root, "lastPlaced", { get: () => placed });
  return root;
}
