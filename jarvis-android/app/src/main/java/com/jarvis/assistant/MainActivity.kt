package com.jarvis.assistant

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.jarvis.assistant.ui.ConversationScreen
import com.jarvis.assistant.ui.MainViewModel
import com.jarvis.assistant.ui.SettingsScreen
import com.jarvis.assistant.ui.theme.JarvisTheme

/** Point d'entrée de l'app : affiche soit la conversation, soit les réglages. */
class MainActivity : ComponentActivity() {

    private val viewModel: MainViewModel by viewModels()

    // Demande de permission micro : la réponse arrive ici.
    private val micPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) viewModel.onMicPressed() else viewModel.onMicPermissionDenied()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            JarvisTheme {
                var showSettings by rememberSaveable { mutableStateOf(false) }
                val state by viewModel.state.collectAsStateWithLifecycle()

                // Premier lancement sans clé : on ouvre directement les réglages.
                var firstCheckDone by rememberSaveable { mutableStateOf(false) }
                if (!firstCheckDone) {
                    firstCheckDone = true
                    if (viewModel.settings.anthropicApiKey.isBlank()) showSettings = true
                }

                if (showSettings) {
                    BackHandler { showSettings = false }
                    SettingsScreen(viewModel.settings, onBack = { showSettings = false })
                } else {
                    ConversationScreen(
                        state = state,
                        onMicClick = ::onMicClick,
                        onNewConversation = viewModel::newConversation,
                        onOpenSettings = { showSettings = true },
                    )
                }
            }
        }
    }

    /** Le micro n'est demandé qu'au moment où on en a besoin (premier appui). */
    private fun onMicClick() {
        val granted = ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) ==
            PackageManager.PERMISSION_GRANTED
        if (granted) viewModel.onMicPressed() else micPermission.launch(Manifest.permission.RECORD_AUDIO)
    }
}
