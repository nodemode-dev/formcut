# formcut on phones

A thin Tauri 2 app for iOS and Android. It shows one screen that asks for your computer's address, then opens the formcut running there; the computer's engine serves its pairing page and, once the phone is paired, the whole interface. The shell stores only the address.

## On the computer first

In formcut, open Settings, then Phones and other computers. Turn access on, press Pair a device, and note the address and the six-digit code. The code lasts five minutes and works once.

## Builds

The `mobile` workflow builds both on every version tag, or on demand:

- Android: a debug APK, installable on a phone that allows installing unknown apps.
- iOS: a debug build for Xcode's iOS simulator.

To build on your own machine, with the Android SDK and NDK or Xcode installed:

```
cd mobile
npm install
npx tauri android init      # or: npx tauri ios init
npx tauri icon ../src-tauri/icons/icon.png
npx tauri android build --debug --apk      # or: npx tauri ios build --debug --target aarch64-sim
```

## Plain HTTP on the local network

The computer serves formcut over plain HTTP on your network, so both platforms need an exception:

- iOS: `src-tauri/Info.ios.plist` sets `NSAllowsLocalNetworking`, which allows private addresses only, and the local network message iOS shows before the first connection.
- Android: Tauri's generated project allows cleartext traffic in debug builds and not in release builds. A signed release build needs `usesCleartextTraffic` set to true for release in `src-tauri/gen/android/app/build.gradle.kts` after `tauri android init`.

## Signed builds and the stores

- Android: a signing keystore, configured in the generated Android project, for a release APK or an App Bundle.
- iOS: an Apple developer account and team for device builds, TestFlight or the App Store.
- App Store review can reject an app that mostly shows a web interface, so TestFlight or direct distribution may be the practical path for iOS.
