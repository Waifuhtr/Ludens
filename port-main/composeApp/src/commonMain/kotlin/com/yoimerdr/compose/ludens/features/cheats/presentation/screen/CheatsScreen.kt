package com.yoimerdr.compose.ludens.features.cheats.presentation.screen

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import androidx.navigation.NavController
import com.yoimerdr.compose.ludens.app.ui.providers.LocalCheatPlayer
import com.yoimerdr.compose.ludens.core.domain.port.player.CheatPlayer
import com.yoimerdr.compose.ludens.ui.components.provider.LocalSpacing
import com.yoimerdr.compose.ludens.ui.icons.LudensIcons
import com.yoimerdr.compose.ludens.ui.icons.outlined.ArrowReset
import com.yoimerdr.compose.ludens.ui.icons.outlined.Circle
import com.yoimerdr.compose.ludens.ui.icons.outlined.Games
import com.yoimerdr.compose.ludens.ui.icons.outlined.Person
import com.yoimerdr.compose.ludens.ui.icons.outlined.Save
import com.yoimerdr.compose.ludens.ui.icons.outlined.Wrench
import com.yoimerdr.compose.ludens.ui.theme.ConsoleCard
import com.yoimerdr.compose.ludens.ui.theme.ConsoleColors
import com.yoimerdr.compose.ludens.ui.theme.ConsoleFooter
import com.yoimerdr.compose.ludens.ui.theme.ConsoleHeader
import com.yoimerdr.compose.ludens.ui.theme.ConsoleTextField
import com.yoimerdr.compose.ludens.ui.theme.StatusPill
import kotlinx.coroutines.launch

/**
 * Local form state held by the cheat screen. All fields are kept as raw strings so text fields
 * can be freely edited (including transient invalid/empty states) without fighting the user;
 * values are parsed defensively at the point of use via [toSafeInt].
 */
private data class CheatFormState(
    val gold: String = "1000",
    val actorId: String = "1",
    val hp: String = "999",
    val mp: String = "999",
    val level: String = "10",
    val saveSlot: String = "1",
)

/** Parses a string field as an int, falling back to [default] for blank/invalid input. */
private fun String.toSafeInt(default: Int = 0): Int = trim().toIntOrNull() ?: default

/**
 * Full-screen debug/cheat menu for the currently loaded game.
 *
 * Kept intentionally small: gold, character stats, and save/load -- the basics that don't need
 * a dedicated UI of their own. Anything more involved (item/variable/switch editing, no-clip,
 * god mode, speed, teleport, and more) lives in the bundled **Gelişmiş Hileler** (Advanced
 * Cheats) panel instead, so the same capability isn't built twice.
 *
 * Every action here operates directly on core RPG Maker MV/MZ engine objects
 * (`$gameParty`, `$gameActors`, ...) through [CheatPlayer], so it works on any exported game
 * regardless of which plugins it bundles. The game keeps running behind this screen (it is not
 * reloaded), so changes are visible immediately once you go back.
 *
 * @param nav Navigation controller used to close this screen.
 * @param cheatPlayer The [CheatPlayer] used to apply cheat commands. Defaults to [LocalCheatPlayer].
 */
@Composable
fun CheatsScreen(
    nav: NavController,
    cheatPlayer: CheatPlayer = LocalCheatPlayer.current,
) {
    val spacing = LocalSpacing.current
    var form by remember { mutableStateOf(CheatFormState()) }
    var isGameActive by remember { mutableStateOf<Boolean?>(null) }
    val scope = rememberCoroutineScope()

    suspend fun refreshState() {
        isGameActive = cheatPlayer.isGameActive()
    }

    LaunchedEffect(Unit) {
        refreshState()
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(ConsoleColors.Background),
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .systemBarsPadding()
                .padding(horizontal = spacing.small, vertical = spacing.medium),
            verticalArrangement = Arrangement.spacedBy(spacing.medium),
        ) {
            ConsoleHeader(
                eyebrow = "SYSTEM // CHEATS.EXE",
                title = "Hile Konsolu",
                accent = ConsoleColors.Cyan,
                onClose = { nav.popBackStack() },
            )

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                StatusPill(
                    text = when (isGameActive) {
                        true -> "OYUN AKTİF"
                        false -> "OYUN AKTİF DEĞİL"
                        null -> "KONTROL EDİLİYOR"
                    },
                    color = when (isGameActive) {
                        true -> ConsoleColors.Green
                        false -> ConsoleColors.Pink
                        null -> ConsoleColors.TextMuted
                    },
                )
                TextButton(onClick = { scope.launch { refreshState() } }) {
                    Text("Yenile", color = ConsoleColors.Cyan)
                }
            }

            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                verticalArrangement = Arrangement.spacedBy(spacing.medium),
            ) {
                item {
                    ConsoleCard(title = "Gelişmiş Hileler", tag = "// ADVANCED", icon = LudensIcons.Default.Wrench, accent = ConsoleColors.Violet) {
                        Text(
                            text = "Eşya, değişken, switch düzenleme, no-clip, god mode, hız, " +
                                    "ışınlanma ve daha fazlası için gelişmiş hile panelini açın.",
                            color = ConsoleColors.TextMuted,
                        )
                        ConsoleFilledButton(
                            text = "Gelişmiş Hile Panelini Aç",
                            accent = ConsoleColors.Violet,
                            fullWidth = true,
                            onClick = { cheatPlayer.openAdvancedCheats() },
                        )
                        Text(
                            text = "Not: panel ilk açılışta stil dosyaları için internet " +
                                    "bağlantısı gerektirebilir. Oyun bu paneli içermiyorsa " +
                                    "hiçbir şey olmaz.",
                            color = ConsoleColors.TextFaint,
                        )
                    }
                }

                item {
                    ConsoleCard(
                        title = "Altın",
                        tag = "// GOLD",
                        icon = LudensIcons.Default.Circle,
                        accent = ConsoleColors.Amber,
                    ) {
                        ConsoleTextField(
                            label = "Miktar",
                            value = form.gold,
                            onValueChange = { form = form.copy(gold = it) },
                            accent = ConsoleColors.Amber,
                        )
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(spacing.small),
                        ) {
                            ConsoleFilledButton(
                                modifier = Modifier.weight(1f),
                                text = "Ayarla",
                                accent = ConsoleColors.Amber,
                                onClick = { cheatPlayer.setGold(form.gold.toSafeInt()) },
                            )
                            ConsoleOutlinedButton(
                                modifier = Modifier.weight(1f),
                                text = "Ekle / Çıkar",
                                accent = ConsoleColors.Amber,
                                onClick = { cheatPlayer.addGold(form.gold.toSafeInt()) },
                            )
                        }
                    }
                }

                item {
                    ConsoleCard(
                        title = "Karakter",
                        tag = "// PARTY",
                        icon = LudensIcons.Default.Person,
                        accent = ConsoleColors.Green,
                    ) {
                        ConsoleTextField(
                            label = "Karakter ID (1 = ana kahraman)",
                            value = form.actorId,
                            onValueChange = { form = form.copy(actorId = it) },
                            accent = ConsoleColors.Green,
                        )
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(spacing.small),
                        ) {
                            ConsoleTextField(
                                modifier = Modifier.weight(1f),
                                label = "HP",
                                value = form.hp,
                                onValueChange = { form = form.copy(hp = it) },
                                accent = ConsoleColors.Green,
                            )
                            ConsoleTextField(
                                modifier = Modifier.weight(1f),
                                label = "MP",
                                value = form.mp,
                                onValueChange = { form = form.copy(mp = it) },
                                accent = ConsoleColors.Green,
                            )
                        }
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(spacing.small),
                        ) {
                            ConsoleFilledButton(
                                modifier = Modifier.weight(1f),
                                text = "HP/MP Uygula",
                                accent = ConsoleColors.Green,
                                onClick = {
                                    val id = form.actorId.toSafeInt(1)
                                    cheatPlayer.setActorHp(id, form.hp.toSafeInt())
                                    cheatPlayer.setActorMp(id, form.mp.toSafeInt())
                                },
                            )
                            ConsoleOutlinedButton(
                                modifier = Modifier.weight(1f),
                                text = "İyileştir",
                                accent = ConsoleColors.Green,
                                icon = LudensIcons.Default.ArrowReset,
                                onClick = { cheatPlayer.healParty() },
                            )
                        }
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(spacing.small),
                        ) {
                            ConsoleTextField(
                                modifier = Modifier.weight(1f),
                                label = "Seviye",
                                value = form.level,
                                onValueChange = { form = form.copy(level = it) },
                                accent = ConsoleColors.Green,
                            )
                            ConsoleFilledButton(
                                text = "Uygula",
                                accent = ConsoleColors.Green,
                                onClick = {
                                    cheatPlayer.setActorLevel(form.actorId.toSafeInt(1), form.level.toSafeInt(1))
                                },
                            )
                        }
                    }
                }

                item {
                    ConsoleCard(
                        title = "Kayıt / Menü",
                        tag = "// SAVE",
                        icon = LudensIcons.Default.Save,
                        accent = ConsoleColors.Cyan,
                    ) {
                        ConsoleTextField(
                            label = "Kayıt Slotu",
                            value = form.saveSlot,
                            onValueChange = { form = form.copy(saveSlot = it) },
                            accent = ConsoleColors.Cyan,
                        )
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(spacing.small),
                        ) {
                            ConsoleFilledButton(
                                modifier = Modifier.weight(1f),
                                text = "Kaydet",
                                accent = ConsoleColors.Cyan,
                                onClick = { cheatPlayer.saveToSlot(form.saveSlot.toSafeInt(1)) },
                            )
                            ConsoleOutlinedButton(
                                modifier = Modifier.weight(1f),
                                text = "Yükle",
                                accent = ConsoleColors.Cyan,
                                onClick = { cheatPlayer.loadFromSlot(form.saveSlot.toSafeInt(1)) },
                            )
                            TextButton(
                                modifier = Modifier.weight(1f),
                                onClick = { cheatPlayer.openMenu() },
                            ) {
                                Icon(
                                    LudensIcons.Default.Games,
                                    contentDescription = null,
                                    tint = ConsoleColors.Cyan,
                                    modifier = Modifier.padding(end = spacing.extraSmall),
                                )
                                Text("Menü", color = ConsoleColors.Cyan)
                            }
                        }
                    }
                }

                item {
                    Box(
                        modifier = Modifier.fillMaxWidth().padding(top = spacing.small, bottom = spacing.medium),
                        contentAlignment = Alignment.Center,
                    ) {
                        ConsoleFooter(text = "// riaslink.fun")
                    }
                }
            }
        }
    }
}

/** Compact content padding shared by the console screens' buttons, for a lower profile. */
private val CompactButtonPadding = PaddingValues(horizontal = 16.dp, vertical = 6.dp)

/** A filled, accent-colored primary action button used across the console screens. */
@Composable
private fun ConsoleFilledButton(
    text: String,
    accent: Color,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    fullWidth: Boolean = false,
) {
    FilledTonalButton(
        onClick = onClick,
        modifier = if (fullWidth) modifier.fillMaxWidth() else modifier,
        contentPadding = CompactButtonPadding,
        colors = ButtonDefaults.filledTonalButtonColors(
            containerColor = accent.copy(alpha = 0.22f),
            contentColor = accent,
        ),
    ) {
        Text(text)
    }
}

/** An outlined, accent-colored secondary action button used across the console screens. */
@Composable
private fun ConsoleOutlinedButton(
    text: String,
    accent: Color,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    icon: ImageVector? = null,
) {
    OutlinedButton(
        onClick = onClick,
        modifier = modifier,
        contentPadding = CompactButtonPadding,
        colors = ButtonDefaults.outlinedButtonColors(contentColor = accent),
        border = BorderStroke(1.dp, accent.copy(alpha = 0.5f)),
    ) {
        if (icon != null) {
            Icon(icon, contentDescription = null, modifier = Modifier.padding(end = 6.dp))
        }
        Text(text)
    }
}
