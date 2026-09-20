package com.medicscribe.audio

import com.medicscribe.net.WsClient
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.launch

class PcmStreamer(
    private val capture: AudioCapture,
    private val ws: WsClient,
) {
    private var job: Job? = null

    fun start(scope: CoroutineScope) {
        if (job?.isActive == true) return
        job = scope.launch {
            capture.pcmFrames()
                .onEach { ws.sendPcm(it) }
                .collect {}
        }
    }

    fun stop() {
        job?.cancel()
        job = null
    }
}
