package com.yoimerdr.compose.ludens.core.domain.model.settings

/**
 * Enum representing types of quick actions.
 *
 * @property value The integer value associated with this action type.
 */
enum class ActionType(val value: Int) {
    /**
     * Opens the settings options.
     *
     * This action type must never be disabled.
     * */
    Settings(3),

    /** Toggle the visibility of on-screen controls */
    ToggleControls(0),

    /** Toggle audio mute/unmute */
    ToggleMute(1),

    /** Toggle FPS counter display */
    ToggleFPS(2),

    /** Toggle WebGL rendering */
    ToggleWebGL(4),

    /** Opens the cheat/debug menu for the running game session. */
    Cheats(5),

    /** Opens the bundled plugins viewer for the running game session. */
    Plugins(6);

    companion object {
        /**
         * Retrieves an ActionType from its integer value.
         *
         * Falls back to [Settings] instead of throwing when [value] does not match any
         * current entry, so that persisted data referencing a type removed in a future
         * version never crashes deserialization.
         *
         * @param value The integer value to convert.
         * @return The corresponding ActionType, or [Settings] if none match.
         */
        fun from(value: Int): ActionType = entries.firstOrNull { value == it.value } ?: Settings
    }
}