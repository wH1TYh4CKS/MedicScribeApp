package com.medicscribe.domain

import kotlinx.serialization.json.JsonObject

enum class RecordingPhase {
    IDLE,
    REQUESTING_PERMISSION,
    CONNECTING,
    RECORDING,
    STOPPING,
    GENERATING_NOTE,
    NOTE_READY,
    DONE,
    ERROR,
}

data class TranscriptLine(
    val text: String,
    val lang: String? = null,
)

data class SessionState(
    val phase: RecordingPhase = RecordingPhase.IDLE,
    val sessionId: String? = null,
    val statusText: String = "Idle",
    val lastError: String? = null,
    val transcript: List<TranscriptLine> = emptyList(),
    val note: JsonObject? = null,
    val rawTranscript: String? = null,
)
