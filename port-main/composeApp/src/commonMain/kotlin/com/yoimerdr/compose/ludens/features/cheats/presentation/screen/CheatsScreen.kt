package com.yoimerdr.compose.ludens.features.cheats.presentation.screen

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
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
import com.yoimerdr.compose.ludens.ui.icons.outlined.ArrowDownload
import com.yoimerdr.compose.ludens.ui.icons.outlined.ArrowReset
import com.yoimerdr.compose.ludens.ui.icons.outlined.ArrowSwap
import com.yoimerdr.compose.ludens.ui.icons.outlined.Circle
import com.yoimerdr.compose.ludens.ui.icons.outlined.Code
import com.yoimerdr.compose.ludens.ui.icons.outlined.Games
import com.yoimerdr.compose.ludens.ui.icons.outlined.Person
import com.yoimerdr.compose.ludens.ui.icons.outlined.Save
import com.yoimerdr.compose.ludens.ui.icons.outlined.TopSpeed
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
 * values are parsed defensively at the point of use via [toSafeInt]/[toSafeFloat].
 */
private data class CheatFormState(
    val gold: String = "1000",
    val actorId: String = "1",
    val hp: String = "999",
    val mp: String = "999",
    val level: String = "10",
    val itemKind: ItemKind = ItemKind.Item,
    val itemId: String = "1",
    val itemCount: String = "1",
    val mapId: String = "1",
    val teleportX: String = "0",
    val teleportY: String = "0",
    val speed: String = "2",
    val saveSlot: String = "1",
)

private enum class ItemKind(val label: String) {
    Item("Eşya"),
    Weapon("Silah"),
    Armor("Zırh"),
}

/** Parses a string field as an int, falling back to [default] for blank/invalid input. */
private fun String.toSafeInt(default: Int = 0): Int = trim().toIntOrNull() ?: default

/** Parses a string field as a float, falling back to [default] for blank/invalid input. */
private fun String.toSafeFloat(default: Float = 1f): Float = trim().toFloatOrNull() ?: default

/**
 * Full-screen debug/cheat menu for the currently loaded game.
 *
 * Every action here operates directly on core RPG Maker MV/MZ engine objects
 * (`$gameParty`, `$gameActors`, `$gamePlayer`, ...) through [CheatPlayer], so it works on any
 * exported game regardless of which plugins it bundles. The game keeps running behind this
 * screen (it is not reloaded), so changes are visible immediately once you go back.
 *
 * God mode and walk-through-walls both keep running in the background independently of this
 * screen, so their switches read back the actual live state on every entry rather than always
 * starting unchecked.
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
    var godMode by remember { mutableStateOf(false) }
    var walkThroughWalls by remember { mutableStateOf(false) }
    var isGameActive by remember { mutableStateOf<Boolean?>(null) }
    val scope = rememberCoroutineScope()

    suspend fun refreshState() {
        isGameActive = cheatPlayer.isGameActive()
        godMode = cheatPlayer.isGodModeActive()
        walkThroughWalls = cheatPlayer.isWalkThroughWallsActive()
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
                .padding(spacing.medium),
            verticalArrangement = Arrangement.spacedBy(spacing.large),
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
                verticalArrangement = Arrangement.spacedBy(spacing.large),
            ) {
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
                        Row(horizontalArrangement = Arrangement.spacedBy(spacing.small)) {
                            ConsoleFilledButton(
                                text = "Ayarla",
                                accent = ConsoleColors.Amber,
                                onClick = { cheatPlayer.setGold(form.gold.toSafeInt()) },
                            )
                            ConsoleOutlinedButton(
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
                        Row(horizontalArrangement = Arrangement.spacedBy(spacing.small)) {
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
                        Row(horizontalArrangement = Arrangement.spacedBy(spacing.small)) {
                            ConsoleFilledButton(
                                text = "HP/MP Uygula",
                                accent = ConsoleColors.Green,
                                onClick = {
                                    val id = form.actorId.toSafeInt(1)
                                    cheatPlayer.setActorHp(id, form.hp.toSafeInt())
                                    cheatPlayer.setActorMp(id, form.mp.toSafeInt())
                                },
                            )
                            ConsoleOutlinedButton(
                                text = "İyileştir",
                                accent = ConsoleColors.Green,
                                icon = LudensIcons.Default.ArrowReset,
                                onClick = { cheatPlayer.healParty() },
                            )
                        }
                        Row(
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
                        title = "Eşya Ekle",
                        tag = "// INVENTORY",
                        icon = LudensIcons.Default.ArrowDownload,
                        accent = ConsoleColors.Violet,
                    ) {
                        Row(horizontalArrangement = Arrangement.spacedBy(spacing.small)) {
                            ItemKind.entries.forEach { kind ->
                                val selected = form.itemKind == kind
                                if (selected) {
                                    ConsoleFilledButton(
                                        text = kind.label,
                                        accent = ConsoleColors.Violet,
                                        onClick = { form = form.copy(itemKind = kind) },
                                    )
                                } else {
                                    ConsoleOutlinedButton(
                                        text = kind.label,
                                        accent = ConsoleColors.Violet,
                                        onClick = { form = form.copy(itemKind = kind) },
                                    )
                                }
                            }
                        }
                        Row(horizontalArrangement = Arrangement.spacedBy(spacing.small)) {
                            ConsoleTextField(
                                modifier = Modifier.weight(1f),
                                label = "ID",
                                value = form.itemId,
                                onValueChange = { form = form.copy(itemId = it) },
                                accent = ConsoleColors.Violet,
                            )
                            ConsoleTextField(
                                modifier = Modifier.weight(1f),
                                label = "Adet",
                                value = form.itemCount,
                                onValueChange = { form = form.copy(itemCount = it) },
                                accent = ConsoleColors.Violet,
                            )
                        }
                        Row(horizontalArrangement = Arrangement.spacedBy(spacing.small)) {
                            ConsoleFilledButton(
                                text = "Envantere Ekle",
                                accent = ConsoleColors.Violet,
                                onClick = {
                                    val id = form.itemId.toSafeInt(1)
                                    val count = form.itemCount.toSafeInt(1)
                                    when (form.itemKind) {
                                        ItemKind.Item -> cheatPlayer.addItem(id, count)
                                        ItemKind.Weapon -> cheatPlayer.addWeapon(id, count)
                                        ItemKind.Armor -> cheatPlayer.addArmor(id, count)
                                    }
                                },
                            )
                            TextButton(onClick = { cheatPlayer.addAllItems() }) {
                                Text("Tüm Eşyaları Ekle", color = ConsoleColors.Violet)
                            }
                        }
                    }
                }

                item {
                    ConsoleCard(
                        title = "Işınlanma",
                        tag = "// TELEPORT",
                        icon = LudensIcons.Default.ArrowSwap,
                        accent = ConsoleColors.Blue,
                    ) {
                        ConsoleTextField(
                            label = "Harita ID",
                            value = form.mapId,
                            onValueChange = { form = form.copy(mapId = it) },
                            accent = ConsoleColors.Blue,
                        )
                        Row(horizontalArrangement = Arrangement.spacedBy(spacing.small)) {
                            ConsoleTextField(
                                modifier = Modifier.weight(1f),
                                label = "X",
                                value = form.teleportX,
                                onValueChange = { form = form.copy(teleportX = it) },
                                accent = ConsoleColors.Blue,
                            )
                            ConsoleTextField(
                                modifier = Modifier.weight(1f),
                                label = "Y",
                                value = form.teleportY,
                                onValueChange = { form = form.copy(teleportY = it) },
                                accent = ConsoleColors.Blue,
                            )
                        }
                        ConsoleFilledButton(
                            text = "Işınlan",
                            accent = ConsoleColors.Blue,
                            fullWidth = true,
                            onClick = {
                                cheatPlayer.teleport(
                                    form.mapId.toSafeInt(1),
                                    form.teleportX.toSafeInt(),
                                    form.teleportY.toSafeInt(),
                                )
                            },
                        )
                    }
                }

                item {
                    ConsoleCard(
                        title = "Modlar",
                        tag = "// MODES",
                        icon = LudensIcons.Default.Code,
                        accent = ConsoleColors.Pink,
                    ) {
                        ConsoleSwitchRow(
                            text = "Ölümsüzlük Modu (God Mode)",
                            checked = godMode,
                            accent = ConsoleColors.Pink,
                            onCheckedChange = {
                                godMode = it
                                cheatPlayer.setGodMode(it)
                            },
                        )
                        ConsoleSwitchRow(
                            text = "Duvarlardan Geçme",
                            checked = walkThroughWalls,
                            accent = ConsoleColors.Pink,
                            onCheckedChange = {
                                walkThroughWalls = it
                                cheatPlayer.setWalkThroughWalls(it)
                            },
                        )
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(spacing.small),
                        ) {
                            Icon(LudensIcons.Default.TopSpeed, contentDescription = null, tint = ConsoleColors.Pink)
                            ConsoleTextField(
                                modifier = Modifier.weight(1f),
                                label = "Oyun Hızı (1x-8x)",
                                value = form.speed,
                                onValueChange = { form = form.copy(speed = it) },
                                accent = ConsoleColors.Pink,
                            )
                            ConsoleFilledButton(
                                text = "Uygula",
                                accent = ConsoleColors.Pink,
                                onClick = { cheatPlayer.setGameSpeed(form.speed.toSafeFloat(1f)) },
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
                        Row(horizontalArrangement = Arrangement.spacedBy(spacing.small)) {
                            ConsoleFilledButton(
                                text = "Kaydet",
                                accent = ConsoleColors.Cyan,
                                onClick = { cheatPlayer.saveToSlot(form.saveSlot.toSafeInt(1)) },
                            )
                            ConsoleOutlinedButton(
                                text = "Yükle",
                                accent = ConsoleColors.Cyan,
                                onClick = { cheatPlayer.loadFromSlot(form.saveSlot.toSafeInt(1)) },
                            )
                            TextButton(onClick = { cheatPlayer.openMenu() }) {
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
                        modifier = Modifier.fillMaxWidth().padding(top = spacing.small, bottom = spacing.large),
                        contentAlignment = Alignment.Center,
                    ) {
                        ConsoleFooter(text = "// riaslink.fun")
                    }
                }
            }
        }
    }
}

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
        colors = ButtonDefaults.outlinedButtonColors(contentColor = accent),
        border = BorderStroke(1.dp, accent.copy(alpha = 0.5f)),
    ) {
        if (icon != null) {
            Icon(icon, contentDescription = null, modifier = Modifier.padding(end = 6.dp))
        }
        Text(text)
    }
}

/** A labeled switch row styled for the console screens' dark surfaces. */
@Composable
private fun ConsoleSwitchRow(
    text: String,
    checked: Boolean,
    accent: Color,
    onCheckedChange: (Boolean) -> Unit,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text = text,
            color = ConsoleColors.TextPrimary,
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.weight(1f),
        )
        Switch(
            checked = checked,
            onCheckedChange = onCheckedChange,
            colors = SwitchDefaults.colors(
                checkedThumbColor = accent,
                checkedTrackColor = accent.copy(alpha = 0.35f),
                checkedBorderColor = accent,
                uncheckedThumbColor = ConsoleColors.TextMuted,
                uncheckedTrackColor = ConsoleColors.SurfaceRaised,
                uncheckedBorderColor = ConsoleColors.Border,
            ),
        )
    }
}
