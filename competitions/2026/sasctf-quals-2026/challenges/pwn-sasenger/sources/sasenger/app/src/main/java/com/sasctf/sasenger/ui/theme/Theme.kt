package com.sasctf.sasenger.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable

private val SasColors = darkColorScheme(
    primary = Mint,
    onPrimary = MintInk,
    primaryContainer = MintDeep,
    onPrimaryContainer = Mint,
    secondary = Mint,
    onSecondary = MintInk,
    background = Ink,
    onBackground = TextHi,
    surface = InkElev,
    onSurface = TextHi,
    surfaceVariant = InkElev2,
    onSurfaceVariant = TextLo,
    outline = OutlineCol,
    error = Danger,
    onError = MintInk,
)

@Composable
fun SasengerTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = SasColors, typography = SasTypography, content = content)
}
