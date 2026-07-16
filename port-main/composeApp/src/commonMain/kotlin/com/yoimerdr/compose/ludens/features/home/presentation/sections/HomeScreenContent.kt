package com.yoimerdr.compose.ludens.features.home.presentation.sections

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.yoimerdr.compose.ludens.app.ui.providers.LocalInputPlayer
import com.yoimerdr.compose.ludens.core.domain.model.key.InputKeyEvent
import com.yoimerdr.compose.ludens.core.domain.model.key.KeyEventType
import com.yoimerdr.compose.ludens.core.domain.model.settings.ItemType
import com.yoimerdr.compose.ludens.core.domain.model.settings.PositionableType
import com.yoimerdr.compose.ludens.core.infrastructure.adapter.script.key.InputKey
import com.yoimerdr.compose.ludens.core.presentation.extension.settings.getEnabled
import com.yoimerdr.compose.ludens.core.presentation.model.settings.ActionSettingsState
import com.yoimerdr.compose.ludens.core.presentation.model.settings.ControlSettingsState
import com.yoimerdr.compose.ludens.core.presentation.model.settings.PositionableItemState
import com.yoimerdr.compose.ludens.features.home.presentation.components.Joystick
import com.yoimerdr.compose.ludens.features.home.presentation.state.HomeEvent
import com.yoimerdr.compose.ludens.features.home.presentation.viewmodel.HomeViewModel
import com.yoimerdr.compose.ludens.ui.components.provider.LocalPlugin
import com.yoimerdr.compose.ludens.ui.icons.LudensIcons
import com.yoimerdr.compose.ludens.ui.icons.outlined.Dismiss
import kotlinx.collections.immutable.persistentListOf

/**
 * Renders the settings actions (configuration button or dock) within the box scope.
 *
 * @param controls The current control settings state
 * @param actions The current action settings state
 * @param viewModel The view model for handling action clicks
 * @param position The position state for the settings actions
 * @param onConfiguration Callback for when the main configuration button is clicked
 */
@Composable
private fun BoxScope.SettingsActions(
    controls: ControlSettingsState,
    actions: ActionSettingsState,
    viewModel: HomeViewModel,
    position: PositionableItemState?,
    onConfiguration: () -> Unit,
) {
    val tools by viewModel.toolState.collectAsStateWithLifecycle()

    SettingsActions(
        modifier = Modifier.align(Alignment.TopEnd),
        position = position,
        control = controls.items.getEnabled(ItemType.Actions)
            .firstOrNull(),
        onConfiguration = onConfiguration,
        actions = actions,
        onActionClick = {
            viewModel.handle(HomeEvent.OnClickAction(it))
        },
        toolSettings = tools,
        controlSettings = controls
    )
}

/**
 * Renders the virtual joystick within the box scope.
 *
 * @param viewModel The view model for handling joystick events
 * @param controls The control settings containing joystick configuration
 * @param position The position state for the joystick
 */
@Composable
private fun BoxScope.Joystick(
    viewModel: HomeViewModel,
    controls: ControlSettingsState,
    position: PositionableItemState,
) {
    Joystick(
        joystick = if (controls.enabled)
            controls.items.getEnabled(ItemType.Joystick)
                .firstOrNull()
        else null,
        onEvent = viewModel::handle,
        position = position,
        modifier = Modifier
            .align(Alignment.BottomStart)
    )
}

/**
 * Renders the key controls (action buttons) within the box scope.
 *
 * @param viewModel The view model for handling key events
 * @param controls The control settings containing key configurations
 * @param position The position state for the key controls
 */
@Composable
private fun BoxScope.KeyControls(
    viewModel: HomeViewModel,
    controls: ControlSettingsState,
    position: PositionableItemState,
) {
    KeyControls(
        items = if (controls.enabled)
            controls.items.getEnabled(ItemType.keys)
        else persistentListOf(),
        modifier = Modifier.align(Alignment.BottomEnd),
        onEvent = viewModel::handle,
        position = position,
    )
}

/**
 * Displays the main content of the home screen including game controls.
 *
 * This composable renders a complete set of game control UI elements within a [BoxScope]
 *
 * Control visibility and positioning are determined by the settings.
 * Only enabled controls are displayed, except for settings that are ever active.
 *
 * @param viewModel The home view model for handling events
 * @param showControls Whether to show on-screen controls
 * @param onConfiguration Callback invoked when the configuration button is clicked
 * */
@Composable
fun BoxScope.HomeScreenContent(
    viewModel: HomeViewModel,
    showControls: Boolean = true,
    onConfiguration: () -> Unit,
) {
    if (!showControls)
        return

    val controls by viewModel.controlState.collectAsStateWithLifecycle()
    val actions by viewModel.actionsState.collectAsStateWithLifecycle()
    val entry by viewModel.entryState.collectAsStateWithLifecycle()

    val plugin = LocalPlugin.current

    if (!plugin.isLoading && entry.isAvailable) {
        HomeScreenContent(
            controls = controls,
            actions = actions,
            viewModel = viewModel,
            onConfiguration = onConfiguration,
        )
    }
}

/**
 * A standalone, always-available Escape/Cancel button, fixed in the top-right area of the
 * screen, separate from the four remappable A/B/X/Y action buttons and not part of the
 * user-repositionable controls system. Tapping it sends [InputKey.Escape] to the game, exactly
 * like the desktop Escape key (closes menus, cancels choices).
 *
 * Offset below [SettingsActions] (also top-right) so the two never overlap.
 */
@Composable
private fun BoxScope.EscButton() {
    val player = LocalInputPlayer.current
    IconButton(
        onClick = {
            player.onKeyEvent(
                key = InputKeyEvent(code = InputKey.Escape.code, type = KeyEventType.Down, timeout = null),
                pressed = false,
            )
        },
        modifier = Modifier
            .align(Alignment.TopEnd)
            .padding(top = 76.dp, end = 8.dp)
            .size(40.dp)
            .clip(CircleShape)
            .background(MaterialTheme.colorScheme.surface.copy(alpha = 0.7f))
            .border(1.dp, MaterialTheme.colorScheme.outline.copy(alpha = 0.4f), CircleShape)
    ) {
        Icon(
            imageVector = LudensIcons.Default.Dismiss,
            contentDescription = "Esc",
            tint = MaterialTheme.colorScheme.onSurface,
        )
    }
}

/**
 * Internal implementation of HomeScreenContent that orchestrates the layout of controls.
 *
 * Iterates through positioned controls (Actions, Joystick, Keys) and renders them
 * according to their configured positions.
 *
 * @param controls The control settings state
 * @param actions The action settings state
 * @param viewModel The view model for event handling
 * @param onConfiguration Callback for configuration requests
 */
@Composable
private fun BoxScope.HomeScreenContent(
    controls: ControlSettingsState,
    actions: ActionSettingsState,
    viewModel: HomeViewModel,
    onConfiguration: () -> Unit,
) {
    var showSettings = false

    EscButton()

    controls.positions.forEach {
        when (it.type) {
            PositionableType.Actions -> {
                showSettings = true
                SettingsActions(
                    controls = controls,
                    actions = actions,
                    viewModel = viewModel,
                    position = it,
                    onConfiguration = onConfiguration
                )
            }

            PositionableType.Joystick -> {
                Joystick(
                    viewModel = viewModel,
                    controls = controls,
                    position = it,
                )
            }

            PositionableType.Keys -> {
                KeyControls(
                    viewModel = viewModel,
                    controls = controls,
                    position = it,
                )
            }
        }
    }
    if (!showSettings) {
        SettingsActions(
            controls = controls,
            actions = actions,
            viewModel = viewModel,
            position = null,
            onConfiguration = onConfiguration
        )
    }
}

