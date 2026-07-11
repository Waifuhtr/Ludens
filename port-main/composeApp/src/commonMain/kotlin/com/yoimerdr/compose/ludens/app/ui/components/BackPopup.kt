package com.yoimerdr.compose.ludens.app.ui.components

import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.ExperimentalComposeUiApi
import androidx.compose.ui.Modifier
import androidx.compose.ui.backhandler.BackHandler
import androidx.navigation.NavController
import androidx.navigation.compose.currentBackStackEntryAsState
import com.yoimerdr.compose.ludens.app.navigation.Destination
import com.yoimerdr.compose.ludens.app.ui.providers.LocalInputPlayer
import com.yoimerdr.compose.ludens.core.domain.model.key.InputKeyEvent
import com.yoimerdr.compose.ludens.core.domain.model.key.KeyEventType
import com.yoimerdr.compose.ludens.core.infrastructure.adapter.script.key.InputKey
import com.yoimerdr.compose.ludens.core.infrastructure.platform.PlatformApplication
import com.yoimerdr.compose.ludens.ui.components.dialogs.ConfirmationDialog
import com.yoimerdr.compose.ludens.ui.components.dialogs.widthInDialog
import ludens.composeapp.generated.resources.Res
import ludens.composeapp.generated.resources.exit_app
import org.jetbrains.compose.resources.stringResource
import org.koin.compose.koinInject
import kotlin.time.Duration.Companion.seconds
import kotlin.time.TimeSource

/** How long a second Home back-press has to follow the first one to trigger the exit prompt. */
private val HOME_BACK_EXIT_WINDOW = 2.seconds

/**
 * Handles back navigation with a confirmation popup for exiting the application.
 *
 * On the Home screen, a back press is first forwarded to the game as an Escape/Cancel key
 * (matching the desktop convention RPG Maker itself uses to close menus, dialogue, and choice
 * windows), rather than immediately prompting to quit. This matches what players expect from
 * the hardware/gesture back control on Android. Pressing back again shortly after (within
 * [HOME_BACK_EXIT_WINDOW], the common "press back again to exit" window) shows the exit
 * confirmation instead. On every other screen this performs standard back navigation.
 *
 * @param nav The [NavController] used for navigation operations and route detection.
 * @param handler The [PlatformApplication] handler for performing platform-specific operations
 * like finishing the application. Injected via Koin by default.
 */
@OptIn(ExperimentalComposeUiApi::class)
@Composable
internal fun BackPopup(
    nav: NavController,
    handler: PlatformApplication = koinInject(),
) {
    var showPopup by remember { mutableStateOf(false) }
    var lastEscapeForward by remember { mutableStateOf<TimeSource.Monotonic.ValueTimeMark?>(null) }
    val currentRoute = nav.currentBackStackEntryAsState().value?.destination?.route ?: return
    val inputPlayer = LocalInputPlayer.current

    BackHandler {
        if (currentRoute == Destination.Home.route) {
            val elapsedSinceLastPress = lastEscapeForward?.elapsedNow()
            if (elapsedSinceLastPress == null || elapsedSinceLastPress > HOME_BACK_EXIT_WINDOW) {
                lastEscapeForward = TimeSource.Monotonic.markNow()
                inputPlayer.onKeyEvent(
                    key = InputKeyEvent(code = InputKey.Escape.code, type = KeyEventType.Down, timeout = null),
                    pressed = false,
                )
            } else {
                showPopup = true
            }
        } else {
            nav.popBackStack()
        }
    }

    ConfirmationDialog(
        modifier = Modifier
            .widthInDialog(),
        showDialog = showPopup,
        message = stringResource(Res.string.exit_app),
        onDismiss = {
            showPopup = false
        },
        onConfirm = {
            showPopup = false
            handler.finish()
        }
    )
}