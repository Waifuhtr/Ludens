package com.yoimerdr.compose.ludens.features.cheats.presentation.screen

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
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
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.input.KeyboardType
import androidx.navigation.NavController
import com.yoimerdr.compose.ludens.app.ui.providers.LocalCheatPlayer
import com.yoimerdr.compose.ludens.core.domain.port.player.CheatPlayer
import com.yoimerdr.compose.ludens.features.settings.presentation.components.CloseIconButton
import com.yoimerdr.compose.ludens.features.settings.presentation.components.OptionCard
import com.yoimerdr.compose.ludens.features.settings.presentation.components.OptionName
import com.yoimerdr.compose.ludens.features.settings.presentation.components.OptionsContainer
import com.yoimerdr.compose.ludens.ui.components.fields.SwitchField
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

private val NUMBER_INPUT_REGEX = Regex("^-?\\d*$")

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

    suspend fun refreshActiveState() {
        isGameActive = cheatPlayer.isGameActive()
    }

    LaunchedEffect(Unit) {
        refreshActiveState()
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
                    text = "Hile Menüsü",
                    style = MaterialTheme.typography.headlineSmall,
                )
                CloseIconButton(onClick = { nav.popBackStack() })
            }

            ActiveStateBanner(
                isActive = isGameActive,
                onRefresh = { scope.launch { refreshActiveState() } },
            )

            OptionsContainer(
                modifier = Modifier.fillMaxSize(),
            ) {
                item {
                    CheatCard(title = "Altın", icon = LudensIcons.Default.Circle) {
                        NumberField(
                            label = "Miktar",
                            value = form.gold,
                            onValueChange = { form = form.copy(gold = it) },
                        )
                        Row(horizontalArrangement = Arrangement.spacedBy(spacing.small)) {
                            OutlinedButton(onClick = { cheatPlayer.setGold(form.gold.toSafeInt()) }) {
                                Text("Ayarla")
                            }
                            OutlinedButton(onClick = { cheatPlayer.addGold(form.gold.toSafeInt()) }) {
                                Text("Ekle / Çıkar")
                            }
                        }
                    }
                }

                item {
                    CheatCard(title = "Karakter (HP / MP / Seviye)", icon = LudensIcons.Default.Person) {
                        NumberField(
                            label = "Karakter ID (1 = ana kahraman)",
                            value = form.actorId,
                            onValueChange = { form = form.copy(actorId = it) },
                        )
                        Row(horizontalArrangement = Arrangement.spacedBy(spacing.small)) {
                            NumberField(
                                modifier = Modifier.weight(1f),
                                label = "HP",
                                value = form.hp,
                                onValueChange = { form = form.copy(hp = it) },
                            )
                            NumberField(
                                modifier = Modifier.weight(1f),
                                label = "MP",
                                value = form.mp,
                                onValueChange = { form = form.copy(mp = it) },
                            )
                        }
                        Row(horizontalArrangement = Arrangement.spacedBy(spacing.small)) {
                            OutlinedButton(onClick = {
                                val id = form.actorId.toSafeInt(1)
                                cheatPlayer.setActorHp(id, form.hp.toSafeInt())
                                cheatPlayer.setActorMp(id, form.mp.toSafeInt())
                            }) {
                                Text("HP/MP Uygula")
                            }
                            OutlinedButton(onClick = { cheatPlayer.healParty() }) {
                                Icon(
                                    LudensIcons.Default.ArrowReset,
                                    contentDescription = null,
                                    modifier = Modifier.padding(end = spacing.extraSmall),
                                )
                                Text("Partiyi İyileştir")
                            }
                        }
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(spacing.small),
                        ) {
                            NumberField(
                                modifier = Modifier.weight(1f),
                                label = "Seviye",
                                value = form.level,
                                onValueChange = { form = form.copy(level = it) },
                            )
                            FilledTonalButton(onClick = {
                                cheatPlayer.setActorLevel(form.actorId.toSafeInt(1), form.level.toSafeInt(1))
                            }) {
                                Text("Uygula")
                            }
                        }
                    }
                }

                item {
                    CheatCard(title = "Eşya Ekle", icon = LudensIcons.Default.ArrowDownload) {
                        Row(horizontalArrangement = Arrangement.spacedBy(spacing.small)) {
                            ItemKind.entries.forEach { kind ->
                                val selected = form.itemKind == kind
                                if (selected) {
                                    FilledTonalButton(onClick = { form = form.copy(itemKind = kind) }) {
                                        Text(kind.label)
                                    }
                                } else {
                                    OutlinedButton(onClick = { form = form.copy(itemKind = kind) }) {
                                        Text(kind.label)
                                    }
                                }
                            }
                        }
                        Row(horizontalArrangement = Arrangement.spacedBy(spacing.small)) {
                            NumberField(
                                modifier = Modifier.weight(1f),
                                label = "ID",
                                value = form.itemId,
                                onValueChange = { form = form.copy(itemId = it) },
                            )
                            NumberField(
                                modifier = Modifier.weight(1f),
                                label = "Adet",
                                value = form.itemCount,
                                onValueChange = { form = form.copy(itemCount = it) },
                            )
                        }
                        Row(horizontalArrangement = Arrangement.spacedBy(spacing.small)) {
                            OutlinedButton(onClick = {
                                val id = form.itemId.toSafeInt(1)
                                val count = form.itemCount.toSafeInt(1)
                                when (form.itemKind) {
                                    ItemKind.Item -> cheatPlayer.addItem(id, count)
                                    ItemKind.Weapon -> cheatPlayer.addWeapon(id, count)
                                    ItemKind.Armor -> cheatPlayer.addArmor(id, count)
                                }
                            }) {
                                Text("Envantere Ekle")
                            }
                            TextButton(onClick = { cheatPlayer.addAllItems() }) {
                                Text("Tüm Eşyaları Ekle")
                            }
                        }
                    }
                }

                item {
                    CheatCard(title = "Işınlanma", icon = LudensIcons.Default.ArrowSwap) {
                        NumberField(
                            label = "Harita ID",
                            value = form.mapId,
                            onValueChange = { form = form.copy(mapId = it) },
                        )
                        Row(horizontalArrangement = Arrangement.spacedBy(spacing.small)) {
                            NumberField(
                                modifier = Modifier.weight(1f),
                                label = "X",
                                value = form.teleportX,
                                onValueChange = { form = form.copy(teleportX = it) },
                            )
                            NumberField(
                                modifier = Modifier.weight(1f),
                                label = "Y",
                                value = form.teleportY,
                                onValueChange = { form = form.copy(teleportY = it) },
                            )
                        }
                        OutlinedButton(onClick = {
                            cheatPlayer.teleport(
                                form.mapId.toSafeInt(1),
                                form.teleportX.toSafeInt(),
                                form.teleportY.toSafeInt(),
                            )
                        }) {
                            Text("Işınlan")
                        }
                    }
                }

                item {
                    CheatCard(title = "Modlar", icon = LudensIcons.Default.Code) {
                        SwitchField(
                            checked = godMode,
                            onCheckedChange = {
                                godMode = it
                                cheatPlayer.setGodMode(it)
                            },
                            text = "Ölümsüzlük Modu (God Mode)",
                        )
                        SwitchField(
                            checked = walkThroughWalls,
                            onCheckedChange = {
                                walkThroughWalls = it
                                cheatPlayer.setWalkThroughWalls(it)
                            },
                            text = "Duvarlardan Geçme",
                        )
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(spacing.small),
                        ) {
                            Icon(LudensIcons.Default.TopSpeed, contentDescription = null)
                            NumberField(
                                modifier = Modifier.weight(1f),
                                label = "Oyun Hızı (1x-8x)",
                                value = form.speed,
                                onValueChange = { form = form.copy(speed = it) },
                            )
                            FilledTonalButton(onClick = {
                                cheatPlayer.setGameSpeed(form.speed.toSafeFloat(1f))
                            }) {
                                Text("Uygula")
                            }
                        }
                    }
                }

                item {
                    CheatCard(title = "Kayıt / Menü", icon = LudensIcons.Default.Save) {
                        NumberField(
                            label = "Kayıt Slotu",
                            value = form.saveSlot,
                            onValueChange = { form = form.copy(saveSlot = it) },
                        )
                        Row(horizontalArrangement = Arrangement.spacedBy(spacing.small)) {
                            OutlinedButton(onClick = { cheatPlayer.saveToSlot(form.saveSlot.toSafeInt(1)) }) {
                                Text("Kaydet")
                            }
                            OutlinedButton(onClick = { cheatPlayer.loadFromSlot(form.saveSlot.toSafeInt(1)) }) {
                                Text("Yükle")
                            }
                            TextButton(onClick = { cheatPlayer.openMenu() }) {
                                Icon(
                                    LudensIcons.Default.Games,
                                    contentDescription = null,
                                    modifier = Modifier.padding(end = spacing.extraSmall),
                                )
                                Text("Menüyü Aç")
                            }
                        }
                    }
                }
            }
        }
    }
}

/**
 * A cheat section card: an icon+title header row followed by tightly-spaced content.
 * Built on the base [OptionCard] so it matches the rest of the app's card styling.
 */
@Composable
private fun CheatCard(
    title: String,
    icon: ImageVector,
    content: @Composable () -> Unit,
) {
    val spacing = LocalSpacing.current
    OptionCard {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(spacing.small),
        ) {
            Icon(icon, contentDescription = null)
            OptionName(text = title)
        }
        Column(verticalArrangement = Arrangement.spacedBy(spacing.small)) {
            content()
        }
    }
}

/** Small banner that informs whether a game session is currently active. */
@Composable
private fun ActiveStateBanner(
    isActive: Boolean?,
    onRefresh: () -> Unit,
) {
    if (isActive == false) {
        val spacing = LocalSpacing.current
        Surface(
            modifier = Modifier.fillMaxWidth(),
            color = MaterialTheme.colorScheme.errorContainer,
            shape = MaterialTheme.shapes.medium,
        ) {
            Row(
                modifier = Modifier.padding(horizontal = spacing.medium, vertical = spacing.small),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = "Aktif bir oyun oturumu bulunamadı. Hileler, oyunu (Yeni Oyun / Devam Et) başlattıktan sonra çalışır.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onErrorContainer,
                    modifier = Modifier.weight(1f),
                )
                TextButton(onClick = onRefresh) {
                    Text("Yenile")
                }
            }
        }
    }
}

/** Compact outlined numeric text field used across the cheat form. */
@Composable
private fun NumberField(
    modifier: Modifier = Modifier,
    label: String,
    value: String,
    onValueChange: (String) -> Unit,
) {
    OutlinedTextField(
        modifier = modifier.fillMaxWidth(),
        value = value,
        onValueChange = { new ->
            if (new.length <= 12 && (new.isEmpty() || NUMBER_INPUT_REGEX.matches(new))) {
                onValueChange(new)
            }
        },
        label = { Text(label) },
        singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
    )
}
