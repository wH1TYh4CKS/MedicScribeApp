package com.medicscribe.domain

enum class RecordingPhase {
    IDLE,
    REQUESTING_PERMISSION,
    CONNECTING,
    RECORDING,
    STOPPING,
    DONE,
    ERROR,
}

data class SessionState(
    val phase: RecordingPhase = RecordingPhase.IDLE,
    val sessionId: String? = null,
    val statusText: String = "Idle",
    val lastError: String? = null,
)
