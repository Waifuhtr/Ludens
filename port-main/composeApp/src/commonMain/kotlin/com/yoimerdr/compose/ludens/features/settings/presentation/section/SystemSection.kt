package com.yoimerdr.compose.ludens.features.settings.presentation.section

import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.sizeIn
import androidx.compose.foundation.layout.wrapContentWidth
import androidx.compose.foundation.lazy.LazyListState
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.yoimerdr.compose.ludens.core.domain.model.settings.SystemLanguage
import com.yoimerdr.compose.ludens.core.domain.model.settings.SystemTheme
import com.yoimerdr.compose.ludens.core.presentation.extension.settings.label
import com.yoimerdr.compose.ludens.core.presentation.model.settings.SystemSettingsState
import com.yoimerdr.compose.ludens.features.settings.presentation.components.OptionCard
import com.yoimerdr.compose.ludens.features.settings.presentation.components.OptionName
import com.yoimerdr.compose.ludens.features.settings.presentation.components.OptionsContainer
import com.yoimerdr.compose.ludens.features.settings.presentation.state.events.OnChangeLanguage
import com.yoimerdr.compose.ludens.features.settings.presentation.state.events.OnChangeSplash
import com.yoimerdr.compose.ludens.features.settings.presentation.state.events.OnChangeTheme
import com.yoimerdr.compose.ludens.features.settings.presentation.state.events.RestoreDefaultSettings
import com.yoimerdr.compose.ludens.features.settings.presentation.state.events.SettingsEvent
import com.yoimerdr.compose.ludens.features.settings.presentation.state.requests.SettingsRequest
import com.yoimerdr.compose.ludens.features.settings.presentation.viewmodel.SystemSettingsViewModel
import com.yoimerdr.compose.ludens.ui.components.buttons.FilledTonalToggleButton
import com.yoimerdr.compose.ludens.ui.components.provider.CollectInteractionResult
import com.yoimerdr.compose.ludens.ui.components.provider.LocalInteractionManager
import com.yoimerdr.compose.ludens.ui.components.provider.LocalSpacing
import com.yoimerdr.compose.ludens.ui.components.splash.GifImage
import com.yoimerdr.compose.ludens.ui.icons.LudensIcons
import com.yoimerdr.compose.ludens.ui.icons.outlined.PhoneDesktop
import com.yoimerdr.compose.ludens.ui.icons.outlined.ScreenShoot
import com.yoimerdr.compose.ludens.ui.icons.outlined.WeatherMoon
import com.yoimerdr.compose.ludens.ui.icons.outlined.WeatherSunny
import ludens.composeapp.generated.resources.Res
import ludens.composeapp.generated.resources.change
import ludens.composeapp.generated.resources.reset
import ludens.composeapp.generated.resources.riaslink_logo
import ludens.composeapp.generated.resources.stc_system_appearance
import ludens.composeapp.generated.resources.stc_system_language
import ludens.composeapp.generated.resources.stc_system_reset_default
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.stringResource

/**
 * A button to reset all settings to default values.
 *
 * @param onEvent Callback invoked when the reset button is clicked.
 */
@Composable
private fun ResetAction(
    onEvent: (RestoreDefaultSettings) -> Unit,
) {
    OptionCard(
        prefix = {
            OptionName(
                text = stringResource(Res.string.stc_system_reset_default)
            )
        }, modifier = Modifier.fillMaxWidth()
    ) {
        FilledTonalToggleButton(
            onClick = {
                onEvent(RestoreDefaultSettings)
            },
        ) {
            Text(
                text = stringResource(Res.string.reset)
            )
        }
    }
}

/**
 * A toggle button for selecting a theme option.
 *
 * @param theme The theme this option represents.
 * @param selected Whether this theme is currently selected.
 * @param onClick Callback invoked when the option is clicked.
 * @param modifier The modifier to be applied to the button.
 */
@Composable
private fun ThemeOption(
    modifier: Modifier = Modifier,
    selected: Boolean = false,
    theme: SystemTheme,
    onClick: () -> Unit,
) {
    val spacing = LocalSpacing.current
    val imageVector = when (theme) {
        SystemTheme.Light -> LudensIcons.Default.WeatherSunny
        SystemTheme.Dark -> LudensIcons.Default.WeatherMoon
        SystemTheme.System -> LudensIcons.Default.PhoneDesktop
    }

    val name = theme.label
    val iconDescription: String? = null

    FilledTonalToggleButton(
        onClick = onClick,
        modifier = modifier,
        selected = selected,
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(spacing.small)
        ) {
            Icon(
                imageVector = imageVector,
                contentDescription = iconDescription,
            )

            Text(
                name,
            )
        }
    }
}

/**
 * A card displaying theme selection options.
 *
 * @param theme The currently selected theme.
 * @param onEvent Callback invoked when a theme is selected.
 */
@Composable
private fun AppearanceAction(
    theme: SystemTheme,
    onEvent: (OnChangeTheme) -> Unit,
) {
    val spacing = LocalSpacing.current
    OptionCard(
        modifier = Modifier.fillMaxWidth(),
    ) {
        OptionName(
            text = stringResource(Res.string.stc_system_appearance)
        )

        FlowRow(
            horizontalArrangement = Arrangement.spacedBy(spacing.small),
            verticalArrangement = Arrangement.spacedBy(spacing.small),
            maxItemsInEachRow = 3,
            modifier = Modifier.fillMaxWidth(),
            itemVerticalAlignment = Alignment.CenterVertically
        ) {
            SystemTheme.entries.forEach {
                ThemeOption(
                    modifier = Modifier.padding(spacing.extraSmall).sizeIn(minWidth = 120.dp)
                        .weight(1f), theme = it, selected = it == theme, onClick = {
                        onEvent(OnChangeTheme(it))
                    })
            }
        }
    }
}

/**
 * A toggle button for selecting a splash screen option, showing a live preview.
 *
 * @param label The label shown below the preview ("Varsayılan", "Açılış 1", ...).
 * @param selected Whether this option is currently selected.
 * @param preview The preview content (a still logo or a playing GIF) shown above the label.
 * @param onClick Callback invoked when the option is clicked.
 * @param modifier The modifier to be applied to the button.
 */
@Composable
private fun SplashOption(
    modifier: Modifier = Modifier,
    label: String,
    selected: Boolean = false,
    preview: @Composable () -> Unit,
    onClick: () -> Unit,
) {
    val spacing = LocalSpacing.current
    FilledTonalToggleButton(
        onClick = onClick,
        modifier = modifier,
        selected = selected,
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(spacing.small)
        ) {
            Box(
                modifier = Modifier
                    .size(56.dp)
                    .clip(RoundedCornerShape(10.dp)),
                contentAlignment = Alignment.Center,
            ) {
                preview()
            }
            Text(label)
        }
    }
}

/**
 * Preview for the default option: a still frame of the bundled Riaslink logo (the same image
 * used for the pulse animation itself).
 */
@Composable
private fun DefaultSplashPreview() {
    Image(
        painter = painterResource(Res.drawable.riaslink_logo),
        contentDescription = null,
        modifier = Modifier.size(44.dp),
    )
}

/**
 * Preview for a custom splash option: reads and plays `files/splash/acilis$id.gif` at a small
 * size. If that file hasn't been added to the build, silently shows a placeholder icon instead
 * (never an error) so an unfilled slot just looks empty, not broken.
 */
@Composable
private fun GifSplashPreview(id: Int) {
    var bytes by remember(id) { mutableStateOf<ByteArray?>(null) }
    var failed by remember(id) { mutableStateOf(false) }

    LaunchedEffect(id) {
        val read = runCatching { Res.readBytes("files/splash/acilis$id.gif") }.getOrNull()
        if (read != null) {
            bytes = read
        } else {
            failed = true
        }
    }

    val currentBytes = bytes
    if (currentBytes != null && !failed) {
        GifImage(
            bytes = currentBytes,
            modifier = Modifier.size(44.dp).clip(RoundedCornerShape(8.dp)),
            onUnsupported = { failed = true },
        )
    } else if (failed) {
        Icon(
            imageVector = LudensIcons.Default.ScreenShoot,
            contentDescription = null,
            modifier = Modifier.size(22.dp),
        )
    }
}

/**
 * A card displaying splash screen selection options with live previews: the default
 * Riaslink-branded pulse animation, plus up to 5 custom bundled alternatives
 * (`acilis1.gif`-`acilis5.gif`). Options for files that haven't been added yet still appear
 * (with a placeholder preview) so they can be prepared for ahead of time.
 *
 * @param splashId The currently selected splash id (`0` = default, `1`-`5` = custom).
 * @param onEvent Callback invoked when a splash option is selected.
 */
@Composable
private fun SplashAction(
    splashId: Int,
    onEvent: (OnChangeSplash) -> Unit,
) {
    val spacing = LocalSpacing.current
    OptionCard(
        modifier = Modifier.fillMaxWidth(),
    ) {
        OptionName(text = "Açılış Ekranı")

        FlowRow(
            horizontalArrangement = Arrangement.spacedBy(spacing.small),
            verticalArrangement = Arrangement.spacedBy(spacing.small),
            maxItemsInEachRow = 3,
            modifier = Modifier.fillMaxWidth(),
            itemVerticalAlignment = Alignment.CenterVertically
        ) {
            SplashOption(
                modifier = Modifier.padding(spacing.extraSmall).sizeIn(minWidth = 120.dp).weight(1f),
                label = "Varsayılan",
                selected = splashId == 0,
                preview = { DefaultSplashPreview() },
                onClick = { onEvent(OnChangeSplash(0)) },
            )
            (1..5).forEach { id ->
                SplashOption(
                    modifier = Modifier.padding(spacing.extraSmall).sizeIn(minWidth = 120.dp).weight(1f),
                    label = "Açılış $id",
                    selected = splashId == id,
                    preview = { GifSplashPreview(id) },
                    onClick = { onEvent(OnChangeSplash(id)) },
                )
            }
        }
    }
}

/**
 * A card displaying language selection dropdown.
 *
 * @param language The currently selected language.
 * @param items The set of available languages.
 * @param onEvent Callback invoked when a language is selected.
 */
@Composable
private fun LanguageAction(
    language: SystemLanguage,
    items: Set<SystemLanguage>,
    onEvent: (OnChangeLanguage) -> Unit,
) {
    var currentLanguage by remember(language) { mutableStateOf(language) }
    var expanded by rememberSaveable { mutableStateOf(false) }

    OptionCard(
        modifier = Modifier.fillMaxWidth(), prefix = {
            OptionName(
                text = stringResource(Res.string.stc_system_language)
            )
        }) {
        Box {
            FilledTonalToggleButton(
                onClick = {
                    expanded = true
                }) {
                Text(
                    text = stringResource(Res.string.change)
                )
            }

            DropdownMenu(
                expanded = expanded,
                onDismissRequest = { expanded = false },
                modifier = Modifier.wrapContentWidth()
            ) {
                items.forEach {
                    DropdownMenuItem(
                        text = { Text(it.label) }, onClick = {
                        expanded = false
                        currentLanguage = it
                        onEvent(OnChangeLanguage(it))
                    }, enabled = currentLanguage != it
                    )
                }
            }
        }
    }
}

/**
 * The system settings section displaying system configuration options.
 *
 * @param settings The current system settings state.
 * @param onEvent Callback invoked when a settings event occurs.
 * @param modifier The modifier to be applied to the section container.
 * @param state The scroll state of the options list.
 */
@Composable
fun SystemSettingsSection(
    modifier: Modifier = Modifier,
    settings: SystemSettingsState,
    state: LazyListState = rememberLazyListState(),
    onEvent: (SettingsEvent) -> Unit,
) {
    OptionsContainer(
        modifier = modifier,
        state = state,
    ) {
        item {
            AppearanceAction(
                theme = settings.theme,
                onEvent = onEvent,
            )
        }

        item {
            SplashAction(
                splashId = settings.splashId,
                onEvent = onEvent,
            )
        }

        item {
            val languages = remember { SystemLanguage.entries.toSet() }
            val selectableLanguages = remember(languages) {
                languages.filterNot { it == SystemLanguage.System }
            }

            if (selectableLanguages.size > 1) {
                LanguageAction(
                    language = settings.language,
                    items = languages,
                    onEvent = onEvent,
                )
            }
        }

        item {
            ResetAction(onEvent)
        }
    }
}

/**
 * The system settings section with view model integration.
 *
 * @param viewModel The system settings view model.
 * @param modifier The modifier to be applied to the section container.
 * @param state The scroll state of the options list.
 */
@Composable
fun SystemSettingsSection(
    modifier: Modifier = Modifier,
    state: LazyListState = rememberLazyListState(),
    viewModel: SystemSettingsViewModel,
) {
    val system by viewModel.state.collectAsStateWithLifecycle()
    val interactionManager = LocalInteractionManager.current

    CollectInteractionResult(
        onReject = {
            if (it.request is SettingsRequest) viewModel.reject(it.request)
        }) {
        if (it.request is SettingsRequest) viewModel.resolve(it.request)
    }

    LaunchedEffect(Unit) {
        viewModel.requests.collect {
            if (it is SettingsRequest.Interaction) interactionManager.request(it)
        }
    }

    SystemSettingsSection(
        modifier = modifier, settings = system, state = state, onEvent = viewModel::handle
    )
}
