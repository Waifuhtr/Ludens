package ludens.build.helpers

import com.android.build.api.variant.AndroidComponentsExtension
import com.android.build.api.variant.ManifestFiles
import org.gradle.api.NamedDomainObjectContainer
import org.gradle.api.Project
import org.jetbrains.kotlin.gradle.dsl.KotlinMultiplatformExtension
import org.jetbrains.kotlin.gradle.plugin.KotlinSourceSet
import java.io.File

/**
 * Root asset store directory used by build-logic tasks.
 *
 * Points to `project/assets` from the repository root (not the current module).
 */
val Project.assetsStoreDir: File
    get() = rootProject.projectDir.resolve("project/assets")

/**
 * Project root www directory.
 *
 * Points to `project/www` from the repository root.
 * This is the staging area where the user places their RPG Maker `www` export
 * before the build process syncs it into Compose resources.
 */
val Project.projectWwwDir: File
    get() = rootProject.projectDir.resolve("project/www")

/**
 * Compose resource directory for the current module.
 *
 * Resolves to `src/commonMain/composeResources` under the current project directory.
 */
val Project.composeResourcesDir: File
    get() = projectDir.resolve("src/commonMain/composeResources")

/**
 * `files` subdirectory inside [composeResourcesDir].
 *
 * This is where game assets (the `www` folder) are synced so that
 * Compose Multiplatform can package them into the final application.
 */
val Project.composeResourcesFilesDir: File
    get() = composeResourcesDir.resolve("files")

/**
 * Base directory for all Ludens code-generated build outputs.
 *
 * Resolves to `build/generated/ludens` in the current module's build directory.
 */
val Project.generationDir: File
    get() = layout.buildDirectory.dir("generated/ludens").get().asFile

/**
 * Compose-specific generation directory under [generationDir].
 */
val Project.composeGenerationDir: File
    get() = generationDir.resolve("compose")

/**
 * Android `src` directory for the current module.
 *
 * Resolves to `src/androidMain` under the current project directory.
 */
val Project.androidMainDir: File
    get() = projectDir.resolve("src/androidMain")

/**
 * Path to the AndroidManifest.xml for the current module.
 */
val Project.androidManifestFile: File
    get() = androidMainDir.resolve("AndroidManifest.xml")

/**
 * Android-specific generation directory under [generationDir].
 */
val Project.androidGenerationDir: File
    get() = generationDir.resolve("android")

/**
 * iOS-specific generation directory under [generationDir].
 *
 * Reserved for future iOS code generation needs.
 */
val Project.iosGenerationDir: File
    get() = generationDir.resolve("ios")

/**
 * Kotlin Multiplatform source sets for this project, if the KMP plugin is applied.
 *
 * @return The [KotlinSourceSet] container, or `null` if KMP is not configured.
 */
val Project.kmpSources: NamedDomainObjectContainer<KotlinSourceSet>?
    get() = extensions.findByType(KotlinMultiplatformExtension::class.java)?.sourceSets

/**
 * The shared `commonMain` source set, if Kotlin Multiplatform is present.
 */
val Project.composeKotlinSourceSet: KotlinSourceSet?
    get() = kmpSources?.findByName("commonMain")

/**
 * The Android `androidMain` source set, if Kotlin Multiplatform is present.
 */
val Project.androidKotlinSourceSet: KotlinSourceSet?
    get() = kmpSources?.findByName("androidMain")

/**
 * The Android Components extension, available when the Android plugin is applied.
 *
 * Provides access to variant-aware configuration APIs for the Android build.
 */
val Project.androidComponents: AndroidComponentsExtension<*, *, *>?
    get() = extensions.findByType(AndroidComponentsExtension::class.java)

/**
 * Convenience wrapper that executes [action] against the [ManifestFiles] collection
 * for each Android variant.
 *
 * Example usage:
 * ```kotlin
 * project.onAndroidManifests { manifests ->
 *     manifests += project.androidGenerationDir.resolve("AndroidManifest.xml")
 * }
 * ```
 *
 * @param action Callback receiving the [ManifestFiles] for each variant.
 */
fun Project.onAndroidManifests(action: (manifests: ManifestFiles) -> Unit) {
    androidComponents?.onVariants {
        action(it.sources.manifests)
    }
}
