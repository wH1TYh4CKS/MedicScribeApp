package com.medicscribe.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.CenterAlignedTopAppBar
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.medicscribe.ui.theme.NavyPrimary
import com.medicscribe.ui.theme.ScribeWhite

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun GeneratingPage(statusText: String) {
    Scaffold(
        topBar = {
            CenterAlignedTopAppBar(
                title = { Text("MedicScribe", color = ScribeWhite) },
                colors = TopAppBarDefaults.centerAlignedTopAppBarColors(
                    containerColor = NavyPrimary,
                ),
            )
        },
        containerColor = ScribeWhite,
    ) { padding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
            contentAlignment = Alignment.Center,
        ) {
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(20.dp),
            ) {
                CircularProgressIndicator(
                    color = NavyPrimary,
                    strokeWidth = 4.dp,
                    modifier = Modifier.size(72.dp),
                )
                Text(
                    "Generating clinical note…",
                    style = MaterialTheme.typography.titleMedium,
                    color = NavyPrimary,
                )
                Spacer(Modifier.height(0.dp))
                Text(
                    statusText,
                    style = MaterialTheme.typography.bodySmall,
                    color = NavyPrimary.copy(alpha = 0.6f),
                )
            }
        }
    }
}
