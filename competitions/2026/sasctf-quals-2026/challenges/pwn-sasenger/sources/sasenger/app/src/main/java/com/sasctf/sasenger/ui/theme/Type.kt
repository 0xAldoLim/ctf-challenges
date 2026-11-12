package com.sasctf.sasenger.ui.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.text.ExperimentalTextApi
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontVariation
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import com.sasctf.sasenger.R

@OptIn(ExperimentalTextApi::class)
private fun manrope(w: Int) = Font(
    R.font.manrope, FontWeight(w),
    variationSettings = FontVariation.Settings(FontVariation.weight(w)))

@OptIn(ExperimentalTextApi::class)
private fun sora(w: Int) = Font(
    R.font.sora, FontWeight(w),
    variationSettings = FontVariation.Settings(FontVariation.weight(w)))

val Manrope = FontFamily(manrope(400), manrope(500), manrope(600), manrope(700))
val Sora = FontFamily(sora(600), sora(700))

val SasTypography = Typography(
    headlineLarge = TextStyle(fontFamily = Sora, fontWeight = FontWeight(700), fontSize = 32.sp, letterSpacing = (-0.5).sp),
    headlineSmall = TextStyle(fontFamily = Sora, fontWeight = FontWeight(700), fontSize = 22.sp),
    titleLarge    = TextStyle(fontFamily = Sora, fontWeight = FontWeight(600), fontSize = 20.sp),
    titleMedium   = TextStyle(fontFamily = Manrope, fontWeight = FontWeight(600), fontSize = 16.sp),
    bodyLarge     = TextStyle(fontFamily = Manrope, fontWeight = FontWeight(400), fontSize = 16.sp),
    bodyMedium    = TextStyle(fontFamily = Manrope, fontWeight = FontWeight(400), fontSize = 14.sp),
    labelLarge    = TextStyle(fontFamily = Manrope, fontWeight = FontWeight(600), fontSize = 14.sp),
    labelMedium   = TextStyle(fontFamily = Manrope, fontWeight = FontWeight(500), fontSize = 12.sp),
    labelSmall    = TextStyle(fontFamily = Manrope, fontWeight = FontWeight(500), fontSize = 11.sp),
)
