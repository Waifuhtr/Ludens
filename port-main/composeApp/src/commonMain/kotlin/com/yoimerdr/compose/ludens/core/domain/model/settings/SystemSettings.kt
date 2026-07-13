package com.yoimerdr.compose.ludens.core.domain.model.settings

/**
 * Represents system-level settings for the application.
 *
 * This data class aggregates system-wide configuration options that affect
 * the overall behavior and appearance of the application.
 *
 * @property theme The application's theme configuration (Light, Dark, or System).
 * @property language The application's language/locale setting.
 * @property splashId The selected splash screen animation. `0` is the default Ludens pulse
 * animation; `1`-`5` select one of the bundled `acilis1.gif`-`acilis5.gif` alternatives.
 */
data class SystemSettings(
    val theme: SystemTheme,
    val language: SystemLanguage,
    val splashId: Int = 0,
)
