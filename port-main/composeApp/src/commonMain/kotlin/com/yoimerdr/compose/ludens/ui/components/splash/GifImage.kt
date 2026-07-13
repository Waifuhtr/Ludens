package com.yoimerdr.compose.ludens.ui.components.splash

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier

/**
 * Plays an animated GIF from raw file bytes, looping continuously and scaled to fit [modifier]'s
 * bounds while preserving aspect ratio.
 *
 * Platform support: fully animated on Android (`android.graphics.Movie`, available since API 1,
 * so this works down to Ludens' minSDK with no extra permissions or dependencies). On platforms
 * where animated GIF decoding isn't implemented, or if [bytes] fails to decode as a GIF, this
 * calls [onUnsupported] once and renders nothing — callers should react to that by switching to
 * their own static fallback rather than relying on this composable to show one.
 *
 * @param bytes The raw GIF file bytes, or null to skip straight to [onUnsupported].
 * @param modifier The modifier applied to the rendered area.
 * @param onUnsupported Invoked once if this platform, or this specific file, cannot be decoded
 * or played.
 */
@Composable
expect fun GifImage(
    bytes: ByteArray?,
    modifier: Modifier,
    onUnsupported: () -> Unit,
)
