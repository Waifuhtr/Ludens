package ludens.build.helpers

import org.gradle.api.Project

/**
 * Controls whether a build-logic plugin should be activated for a given Gradle invocation.
 *
 * Used by plugins that should only produce output during release builds
 * (e.g., signing or manifest optimizations) to avoid unnecessary work during
 * debug iterations.
 */
enum class PluginActivationMode {
    /** Always activate the plugin, regardless of the requested build type. */
    All,

    /** Activate only when the requested Gradle tasks include a release build variant. */
    ReleaseOnly,
}

/**
 * Returns `true` when the current Gradle invocation matches [mode].
 *
 * For [PluginActivationMode.All] this always returns `true`.
 * For [PluginActivationMode.ReleaseOnly] it returns `true` when any
 * of the requested task names contain "release" (case-insensitive).
 *
 * @param mode The activation mode to test against.
 * @return Whether the plugin should be enabled.
 */
fun Project.isPluginEnabled(mode: PluginActivationMode): Boolean {
    return when (mode) {
        PluginActivationMode.All -> true
        PluginActivationMode.ReleaseOnly -> gradle.startParameter.taskNames.any {
            it.contains("release", ignoreCase = true)
        }
    }
}
