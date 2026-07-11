package ludens.build

import org.gradle.api.Project
import javax.inject.Inject

/**
 * Android-specific sub-extension exposed through [LudensExtension.android].
 *
 * This extension serves as the configuration entry point for Android build
 * plugin customizations.
 *
 * **Note:** The division between [LudensAndroidExtension] and [LudensComposeExtension]
 * is based on convention rather than strict restriction. For example, a plugin that affects
 * Android could technically be activated via the Compose extension, though doing so
 * is not ideal.
 *
 * Each consuming plugin (e.g., [ludens.build.android.configuration.PermissionsManifestPlugin])
 * reads the resolved configuration from this extension's associated [Project] to generate
 * the corresponding Android related files.
 *
 * @property project The Gradle project this extension is attached to.
 */
abstract class LudensAndroidExtension @Inject constructor(internal val project: Project)