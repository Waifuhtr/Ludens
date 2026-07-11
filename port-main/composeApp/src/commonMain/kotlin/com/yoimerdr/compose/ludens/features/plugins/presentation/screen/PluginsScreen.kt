package com.yoimerdr.compose.ludens.features.plugins.presentation.screen

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.navigation.NavController
import com.multiplatform.webview.web.WebViewNavigator
import com.yoimerdr.compose.ludens.app.ui.providers.LocalWebViewNavigator
import com.yoimerdr.compose.ludens.core.domain.port.ScriptEvaluator
import com.yoimerdr.compose.ludens.core.domain.port.evaluatingScript
import com.yoimerdr.compose.ludens.core.presentation.player.rememberJavascriptEvaluator
import com.yoimerdr.compose.ludens.features.settings.presentation.components.CloseIconButton
import com.yoimerdr.compose.ludens.features.settings.presentation.components.OptionCard
import com.yoimerdr.compose.ludens.features.settings.presentation.components.OptionName
import com.yoimerdr.compose.ludens.features.settings.presentation.components.OptionsContainer
import com.yoimerdr.compose.ludens.ui.components.provider.LocalSpacing
import kotlinx.coroutines.launch
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

/**
 * A single entry from the running game's `$plugins` array. Only the fields Ludens itself reads
 * are declared; the rest of a plugin entry (most importantly its `parameters`, whose shape is
 * entirely plugin-specific) is intentionally ignored rather than modeled.
 */
@Serializable
private data class RawPluginEntry(
    val name: String = "",
    val status: Boolean = true,
    val description: String = "",
)

private val LenientPluginJson = Json {
    ignoreUnknownKeys = true
    isLenient = true
}

/**
 * Escapes a Kotlin string into a double-quoted JavaScript string literal.
 */
private fun String.toJsStringLiteral(): String = buildString {
    append('"')
    for (c in this@toJsStringLiteral) {
        when (c) {
            '"' -> append("\\\"")
            '\\' -> append("\\\\")
            '\n' -> append("\\n")
            '\r' -> append("\\r")
            '\t' -> append("\\t")
            else -> append(c)
        }
    }
    append('"')
}

/**
 * Android's WebView (and by extension this multiplatform wrapper) reports `evaluateJavaScript`
 * results as the JSON representation of the JS value. For an expression that evaluates to a
 * JS *string* (as `JSON.stringify(...)` does), that means the callback value may itself be
 * quoted/escaped one extra time. This unwraps that outer layer when present, and passes the
 * value through unchanged otherwise, so this works correctly either way.
 */
private fun unwrapJsStringResult(raw: String): String {
    val trimmed = raw.trim()
    if (trimmed.length >= 2 && trimmed.startsWith("\"") && trimmed.endsWith("\"")) {
        return try {
            Json.decodeFromString<String>(trimmed)
        } catch (_: Exception) {
            trimmed
        }
    }
    return trimmed
}

private sealed interface PluginsLoadState {
    data object Loading : PluginsLoadState
    data object Error : PluginsLoadState
    data class Loaded(val entries: List<RawPluginEntry>) : PluginsLoadState
}

private suspend fun loadPlugins(evaluator: ScriptEvaluator): PluginsLoadState {
    return try {
        val raw = evaluator.evaluatingScript("JSON.stringify(window.\$plugins||[])")
        val json = unwrapJsStringResult(raw)
        val entries = LenientPluginJson.decodeFromString<List<RawPluginEntry>>(json)
        PluginsLoadState.Loaded(entries)
    } catch (_: Exception) {
        PluginsLoadState.Error
    }
}

/**
 * Full-screen viewer for the plugins bundled into the currently loaded game.
 *
 * The list is read directly from the live `window.$plugins` array (rather than the packaged
 * `plugins.js` file), so it always reflects what the running game actually has registered.
 * Toggling a switch here flips that plugin's `status` flag on the live array; because RPG Maker
 * plugin scripts already finished executing by the time this screen can run, this mainly affects
 * plugins that check their own status at runtime rather than only at boot (a common pattern for
 * debug/utility plugins). The change is best-effort and only lasts for the current session; it
 * is not written back to the APK.
 *
 * @param nav Navigation controller used to close this screen.
 * @param navigator The [WebViewNavigator] used to read/write the live game state. Defaults to
 * [LocalWebViewNavigator].
 */
@Composable
fun PluginsScreen(
    nav: NavController,
    navigator: WebViewNavigator = LocalWebViewNavigator.current,
) {
    val spacing = LocalSpacing.current
    val evaluator = rememberJavascriptEvaluator(navigator)
    val scope = rememberCoroutineScope()

    var loadState by remember { mutableStateOf<PluginsLoadState>(PluginsLoadState.Loading) }
    val overrides = remember { mutableStateMapOf<String, Boolean>() }

    suspend fun refresh() {
        loadState = PluginsLoadState.Loading
        loadState = loadPlugins(evaluator)
    }

    LaunchedEffect(Unit) {
        refresh()
    }

    fun toggle(name: String, enabled: Boolean) {
        overrides[name] = enabled
        val script = "(function(){if(window.\$plugins){var p=window.\$plugins.find(function(x){" +
                "return x.name===${name.toJsStringLiteral()};});if(p)p.status=$enabled;}})();"
        evaluator.evaluateScript(script)
    }

    Surface(
        modifier = Modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background,
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .systemBarsPadding()
                .padding(spacing.medium),
            verticalArrangement = Arrangement.spacedBy(spacing.medium),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = "Eklentiler",
                    style = MaterialTheme.typography.headlineSmall,
                )
                CloseIconButton(onClick = { nav.popBackStack() })
            }

            Surface(
                modifier = Modifier.fillMaxWidth(),
                color = MaterialTheme.colorScheme.surfaceContainerHighest,
                shape = MaterialTheme.shapes.medium,
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = spacing.medium, vertical = spacing.small),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        text = "Bu liste, oyunun şu an çalışan sürümünden okunur. Bir eklentiyi " +
                                "kapatmak bazı eklentilerde anında etkili olur; bazılarında ise " +
                                "yalnızca oyun yeniden başlatıldığında görülür. Değişiklikler " +
                                "yalnızca bu oturum için geçerlidir, APK'ya yazılmaz.",
                        style = MaterialTheme.typography.bodySmall,
                        modifier = Modifier.weight(1f),
                    )
                }
            }

            when (val state = loadState) {
                is PluginsLoadState.Loading -> {
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(spacing.large),
                        horizontalArrangement = Arrangement.Center,
                    ) {
                        CircularProgressIndicator(modifier = Modifier.size(28.dp))
                    }
                }

                is PluginsLoadState.Error -> {
                    EmptyState(
                        message = "Eklenti listesi okunamadı. Oyunun yüklendiğinden emin olun ve tekrar deneyin.",
                        onRefresh = { scope.launch { refresh() } },
                    )
                }

                is PluginsLoadState.Loaded -> {
                    if (state.entries.isEmpty()) {
                        EmptyState(
                            message = "Bu oyunda kayıtlı bir eklenti bulunamadı.",
                            onRefresh = { scope.launch { refresh() } },
                        )
                    } else {
                        OptionsContainer(
                            modifier = Modifier.fillMaxSize(),
                        ) {
                            item {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically,
                                ) {
                                    Text(
                                        text = "${state.entries.size} eklenti",
                                        style = MaterialTheme.typography.labelMedium,
                                    )
                                    TextButton(onClick = { scope.launch { refresh() } }) {
                                        Text("Yenile")
                                    }
                                }
                            }

                            items(state.entries) { entry ->
                                val isOn = overrides[entry.name] ?: entry.status
                                OptionCard(
                                    prefix = {
                                        Column(modifier = Modifier.weight(1f)) {
                                            OptionName(text = entry.name)
                                            if (entry.description.isNotBlank()) {
                                                Text(
                                                    text = entry.description,
                                                    style = MaterialTheme.typography.bodySmall,
                                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                                )
                                            }
                                        }
                                    },
                                    suffix = {
                                        Switch(
                                            checked = isOn,
                                            onCheckedChange = { toggle(entry.name, it) },
                                        )
                                    }
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun EmptyState(
    message: String,
    onRefresh: () -> Unit,
) {
    val spacing = LocalSpacing.current
    Column(
        modifier = Modifier.fillMaxWidth().padding(spacing.large),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(spacing.small),
    ) {
        Text(
            text = message,
            style = MaterialTheme.typography.bodyMedium,
            fontWeight = FontWeight.Normal,
        )
        TextButton(onClick = onRefresh) {
            Text("Tekrar Dene")
        }
    }
}
