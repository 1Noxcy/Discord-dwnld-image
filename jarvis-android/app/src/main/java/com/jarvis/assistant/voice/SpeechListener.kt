package com.jarvis.assistant.voice

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer

/**
 * Reconnaissance vocale (le micro → du texte), via le moteur fourni par Android
 * (en général celui de Google).
 *
 * Toutes les méthodes doivent être appelées depuis le fil principal (l'écran).
 */
class SpeechListener(private val context: Context) {

    /** Ce que l'appelant reçoit pendant l'écoute. */
    interface Callbacks {
        fun onPartial(text: String)   // texte provisoire, pendant que vous parlez
        fun onVolume(level: Float)    // niveau sonore 0..1 (servira à animer le HUD)
        fun onResult(text: String)    // phrase finale reconnue
        fun onError(message: String)  // message lisible en français
    }

    private var recognizer: SpeechRecognizer? = null

    fun isAvailable(): Boolean = SpeechRecognizer.isRecognitionAvailable(context)

    fun start(callbacks: Callbacks) {
        stop()
        if (!isAvailable()) {
            callbacks.onError(
                "Aucun moteur de reconnaissance vocale trouvé. Installez ou mettez à jour " +
                    "l'application Google depuis le Play Store."
            )
            return
        }

        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "fr-FR")
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
        }

        recognizer = SpeechRecognizer.createSpeechRecognizer(context).apply {
            setRecognitionListener(object : RecognitionListener {
                override fun onPartialResults(partialResults: Bundle?) {
                    firstResult(partialResults)?.let(callbacks::onPartial)
                }

                override fun onResults(results: Bundle?) {
                    val text = firstResult(results)
                    if (text.isNullOrBlank()) {
                        callbacks.onError("Je n'ai rien entendu, Monsieur.")
                    } else {
                        callbacks.onResult(text)
                    }
                }

                override fun onRmsChanged(rmsdB: Float) {
                    // rmsdB varie environ de -2 (silence) à 10 (voix forte) : on ramène entre 0 et 1.
                    callbacks.onVolume(((rmsdB + 2f) / 12f).coerceIn(0f, 1f))
                }

                override fun onError(error: Int) = callbacks.onError(describeError(error))

                // Événements dont on n'a pas besoin pour l'instant
                override fun onReadyForSpeech(params: Bundle?) {}
                override fun onBeginningOfSpeech() {}
                override fun onBufferReceived(buffer: ByteArray?) {}
                override fun onEndOfSpeech() {}
                override fun onEvent(eventType: Int, params: Bundle?) {}
            })
            startListening(intent)
        }
    }

    fun stop() {
        recognizer?.destroy()
        recognizer = null
    }

    private fun firstResult(bundle: Bundle?): String? =
        bundle?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull()

    private fun describeError(code: Int): String = when (code) {
        SpeechRecognizer.ERROR_NO_MATCH,
        SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> "Je n'ai rien entendu, Monsieur."
        SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS ->
            "Je n'ai pas accès au micro. Autorisez-le dans les paramètres de l'application."
        SpeechRecognizer.ERROR_NETWORK,
        SpeechRecognizer.ERROR_NETWORK_TIMEOUT -> "La reconnaissance vocale a besoin d'Internet, Monsieur."
        SpeechRecognizer.ERROR_AUDIO -> "Le micro semble indisponible."
        SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> "La reconnaissance vocale est occupée, réessayez."
        SpeechRecognizer.ERROR_LANGUAGE_NOT_SUPPORTED,
        SpeechRecognizer.ERROR_LANGUAGE_UNAVAILABLE ->
            "Le français n'est pas disponible pour la reconnaissance vocale sur ce téléphone."
        else -> "Erreur de reconnaissance vocale (code $code)."
    }
}
