package com.yoimerdr.compose.ludens.ui.components.splash

import android.graphics.Movie
import androidx.compose.foundation.Canvas
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.withFrameNanos
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.drawscope.drawIntoCanvas
import androidx.compose.ui.graphics.nativeCanvas

/**
 * Android implementation of [GifImage], backed by [android.graphics.Movie].
 *
 * `Movie` has been part of the Android SDK since API 1, so this needs no extra dependency and
 * works across Ludens' full supported SDK range. Each frame is driven manually via
 * [withFrameNanos] and drawn straight onto the platform [android.graphics.Canvas] obtained
 * through [drawIntoCanvas]/[nativeCanvas], scaled to fit while preserving aspect ratio.
 *
 * Decoding happens once per distinct [bytes] instance (via [remember]); if it fails or yields a
 * zero-duration movie (not a valid/animated GIF), [onUnsupported] is invoked and nothing is
 * drawn, instead of showing a broken frame or crashing.
 */
@Composable
actual fun GifImage(
    bytes: ByteArray?,
    modifier: Modifier,
    onUnsupported: () -> Unit,
) {
    if (bytes == null) {
        LaunchedEffect(Unit) {
            onUnsupported()
        }
        return
    }

    val movie = remember(bytes) {
        runCatching { Movie.decodeByteArray(bytes, 0, bytes.size) }.getOrNull()
    }

    if (movie == null || movie.duration() <= 0 || movie.width() <= 0 || movie.height() <= 0) {
        LaunchedEffect(movie) {
            onUnsupported()
        }
        return
    }

    var elapsedMs by remember(movie) { mutableIntStateOf(0) }

    LaunchedEffect(movie) {
        val startNanos = withFrameNanos { it }
        while (true) {
            withFrameNanos { nowNanos ->
                val elapsedTotalMs = ((nowNanos - startNanos) / 1_000_000L).toInt()
                elapsedMs = elapsedTotalMs % movie.duration()
            }
        }
    }

    Canvas(modifier = modifier) {
        val movieWidth = movie.width().toFloat()
        val movieHeight = movie.height().toFloat()
        val scale = minOf(size.width / movieWidth, size.height / movieHeight)
        val drawWidth = movieWidth * scale
        val drawHeight = movieHeight * scale
        val dx = (size.width - drawWidth) / 2f
        val dy = (size.height - drawHeight) / 2f

        drawIntoCanvas { canvas ->
            movie.setTime(elapsedMs)
            val native = canvas.nativeCanvas
            val saveCount = native.save()
            native.translate(dx, dy)
            native.scale(scale, scale)
            movie.draw(native, 0f, 0f)
            native.restoreToCount(saveCount)
        }
    }
}
