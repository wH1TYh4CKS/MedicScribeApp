package com.medicscribe.ui.screens

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CenterAlignedTopAppBar
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
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
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
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
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull

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
                        is ServerMessage.TranscriptFinal -> {
                            _state.value = _state.value.copy(
                                transcript = _state.value.transcript +
                                    TranscriptLine(text = m.text, lang = m.lang),
                            )
                        }
                        is ServerMessage.NoteProgress -> {
                            _state.value = _state.value.copy(
                                phase = RecordingPhase.GENERATING_NOTE,
                                statusText = "Generating note (${m.stage} ${m.pct}%)",
                            )
                        }
                        is ServerMessage.NoteDone -> {
                            _state.value = _state.value.copy(
                                phase = RecordingPhase.NOTE_READY,
                                note = m.note,
                                rawTranscript = m.rawTranscript,
                                statusText = "Note ready",
                            )
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
        // Send Stop and WAIT for note_done / error / server-side close.
        // The server can take ~30s to generate the note; closing here would
        // kill the socket before the note frame arrives.
        ws?.send(ClientMessage.Stop)
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
            LazyColumn(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f),
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                if (state.transcript.isEmpty()) {
                    item {
                        Text(
                            "Transcript will appear here…",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                } else {
                    items(state.transcript) { line ->
                        val prefix = line.lang?.let { "[$it] " } ?: ""
                        Text(
                            "$prefix${line.text}",
                            style = MaterialTheme.typography.bodyLarge,
                        )
                    }
                }
                state.note?.let { note ->
                    val soapText = (note["soap_text"] as? JsonPrimitive)?.contentOrNull
                        ?.trim().orEmpty()
                    if (soapText.isNotEmpty()) {
                        item {
                            SoapNoteCard(soapText = soapText)
                        }
                    }
                }
            }
            val recording = state.phase == RecordingPhase.RECORDING
            val busy = state.phase == RecordingPhase.STOPPING ||
                state.phase == RecordingPhase.GENERATING_NOTE ||
                state.phase == RecordingPhase.CONNECTING
            Button(
                onClick = {
                    when {
                        recording -> controller.stop()
                        hasMic -> controller.start()
                        else -> permLauncher.launch(Manifest.permission.RECORD_AUDIO)
                    }
                },
                enabled = !busy,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(
                    when {
                        recording -> "Stop"
                        busy -> "Working…"
                        else -> "Record"
                    },
                )
            }
        }
    }
}

/** Splits "S: ... O: ... A: ... P: ..." into ordered (label, body) pairs.
 *  Tolerant of leading whitespace, extra blank lines, and missing sections. */
private fun parseSoap(text: String): List<Pair<String, String>> {
    val labels = mapOf(
        "S" to "Subjective",
        "O" to "Objective",
        "A" to "Assessment",
        "P" to "Plan",
    )
    val regex = Regex("(?m)^([SOAP]):\\s*")
    val matches = regex.findAll(text).toList()
    if (matches.isEmpty()) return listOf("Note" to text)
    return matches.mapIndexed { i, m ->
        val key = m.groupValues[1]
        val bodyStart = m.range.last + 1
        val bodyEnd = if (i + 1 < matches.size) matches[i + 1].range.first else text.length
        val body = text.substring(bodyStart, bodyEnd).trim()
        (labels[key] ?: key) to body
    }
}

@Composable
private fun SoapNoteCard(soapText: String) {
    val clipboard = LocalClipboardManager.current
    val sections = parseSoap(soapText)
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = 16.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant,
        ),
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    "SOAP Note",
                    style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier.weight(1f),
                )
                OutlinedButton(onClick = {
                    clipboard.setText(AnnotatedString(soapText))
                }) {
                    Text("Copy")
                }
            }
            Spacer(modifier = Modifier.height(12.dp))
            sections.forEach { (label, body) ->
                Text(
                    label,
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.primary,
                )
                Text(
                    body.ifEmpty { "Not documented." },
                    style = MaterialTheme.typography.bodyMedium,
                    modifier = Modifier.padding(bottom = 8.dp),
                )
            }
        }
    }
}
