import type { ProjectEngine } from "../engine/project";
import type { MediaBin } from "../engine/media";
import { t } from "../i18n";
import { text } from "../i18n/text";
import { icon } from "./icons";

export type RecordMode = "mic" | "camera" | "screen";

/**
 * One recording section. The mode is fixed at build time, so Studio's
 * Recording tab holds three of these, each with its own devices, live
 * preview, meter, take and placement, and a take in one never disturbs
 * another. All three record through MediaRecorder; the engine's routes turn
 * a microphone take into a wav and remux a screen or camera take so it seeks.
 */
export function buildRecorder(engine: ProjectEngine, bin: MediaBin, mode: RecordMode): HTMLElement {
  const root = document.createElement("div");
  root.className = `panel-section voiceover recorder recorder-${mode}`;
  const title = mode === "mic" ? t("voice.source.mic") : mode === "camera" ? t("voice.source.camera") : t("voice.source.screen");
  const hint = mode === "mic" ? t("voice.hint") : mode === "camera" ? text("The camera with its microphone, previewed live, straight onto the timeline") : text("The screen or a window, with the system sound the browser offers and your microphone if you want it, straight onto the timeline");
  root.innerHTML = `
    <div class="panel-section-head"><span>${title}</span><small>${hint}</small></div>
    <div class="panel-rows">
      <div class="stock-row recorder-devices">
        ${mode !== "screen" ? `<label>${text("Microphone")} <select class="mini-select" data-ref="rec-mic" aria-label="${text("Microphone")}"></select></label>` : ""}
        ${mode === "camera" ? `<label>${text("Camera")} <select class="mini-select" data-ref="rec-cam" aria-label="${text("Camera")}"></select></label>` : ""}
        ${mode === "screen" ? `<label class="recorder-toggle"><input type="checkbox" data-ref="rec-with-mic" /> ${text("Include my microphone")}</label><label>${text("Microphone")} <select class="mini-select" data-ref="rec-mic" aria-label="${text("Microphone")}"></select></label>` : ""}
        ${mode === "camera" ? `<button class="tool-chip" data-ref="rec-preview">${icon("eye")}${text("Show camera")}</button>` : ""}
      </div>
      <div class="stock-row">
        <button class="tool-chip is-primary" data-ref="vo-record">${t("voice.record")}</button>
        <button class="tool-chip" data-ref="vo-stop" hidden>${t("voice.stop")}</button>
        <span class="vo-time" data-ref="vo-time">0.0s</span>
      </div>
      <div class="vo-meter" aria-hidden="true"><span data-ref="vo-level"></span></div>
      ${mode !== "mic" ? `<video class="vo-video recorder-live" data-ref="rec-live" muted autoplay playsinline hidden></video>` : ""}
      <audio class="vo-preview" data-ref="vo-preview" controls hidden></audio>
      <video class="vo-video" data-ref="vo-video" controls playsinline hidden></video>
      <div class="stock-row">
        <button class="tool-chip" data-ref="vo-place" hidden>${t("voice.place")}</button>
        <button class="tool-chip" data-ref="vo-discard" hidden>${t("voice.discard")}</button>
      </div>
      <p class="stock-note" data-ref="vo-note"></p>
    </div>`;

  const pick = <T extends HTMLElement>(ref: string) => root.querySelector<T>(`[data-ref="${ref}"]`)!;
  const maybe = <T extends HTMLElement>(ref: string) => root.querySelector<T>(`[data-ref="${ref}"]`);
  const recordButton = pick<HTMLButtonElement>("vo-record");
  const stopButton = pick<HTMLButtonElement>("vo-stop");
  const placeButton = pick<HTMLButtonElement>("vo-place");
  const discardButton = pick<HTMLButtonElement>("vo-discard");
  const level = pick<HTMLElement>("vo-level");
  const clock = pick<HTMLElement>("vo-time");
  const preview = pick<HTMLAudioElement>("vo-preview");
  const video = pick<HTMLVideoElement>("vo-video");
  const note = pick<HTMLElement>("vo-note");
  const live = maybe<HTMLVideoElement>("rec-live");
  const micSelect = maybe<HTMLSelectElement>("rec-mic");
  const camSelect = maybe<HTMLSelectElement>("rec-cam");
  const withMic = maybe<HTMLInputElement>("rec-with-mic");
  const previewButton = maybe<HTMLButtonElement>("rec-preview");

  let recorder: MediaRecorder | null = null;
  let chunks: Blob[] = [];
  let stream: MediaStream | null = null;
  let liveStream: MediaStream | null = null;
  let context: AudioContext | null = null;
  let mixContext: AudioContext | null = null;
  let meterTimer = 0;
  let clockTimer = 0;
  let startedAt = 0;
  let take: Blob | null = null;
  let peak = 0;
  let heard = false;
  let placed: { id: string; duration: number } | null = null;
  const takeVideo = mode !== "mic";

  // Device lists: labels appear only after a permission grant, so the lists
  // are filled again after the first take starts. Options are patched in
  // place; a chosen device is kept across refills.
  const fillDevices = async () => {
    if (!navigator.mediaDevices?.enumerateDevices) return;
    let devices: MediaDeviceInfo[] = [];
    try { devices = await navigator.mediaDevices.enumerateDevices(); } catch { return; }
    const fill = (select: HTMLSelectElement | null, kind: MediaDeviceKind, fallback: string) => {
      if (!select) return;
      const wanted = devices.filter((device) => device.kind === kind);
      const chosen = select.value;
      const options = wanted.length ? wanted.map((device, index) => ({ value: device.deviceId, label: device.label || `${fallback} ${index + 1}` })) : [{ value: "", label: text("Default") }];
      while (select.options.length > options.length) select.remove(select.options.length - 1);
      options.forEach((option, index) => {
        let node = select.options[index];
        if (!node) { node = document.createElement("option"); select.append(node); }
        if (node.value !== option.value) node.value = option.value;
        if (node.textContent !== option.label) node.textContent = option.label;
      });
      if (chosen && options.some((option) => option.value === chosen) && select.value !== chosen) select.value = chosen;
    };
    fill(micSelect, "audioinput", text("Microphone"));
    fill(camSelect, "videoinput", text("Camera"));
  };
  void fillDevices();
  navigator.mediaDevices?.addEventListener?.("devicechange", () => void fillDevices());

  const audioConstraint = (): MediaTrackConstraints | boolean => {
    const id = micSelect?.value;
    return id ? { deviceId: { exact: id } } : true;
  };
  const videoConstraint = (): MediaTrackConstraints | boolean => {
    const id = camSelect?.value;
    return id ? { deviceId: { exact: id } } : true;
  };

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
    // silence however loud the input is. A silent gain node keeps the graph
    // running without putting the microphone through the speakers.
    const silence = context.createGain();
    silence.gain.value = 0;
    analyser.connect(silence).connect(context.destination);
    const buffer = new Float32Array(analyser.fftSize);
    meterTimer = window.setInterval(() => {
      analyser.getFloatTimeDomainData(buffer);
      let sum = 0;
      for (const sample of buffer) sum += sample * sample;
      const rms = Math.sqrt(sum / buffer.length);
      const shown = Math.min(100, Math.round(Math.sqrt(rms) * 220));
      // The meter holds its peak and falls back slowly, the way a real one does.
      peak = Math.max(shown, peak - 4);
      if (peak > 2) heard = true;
      level.style.width = `${peak}%`;
      level.dataset.live = heard ? "yes" : "no";
    }, 80);
    clockTimer = window.setInterval(() => {
      clock.textContent = `${((performance.now() - startedAt) / 1000).toFixed(1)}s`;
    }, 100);
  };

  const showLive = (source: MediaStream) => {
    if (!live) return;
    live.srcObject = source;
    live.hidden = false;
  };
  const hideLive = () => {
    if (!live) return;
    live.srcObject = null;
    live.hidden = true;
  };
  const stopLivePreview = () => {
    liveStream?.getTracks().forEach((track) => track.stop());
    liveStream = null;
    if (!recorder) hideLive();
  };

  // The camera can be looked at before a take: the preview stream is the
  // camera alone, and a take starts its own stream so the microphone joins.
  previewButton?.addEventListener("click", () => void (async () => {
    if (liveStream) { stopLivePreview(); previewButton.innerHTML = `${icon("eye")}${text("Show camera")}`; return; }
    try {
      liveStream = await navigator.mediaDevices.getUserMedia({ video: videoConstraint(), audio: false });
    } catch (error) {
      note.textContent = `${t("voice.nosource")}: ${error instanceof Error ? error.message : "?"}`;
      return;
    }
    showLive(liveStream);
    previewButton.innerHTML = `${icon("eye")}${text("Hide camera")}`;
    await fillDevices();
  })());

  // A screen take with the microphone: the browser's display stream may carry
  // system sound and the microphone is a second stream; both feed one
  // destination so the take has one audio track with everything in it.
  const captureStream = async (): Promise<MediaStream> => {
    if (mode === "mic") return navigator.mediaDevices.getUserMedia({ audio: audioConstraint() });
    if (mode === "camera") return navigator.mediaDevices.getUserMedia({ video: videoConstraint(), audio: audioConstraint() });
    const display = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: true });
    if (!withMic?.checked) return display;
    let mic: MediaStream;
    try { mic = await navigator.mediaDevices.getUserMedia({ audio: audioConstraint() }); } catch { return display; }
    mixContext = new AudioContext();
    if (mixContext.state === "suspended") void mixContext.resume();
    const destination = mixContext.createMediaStreamDestination();
    if (display.getAudioTracks().length) mixContext.createMediaStreamSource(new MediaStream(display.getAudioTracks())).connect(destination);
    mixContext.createMediaStreamSource(mic).connect(destination);
    const mixed = new MediaStream([...display.getVideoTracks(), ...destination.stream.getAudioTracks()]);
    display.getVideoTracks()[0]?.addEventListener("ended", () => { mic.getTracks().forEach((track) => track.stop()); });
    return mixed;
  };

  recordButton.addEventListener("click", () => void (async () => {
    note.textContent = "";
    try {
      stream = await captureStream();
    } catch (error) {
      note.textContent = `${t(takeVideo ? "voice.nosource" : "voice.nomic")}: ${error instanceof Error ? error.message : "?"}`;
      return;
    }
    if (liveStream) stopLivePreview();
    const hasAudio = stream.getAudioTracks().length > 0;
    chunks = [];
    recorder = new MediaRecorder(stream);
    recorder.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data); };
    recorder.onstop = () => {
      take = new Blob(chunks, { type: chunks[0]?.type || (takeVideo ? "video/webm" : "audio/webm") });
      const shown = takeVideo ? video : preview;
      shown.src = URL.createObjectURL(take);
      shown.hidden = false;
      placeButton.hidden = false;
      discardButton.hidden = false;
      const took = `${t("voice.took")} ${((performance.now() - startedAt) / 1000).toFixed(1)}s`;
      note.textContent = heard || (takeVideo && !hasAudio) ? took : `${took}, ${t("voice.silent")}`;
      stream?.getTracks().forEach((track) => track.stop());
      void mixContext?.close();
      mixContext = null;
      recorder = null;
      hideLive();
      if (previewButton) previewButton.innerHTML = `${icon("eye")}${text("Show camera")}`;
      recordButton.hidden = false;
      stopButton.hidden = true;
      stopMeter();
    };
    // The browser's own "Stop sharing" control ends a screen take without this
    // panel; the track's ending is the stop, wherever it came from.
    if (mode === "screen") stream.getVideoTracks()[0]?.addEventListener("ended", () => recorder?.stop());
    peak = 0;
    heard = false;
    startedAt = performance.now();
    recorder.start();
    if (takeVideo) showLive(stream);
    // A stream with no audio track has nothing to meter; the clock still runs.
    if (hasAudio) startMeter(stream);
    else clockTimer = window.setInterval(() => {
      clock.textContent = `${((performance.now() - startedAt) / 1000).toFixed(1)}s`;
    }, 100);
    recordButton.hidden = true;
    stopButton.hidden = false;
    preview.hidden = true;
    video.hidden = true;
    placeButton.hidden = true;
    discardButton.hidden = true;
    void fillDevices();
  })());

  stopButton.addEventListener("click", () => {
    recorder?.stop();
  });

  discardButton.addEventListener("click", () => {
    take = null;
    placed = null;
    preview.hidden = true;
    video.hidden = true;
    placeButton.hidden = true;
    discardButton.hidden = true;
    note.textContent = t("voice.discarded");
  });

  placeButton.addEventListener("click", () => void (async () => {
    if (!take) return;
    note.textContent = t("voice.saving");
    const body = new FormData();
    body.append("file", take, takeVideo ? `${mode}.webm` : "voiceover.webm");
    try {
      const item = await fetch(takeVideo ? "/api/media/capture" : "/api/media/voiceover", {
        method: "POST", body, headers: { "x-formcut-local": "1" },
      }).then((response) => (response.ok ? response.json() : Promise.reject(new Error(String(response.status)))));
      await bin.load();
      placed = { id: item.id, duration: item.duration ?? 0 };
      const state = engine.snapshot;
      const timeline = state.timelines[state.activeTimeline];
      const wanted = takeVideo ? /video/i : /audio/i;
      const trackIndex = timeline.tracks.findIndex((track) => wanted.test(track.name));
      engine.dispatch("clip.add", {
        trackIndex: trackIndex >= 0 ? trackIndex : takeVideo ? 0 : timeline.tracks.length - 1,
        clip: {
          id: crypto.randomUUID(), kind: takeVideo ? "video" : "audio", label: item.name,
          mediaId: item.id, start: state.playhead, duration: item.duration || 1,
          ...(takeVideo ? { filmstrip: true } : {}),
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

/** Studio's Recording tab: the three sections under one sub-tab row. */
export function buildRecording(engine: ProjectEngine, bin: MediaBin): HTMLElement {
  const host = document.createElement("div");
  host.className = "recording";
  host.innerHTML = `<div class="stock-row recording-tabs"><div class="seg" data-ref="rec-tabs" role="tablist">
    <button class="is-active" data-mode="mic" role="tab" aria-selected="true">${icon("speak")}${t("voice.source.mic")}</button>
    <button data-mode="screen" role="tab" aria-selected="false">${icon("layout")}${t("voice.source.screen")}</button>
    <button data-mode="camera" role="tab" aria-selected="false">${icon("eye")}${t("voice.source.camera")}</button>
  </div></div>`;
  const sections: Record<RecordMode, HTMLElement> = {
    mic: buildRecorder(engine, bin, "mic"),
    screen: buildRecorder(engine, bin, "screen"),
    camera: buildRecorder(engine, bin, "camera"),
  };
  for (const [mode, section] of Object.entries(sections)) {
    section.dataset.mode = mode;
    section.hidden = mode !== "mic";
    host.append(section);
  }
  const tabs = host.querySelector<HTMLElement>('[data-ref="rec-tabs"]')!;
  tabs.addEventListener("click", (event) => {
    const hit = (event.target as HTMLElement).closest<HTMLButtonElement>("[data-mode]");
    if (!hit) return;
    const mode = hit.dataset.mode as RecordMode;
    for (const button of tabs.querySelectorAll<HTMLButtonElement>("[data-mode]")) {
      const active = button === hit;
      if (button.classList.contains("is-active") !== active) button.classList.toggle("is-active", active);
      if (button.getAttribute("aria-selected") !== String(active)) button.setAttribute("aria-selected", String(active));
    }
    for (const [name, section] of Object.entries(sections)) {
      const shown = name === mode;
      if (section.hidden === shown) section.hidden = !shown;
    }
  });
  return host;
}
