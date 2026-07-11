package ludens.build.compose.resources

import ludens.build.LudensComposeExtension
import ludens.build.helpers.composeGenerationDir
import ludens.build.helpers.composeKotlinSourceSet
import ludens.build.helpers.composeResourcesFilesDir
import org.gradle.api.Plugin
import org.gradle.api.Project
import org.gradle.kotlin.dsl.register
import org.jetbrains.kotlin.gradle.tasks.KotlinCompile

/**
 * Registers the file-resource generator used by the Compose Multiplatform app.
 *
 * The task scans `composeResources/files`, generates a typed accessor object and exposes the
 * generated source to `commonMain`.
 */
class ComposeResourceFilesPlugin : Plugin<Project> {
    override fun apply(target: Project) {
        with(target) {

            val generateTask =
                tasks.register<ComposeResourceFilesTask>("generateComposeFileResources") {
                    inputDir.set(
                        composeResourcesFilesDir
                    )
                    outputFile.set(
                        composeGenerationDir
                            .resolve("resources")
                            .resolve("FileRes.kt")
                    )
                    packageName.set("com.yoimerdr.compose.ludens.generated.res")
                    includePatterns.set(
                        listOf(
                            "**/www/index.html", "**/boot/**",
                            "**/fallback/**",
                        )
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
 * Applies the [ComposeResourceFilesPlugin] to the current project.
 *
 * This DSL function should be called inside a `ludens { compose { ... } }` block.
 * Once applied, the plugin scans `composeResources/files`, generates a typed
 * accessor object (`FileRes.kt`) for the project's file resources, and exposes
 * the generated source to `commonMain` for use in the app.
 *
 * Usage:
 * ```kotlin
 * ludens {
 *     compose {
 *         filesRes()
 *     }
 * }
 * ```
 */
fun LudensComposeExtension.filesRes() {
    project.pluginManager.apply(ComposeResourceFilesPlugin::class.java)
}
