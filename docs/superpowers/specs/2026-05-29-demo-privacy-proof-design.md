# Demo Privacy Proof — Design

**Date:** 2026-05-29
**Status:** Approved (design); pending implementation plan
**Scope:** Phone app (Kotlin/Compose) + server (FastAPI WS), ~6 files

## Purpose

Demo MedicScribe to a clinic client. Prove "zero data retention" *inside the
phone app*, honestly, given the demo runs phone → remote GPU rig over Tailscale
(NOT on-prem yet). Two in-app proofs:

1. **Server identity banner** — show the connection is a private machine, not a
   public cloud service.
2. **Lifecycle receipt card** — show, per consultation, that audio is deleted and
   nothing is stored, with the deletion line backed by a real server event.

## Honesty constraints

- Demo connects over Tailscale to a remote box. Banner must say "Private ·
  Tailscale", NOT "data never leaves the building" (that claim only holds for the
  on-prem production deployment).
- Card states only what the app/server actually did. The "Audio DELETED" line is
  backed by a real `audio_deleted` server event, not a hardcoded claim.

## Current architecture (as built)

- `MainActivity` → `RecordScreen()` (the active screen, in
  `ui/screens/RecordScreen.kt`). `RecordPage`, `NotePage`, `GeneratingPage` are
  presentational; `RecordController` (in `RecordScreen.kt`) holds `SessionState`
  and drives the WebSocket.
- Observable lifecycle points in `RecordController`:
  - `ServerMessage.Ack` → recording started
  - `controller.stop()` → user stopped recording
  - `ServerMessage.NoteDone` → note ready
- Server `WSSession._on_stop()` (in `server/.../ws/session.py`): transcribe whole
  buffer → `_delete_wav()` (PDPA delete) → `_maybe_generate_note()` → `NoteDone`.
  No deletion event is currently emitted to the client.
- `domain/SessionState.kt`: `phase`, `note`, `justCleared`, etc.
- Protocol: client `net/Protocol.kt`, server `ws/protocol.py` (discriminated by
  `type`).

## Feature 1 — Server identity banner (client-only)

**New file** `net/ServerIdentity.kt`:

```kotlin
data class ServerIdentity(val host: String, val label: String, val isPrivate: Boolean)

fun classifyServer(host: String): ServerIdentity
```

Classification rules (first match wins):

| Host pattern | label | isPrivate |
|---|---|---|
| `10.0.2.2` | "Local (emulator)" | true |
| starts `100.` (64–127 second octet) OR ends `.ts.net` | "Private · Tailscale" | true |
| starts `10.` / `192.168.` / `172.16.`–`172.31.` | "Private · LAN" | true |
| anything else | "⚠ External" | false |

(Keep the Tailscale CGNAT check simple: `100.` prefix is acceptable for the demo;
note the 64–127 range in a comment.)

**UI**: a thin banner row rendered under the top app bar on `RecordPage` and
`NotePage`:

```
🔒 <host> · <label> · Not the cloud
```

- Navy text on white when `isPrivate`, error-red when not (catches a
  misconfigured build before it reaches a client).
- Host comes from `BuildConfig.SERVER_HOST`.

## Feature 2 — Lifecycle receipt card (approach C)

### Server change — one new event

`ws/protocol.py`: add

```python
class AudioDeleted(BaseModel):
    type: Literal["audio_deleted"] = "audio_deleted"
    session_id: str
```

Add to the `ServerMessage` union.

`ws/session.py._on_stop()`: emit it immediately after `_delete_wav()`:

```python
self._delete_wav()
if self.session_id is not None:
    await self._send(AudioDeleted(session_id=self.session_id))
await self._maybe_generate_note()
```

So ordering on the wire is: `transcript_final*` → `audio_deleted` → `note_progress`
→ `note_done`.

### Client changes

`net/Protocol.kt`: add

```kotlin
@Serializable
@SerialName("audio_deleted")
data class AudioDeleted(
    @SerialName("session_id") val sessionId: String,
) : ServerMessage()
```

`domain/SessionState.kt`: add nullable epoch-millis fields (default null):
`recordingStartedAt`, `recordingStoppedAt`, `audioDeletedAt`, `noteReadyAt`.

`RecordController` stamps timestamps (`System.currentTimeMillis()`):
- on `Ack` → `recordingStartedAt`
- in `stop()` → `recordingStoppedAt`
- on `AudioDeleted` → `audioDeletedAt` (real server confirmation)
- on `NoteDone` → `noteReadyAt`

`reset()` already builds a fresh `SessionState`, so timestamps clear on Done.

### Card UI

A collapsible "Privacy" section on `NotePage`, under the note, above the Done
button. Collapsed by default (doctor wants the note first); one tap expands.

```
Privacy ▾
  ✓ Recording started   <recordingStartedAt, HH:mm:ss>
  ✓ Recording stopped   <recordingStoppedAt>
  ✗ Audio DELETED       <audioDeletedAt>   (server confirmed)
  ✓ Note ready          <noteReadyAt>
  ✗ Note NOT stored — export only
  ✗ Memory wiped when you tap Done
```

Each timestamped row maps 1:1 to a real client-observed event (Ack, stop tap,
`audio_deleted`, `note_done`). No "Transcribed" row — transcription is a
server-side step between stop and delete with no honest client timestamp.

- `✓` = navy, `✗` (deletion/non-retention) = green (good — data gone).
- Times formatted `HH:mm:ss` local. Rows with null timestamp render the line
  without a time (defensive; in the normal flow all four are set).
- `NotePage` signature gains the timestamp inputs (or the whole `SessionState`).

## Files touched

1. `server/.../ws/protocol.py` — `AudioDeleted` model + union.
2. `server/.../ws/session.py` — emit `AudioDeleted` in `_on_stop()`.
3. `app/.../net/Protocol.kt` — `AudioDeleted` client model.
4. `app/.../net/ServerIdentity.kt` — NEW, classifier.
5. `app/.../domain/SessionState.kt` — timestamp fields.
6. `app/.../ui/screens/RecordScreen.kt` — `RecordController` stamps timestamps,
   handles `AudioDeleted`; passes data to pages.
7. `app/.../ui/screens/RecordPage.kt` + `NotePage.kt` — banner + lifecycle card.

(Counts as ~6–7 files; RecordPage/NotePage are small presentational edits.)

## Testing

- **Server pytest** (extend `tests/test_ws_note.py` or `test_ws_session.py`):
  assert an `audio_deleted` frame is received, and that it arrives before
  `note_done`.
- **Kotlin unit** (`ServerIdentityTest`): classify cases — `10.0.2.2`, a `100.x`
  Tailscale IP, `192.168.x`, a public IP.

## Out of scope (YAGNI)

- Dedicated full privacy/status screen with live on-disk counts.
- `session_purged` server event (phone memory wipe is client-side via `reset()`;
  server purge is already logged server-side).
- Airplane-mode / LAN-only proof (only valid for on-prem production, not this
  remote demo).
- GPU-tier packaging and pricing (separate, non-code workstream).
