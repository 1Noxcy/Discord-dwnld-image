package com.jarvis.assistant.data

import android.content.Context

/**
 * Réglages de Jarvis.
 *  - La clé API Anthropic passe par [SecureStore] (chiffrée).
 *  - Le nom du modèle n'est pas secret : préférences normales.
 */
class Settings(context: Context) {

    private val secure = SecureStore(context)
    private val prefs = context.getSharedPreferences("jarvis_settings", Context.MODE_PRIVATE)

    var anthropicApiKey: String
        get() = secure.get(KEY_ANTHROPIC).orEmpty()
        set(value) = secure.put(KEY_ANTHROPIC, value.trim())

    var model: String
        get() = prefs.getString(KEY_MODEL, null)?.takeIf { it.isNotBlank() } ?: DEFAULT_MODEL
        set(value) = prefs.edit().putString(KEY_MODEL, value.trim()).apply()

    companion object {
        /** Modèle par défaut : Claude Haiku 5.5, rapide et peu cher. */
        const val DEFAULT_MODEL = "claude-haiku-5-5"

        private const val KEY_ANTHROPIC = "anthropic_api_key"
        private const val KEY_MODEL = "model"
    }
}
