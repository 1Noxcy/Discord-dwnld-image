package com.jarvis.assistant.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.jarvis.assistant.brain.JarvisBrain
import com.jarvis.assistant.brain.JarvisException
import com.jarvis.assistant.data.Settings
import com.jarvis.assistant.voice.Speaker
import com.jarvis.assistant.voice.SpeechListener
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/** Ce que fait Jarvis en ce moment (servira aussi à animer le HUD en phase 6). */
enum class JarvisStatus { IDLE, LISTENING, THINKING, SPEAKING }

/** Une bulle de la conversation affichée à l'écran. */
data class ChatLine(val fromUser: Boolean, val text: String, val isError: Boolean = false)

/** Tout l'état de l'écran, en un seul objet. */
data class UiState(
    val status: JarvisStatus = JarvisStatus.IDLE,
    val lines: List<ChatLine> = emptyList(),
    val partialText: String = "",   // ce que le micro entend en direct
    val voiceLevel: Float = 0f,     // volume du micro, 0..1
)

/**
 * Le chef d'orchestre : micro → Claude → voix, et met à jour l'écran.
 * Il survit aux rotations d'écran (contrairement à l'Activity).
 */
class MainViewModel(app: Application) : AndroidViewModel(app) {

    val settings = Settings(app)
    private val brain = JarvisBrain()
    private val listener = SpeechListener(app)
    private val speaker = Speaker(app) { speaking ->
        // Fin de la parole → retour au repos (sauf si on écoute déjà de nouveau).
        _state.update {
            when {
                speaking -> it.copy(status = JarvisStatus.SPEAKING)
                it.status == JarvisStatus.SPEAKING -> it.copy(status = JarvisStatus.IDLE)
                else -> it
            }
        }
    }

    private val _state = MutableStateFlow(UiState())
    val state: StateFlow<UiState> = _state.asStateFlow()

    private var thinkingJob: Job? = null

    /** Appui sur le bouton micro : démarre l'écoute, ou l'arrête si elle est en cours. */
    fun onMicPressed() {
        when (_state.value.status) {
            JarvisStatus.LISTENING -> {
                listener.stop()
                _state.update { it.copy(status = JarvisStatus.IDLE, partialText = "", voiceLevel = 0f) }
            }
            else -> startListening()
        }
    }

    /** Appelé si l'utilisateur refuse l'accès au micro. */
    fun onMicPermissionDenied() {
        addLine(
            ChatLine(
                fromUser = false,
                text = "Sans accès au micro, je suis sourd comme un pot, Monsieur. " +
                    "Autorisez-le dans Paramètres › Applications › Jarvis › Autorisations.",
                isError = true,
            )
        )
    }

    fun newConversation() {
        thinkingJob?.cancel()
        listener.stop()
        speaker.stop()
        brain.reset()
        _state.value = UiState()
    }

    private fun startListening() {
        // On interrompt Jarvis s'il parlait ou réfléchissait.
        speaker.stop()
        thinkingJob?.cancel()
        _state.update { it.copy(status = JarvisStatus.LISTENING, partialText = "") }

        listener.start(object : SpeechListener.Callbacks {
            override fun onPartial(text: String) = _state.update { it.copy(partialText = text) }
            override fun onVolume(level: Float) = _state.update { it.copy(voiceLevel = level) }
            override fun onResult(text: String) = sendToJarvis(text)
            override fun onError(message: String) {
                _state.update { it.copy(status = JarvisStatus.IDLE, partialText = "", voiceLevel = 0f) }
                addLine(ChatLine(fromUser = false, text = message, isError = true))
            }
        })
    }

    private fun sendToJarvis(text: String) {
        addLine(ChatLine(fromUser = true, text = text))
        _state.update { it.copy(status = JarvisStatus.THINKING, partialText = "", voiceLevel = 0f) }

        thinkingJob = viewModelScope.launch {
            val reply = try {
                ChatLine(false, brain.ask(text, settings.anthropicApiKey, settings.model))
            } catch (e: JarvisException) {
                ChatLine(false, e.message.orEmpty(), isError = true)
            }
            addLine(reply)
            _state.update { it.copy(status = JarvisStatus.SPEAKING) }
            speaker.speak(reply.text)
        }
    }

    private fun addLine(line: ChatLine) = _state.update { it.copy(lines = it.lines + line) }

    override fun onCleared() {
        listener.stop()
        speaker.shutdown()
    }
}
