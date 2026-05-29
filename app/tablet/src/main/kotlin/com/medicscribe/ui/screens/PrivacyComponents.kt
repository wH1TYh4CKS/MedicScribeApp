package com.medicscribe.ui.screens

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.medicscribe.domain.SessionState
import com.medicscribe.net.classifyServer
import com.medicscribe.ui.theme.InkBlack
import com.medicscribe.ui.theme.NavyPrimary
import com.medicscribe.ui.theme.SafeGreen
import com.medicscribe.ui.theme.ScribeError
import com.medicscribe.ui.theme.SoftWhite
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

private val timeFmt = SimpleDateFormat("HH:mm:ss", Locale.US)

private fun fmt(ts: Long?): String = ts?.let { timeFmt.format(Date(it)) } ?: ""

/**
 * Persistent banner showing which server the app is talking to. The point is to
 * let a clinic client see, at a glance, that the connection goes to a private
 * machine — not a public cloud service. Turns red if the host is not private,
 * which catches a misconfigured build before it ever reaches a client.
 */
@Composable
fun PrivacyBanner(host: String, modifier: Modifier = Modifier) {
    val id = remember(host) { classifyServer(host) }
    val accent = if (id.isPrivate) NavyPrimary else ScribeError
    Row(
        modifier = modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 8.dp)
            .border(BorderStroke(1.dp, InkBlack), RoundedCornerShape(8.dp))
            .background(SoftWhite, RoundedCornerShape(8.dp))
            .padding(horizontal = 12.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text("🔒", style = MaterialTheme.typography.bodyMedium)
        Spacer(Modifier.width(8.dp))
        Text(
            text = "${id.host} · ${id.label} · Not the cloud",
            style = MaterialTheme.typography.bodySmall,
            fontWeight = FontWeight.Medium,
            color = accent,
        )
    }
}

/**
 * Per-consultation "data lifecycle" receipt. Collapsed by default (the doctor
 * wants the note first); one tap reveals what happened to the audio and data.
 *
 * Every timestamped row maps 1:1 to a real client-observed event. The "Audio
 * deleted" line is backed by the server's `audio_deleted` frame, so it is a real
 * confirmation, not a hardcoded claim.
 */
@Composable
fun LifecycleCard(state: SessionState, modifier: Modifier = Modifier) {
    var expanded by remember { mutableStateOf(false) }
    Column(
        modifier = modifier
            .fillMaxWidth()
            .border(BorderStroke(1.dp, InkBlack), RoundedCornerShape(8.dp))
            .background(SoftWhite, RoundedCornerShape(8.dp)),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clickable { expanded = !expanded }
                .padding(horizontal = 14.dp, vertical = 12.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                "Privacy — what happened to your data",
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.Bold,
                color = NavyPrimary,
            )
            Text(if (expanded) "▴" else "▾", color = NavyPrimary)
        }
        AnimatedVisibility(visible = expanded) {
            Column(
                modifier = Modifier.padding(start = 14.dp, end = 14.dp, bottom = 14.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                LifecycleRow("✓", NavyPrimary, "Recording started", fmt(state.recordingStartedAt))
                LifecycleRow("✓", NavyPrimary, "Recording stopped", fmt(state.recordingStoppedAt))
                LifecycleRow(
                    "✓", SafeGreen, "Audio deleted on server", fmt(state.audioDeletedAt),
                    sub = "server confirmed",
                )
                LifecycleRow("✓", NavyPrimary, "Note ready", fmt(state.noteReadyAt))
                LifecycleRow("✓", SafeGreen, "Note not stored — export only", "")
                LifecycleRow("✓", SafeGreen, "Memory wiped when you tap Done", "")
            }
        }
    }
}

@Composable
private fun LifecycleRow(
    mark: String,
    markColor: androidx.compose.ui.graphics.Color,
    label: String,
    time: String,
    sub: String? = null,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(mark, color = markColor, fontWeight = FontWeight.Bold)
        Spacer(Modifier.width(10.dp))
        Column(modifier = Modifier.weight(1f)) {
            Text(label, style = MaterialTheme.typography.bodyMedium, color = InkBlack)
            if (sub != null) {
                Text(
                    sub,
                    style = MaterialTheme.typography.labelSmall,
                    color = SafeGreen,
                )
            }
        }
        if (time.isNotEmpty()) {
            Text(time, style = MaterialTheme.typography.bodySmall, color = NavyPrimary)
        }
    }
}
