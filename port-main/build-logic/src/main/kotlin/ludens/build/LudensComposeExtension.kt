package ludens.build

import org.gradle.api.Project
import javax.inject.Inject

/**
 * Compose-specific sub-extension exposed through [LudensExtension.compose].
 *
 * This extension is the configuration entry point for Compose Multiplatform
 * related tasks within the Ludens build system.
 *
 * **Note:** The division between [LudensComposeExtension] and [LudensAndroidExtension]
 * is based on convention rather than strict restriction. For example, a plugin that affects
 * Android could technically be activated via this extension, though doing so is not ideal.
 *
 * Each consuming plugin (e.g., [ludens.build.compose.resources.WebAssetsSyncPlugin],
 * [ludens.build.compose.settings.SettingsPresetPlugin]) reads the resolved configuration
 * from this extension's associated [Project] to generate or sync the corresponding
 * Compose sources.
 *
 * @property project The Gradle project this extension is attached to.
 */
abstract class LudensComposeExtension @Inject constructor(internal val project: Project)
