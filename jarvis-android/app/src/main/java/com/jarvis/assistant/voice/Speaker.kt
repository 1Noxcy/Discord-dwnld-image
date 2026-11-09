package com.jarvis.assistant.voice

import android.content.Context
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import java.util.Locale

/**
 * Synthèse vocale (du texte → la voix de Jarvis), via le moteur Android.
 *
 * [onSpeakingChanged] est appelé avec true quand Jarvis commence à parler, false quand il a fini.
 * Attention : ce rappel arrive sur un fil secondaire.
 */
class Speaker(context: Context, private val onSpeakingChanged: (Boolean) -> Unit) {

    private var ready = false
    private var pending: String? = null // phrase demandée avant que le moteur soit prêt

    private val tts: TextToSpeech = TextToSpeech(context.applicationContext) { status ->
        if (status == TextToSpeech.SUCCESS) {
            ready = true
            configure()
            pending?.let { speak(it) }
            pending = null
        }
    }

    private fun configure() {
        val result = tts.setLanguage(Locale.FRANCE)
        if (result == TextToSpeech.LANG_MISSING_DATA || result == TextToSpeech.LANG_NOT_SUPPORTED) {
            tts.setLanguage(Locale.FRENCH) // repli sur le français générique
        }
        // Une voix un peu plus grave et posée, façon majordome.
        tts.setPitch(0.9f)
        tts.setSpeechRate(1.05f)

        tts.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(utteranceId: String?) = onSpeakingChanged(true)
            override fun onDone(utteranceId: String?) = onSpeakingChanged(false)
            @Deprecated("Requis par les anciennes versions d'Android")
            override fun onError(utteranceId: String?) = onSpeakingChanged(false)
            override fun onError(utteranceId: String?, errorCode: Int) = onSpeakingChanged(false)
            override fun onStop(utteranceId: String?, interrupted: Boolean) = onSpeakingChanged(false)
        })
    }

    fun speak(text: String) {
        if (!ready) {
            pending = text
            return
        }
        tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, "jarvis-${System.currentTimeMillis()}")
    }

    /** Coupe la parole à Jarvis (par ex. quand on appuie sur le micro pendant qu'il parle). */
    fun stop() {
        pending = null
        if (ready) tts.stop()
    }

    fun shutdown() = tts.shutdown()
}
