# formcut mobile

## Current browser surface

The responsive layout and PWA shell are retained. They do not provide an offline mobile media engine. The current editor requires a Python service on the same machine, bound to loopback; a phone cannot connect to a desktop service over the LAN. Browser and touch acceptance on a phone is still to be rerun.

## Native shells (Tauri 2, build on machines with the SDKs)
Native mobile is not implemented. The following Tauri generator commands can initialize shells on SDK-equipped machines, but they do not supply a mobile engine or make this desktop application run on a phone:

    cargo install tauri-cli --version "^2"
    cd src-tauri
    cargo tauri android init     # needs Android Studio, SDK, NDK, JDK 17
    cargo tauri android dev
    cargo tauri ios init         # macOS only; needs Xcode and cocoapods
    cargo tauri ios dev

The generators create platform projects only. Android and iOS cannot use the desktop PyInstaller executable or its process-spawn lifecycle unchanged. Completing mobile requires platform-compatible media/inference/render processing, permissions, storage and lifecycle integration, followed by device verification.
