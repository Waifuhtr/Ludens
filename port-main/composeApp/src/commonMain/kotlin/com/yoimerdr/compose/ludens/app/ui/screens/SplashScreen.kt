package com.yoimerdr.compose.ludens.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.navigation.NavHostController
import com.yoimerdr.compose.ludens.app.navigation.Destination
import com.yoimerdr.compose.ludens.app.navigation.navigateTo
import com.yoimerdr.compose.ludens.core.domain.usecase.GetSystemSettingsUseCase
import com.yoimerdr.compose.ludens.ui.components.splash.DesignSplash
import com.yoimerdr.compose.ludens.ui.components.splash.GifImage
import com.yoimerdr.compose.ludens.ui.components.webview.WebViewStartBoot
import com.yoimerdr.compose.ludens.ui.state.WebFeaturesState
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.first
import ludens.composeapp.generated.resources.Res
import ludens.composeapp.generated.resources.riaslink_logo
import org.jetbrains.compose.resources.painterResource
import org.koin.compose.koinInject

/**
 * Primary gradient color for the splash screen.
 */
val SplashPrimaryColor = Color(0xFF2457D7)

/**
 * Secondary gradient color for the splash screen.
 */
val SplashSecondaryColor = Color(0xFF7A57FF)

/**
 * Displays the application splash screen while the WebView and feature state initialize.
 *
 * This composable shows a branded splash screen with a soft gradient background and a centered
 * logo animation. Once both the minimum display delay and WebView initialization are complete,
 * it navigates to the home screen.
 *
 * The splash screen performs two parallel operations:
 * 1. Displays the splash animation for the specified delay duration
 * 2. Initializes the WebView and loads its features
 *
 * Navigation to the Home screen only occurs when both operations are complete.
 *
 * @param nav The [NavHostController] used for navigating to the Home screen after loading.
 * @param delay The minimum duration in milliseconds to display the splash screen. Default is 1500ms.
 * @param onLoad Optional callback invoked with [WebFeaturesState] when WebView initialization is complete,
 * before navigation occurs.
 */
@Composable
fun SplashScreen(
    nav: NavHostController,
    delay: Long = 1500,
    onLoad: ((WebFeaturesState) -> Unit)? = null,
) {
    var params by remember { mutableStateOf<WebFeaturesState?>(null) }
    var isEnd by remember { mutableStateOf(false) }

    LaunchedEffect(onLoad) {
        if (!isEnd) {
            delay(delay)
            isEnd = true
        }
    }

    LaunchedEffect(isEnd, params) {
        if (isEnd && params != null) {
            onLoad?.invoke(params!!)
            nav.navigateTo(Destination.Home)
        }
    }


    SplashContent {
        params = it
    }
}

/**
 * Renders the splash screen content with a gradient background and branding.
 *
 * Displays a branded gradient background, overlaid with either the user-selected splash GIF
 * (`Settings > System > Açılış Ekranı`, backed by [GetSystemSettingsUseCase]'s `splashId`) or the
 * default Riaslink-branded pulse animation. If no custom splash is selected, if the selected
 * file can't be read, or if GIF playback isn't supported on this platform, it falls back to the
 * default pulse animation rather than showing nothing. It also triggers WebView initialization
 * in the background.
 *
 * @param onLoad Callback invoked with [WebFeaturesState] when WebView initialization completes.
 */
@Composable
private fun SplashContent(onLoad: ((WebFeaturesState) -> Unit)) {
    val getSystemSettings = koinInject<GetSystemSettingsUseCase>()

    var splashId by remember { mutableStateOf(0) }
    var gifBytes by remember { mutableStateOf<ByteArray?>(null) }
    var useFallback by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) {
        val selected = runCatching { getSystemSettings().first().splashId }.getOrDefault(0)
        splashId = selected

        if (selected in 1..5) {
            gifBytes = runCatching {
                Res.readBytes("files/splash/acilis$selected.gif")
            }.getOrNull()

            if (gifBytes == null) {
                useFallback = true
            }
        } else {
            useFallback = true
        }
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(
                Brush.linearGradient(
                    colors = listOf(
                        SplashPrimaryColor,
                        SplashSecondaryColor,
                    )
                )
            )
    ) {
        val bytes = gifBytes
        if (!useFallback && bytes != null) {
            GifImage(
                bytes = bytes,
                modifier = Modifier.fillMaxSize().padding(56.dp),
                onUnsupported = { useFallback = true },
            )
        }

        if (useFallback) {
            DesignSplash(
                imagePainter = painterResource(Res.drawable.riaslink_logo),
                contentDescription = "Riaslink Logo",
                duration = 1800
            )
        }
    }

    WebViewStartBoot(onLoad)
}
