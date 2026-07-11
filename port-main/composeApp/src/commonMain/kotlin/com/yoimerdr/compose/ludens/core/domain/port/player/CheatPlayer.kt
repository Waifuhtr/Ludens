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
     * Enables or disables walking through walls/obstacles for the player character.
     *
     * @param enabled Whether collision should be bypassed.
     */
    fun setWalkThroughWalls(enabled: Boolean)

    /**
     * Sets a game logic speed multiplier (fast-forward).
     *
     * @param rate The speed multiplier. Implementations should clamp this to a safe range
     * (e.g. 1x-8x) to avoid freezing the WebView.
     */
    fun setGameSpeed(rate: Float)

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
