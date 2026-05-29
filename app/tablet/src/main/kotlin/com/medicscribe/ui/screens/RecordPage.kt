package com.medicscribe.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.CenterAlignedTopAppBar
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.medicscribe.domain.RecordingPhase
import com.medicscribe.domain.SessionState
import com.medicscribe.ui.theme.InkBlack
import com.medicscribe.ui.theme.NavyPrimary
import com.medicscribe.ui.theme.RecordRed
import com.medicscribe.ui.theme.ScribeWhite
import com.medicscribe.ui.theme.SoftWhite

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RecordPage(
    state: SessionState,
    serverHost: String,
    onRecordClick: () -> Unit,
) {
    val recording = state.phase == RecordingPhase.RECORDING
    val busy = state.phase == RecordingPhase.STOPPING ||
        state.phase == RecordingPhase.CONNECTING

    val snackbarHostState = remember { SnackbarHostState() }
    // Flash the confirmation once when the session was just wiped via Done.
    LaunchedEffect(state.justCleared) {
        if (state.justCleared) {
            snackbarHostState.showSnackbar("All consultation data cleared")
        }
    }

    Scaffold(
        topBar = {
            CenterAlignedTopAppBar(
                title = { Text("MedicScribe", color = ScribeWhite) },
                colors = TopAppBarDefaults.centerAlignedTopAppBarColors(
                    containerColor = NavyPrimary,
                ),
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) },
        containerColor = SoftWhite,
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
        ) {
            PrivacyBanner(serverHost)
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f),
                contentAlignment = Alignment.Center,
            ) {
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(24.dp),
            ) {
                Box(
                    modifier = Modifier
                        .size(160.dp)
                        .clip(CircleShape)
                        .background(if (busy) Color.Gray else RecordRed)
                        .border(3.dp, InkBlack, CircleShape)
                        .clickable(enabled = !busy) { onRecordClick() },
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(
                        imageVector = if (recording) Icons.Filled.Stop else Icons.Filled.PlayArrow,
                        contentDescription = if (recording) "Stop recording" else "Start recording",
                        tint = ScribeWhite,
                        modifier = Modifier.size(72.dp),
                    )
                }
                Text(
                    text = when {
                        busy -> state.statusText
                        recording -> "Tap to stop"
                        else -> "Tap to record"
                    },
                    style = MaterialTheme.typography.titleMedium,
                    color = NavyPrimary,
                )
                state.lastError?.let {
                    Spacer(Modifier.height(0.dp))
                    Text(
                        text = it,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error,
                    )
                }
            }
            }
        }
    }
}
