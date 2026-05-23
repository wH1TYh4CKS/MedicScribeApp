package com.medicscribe.net

import java.util.concurrent.TimeUnit
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.receiveAsFlow
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import okio.ByteString.Companion.toByteString

sealed class WsEvent {
    data object Connected : WsEvent()
    data class Message(val msg: ServerMessage) : WsEvent()
    data class RawMessage(val text: String) : WsEvent()
    data class Closing(val code: Int, val reason: String) : WsEvent()
    data object Closed : WsEvent()
    data class Failure(val t: Throwable) : WsEvent()
}

class WsClient(private val url: String) {
    private val client = OkHttpClient.Builder()
        .pingInterval(20, TimeUnit.SECONDS)
        .build()
    private val events = Channel<WsEvent>(Channel.UNLIMITED)
    private var socket: WebSocket? = null
    val flow: Flow<WsEvent> = events.receiveAsFlow()

    fun connect() {
        val request = Request.Builder().url(url).build()
        socket = client.newWebSocket(request, listener)
    }

    fun send(msg: ClientMessage) {
        socket?.send(ProtocolJson.encodeToString(ClientMessage.serializer(), msg))
    }

    fun sendPcm(data: ByteArray) {
        socket?.send(data.toByteString())
    }

    fun close() {
        socket?.close(1000, "client done")
        socket = null
    }

    private val listener = object : WebSocketListener() {
        override fun onOpen(ws: WebSocket, response: Response) {
            events.trySend(WsEvent.Connected)
        }

        override fun onMessage(ws: WebSocket, text: String) {
            try {
                val parsed = ProtocolJson.decodeFromString(ServerMessage.serializer(), text)
                events.trySend(WsEvent.Message(parsed))
            } catch (t: Throwable) {
                events.trySend(WsEvent.RawMessage(text))
            }
        }

        override fun onClosing(ws: WebSocket, code: Int, reason: String) {
            events.trySend(WsEvent.Closing(code, reason))
        }

        override fun onClosed(ws: WebSocket, code: Int, reason: String) {
            events.trySend(WsEvent.Closed)
        }

        override fun onFailure(ws: WebSocket, t: Throwable, response: Response?) {
            events.trySend(WsEvent.Failure(t))
        }
    }
}
