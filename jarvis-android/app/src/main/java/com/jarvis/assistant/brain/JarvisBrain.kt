package com.jarvis.assistant.brain

import com.anthropic.client.AnthropicClient
import com.anthropic.client.okhttp.AnthropicOkHttpClient
import com.anthropic.errors.AnthropicIoException
import com.anthropic.errors.AnthropicServiceException
import com.anthropic.errors.BadRequestException
import com.anthropic.errors.InternalServerException
import com.anthropic.errors.NotFoundException
import com.anthropic.errors.PermissionDeniedException
import com.anthropic.errors.RateLimitException
import com.anthropic.errors.UnauthorizedException
import com.anthropic.models.messages.Message
import com.anthropic.models.messages.MessageCreateParams
import com.anthropic.models.messages.MessageParam
import com.anthropic.models.messages.OutputConfig
import com.anthropic.models.messages.StopReason
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.time.Duration

/** Erreur "lisible" : [message] est directement affichable / prononçable. */
class JarvisException(message: String, cause: Throwable? = null) : Exception(message, cause)

/**
 * Le "cerveau" de Jarvis : envoie la conversation à Claude et renvoie sa réponse.
 *
 * L'historique est gardé en mémoire tant que l'app tourne. On renvoie à chaque fois
 * la conversation complète, car l'API ne se souvient de rien d'un appel à l'autre.
 */
class JarvisBrain {

    /** Historique au format de l'API (messages utilisateur + réponses complètes de Claude). */
    private val history = mutableListOf<MessageParam>()

    /**
     * Numéro de "version" de l'historique. Si Monsieur coupe la parole à Jarvis et pose une
     * nouvelle question, la réponse à l'ancienne question arrive trop tard : grâce à ce numéro,
     * on la jette au lieu de mélanger les deux échanges.
     */
    private var generation = 0

    // Le client est recréé seulement si la clé change.
    private var client: AnthropicClient? = null
    private var clientKey: String? = null

    /** Oublie la conversation en cours (bouton "Nouvelle conversation"). */
    @Synchronized
    fun reset() {
        history.clear()
        generation++
    }

    /**
     * Envoie [userText] à Claude et renvoie le texte de sa réponse.
     * Lève [JarvisException] avec un message en français en cas de problème.
     */
    suspend fun ask(userText: String, apiKey: String, model: String): String =
        withContext(Dispatchers.IO) { // le réseau ne doit jamais bloquer l'écran
            if (apiKey.isBlank()) {
                throw JarvisException("Aucune clé API, Monsieur. Ajoutez-la dans les Réglages.")
            }

            // On prépare l'échange sur une copie : l'historique officiel n'est modifié
            // qu'en cas de succès, il reste donc toujours valide.
            val (turn, myGeneration) = synchronized(this@JarvisBrain) {
                (history + MessageParam.ofUser(userText)) to ++generation
            }

            val response = try {
                clientFor(apiKey).messages().create(buildParams(model, turn))
            } catch (e: Exception) {
                throw toReadableError(e)
            }

            synchronized(this@JarvisBrain) {
                if (myGeneration == generation) {
                    // On garde la réponse COMPLÈTE (y compris les blocs de réflexion) telle
                    // quelle : l'API exige qu'on ne la modifie pas.
                    history.clear()
                    history += turn
                    history += response.toParam()
                }
            }
            readAnswer(response)
        }

    private fun buildParams(model: String, messages: List<MessageParam>): MessageCreateParams =
        MessageCreateParams.builder()
            .model(model)
            .maxTokens(4096L)
            .system(SYSTEM_PROMPT)
            // Effort "faible" : réponses rapides, idéal pour une conversation vocale.
            .outputConfig(OutputConfig.builder().effort(OutputConfig.Effort.LOW).build())
            .messages(messages)
            .build()

    /** Extrait le texte de la réponse en tenant compte de la raison de l'arrêt. */
    private fun readAnswer(response: Message): String {
        val text = response.content()
            .mapNotNull { block -> block.text().orElse(null)?.text() }
            .joinToString(" ")
            .trim()

        return when (response.stopReason().orElse(null)) {
            StopReason.REFUSAL ->
                "Je crains de devoir décliner cette demande, Monsieur."
            StopReason.MAX_TOKENS ->
                text.ifEmpty { "Ma réponse était trop longue, Monsieur. Pourriez-vous préciser ?" }
            else ->
                text.ifEmpty { "Je n'ai rien à ajouter, Monsieur." }
        }
    }

    @Synchronized
    private fun clientFor(apiKey: String): AnthropicClient {
        if (client == null || clientKey != apiKey) {
            client = AnthropicOkHttpClient.builder()
                .apiKey(apiKey)
                .maxRetries(2)                       // réessaie seul en cas de surcharge passagère
                .timeout(Duration.ofSeconds(60))
                .build()
            clientKey = apiKey
        }
        return client!!
    }

    /** Traduit les erreurs techniques en phrases compréhensibles (du plus précis au plus général). */
    private fun toReadableError(e: Exception): JarvisException = when (e) {
        is UnauthorizedException ->
            JarvisException("Clé API invalide, Monsieur. Vérifiez-la dans les Réglages.", e)
        is PermissionDeniedException ->
            JarvisException("Cette clé API n'a pas accès à ce modèle, Monsieur.", e)
        is NotFoundException ->
            JarvisException("Modèle introuvable, Monsieur. Vérifiez son nom dans les Réglages.", e)
        is RateLimitException ->
            JarvisException("Trop de demandes d'un coup, Monsieur. Réessayez dans un instant.", e)
        is InternalServerException ->
            JarvisException("Les serveurs d'Anthropic sont indisponibles, Monsieur. Réessayez plus tard.", e)
        is BadRequestException -> {
            val details = e.message.orEmpty()
            if (details.contains("credit", ignoreCase = true)) {
                JarvisException("Crédit API épuisé, Monsieur. Rechargez votre compte Anthropic.", e)
            } else {
                JarvisException("Requête refusée par l'API : $details", e)
            }
        }
        is AnthropicServiceException ->
            JarvisException("Erreur de l'API (code ${e.statusCode()}), Monsieur.", e)
        is AnthropicIoException ->
            JarvisException("Pas de connexion Internet, Monsieur. Vérifiez le Wi-Fi ou les données mobiles.", e)
        is JarvisException -> e
        else ->
            JarvisException("Une erreur inattendue s'est produite : ${e.message}", e)
    }

    private companion object {
        /** Personnalité de Jarvis. Les réponses sont lues à voix haute : pas de mise en forme. */
        val SYSTEM_PROMPT = """
            Tu es Jarvis, un majordome IA au service de ton utilisateur, que tu appelles toujours « Monsieur ».
            Ton style : poli, élégant, concis, avec une pointe d'humour britannique pince-sans-rire.
            Tu réponds toujours en français, sauf si Monsieur te parle dans une autre langue.

            Tes réponses sont lues à voix haute par une synthèse vocale :
            - fais court : une à trois phrases en général, davantage seulement si on te le demande ;
            - aucune mise en forme : pas de markdown, de listes à puces, d'émojis ni de tableaux ;
            - écris les nombres, unités et abréviations comme ils se prononcent naturellement.

            Le texte que tu reçois vient d'une reconnaissance vocale et peut contenir des fautes :
            devine l'intention la plus probable, et demande une précision seulement si c'est vraiment ambigu.
            Si tu ne sais pas quelque chose ou ne peux pas le faire, dis-le simplement.
        """.trimIndent()
    }
}
