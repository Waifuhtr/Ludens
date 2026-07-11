package com.yoimerdr.compose.ludens.core.infrastructure.adapter.player

import com.yoimerdr.compose.ludens.core.domain.port.ScriptEvaluator
import com.yoimerdr.compose.ludens.core.domain.port.evaluatingScript
import com.yoimerdr.compose.ludens.core.domain.port.player.CheatPlayer
import org.koin.core.annotation.Factory
import org.koin.core.annotation.InjectedParam
import kotlin.math.roundToInt

/**
 * Adapter implementation of [CheatPlayer].
 *
 * Mutates a running RPG Maker MV/MZ session through script execution against core engine
 * globals (`$gameParty`, `$gameActors`, `$gamePlayer`, `$gameMap`, `SceneManager`,
 * `DataManager`). Unlike [com.yoimerdr.compose.ludens.core.infrastructure.adapter.player.AudioPlayerAdapter]
 * or [com.yoimerdr.compose.ludens.core.infrastructure.adapter.player.FPSPlayerAdapter], this
 * adapter does not depend on the `YDP_Ludens` bridge plugin being present in the game, since
 * it only touches base engine objects that exist in every MV/MZ export.
 *
 * Every generated script guards against the relevant global being unavailable (e.g. while the
 * title screen is still showing, before `$gameParty`/`$gamePlayer` exist) so calls silently
 * no-op instead of throwing inside the WebView.
 *
 * This class is registered as a Factory in the dependency injection container.
 *
 * @property evaluator The script evaluator used to execute cheat commands.
 */
@Factory
class CheatPlayerAdapter(
    @InjectedParam
    val evaluator: ScriptEvaluator,
) : CheatPlayer {

    override fun setGold(amount: Int) {
        val value = amount.coerceAtLeast(0)
        evaluator.evaluateScript(
            "if(window.\$gameParty){window.\$gameParty._gold=$value;}"
        )
    }

    override fun addGold(amount: Int) {
        evaluator.evaluateScript(
            "if(window.\$gameParty){window.\$gameParty.gainGold($amount);}"
        )
    }

    override fun setActorHp(actorId: Int, hp: Int) {
        val id = actorId.coerceAtLeast(1)
        val value = hp.coerceAtLeast(0)
        evaluator.evaluateScript(
            "if(window.\$gameActors){var a=window.\$gameActors.actor($id);if(a)a.setHp($value);}"
        )
    }

    override fun setActorMp(actorId: Int, mp: Int) {
        val id = actorId.coerceAtLeast(1)
        val value = mp.coerceAtLeast(0)
        evaluator.evaluateScript(
            "if(window.\$gameActors){var a=window.\$gameActors.actor($id);if(a)a.setMp($value);}"
        )
    }

    override fun setActorLevel(actorId: Int, level: Int) {
        val id = actorId.coerceAtLeast(1)
        val value = level.coerceAtLeast(1)
        evaluator.evaluateScript(
            "if(window.\$gameActors){var a=window.\$gameActors.actor($id);if(a)a.changeLevel($value,false);}"
        )
    }

    override fun healParty() {
        evaluator.evaluateScript(
            "if(window.\$gameParty){window.\$gameParty.members().forEach(function(m){m.recoverAll();});}"
        )
    }

    override fun addItem(itemId: Int, count: Int) {
        val id = itemId.coerceAtLeast(1)
        evaluator.evaluateScript(
            "if(window.\$gameParty&&window.\$dataItems&&window.\$dataItems[$id]){window.\$gameParty.gainItem(window.\$dataItems[$id],$count);}"
        )
    }

    override fun addWeapon(weaponId: Int, count: Int) {
        val id = weaponId.coerceAtLeast(1)
        evaluator.evaluateScript(
            "if(window.\$gameParty&&window.\$dataWeapons&&window.\$dataWeapons[$id]){window.\$gameParty.gainItem(window.\$dataWeapons[$id],$count);}"
        )
    }

    override fun addArmor(armorId: Int, count: Int) {
        val id = armorId.coerceAtLeast(1)
        evaluator.evaluateScript(
            "if(window.\$gameParty&&window.\$dataArmors&&window.\$dataArmors[$id]){window.\$gameParty.gainItem(window.\$dataArmors[$id],$count);}"
        )
    }

    override fun addAllItems() {
        evaluator.evaluateScript(
            """
            if(window.${'$'}gameParty&&window.${'$'}dataItems){
                for(var i=1;i<window.${'$'}dataItems.length;i++){
                    if(window.${'$'}dataItems[i])window.${'$'}gameParty.gainItem(window.${'$'}dataItems[i],99);
                }
            }
            """.trimIndent()
        )
    }

    override fun teleport(mapId: Int, x: Int, y: Int) {
        val id = mapId.coerceAtLeast(1)
        evaluator.evaluateScript(
            "if(window.\$gamePlayer){window.\$gamePlayer.reserveTransfer($id,$x,$y,2,0);}"
        )
    }

    override fun setGodMode(enabled: Boolean) {
        evaluator.evaluateScript(
            if (enabled) {
                """
                if(!window.__ludensGodMode){
                    window.__ludensGodMode=setInterval(function(){
                        if(window.${'$'}gameParty){
                            window.${'$'}gameParty.members().forEach(function(m){
                                if(m.hp>0){m.setHp(m.mhp);m.setMp(m.mmp);}
                            });
                        }
                    },400);
                }
                """.trimIndent()
            } else {
                """
                if(window.__ludensGodMode){
                    clearInterval(window.__ludensGodMode);
                    window.__ludensGodMode=null;
                }
                """.trimIndent()
            }
        )
    }

    override fun setWalkThroughWalls(enabled: Boolean) {
        evaluator.evaluateScript(
            "if(window.\$gamePlayer){window.\$gamePlayer.setThrough($enabled);}"
        )
    }

    override fun setGameSpeed(rate: Float) {
        // Clamp to a safe range: below 1x is a no-op (use game's own settings for slow-mo),
        // and above 8x risks freezing the WebView by running too many logic updates per frame.
        val multiplier = rate.roundToInt().coerceIn(1, 8)
        evaluator.evaluateScript(
            """
            (function(){
                if(window.SceneManager&&!window.__ludensSpeedPatched){
                    window.__ludensSpeedPatched=true;
                    window.__ludensSpeedMultiplier=1;
                    var _update=window.SceneManager.update.bind(window.SceneManager);
                    window.SceneManager.update=function(){
                        var n=window.__ludensSpeedMultiplier||1;
                        for(var i=0;i<n;i++){_update();}
                    };
                }
                window.__ludensSpeedMultiplier=$multiplier;
            })();
            """.trimIndent()
        )
    }

    override fun saveToSlot(slot: Int) {
        val id = slot.coerceAtLeast(1)
        evaluator.evaluateScript(
            "if(window.DataManager&&window.\$gameSystem){window.\$gameSystem.onBeforeSave();window.DataManager.saveGame($id);}"
        )
    }

    override fun loadFromSlot(slot: Int) {
        val id = slot.coerceAtLeast(1)
        evaluator.evaluateScript(
            """
            if(window.DataManager){
                var r=window.DataManager.loadGame($id);
                if(r&&typeof r.then==='function'){
                    r.then(function(){if(window.${'$'}gameSystem)window.${'$'}gameSystem.onAfterLoad();});
                } else if(window.${'$'}gameSystem){
                    window.${'$'}gameSystem.onAfterLoad();
                }
            }
            """.trimIndent()
        )
    }

    override fun openMenu() {
        evaluator.evaluateScript(
            "if(window.\$gameParty&&window.SceneManager&&window.Scene_Menu){window.SceneManager.push(window.Scene_Menu);}"
        )
    }

    override fun isGameActive(isActive: (Boolean) -> Unit) {
        evaluator.evaluateScript("!!window.\$gameParty") {
            isActive(it.toBoolean())
        }
    }

    override suspend fun isGameActive(): Boolean {
        return evaluator.evaluatingScript("!!window.\$gameParty").toBoolean()
    }
}
