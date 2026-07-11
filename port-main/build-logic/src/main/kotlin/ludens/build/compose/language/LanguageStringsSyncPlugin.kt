package ludens.build.compose.language

import ludens.build.LudensComposeExtension
import ludens.build.compose.configuration.ludensConfiguration
import ludens.build.helpers.PluginActivationMode
import ludens.build.helpers.assetsStoreDir
import ludens.build.helpers.composeResourcesDir
import ludens.build.helpers.isPluginEnabled
import org.gradle.api.Action
import org.gradle.api.Plugin
import org.gradle.api.Project
import org.gradle.api.provider.Property
import org.gradle.kotlin.dsl.register
import org.jetbrains.kotlin.gradle.tasks.KotlinCompile

/**
 * Registers the language strings sync task and wires it into Kotlin compilation.
 *
 * The plugin keeps Compose resources in sync with the language asset store before Kotlin source
 * compilation runs.
 *
 * Recommended workflow:
 * - keep the language configuration aligned for all supported locales
 * - when adding a new language, update both the original `composeResources/values*` files and
 *   the matching asset store files so the sync task can discover and copy it correctly
 * - for no overwrite developer changes, update activationMode to `ReleaseOnly` and run a debug build only.
 */
class LanguageStringsSyncPlugin : Plugin<Project> {
    /**
     * Applies the language synchronization convention to the target project.
     */
    override fun apply(target: Project) {
        with(target) {
            val activationMode = if (extensions.extraProperties.has("ludens.languageStringsSync.mode")) {
                extensions.extraProperties.get("ludens.languageStringsSync.mode") as PluginActivationMode
            } else {
                PluginActivationMode.All
            }
            if (!isPluginEnabled(activationMode)) return

            /**
             * Task that syncs translated `strings.xml` files into Compose resources.
             */
            val syncTask = tasks.register<LanguageStringsSyncTask>("ludensLanguageStringsSync") {
                assetLanguagesDir.set(assetsStoreDir.resolve("languages"))
                resourcesDir.set(composeResourcesDir)
                configuration.set(ludensConfiguration.languages)
                group = "ludens"
                description = "Syncs language strings.xml from asset store to Compose resources."
            }

            syncTask.configure {
                dependsOn("ludensFontSync")
            }

            tasks.matching {
                it.name == "copyNonXmlValueResourcesForCommonMain" ||
                        it.name == "convertXmlValueResourcesForCommonMain" ||
                        it.name == "generateComposeFileResources"
            }.configureEach {
                dependsOn(syncTask)
            }

            tasks.withType(KotlinCompile::class.java).configureEach {
                dependsOn(syncTask)
            }
        }
    }
}

/**
 * DSL extension that configures the behaviour of [LanguageStringsSyncPlugin].
 *
 * Instantiated internally when the action-accepting overload of
 * [LudensComposeExtension.languageStringsSync] is called.
 *
 * @property mode Controls when the sync task executes.
 *   Defaults to [PluginActivationMode.All].
 */
abstract class LanguageStringsSyncExtension {
    abstract val mode: Property<PluginActivationMode>

    init {
        mode.convention(PluginActivationMode.All)
    }
}

/**
 * Applies the [LanguageStringsSyncPlugin] with a custom configuration block.
 *
 * This overload accepts an [Action] to configure the [LanguageStringsSyncExtension],
 * which allows setting the [LanguageStringsSyncExtension.mode] to control
 * whether the sync runs for all builds or only release builds.
 *
 * Usage:
 * ```kotlin
 * ludens {
 *     compose {
 *         languageStringsSync {
 *             mode.set(PluginActivationMode.ReleaseOnly)
 *         }
 *     }
 * }
 * ```
 *
 * @param action Configuration block for the [LanguageStringsSyncExtension].
 */
fun LudensComposeExtension.languageStringsSync(action: Action<LanguageStringsSyncExtension>) {
    val ext = project.objects.newInstance(LanguageStringsSyncExtension::class.java)
    action.execute(ext)
    project.extensions.extraProperties.set("ludens.languageStringsSync.mode", ext.mode.get())
    project.pluginManager.apply(LanguageStringsSyncPlugin::class.java)
}

/**
 * Applies the [LanguageStringsSyncPlugin] with default settings.
 *
 * This overload uses [PluginActivationMode.All], meaning the sync runs for every
 * build invocation. Call the overload accepting an [Action] if you need to restrict
 * sync to release builds only.
 *
 * Usage:
 * ```kotlin
 * ludens {
 *     compose {
 *         languageStringsSync()
 *     }
 * }
 * ```
 */
fun LudensComposeExtension.languageStringsSync() {
    project.extensions.extraProperties.set(
        "ludens.languageStringsSync.mode",
        PluginActivationMode.All
    )
    project.pluginManager.apply(LanguageStringsSyncPlugin::class.java)
}
