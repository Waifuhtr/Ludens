package com.yoimerdr.compose.ludens.ui.components.splash

import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Modifier

/**
 * iOS implementation of [GifImage].
 *
 * Animated GIF decoding isn't implemented on this target. Rather than guess at an
 * implementation without the ability to verify it, this immediately reports itself as
 * unsupported so the caller falls back to its own static/animated placeholder — the same
 * behavior callers already need to handle for a decode failure on any platform.
 */
@Composable
actual fun GifImage(
    bytes: ByteArray?,
    modifier: Modifier,
    onUnsupported: () -> Unit,
) {
    LaunchedEffect(Unit) {
        onUnsupported()
    }
}
