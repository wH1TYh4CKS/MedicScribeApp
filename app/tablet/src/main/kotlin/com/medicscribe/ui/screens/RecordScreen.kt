package com.medicscribe.ui.screens

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import androidx.core.content.ContextCompat
import com.medicscribe.BuildConfig
import com.medicscribe.audio.AudioCapture
import com.medicscribe.audio.PcmStreamer
import com.medicscribe.domain.RecordingPhase
import com.medicscribe.domain.SessionState
import com.medicscribe.domain.TranscriptLine
import com.medicscribe.net.ClientMessage
import com.medicscribe.net.ServerMessage
import com.medicscribe.net.WsClient
import com.medicscribe.net.WsEvent
import java.util.UUID
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class RecordController(private val scope: CoroutineScope) {
    private val _state = MutableStateFlow(SessionState())
    val state = _state.asStateFlow()
    private var ws: WsClient? = null
    private var streamer: PcmStreamer? = null
    private val capture = AudioCapture()

    fun start() {
        val sid = UUID.randomUUID().toString()
        _state.value = SessionState(
            phase = RecordingPhase.CONNECTING,
            sessionId = sid,
            statusText = "Connecting...",
        )
        val url = "ws://${BuildConfig.SERVER_HOST}:${BuildConfig.SERVER_PORT}${BuildConfig.WS_PATH}"
        val client = WsClient(url)
        ws = client
        scope.launch {
            client.flow.collect { ev ->
                when (ev) {
                    WsEvent.Connected -> {
                        client.send(ClientMessage.Start(sessionId = sid))
                        _state.value = _state.value.copy(statusText = "Sent start")
                    }
                    is WsEvent.Message -> when (val m = ev.msg) {
                        is ServerMessage.Ack -> {
                            _state.value = _state.value.copy(
                                phase = RecordingPhase.RECORDING,
                                statusText = "Recording ${m.sessionId.take(8)}",
                                recordingStartedAt = System.currentTimeMillis(),
                            )
                            streamer = PcmStreamer(capture, client).also { it.start(scope) }
                        }
                        is ServerMessage.AudioDeleted -> {
                            // Server confirms the WAV is gone (PDPA). Stamp it for
                            // the privacy receipt — real proof, not a claim.
                            _state.value = _state.value.copy(
                                audioDeletedAt = System.currentTimeMillis(),
                            )
                        }
                        is ServerMessage.TranscriptFinal -> {
                            _state.value = _state.value.copy(
                                transcript = _state.value.transcript +
                                    TranscriptLine(text = m.text, lang = m.lang),
                            )
                        }
                        is ServerMessage.NoteProgress -> {
                            _state.value = _state.value.copy(
                                phase = RecordingPhase.GENERATING_NOTE,
                                statusText = "${m.stage} ${m.pct}%",
                            )
                        }
                        is ServerMessage.NoteDone -> {
                            _state.value = _state.value.copy(
                                phase = RecordingPhase.NOTE_READY,
                                note = m.note,
                                rawTranscript = m.rawTranscript,
                                statusText = "Note ready",
                                noteReadyAt = System.currentTimeMillis(),
                            )
                            // Note is in hand. Close the socket ourselves so OkHttp
                            // stops pinging — otherwise a lagging server-side close
                            // (e.g. over Tailscale) trips the 20s ping timeout and
                            // would knock us off the note screen.
                            streamer?.stop()
                            streamer = null
                            ws?.close()
                            ws = null
                        }
                        is ServerMessage.ErrorMessage -> {
                            _state.value = _state.value.copy(
                                phase = RecordingPhase.ERROR,
                                lastError = "${m.code}: ${m.message}",
                                statusText = "Error",
                            )
                        }
                        else -> Unit
                    }
                    is WsEvent.Failure -> {
                        // Once the note is shown the socket is being torn down;
                        // ignore late failures/pings so the note screen survives.
                        if (_state.value.phase != RecordingPhase.NOTE_READY) {
                            _state.value = _state.value.copy(
                                phase = RecordingPhase.ERROR,
                                lastError = ev.t.message,
                                statusText = "WS failure",
                            )
                        }
                    }
                    WsEvent.Closed -> {
                        if (_state.value.phase != RecordingPhase.NOTE_READY) {
                            _state.value = _state.value.copy(
                                phase = RecordingPhase.DONE,
                                statusText = "Closed",
                            )
                        }
                    }
                    else -> Unit
                }
            }
        }
        client.connect()
    }

    fun stop() {
        _state.value = _state.value.copy(
            phase = RecordingPhase.STOPPING,
            statusText = "Stopping...",
            recordingStoppedAt = System.currentTimeMillis(),
        )
        streamer?.stop()
        streamer = null
        // Send Stop and WAIT for note_done / error / server-side close.
        // The server can take ~30s to generate the note; closing here would
        // kill the socket before the note frame arrives.
        ws?.send(ClientMessage.Stop)
    }

    fun reset() {
        streamer?.stop()
        streamer = null
        ws?.close()
        ws = null
        // Wipe all session data; flag the idle screen to confirm "Cleared".
        _state.value = SessionState(statusText = "Cleared", justCleared = true)
    }
}

@Composable
fun RecordScreen() {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val controller = remember { RecordController(scope) }
    val state by controller.state.collectAsState()
    var hasMic by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO)
                == PackageManager.PERMISSION_GRANTED,
        )
    }
    val permLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        hasMic = granted
        if (granted) controller.start()
    }

    val serverHost = BuildConfig.SERVER_HOST

    when (state.phase) {
        RecordingPhase.GENERATING_NOTE -> GeneratingPage(statusText = state.statusText)
        RecordingPhase.NOTE_READY -> NotePage(
            note = state.note,
            state = state,
            serverHost = serverHost,
            onNewSession = { controller.reset() },
        )
        else -> RecordPage(
            state = state,
            serverHost = serverHost,
            onRecordClick = {
                when {
                    state.phase == RecordingPhase.RECORDING -> controller.stop()
                    hasMic -> controller.start()
                    else -> permLauncher.launch(Manifest.permission.RECORD_AUDIO)
                }
            },
        )
    }
}
