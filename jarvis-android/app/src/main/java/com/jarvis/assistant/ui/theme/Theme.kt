package com.jarvis.assistant.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// Palette Jarvis : fond presque noir, accents cyan (froid) et orange (chaud).
val JarvisBackground = Color(0xFF05080C)
val JarvisSurface = Color(0xFF0D141B)
val JarvisCyan = Color(0xFF00E5FF)
val JarvisOrange = Color(0xFFFF9100)
val JarvisText = Color(0xFFD7F6FF)
val JarvisError = Color(0xFFFF5370)

private val colors = darkColorScheme(
    primary = JarvisCyan,
    onPrimary = JarvisBackground,
    secondary = JarvisOrange,
    onSecondary = JarvisBackground,
    background = JarvisBackground,
    onBackground = JarvisText,
    surface = JarvisSurface,
    onSurface = JarvisText,
    error = JarvisError,
)

/** Thème simple pour la phase 1 ; le vrai look HUD arrive en phase 6. */
@Composable
fun JarvisTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = colors, content = content)
}
