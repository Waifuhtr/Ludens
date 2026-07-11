package ludens.build

import org.gradle.api.Plugin
import org.gradle.api.Project

/**
 * Entry point for the Ludens build-logic plugin.
 *
 * Registers the top-level `ludens` extension on the target project, which exposes
 * sub-extensions for configuring Compose and Android build behavior respectively.
 *
 * **Note:** These sub-extensions act as entry points by convention, not strict restriction.
 * While a plugin affecting Android could technically be activated from the Compose
 * extension, it is not ideal.
 *
 * All other build-logic plugins (e.g., [ludens.build.android.configuration.PermissionsManifestPlugin],
 * [ludens.build.compose.resources.WebAssetsSyncPlugin]) are applied independently
 * and consume this extension's state.
 *
 * Usage in a module-level `build.gradle.kts`:
 * ```kotlin
 * plugins {
 *     id("ludens.build")
 * }
 *
 * ludens {
 *     compose { /* ... */ }
 *     android { /* ... */ }
 * }
 * ```
 */
class LudensBuildPlugin : Plugin<Project> {
    override fun apply(target: Project) {
        target.extensions.create("ludens", LudensExtension::class.java, target)
    }
}
