package com.yoimerdr.compose.ludens.features.settings.presentation.state.events

import com.yoimerdr.compose.ludens.core.domain.model.settings.SystemLanguage
import com.yoimerdr.compose.ludens.core.domain.model.settings.SystemTheme

/**
 * Base interface for system settings events.
 */
sealed interface SystemSettingsEvent : SettingsEvent {
    /**
     * Event indicating an update to system settings.
     * */
    sealed interface UpdateSettings : SystemSettingsEvent,
        SettingsEvent.UpdateSettings
}

/**
 * Changes the application language.
 *
 * @param language The language to apply.
 */
data class OnChangeLanguage(val language: SystemLanguage) : SystemSettingsEvent.UpdateSettings

/**
 * Changes the application theme.
 *
 * @param theme The theme to apply.
 */
data class OnChangeTheme(val theme: SystemTheme) : SystemSettingsEvent.UpdateSettings

/**
 * Changes the splash screen animation.
 *
 * @param splashId The selected splash id. `0` is the default Ludens pulse animation;
 * `1`-`5` select one of the bundled `acilis1.gif`-`acilis5.gif` alternatives.
 */
data class OnChangeSplash(val splashId: Int) : SystemSettingsEvent.UpdateSettings

/**
 * Resets all settings to default values.
 */
data object RestoreDefaultSettings : SystemSettingsEvent

