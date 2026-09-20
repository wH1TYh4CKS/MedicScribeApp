# `app/` — Android client (UI/UX + client behaviour)

Tablet app the doctor uses. Records audio, streams it to the server, displays the live transcript, lets the doctor edit and export the final note. Thin client — no business logic beyond record / display / edit / export.

## Layout

```
app/
├── build.gradle.kts          root Gradle project
├── settings.gradle.kts
├── gradle.properties         shared with project.properties (TBD bridge)
├── gradle/                   wrapper
└── tablet/                   the Android module
    ├── build.gradle.kts
    └── src/main/
        ├── AndroidManifest.xml
        ├── kotlin/com/medicscribe/
        │   ├── MainActivity.kt
        │   ├── ui/
        │   │   ├── theme/
        │   │   ├── screens/        RecordScreen, ReviewScreen
        │   │   └── components/     reusable Compose pieces
        │   ├── audio/              AudioCapture, PcmStreamer
        │   ├── net/                WsClient, RestClient, Protocol
        │   ├── data/               SessionRepo, SettingsStore
        │   ├── domain/             state models, immutable types
        │   └── export/             PdfExporter, DocxExporter, JsonExporter
        └── res/
```

## Why a `tablet/` sub-module

`app/` is a Gradle multi-project root. `tablet/` is the Android app module today; later we can add `wear/`, `phone/`, or `desktop/` modules without restructuring.

## Status

v1.0 scope: Record/Stop button → live transcript → edit → export PDF / DOCX / JSON. No auth, no diarization, no template picker (server uses fixed SOAP_v1).
