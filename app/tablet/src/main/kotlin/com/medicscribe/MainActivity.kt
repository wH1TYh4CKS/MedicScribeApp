package com.medicscribe

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import com.medicscribe.ui.screens.RecordScreen
import com.medicscribe.ui.theme.MedicScribeTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            MedicScribeTheme {
                RecordScreen()
            }
        }
    }
}
