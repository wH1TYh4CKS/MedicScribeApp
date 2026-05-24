package com.medicscribe.net

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject

@Serializable
sealed class ClientMessage {
    @Serializable
    @SerialName("start")
    data class Start(
        @SerialName("session_id") val sessionId: String,
        val template: String = "soap_v1",
        val languages: List<String> = listOf("en", "zh", "ms", "ta"),
    ) : ClientMessage()

    @Serializable
    @SerialName("stop")
    data object Stop : ClientMessage()
}

@Serializable
sealed class ServerMessage {
    @Serializable
    @SerialName("ack")
    data class Ack(
        @SerialName("session_id") val sessionId: String,
    ) : ServerMessage()

    @Serializable
    @SerialName("transcript_partial")
    data class TranscriptPartial(
        val text: String,
        val speaker: String? = null,
        val lang: String? = null,
        val t: Float,
    ) : ServerMessage()

    @Serializable
    @SerialName("transcript_final")
    data class TranscriptFinal(
        val text: String,
        val speaker: String? = null,
        val lang: String? = null,
        val t: Float,
    ) : ServerMessage()

    @Serializable
    @SerialName("note_progress")
    data class NoteProgress(
        val stage: String,
        val pct: Int,
    ) : ServerMessage()

    @Serializable
    @SerialName("note_done")
    data class NoteDone(
        val note: JsonObject,
        @SerialName("raw_transcript") val rawTranscript: String,
    ) : ServerMessage()

    @Serializable
    @SerialName("error")
    data class ErrorMessage(
        val code: String,
        val message: String,
    ) : ServerMessage()
}

val ProtocolJson: Json = Json {
    ignoreUnknownKeys = true
    classDiscriminator = "type"
}
