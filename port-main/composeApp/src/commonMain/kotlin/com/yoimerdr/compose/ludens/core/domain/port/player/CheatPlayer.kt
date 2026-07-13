package com.yoimerdr.compose.ludens.core.domain.port.player

/**
 * Port interface for debug/cheat operations against a running RPG Maker MV/MZ session.
 *
 * This interface defines the contract for mutating live game state (gold, party stats,
 * inventory, position) and for toggling convenience modes (god mode, walk-through-walls,
 * game speed) for testing or casual play purposes.
 *
 * All operations act on core RPG Maker engine globals (`$gameParty`, `$gameActors`,
 * `$gamePlayer`, etc.) and therefore work on any MV/MZ export, independent of whether
 * the `YDP_Ludens` bridge plugin is present in the game. Implementations should guard
 * against these globals being unavailable (e.g. while still on the title screen, before
 * a game session has started) and silently no-op in that case rather than throwing.
 */
interface CheatPlayer {
    /**
     * Sets the party's gold to an exact amount.
     *
     * @param amount The new gold amount. Implementations should clamp negative values to 0.
     */
    fun setGold(amount: Int)

    /**
     * Adds (or subtracts, if negative) gold from the party's current amount.
     *
     * @param amount The amount of gold to add.
     */
    fun addGold(amount: Int)

    /**
     * Sets an actor's current HP.
     *
     * @param actorId The database actor id (1-based, 1 is typically the main hero).
     * @param hp The new HP value. The engine clamps this to the actor's current max HP.
     */
    fun setActorHp(actorId: Int, hp: Int)

    /**
     * Sets an actor's current MP.
     *
     * @param actorId The database actor id.
     * @param mp The new MP value. The engine clamps this to the actor's current max MP.
     */
    fun setActorMp(actorId: Int, mp: Int)

    /**
     * Changes an actor's level.
     *
     * @param actorId The database actor id.
     * @param level The new level.
     */
    fun setActorLevel(actorId: Int, level: Int)

    /**
     * Fully restores HP/MP/state for every member currently in the party.
     */
    fun healParty()

    /**
     * Adds a quantity of a database item to the party's inventory.
     *
     * @param itemId The database item id.
     * @param count The quantity to add.
     */
    fun addItem(itemId: Int, count: Int)

    /**
     * Adds a quantity of a database weapon to the party's inventory.
     *
     * @param weaponId The database weapon id.
     * @param count The quantity to add.
     */
    fun addWeapon(weaponId: Int, count: Int)

    /**
     * Adds a quantity of a database armor to the party's inventory.
     *
     * @param armorId The database armor id.
     * @param count The quantity to add.
     */
    fun addArmor(armorId: Int, count: Int)

    /**
     * Adds one of every regular item defined in the database to the party's inventory.
     */
    fun addAllItems()

    /**
     * Teleports the player to a specific map and tile coordinate.
     *
     * @param mapId The database map id.
     * @param x The destination tile X coordinate.
     * @param y The destination tile Y coordinate.
     */
    fun teleport(mapId: Int, x: Int, y: Int)

    /**
     * Enables or disables god mode (party HP/MP are continuously kept full while alive).
     *
     * @param enabled Whether god mode should be active.
     */
    fun setGodMode(enabled: Boolean)

    /**
     * Checks whether god mode is currently active.
     *
     * Useful for restoring a toggle's visual state after navigating back to the cheat screen,
     * since god mode itself keeps running in the background independently of which screen is
     * currently shown.
     */
    suspend fun isGodModeActive(): Boolean

    /**
     * Enables or disables walking through walls/obstacles for the player character.
     *
     * @param enabled Whether collision should be bypassed.
     */
    fun setWalkThroughWalls(enabled: Boolean)

    /**
     * Checks whether walk-through-walls is currently active.
     *
     * Useful for restoring a toggle's visual state after navigating back to the cheat screen.
     */
    suspend fun isWalkThroughWallsActive(): Boolean

    /**
     * Sets a game logic speed multiplier (fast-forward).
     *
     * @param rate The speed multiplier. Implementations should clamp this to a safe range
     * (e.g. 1x-8x) to avoid freezing the WebView.
     */
    fun setGameSpeed(rate: Float)

    /**
     * Sets a damage multiplier applied to damage the party deals to enemies (healing and
     * enemy-to-party damage are unaffected).
     *
     * @param multiplier The damage multiplier. Implementations should clamp this to a safe
     * range (e.g. 1x-99x) to avoid integer overflow/absurd values.
     */
    fun setDamageMultiplier(multiplier: Float)

    /**
     * Checks the currently active damage multiplier.
     *
     * Useful for restoring the field's value after navigating back to the cheat screen.
     */
    suspend fun getDamageMultiplier(): Float

    /**
     * Enables or disables instant kill: while active, any damage the party deals to an enemy
     * reduces it to 0 HP.
     *
     * @param enabled Whether instant kill should be active.
     */
    fun setInstantKill(enabled: Boolean)

    /**
     * Checks whether instant kill is currently active.
     *
     * Useful for restoring a toggle's visual state after navigating back to the cheat screen.
     */
    suspend fun isInstantKillActive(): Boolean

    /**
     * Enables or disables random encounters, using the engine's own encounter system (the same
     * mechanism the "Change Encounter" event command uses), so this behaves exactly like the
     * game's own designed toggle rather than a patched approximation.
     *
     * @param enabled Whether random encounters should be enabled.
     */
    fun setEncountersEnabled(enabled: Boolean)

    /**
     * Checks whether random encounters are currently enabled.
     *
     * Useful for restoring a toggle's visual state after navigating back to the cheat screen.
     */
    suspend fun isEncountersEnabled(): Boolean

    /**
     * Saves the current session to a save slot.
     *
     * @param slot The save file slot number, as used by the engine's own save/load menu.
     */
    fun saveToSlot(slot: Int)

    /**
     * Loads a session from a save slot.
     *
     * @param slot The save file slot number to load.
     */
    fun loadFromSlot(slot: Int)

    /**
     * Opens the in-game main menu, if a session is active.
     */
    fun openMenu()

    /**
     * Checks whether a game session is currently active (i.e. not on the title screen).
     *
     * @param isActive Callback invoked with the result.
     */
    fun isGameActive(isActive: (Boolean) -> Unit)

    /** A suspend function that checks whether a game session is currently active. */
    suspend fun isGameActive(): Boolean
}
