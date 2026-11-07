# HASHOUT_LOG · desktop shell and window

Reasoning behind the shell's startup, newest first.

## 2.13.2 · splash parity with formvis

- **Why the main window is built hidden.** It is created only once the engine answers, so before that the person sees nothing; with the splash up first the launch shows a card at once. On macOS a hidden window's web view stops its animation frames and the page renders through them, so the window is built hidden and `conceal` puts it on screen at alpha 0 with clicks passed through; elsewhere it is built hidden and shown by `show_main`. Both carry the page's #0a0a0a background, so no white frame shows.
- **Timing.** `show_main` waits until 2600 ms since `mark_launch`, runs `formcutSplashDone` so the bar completes over 220 ms, shows the main window whole and closes the splash. A 20 s fallback shows the window if the page never reports, so a page that failed to load cannot leave only the splash.
- **Corners.** The splash window is transparent and its page draws the 16 px card. macOS still painted a square behind it, so `round_splash` makes the window non-opaque with a clear background and masks the content layer to the same radius, then shows it. Elsewhere it just shows.
- **Remote origin.** The main window shows the page the engine serves on 127.0.0.1, a remote origin to Tauri, so the capability gains a remote URL list and `app_ready` gets a generated allow permission through `build.rs`. The page calls it through `__TAURI_INTERNALS__`, since the frontend has no Tauri API dependency, two frames after its first content is mounted.
- **Failure paths.** If the engine never starts or the window cannot be built, the splash is closed before the error dialog so the dialog is not hidden behind it.
- **Differs from formvis.** No traffic-light placement, window-state memory or single-instance handling: formcut has none of them.
