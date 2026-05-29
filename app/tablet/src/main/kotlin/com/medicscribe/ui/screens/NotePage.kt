package com.medicscribe.ui.screens

import android.content.Intent
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CenterAlignedTopAppBar
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.medicscribe.domain.SessionState
import com.medicscribe.ui.theme.InkBlack
import com.medicscribe.ui.theme.NavyPrimary
import com.medicscribe.ui.theme.ScribeWhite
import com.medicscribe.ui.theme.SoftWhite
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull

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

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun NotePage(
    note: JsonObject?,
    state: SessionState,
    serverHost: String,
    onNewSession: () -> Unit,
) {
    val context = LocalContext.current
    val soapText = (note?.get("soap_text") as? JsonPrimitive)?.contentOrNull?.trim().orEmpty()
    val sections = parseSoap(soapText)

    Scaffold(
        topBar = {
            CenterAlignedTopAppBar(
                title = { Text("SOAP Note", color = ScribeWhite) },
                actions = {
                    IconButton(onClick = {
                        val intent = Intent(Intent.ACTION_SEND).apply {
                            type = "text/plain"
                            putExtra(Intent.EXTRA_TEXT, soapText)
                            putExtra(Intent.EXTRA_SUBJECT, "SOAP Note")
                        }
                        context.startActivity(Intent.createChooser(intent, "Share Note"))
                    }) {
                        Icon(Icons.Filled.Share, contentDescription = "Share", tint = ScribeWhite)
                    }
                },
                colors = TopAppBarDefaults.centerAlignedTopAppBarColors(
                    containerColor = NavyPrimary,
                ),
            )
        },
        bottomBar = {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 24.dp, vertical = 16.dp),
                contentAlignment = Alignment.Center,
            ) {
                Button(
                    onClick = onNewSession,
                    modifier = Modifier.fillMaxWidth(),
                    colors = ButtonDefaults.buttonColors(containerColor = NavyPrimary),
                    border = BorderStroke(1.dp, InkBlack),
                ) {
                    Text("Done", color = ScribeWhite)
                }
            }
        },
        containerColor = SoftWhite,
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 24.dp, vertical = 16.dp),
        ) {
            item {
                PrivacyBanner(serverHost)
                Spacer(Modifier.height(16.dp))
            }
            itemsIndexed(sections) { idx, (label, body) ->
                Text(
                    label,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = NavyPrimary,
                )
                Spacer(Modifier.height(6.dp))
                Text(
                    body.ifEmpty { "Not documented." },
                    style = MaterialTheme.typography.bodyMedium,
                )
                if (idx < sections.lastIndex) {
                    Spacer(Modifier.height(16.dp))
                    HorizontalDivider(color = NavyPrimary.copy(alpha = 0.15f))
                    Spacer(Modifier.height(16.dp))
                }
            }
            item {
                Spacer(Modifier.height(24.dp))
                LifecycleCard(state)
            }
        }
    }
}
