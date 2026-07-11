package ludens.build.android.configuration

import ludens.build.LudensAndroidExtension
import ludens.build.helpers.androidGenerationDir
import ludens.build.compose.configuration.ludensConfiguration
import ludens.build.helpers.onAndroidManifests
import org.gradle.api.Plugin
import org.gradle.api.Project
import org.gradle.kotlin.dsl.register

/**
 * Registers the manifest-permission generator for the Android app module.
 *
 * The plugin reads the permission flags from `ludens.properties`, generates a small manifest
 * fragment and wires that fragment into the main Android source set before manifest merge.
 */
class PermissionsManifestPlugin : Plugin<Project> {

    override fun apply(project: Project) {
        // Generated manifest fragment containing only the enabled permissions.
        val generatedManifestFile = project.androidGenerationDir.resolve("permissions")
            .resolve("AndroidManifest.xml")

        // Task input is derived from the loaded Ludens Android permission block.
        val generateManifestTask =
            project.tasks.register<GeneratePermissionsManifestTask>("ludensGeneratePermissionsManifest") {
                this.manifest.set(generatedManifestFile)
                this.permissions.set(project.provider {
                    val settings = project.ludensConfiguration.android.permissions
                    val permissions = mutableListOf<String>()

                    if (settings.internet) permissions.add("android.permission.INTERNET")
                    if (settings.networkState) permissions.add("android.permission.ACCESS_NETWORK_STATE")
                    if (settings.wakeLock) permissions.add("android.permission.WAKE_LOCK")
                    if (settings.accessWifiState) permissions.add("android.permission.ACCESS_WIFI_STATE")
                    if (settings.changeWifiState) permissions.add("android.permission.CHANGE_WIFI_STATE")

                    permissions
                })
            }

        project.onAndroidManifests {
            it.addGeneratedManifestFile(
                generateManifestTask,
                GeneratePermissionsManifestTask::manifest
            )
        }
    }
}

/**
 * Applies the [PermissionsManifestPlugin] to the current project.
 *
 * This DSL function should be called inside a `ludens { android { ... } }` block.
 * Once applied, the plugin reads the permission flags from `ludens.properties`,
 * generates a small Android manifest fragment containing only the enabled
 * permissions, and wires that fragment into the main Android source set before
 * manifest merge.
 *
 * Usage:
 * ```kotlin
 * ludens {
 *     android {
 *         permissions()
 *     }
 * }
 * ```
 */
fun LudensAndroidExtension.permissions() {
    project.pluginManager.apply(
        PermissionsManifestPlugin::class.java
    )
}

