package org.ridgewatch.rescuer.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable

private val DarkColorScheme = darkColorScheme(
    primary = RescueBlue,
    secondary = RescueGreen,
    tertiary = RescueYellow,
    background = RescueDark,
    surface = RescueSurface,
    onPrimary = RescueText,
    onSecondary = RescueText,
    onBackground = RescueText,
    onSurface = RescueText
)

@Composable
fun RidgeWatchCompanionTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = DarkColorScheme,
        content = content
    )
}
