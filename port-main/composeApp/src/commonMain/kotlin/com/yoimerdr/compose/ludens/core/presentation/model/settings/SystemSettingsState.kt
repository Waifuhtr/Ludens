package com.yoimerdr.compose.ludens.core.presentation.model.settings

import androidx.compose.runtime.Immutable
import com.yoimerdr.compose.ludens.core.domain.model.settings.SystemLanguage
import com.yoimerdr.compose.ludens.core.domain.model.settings.SystemTheme

/**
 * Represents the state of system-level settings in the presentation layer.
 *
 * This immutable data class holds the configuration for system-wide settings
 * that affect the overall behavior and appearance of the application.
 *
 * @property theme The application's theme configuration (Light, Dark, or System).
 * @property language The application's language/locale setting.
 * @property splashId The selected splash screen animation. `0` is the default Ludens pulse
 * animation; `1`-`5` select one of the bundled `acilis1.gif`-`acilis5.gif` alternatives.
 */
@Immutable
data class SystemSettingsState(
    val theme: SystemTheme = SystemTheme.System,
    val language: SystemLanguage = SystemLanguage.System,
    val splashId: Int = 0,
)

