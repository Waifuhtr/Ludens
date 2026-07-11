package ludens.build.compose.language

import ludens.build.compose.configuration.LudensLanguageConfiguration
import ludens.build.compose.configuration.resolveActiveLanguages
import org.gradle.api.DefaultTask
import org.gradle.api.file.DirectoryProperty
import org.gradle.api.provider.Property
import org.gradle.api.tasks.Input
import org.gradle.api.tasks.InputDirectory
import org.gradle.api.tasks.OutputDirectory
import org.gradle.api.tasks.PathSensitive
import org.gradle.api.tasks.PathSensitivity
import org.gradle.api.tasks.TaskAction

/**
 * Synchronizes language `strings.xml` files from the asset store into Compose resources.
 *
 * The task keeps the resource tree aligned with the currently active language set: it removes
 * previously generated `strings.xml` files, copies the active ones from the asset store, and
 * skips everything else.
 */
abstract class LanguageStringsSyncTask : DefaultTask() {

    /**
     * Source directory that contains the language asset folders.
     */
    @get:InputDirectory
    @get:PathSensitive(PathSensitivity.RELATIVE)
    abstract val assetLanguagesDir: DirectoryProperty

    /**
     * Destination Compose resources directory where generated language folders are written.
     */
    @get:OutputDirectory
    abstract val resourcesDir: DirectoryProperty

    /**
     * Language allowlist used to decide which discovered translations are copied.
     */
    @get:Input
    abstract val configuration: Property<LudensLanguageConfiguration>

    /**
     * Executes the sync between asset language files and Compose resources.
     *
     * The task first discovers languages from the asset tree, resolves the active subset, cleans
     * any previously generated output, and then copies the active `strings.xml` files into the
     * correct Compose `values*` directory.
     */
    @TaskAction
    fun sync() {
        val langDir = assetLanguagesDir.get().asFile
        if (!langDir.isDirectory) return

        val configuration = configuration.get()

        val discovered = discoverAssetLanguages(langDir)
        val active = configuration.resolveActiveLanguages(discovered.map { it.tag }.toSet())
        if (active.isEmpty()) return

        val resourcesRoot = resourcesDir.get().asFile
        val defaultTag = active.first()
        val activeSet = active.toSet()

        // Remove previously generated language files before rewriting the active set.
        resourcesRoot.listFiles()
            ?.filter { it.isDirectory && (it.name == "values" || it.name.startsWith("values-")) }
            ?.forEach { dir ->
                val stringsFile = dir.resolve("strings.xml")
                if (stringsFile.exists()) {
                    stringsFile.delete()
                    logger.info("[ludens] Deleted ${stringsFile.name} from ${dir.name}")
                }
            }

        discovered.forEach { entry ->
            val androidQualifier = androidQualifier(entry.tag)
            if (entry.tag !in activeSet) return@forEach

            // Copy the active strings.xml file from assets into the matching Compose directory.
            val sourceDir = langDir.resolve(androidQualifier)
            val targetName = if (entry.tag == defaultTag) "values"
            else "values-${androidQualifier}"

            val stringsFile = sourceDir.resolve("strings.xml")

            if (stringsFile.isFile) {
                val targetDir = resourcesRoot.resolve(targetName)
                targetDir.mkdirs()
                stringsFile.copyTo(
                    targetDir.resolve("strings.xml"),
                    overwrite = true,
                )
                logger.info("[ludens] Copied ${stringsFile.name} -> $targetName/strings.xml")
            }
        }
    }
}
