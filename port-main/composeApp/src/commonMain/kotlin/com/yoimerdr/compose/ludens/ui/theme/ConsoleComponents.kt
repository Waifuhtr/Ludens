package com.yoimerdr.compose.ludens.ui.theme

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.yoimerdr.compose.ludens.ui.components.provider.LocalSpacing
import com.yoimerdr.compose.ludens.ui.icons.LudensIcons
import com.yoimerdr.compose.ludens.ui.icons.outlined.Dismiss

/**
 * Signature header for the console-styled screens (Cheats, Plugins): a raised panel with a
 * subtle diagonal gradient, a colored border, a small monospace "eyebrow" tag above the title,
 * and a square close button.
 *
 * @param eyebrow Short monospace label shown above the title, e.g. "SYSTEM // CHEATS".
 * @param title The screen's title.
 * @param accent The screen's accent color, used for the eyebrow, border, and close button.
 * @param onClose Invoked when the close button is tapped.
 */
@Composable
fun ConsoleHeader(
    eyebrow: String,
    title: String,
    accent: Color,
    onClose: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val spacing = LocalSpacing.current
    Box(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(20.dp))
            .background(
                Brush.linearGradient(
                    listOf(ConsoleColors.SurfaceRaised, ConsoleColors.Surface)
                )
            )
            .border(1.dp, accent.copy(alpha = 0.35f), RoundedCornerShape(20.dp))
            .padding(horizontal = spacing.large, vertical = spacing.medium)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column {
                Text(
                    text = eyebrow,
                    style = MaterialTheme.typography.labelSmall.copy(
                        fontFamily = FontFamily.Monospace,
                        letterSpacing = 2.sp,
                    ),
                    color = accent,
                )
                Text(
                    text = title,
                    style = MaterialTheme.typography.headlineSmall,
                    fontWeight = FontWeight.Bold,
                    color = ConsoleColors.TextPrimary,
                )
            }

            IconButton(
                onClick = onClose,
                modifier = Modifier
                    .size(40.dp)
                    .clip(RoundedCornerShape(12.dp))
                    .background(ConsoleColors.Surface)
                    .border(1.dp, accent.copy(alpha = 0.45f), RoundedCornerShape(12.dp))
            ) {
                Icon(
                    imageVector = LudensIcons.Default.Dismiss,
                    contentDescription = "Kapat",
                    tint = accent,
                )
            }
        }
    }
}

/**
 * A pill-shaped status indicator with a colored dot, used for compact state readouts
 * (e.g. whether a game session is currently active).
 */
@Composable
fun StatusPill(
    text: String,
    color: Color,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier = modifier
            .clip(RoundedCornerShape(50))
            .background(color.copy(alpha = 0.14f))
            .border(1.dp, color.copy(alpha = 0.4f), RoundedCornerShape(50))
            .padding(horizontal = 12.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Box(
            modifier = Modifier
                .size(6.dp)
                .clip(CircleShape)
                .background(color)
        )
        Text(
            text = text,
            style = MaterialTheme.typography.labelSmall.copy(fontFamily = FontFamily.Monospace),
            color = color,
        )
    }
}

/**
 * A small monospace uppercase tag, used as a category label inside [ConsoleCard] headers.
 */
@Composable
fun ConsoleTag(
    text: String,
    color: Color,
    modifier: Modifier = Modifier,
) {
    Text(
        text = text,
        modifier = modifier,
        style = MaterialTheme.typography.labelSmall.copy(
            fontFamily = FontFamily.Monospace,
            letterSpacing = 1.5.sp,
        ),
        color = color,
    )
}

/**
 * A console-styled section card: a colored icon badge, a tag + title header, and freeform
 * content below, inside an outlined dark panel.
 *
 * @param title The section's display title.
 * @param tag A short monospace category tag shown above the title, e.g. "// GOLD".
 * @param icon The section's icon, shown inside a tinted badge.
 * @param accent The section's accent color (badge, tag, border).
 * @param content The section's body content.
 */
@Composable
fun ConsoleCard(
    title: String,
    tag: String,
    icon: ImageVector,
    accent: Color,
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit,
) {
    val spacing = LocalSpacing.current
    Column(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(18.dp))
            .background(ConsoleColors.Surface)
            .border(1.dp, accent.copy(alpha = 0.22f), RoundedCornerShape(18.dp))
            .padding(spacing.large),
        verticalArrangement = Arrangement.spacedBy(spacing.medium),
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(spacing.medium),
        ) {
            Box(
                modifier = Modifier
                    .size(40.dp)
                    .clip(RoundedCornerShape(12.dp))
                    .background(accent.copy(alpha = 0.16f)),
                contentAlignment = Alignment.Center,
            ) {
                Icon(
                    imageVector = icon,
                    contentDescription = null,
                    tint = accent,
                )
            }
            Column {
                ConsoleTag(text = tag, color = accent)
                Text(
                    text = title,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = ConsoleColors.TextPrimary,
                )
            }
        }

        Column(verticalArrangement = Arrangement.spacedBy(spacing.small)) {
            content()
        }
    }
}

/**
 * Small centered footer credit line used at the bottom of the console-styled screens.
 */
@Composable
fun ConsoleFooter(
    text: String,
    modifier: Modifier = Modifier,
) {
    Text(
        text = text,
        modifier = modifier,
        style = MaterialTheme.typography.labelSmall.copy(fontFamily = FontFamily.Monospace),
        color = ConsoleColors.TextFaint,
    )
}

/**
 * A numeric [OutlinedTextField] pre-styled to read clearly on the console screens' dark
 * surfaces, with an accent-colored focus border.
 *
 * @param label The field's floating label.
 * @param value The current text value.
 * @param onValueChange Invoked with the new value. Only digits and a single leading `-` are
 * accepted; anything else is silently ignored.
 * @param accent The section's accent color, used for the focused border/label/cursor.
 */
@Composable
fun ConsoleTextField(
    label: String,
    value: String,
    onValueChange: (String) -> Unit,
    accent: Color,
    modifier: Modifier = Modifier,
) {
    OutlinedTextField(
        modifier = modifier.fillMaxWidth(),
        value = value,
        onValueChange = { new ->
            if (new.length <= 12 && (new.isEmpty() || CONSOLE_NUMBER_REGEX.matches(new))) {
                onValueChange(new)
            }
        },
        label = { Text(label) },
        singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
        shape = RoundedCornerShape(12.dp),
        colors = OutlinedTextFieldDefaults.colors(
            focusedTextColor = ConsoleColors.TextPrimary,
            unfocusedTextColor = ConsoleColors.TextPrimary,
            focusedBorderColor = accent,
            unfocusedBorderColor = ConsoleColors.Border,
            focusedLabelColor = accent,
            unfocusedLabelColor = ConsoleColors.TextMuted,
            cursorColor = accent,
            focusedContainerColor = ConsoleColors.SurfaceRaised,
            unfocusedContainerColor = ConsoleColors.SurfaceRaised,
        ),
    )
}

private val CONSOLE_NUMBER_REGEX = Regex("^-?\\d*$")
