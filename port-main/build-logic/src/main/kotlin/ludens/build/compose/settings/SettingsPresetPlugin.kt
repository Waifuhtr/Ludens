package ludens.build.compose.settings

import ludens.build.LudensComposeExtension
import ludens.build.compose.configuration.ludensConfiguration
import ludens.build.compose.configuration.resolvedSettingsPreset
import ludens.build.helpers.composeGenerationDir
import ludens.build.helpers.composeKotlinSourceSet
import org.gradle.api.Plugin
import org.gradle.api.Project
import org.gradle.kotlin.dsl.register
import org.jetbrains.kotlin.gradle.tasks.KotlinCompile

/**
 * Registers the task that generates `LudensSettingsPreset.kt` from `ludens.properties`.
 *
 * The plugin resolves the Ludens configuration once, wires the generation task into the KMP
 * source set and makes all Kotlin compile tasks depend on the generated file.
 */
class SettingsPresetPlugin : Plugin<Project> {
    override fun apply(target: Project) {
        with(target) {
            val preset = ludensConfiguration.resolvedSettingsPreset()

            val generateTask =
                tasks.register<SettingsPresetGenerationTask>("generateLudensSettingsPreset") {
                    packageName.set("com.yoimerdr.compose.ludens.generated.settings")
                    objectName.set("LudensSettingsPreset")
                    presets.set(preset)

                    outputFile.set(
                        composeGenerationDir
                            .resolve("settings")
                            .resolve("LudensSettingsPreset.kt")
                    )
                }

            afterEvaluate {
                composeKotlinSourceSet
                    ?.kotlin
                    ?.srcDir(generateTask.map { it.outputFile.get().asFile.parentFile })
            }

            tasks.withType(KotlinCompile::class.java)
                .configureEach {
                    dependsOn(generateTask)
                }
        }
    }
}

/**
 * Applies the [SettingsPresetPlugin] to the current project.
 *
 * This DSL function should be called inside a `ludens { compose { ... } }` block.
 * Once applied, the plugin reads the settings preset values from `ludens.properties`,
 * generates a `LudensSettingsPreset.kt` source file with the resolved defaults,
 * and ensures the generated source is available to `commonMain` before compilation.
 *
 * Usage:
 * ```kotlin
 * ludens {
 *     compose {
 *         settingsPreset()
 *     }
 * }
 * ```
 */
fun LudensComposeExtension.settingsPreset() {
    project.pluginManager.apply(SettingsPresetPlugin::class.java)
}
