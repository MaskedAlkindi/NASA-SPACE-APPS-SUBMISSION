# Mobile setup

Both apps are native clients of the Docker-hosted backend. Start the backend first:

```bash
docker compose up -d --build
```

## Server addresses

| Where the app runs | Server URL to enter in the app |
|---|---|
| iOS Simulator (on the Mac running Docker) | `http://localhost:8000` |
| Android Emulator | `http://10.0.2.2:8000` (default in the app) |
| Physical iPhone / Android phone | `http://<LAN IP of the computer running Docker>:8000`. Phone and computer must be on the same Wi-Fi, and the firewall must allow port 8000 |

Find the LAN IP with `ipconfig` (Windows) or `ipconfig getifaddr en0` (macOS).

## Accounts

- `pilot` (passcode = `DEMO_PASSCODE`, default `hmt-demo`): an empty, **real-data** astronaut (`AST-900`). Use it to upload your own HealthKit / Health Connect data. The anomaly model needs about 7 days of history before it scores.
- `hajid`, `osama`, `hamood`, `haitham`, `mohmmed`: simulated crew. Use these to try the app **without a wearable**.

## iOS (SwiftUI + HealthKit): `ios/HealthMonitor`

Requirements: macOS, Xcode 16+ (the project uses synchronized folder groups), iOS 17+.

1. Open `ios/HealthMonitor/HealthMonitor.xcodeproj`.
2. Select the **HEALTH-01** target, then **Signing & Capabilities**, and choose your Team. Change the bundle ID `org.spaceapps.healthmonitor` if it's already taken.
3. Check that the **HealthKit** capability is present. It comes from `HealthMonitor/HealthMonitor.entitlements`; re-add it in Xcode if signing complains.
4. Run on a simulator or an iPhone. HealthKit works in the Simulator, but there's no Apple Watch data unless you add samples in the Health app.

If Xcode can't open the project, regenerate it with XcodeGen: `brew install xcodegen && cd ios/HealthMonitor && xcodegen generate` (uses `project.yml`).

**Features:** login (token stored in Keychain), backend connection status, dashboard, alerts with evidence, predictions (anomaly, fatigue, forecasts with Swift Charts), assistant chat, fatigue check-in, and offline cache of the last responses.

**HealthKit:** read-only. Each type is requested **individually** from the "Health & Sync" tab, and only for implemented features: heart rate (hourly averages), resting HR, HRV SDNN, sleep (asleep stages merged across sources, per wake-up date), steps, and exercise minutes. No write access is requested. iOS never reports whether read access was denied, so types with no data are shown as unavailable rather than assumed. Not every Apple Watch records every metric. Uploads go through the `apple_health` module with idempotent `external_id`s, so re-syncing updates values instead of duplicating them.

Plain HTTP to the local server is allowed via `NSAllowsLocalNetworking` / `NSAllowsArbitraryLoads` in `Info.plist`. Use HTTPS for anything beyond a local demo. No watchOS app is needed: the iPhone reads Apple Watch data from HealthKit.

## Android (Kotlin + Jetpack Compose + Health Connect): `android/`

Requirements: Android Studio (Ladybug or newer) or the command line with JDK 17, and Android SDK 35.

```bash
cd android
./gradlew assembleDebug
```

```bash
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

On Windows use `gradlew.bat`. Make sure `JAVA_HOME` points to JDK 17. `local.properties` with `sdk.dir=...` is created automatically by Android Studio.

**Health Connect:** the app declares and requests only `READ_HEART_RATE`, `READ_RESTING_HEART_RATE`, `READ_HEART_RATE_VARIABILITY`, `READ_SLEEP`, `READ_STEPS` and `READ_EXERCISE`. Each is requested **individually** with its own "Allow" button. It includes the permission-rationale activity (Android ≤ 13) and the `VIEW_PERMISSION_USAGE` alias (Android 14+). Health Connect reports HRV as **RMSSD**, which is stored as `hrv_rmssd` and never mixed with Apple's SDNN.

- Android 14+: Health Connect is built in.
- Android 9–13: install "Health Connect" from Google Play. The app detects when it's missing or outdated and tells you.
- **No wearable or no Health Connect:** sign in as a simulated crew member to use the dashboard, alerts, predictions and assistant with simulated data.

Cleartext HTTP is allowed for the local demo (`res/xml/network_security_config.xml`).

## Verification status (this build)

| | Status |
|---|---|
| Android | `./gradlew assembleDebug` **succeeded** on Windows (JDK 17, Gradle 8.9, AGP 8.7.3). The APK was installed on an API 30 emulator: login, dashboard and predictions against the backend were **verified**. That emulator has no Health Connect installed, so the app showed the "install/update Health Connect" message as designed. The real Health Connect permission and read flow is **unverified** (it needs a device or emulator with Health Connect) |
| iOS | **Unverified.** It was written on Windows, where Xcode isn't available, so it has not been compiled. Open it in Xcode 16 on a Mac. If the hand-written project file has issues, use the XcodeGen fallback |

## Exercise on a phone

The exercise programs, calendar, manual log, and camera counter live on the website, which is the same UI in a phone browser and on a desktop. The native apps keep uploading HealthKit / Health Connect exercise minutes; those minutes show on the exercise dashboard as wearable time and are not mixed into the manually logged sessions. In-browser pose counting needs camera permission and a MediaPipe download. If that fails, use **Log** on the Exercise page. See [EXERCISE.md](EXERCISE.md).
