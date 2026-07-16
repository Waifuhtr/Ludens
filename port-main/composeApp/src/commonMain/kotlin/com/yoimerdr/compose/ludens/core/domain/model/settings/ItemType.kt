package com.yoimerdr.compose.ludens.core.domain.model.settings

/**
 * Enum representing types of control items.
 *
 * @property value The integer value associated with this type.
 */
enum class ItemType(val value: Int) {
    /** The joystick control */
    Joystick(0),

    /** The A action button */
    KeyA(1),

    /** The B action button */
    KeyB(2),

    /** The X action button */
    KeyX(3),

    /** The Y action button */
    KeyY(4),

    /** The fast actions button */
    Actions(5);

    companion object {
        /**
         * Retrieves an ItemType from its integer value.
         *
         * Falls back to [Joystick] instead of throwing when [value] does not match any current
         * entry, so that persisted data referencing a type removed in a future version never
         * crashes deserialization.
         *
         * @param value The integer value to convert.
         * @return The corresponding ItemType, or [Joystick] if none match.
         */
        fun from(value: Int): ItemType = entries.firstOrNull { value == it.value } ?: Joystick

        /**
         * Set of all key-type items.
         */
        val keys: Set<ItemType>
            get() = setOf(KeyA, KeyB, KeyX, KeyY)

        val Settings = Actions
    }

    /**
     * Converts this ItemType to its corresponding PositionableType.
     *
     * @return The PositionableType for this item.
     */
    fun toPositionable(): PositionableType {
        return when (this) {
            Joystick -> PositionableType.Joystick
            KeyA, KeyB, KeyX, KeyY -> PositionableType.Keys
            Actions -> PositionableType.Actions
        }
    }

    /**
     * The simplified name for this item type.
     */
    val simpleName: String
        get() = when (this) {
            Joystick -> "JS"
            Actions -> "AT"
            KeyA -> "A"
            KeyB -> "B"
            KeyX -> "X"
            KeyY -> "Y"
        }

    /**
     * Returns the valid alpha range for this item type.
     *
     * @return A float range representing valid alpha values.
     */
    fun toRange() = if (this == Actions) 0.35f..1f else .15f..1f

}
