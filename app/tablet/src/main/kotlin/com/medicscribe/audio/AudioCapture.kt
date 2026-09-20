package com.medicscribe.audio

import android.annotation.SuppressLint
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.channelFlow
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.isActive

const val SAMPLE_RATE = 16000
const val CHANNEL_MASK = AudioFormat.CHANNEL_IN_MONO
const val ENCODING = AudioFormat.ENCODING_PCM_16BIT
const val FRAME_MS = 20
const val SAMPLES_PER_FRAME = SAMPLE_RATE * FRAME_MS / 1000
const val BYTES_PER_FRAME = SAMPLES_PER_FRAME * 2

class AudioCapture {

    @SuppressLint("MissingPermission")
    fun pcmFrames(): Flow<ByteArray> = channelFlow {
        val minBuf = AudioRecord.getMinBufferSize(SAMPLE_RATE, CHANNEL_MASK, ENCODING)
        check(minBuf > 0) { "AudioRecord.getMinBufferSize failed: $minBuf" }
        val bufSize = maxOf(minBuf * 4, BYTES_PER_FRAME * 8)
        val recorder = AudioRecord(
            MediaRecorder.AudioSource.VOICE_RECOGNITION,
            SAMPLE_RATE,
            CHANNEL_MASK,
            ENCODING,
            bufSize,
        )
        check(recorder.state == AudioRecord.STATE_INITIALIZED) { "AudioRecord init failed" }
        recorder.startRecording()
        try {
            val frame = ByteArray(BYTES_PER_FRAME)
            while (isActive) {
                var off = 0
                while (off < BYTES_PER_FRAME) {
                    val n = recorder.read(frame, off, BYTES_PER_FRAME - off)
                    if (n <= 0) break
                    off += n
                }
                if (off == BYTES_PER_FRAME) trySend(frame.copyOf())
            }
        } finally {
            recorder.stop()
            recorder.release()
        }
    }.flowOn(Dispatchers.IO)
}
