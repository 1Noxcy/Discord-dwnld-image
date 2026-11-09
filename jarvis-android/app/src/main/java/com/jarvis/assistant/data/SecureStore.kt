package com.jarvis.assistant.data

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/**
 * Petit coffre-fort pour les secrets (clés API).
 *
 * Principe :
 *  - une clé de chiffrement AES est créée UNE fois dans l'Android Keystore
 *    (une puce/zone sécurisée du téléphone : la clé ne peut pas en sortir) ;
 *  - chaque secret est chiffré avec cette clé avant d'être écrit dans les préférences ;
 *  - même si quelqu'un copiait les fichiers de l'app, il ne verrait que du charabia.
 */
class SecureStore(context: Context) {

    private val prefs = context.getSharedPreferences("jarvis_secure", Context.MODE_PRIVATE)

    /** Enregistre (chiffré) une valeur. Une valeur vide efface l'entrée. */
    fun put(name: String, value: String) {
        if (value.isBlank()) {
            prefs.edit().remove(name).apply()
            return
        }
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.ENCRYPT_MODE, getOrCreateKey())
        val encrypted = cipher.doFinal(value.toByteArray(Charsets.UTF_8))
        // On stocke le vecteur d'initialisation (IV) avec le texte chiffré : "iv:données"
        val stored = b64(cipher.iv) + ":" + b64(encrypted)
        prefs.edit().putString(name, stored).apply()
    }

    /** Relit et déchiffre une valeur, ou renvoie null si absente/illisible. */
    fun get(name: String): String? {
        val stored = prefs.getString(name, null) ?: return null
        return try {
            val (iv, data) = stored.split(":").let { unb64(it[0]) to unb64(it[1]) }
            val cipher = Cipher.getInstance(TRANSFORMATION)
            cipher.init(Cipher.DECRYPT_MODE, getOrCreateKey(), GCMParameterSpec(128, iv))
            String(cipher.doFinal(data), Charsets.UTF_8)
        } catch (e: Exception) {
            // Clé du Keystore perdue (ex. réinitialisation) : on oublie la valeur.
            null
        }
    }

    private fun getOrCreateKey(): SecretKey {
        val keyStore = KeyStore.getInstance(KEYSTORE).apply { load(null) }
        (keyStore.getKey(KEY_ALIAS, null) as? SecretKey)?.let { return it }

        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, KEYSTORE)
        generator.init(
            KeyGenParameterSpec.Builder(
                KEY_ALIAS,
                KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT
            )
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .build()
        )
        return generator.generateKey()
    }

    private fun b64(bytes: ByteArray) = Base64.encodeToString(bytes, Base64.NO_WRAP)
    private fun unb64(text: String) = Base64.decode(text, Base64.NO_WRAP)

    private companion object {
        const val KEYSTORE = "AndroidKeyStore"
        const val KEY_ALIAS = "jarvis_secrets_key"
        const val TRANSFORMATION = "AES/GCM/NoPadding"
    }
}
