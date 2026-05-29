package com.medicscribe.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable

private val MedicColorScheme = lightColorScheme(
    primary = NavyPrimary,
    onPrimary = ScribeWhite,
    primaryContainer = NavyDark,
    onPrimaryContainer = ScribeWhite,
    background = SoftWhite,
    onBackground = InkBlack,
    surface = ScribeSurface,
    onSurface = NavyDark,
    surfaceVariant = ScribeSurfaceVariant,
    onSurfaceVariant = NavyDark,
    error = ScribeError,
    onError = ScribeWhite,
)

@Composable
fun MedicScribeTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = MedicColorScheme,
        typography = Typography,
        content = content,
    )
}
