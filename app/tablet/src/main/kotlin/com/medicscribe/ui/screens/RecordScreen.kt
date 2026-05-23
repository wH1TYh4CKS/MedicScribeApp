package com.medicscribe.ui.screens

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.CenterAlignedTopAppBar
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import com.medicscribe.BuildConfig
import com.medicscribe.audio.AudioCapture
import com.medicscribe.audio.PcmStreamer
import com.medicscribe.domain.RecordingPhase
import com.medicscribe.domain.SessionState
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
                            )
                            streamer = PcmStreamer(capture, client).also { it.start(scope) }
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
                        _state.value = _state.value.copy(
                            phase = RecordingPhase.ERROR,
                            lastError = ev.t.message,
                            statusText = "WS failure",
                        )
                    }
                    WsEvent.Closed -> {
                        _state.value = _state.value.copy(
                            phase = RecordingPhase.DONE,
                            statusText = "Closed",
                        )
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
        )
        streamer?.stop()
        streamer = null
        ws?.send(ClientMessage.Stop)
        ws?.close()
        ws = null
    }
}

@OptIn(ExperimentalMaterial3Api::class)
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

    Scaffold(
        topBar = { CenterAlignedTopAppBar(title = { Text("MedicScribe") }) },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(16.dp, Alignment.CenterVertically),
        ) {
            Text(
                "Server: ${BuildConfig.SERVER_HOST}:${BuildConfig.SERVER_PORT}",
                style = MaterialTheme.typography.bodySmall,
            )
            Text(state.statusText, style = MaterialTheme.typography.titleMedium)
            state.lastError?.let {
                Text(it, color = MaterialTheme.colorScheme.error)
            }
            val recording = state.phase == RecordingPhase.RECORDING
            Button(
                onClick = {
                    when {
                        recording -> controller.stop()
                        hasMic -> controller.start()
                        else -> permLauncher.launch(Manifest.permission.RECORD_AUDIO)
                    }
                },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(if (recording) "Stop" else "Record")
            }
        }
    }
}
