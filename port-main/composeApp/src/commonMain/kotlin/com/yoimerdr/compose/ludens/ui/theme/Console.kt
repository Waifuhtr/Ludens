package com.yoimerdr.compose.ludens.ui.theme

import androidx.compose.ui.graphics.Color

/**
 * Color palette for the "console" visual treatment used by the Cheats and Plugins screens.
 *
 * These two screens are a developer/debug surface layered on top of the running game, so they
 * are deliberately styled as a dark terminal/HUD readout rather than reusing the light, neutral
 * Settings look. Every value here is plain data used through standard Material components
 * (backgrounds, borders, tints, text colors) — nothing here changes the base app theme.
 */
object ConsoleColors {
    /** Screen background: near-black deep navy. */
    val Background = Color(0xFF090D16)

    /** Default card/section surface. */
    val Surface = Color(0xFF121A2E)

    /** Slightly lighter surface, used for the header and emphasis panels. */
    val SurfaceRaised = Color(0xFF1A2542)

    /** Subtle hairline border/divider color. */
    val Border = Color(0xFF2A3557)

    /** Primary accent: electric cyan. Used for the header and neutral/info actions. */
    val Cyan = Color(0xFF3CE7E0)

    /** Secondary accent: violet. Used for inventory/items. */
    val Violet = Color(0xFFB07CFF)

    /** Positive/on/success accent. Used for heal and "enabled" states. */
    val Green = Color(0xFF4CE0A0)

    /** Currency accent. Used for the gold section. */
    val Amber = Color(0xFFFFC168)

    /** High-impact accent. Used for god mode / walk-through-walls. */
    val Pink = Color(0xFFFF6FA8)

    /** Movement/save accent. Used for teleport and save/load. */
    val Blue = Color(0xFF6FA0FF)

    /** Primary readable text on dark surfaces. */
    val TextPrimary = Color(0xFFEAF1FF)

    /** Secondary/muted text on dark surfaces. */
    val TextMuted = Color(0xFF8792B3)

    /** Faint tertiary text, e.g. footnotes. */
    val TextFaint = Color(0xFF525E82)
}
