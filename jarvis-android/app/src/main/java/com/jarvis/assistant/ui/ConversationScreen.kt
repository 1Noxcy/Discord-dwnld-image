package com.jarvis.assistant.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.scale
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.jarvis.assistant.ui.theme.JarvisBackground
import com.jarvis.assistant.ui.theme.JarvisCyan
import com.jarvis.assistant.ui.theme.JarvisError
import com.jarvis.assistant.ui.theme.JarvisOrange
import com.jarvis.assistant.ui.theme.JarvisSurface
import com.jarvis.assistant.ui.theme.JarvisText

/** Écran principal : historique de la conversation + gros bouton micro. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ConversationScreen(
    state: UiState,
    onMicClick: () -> Unit,
    onNewConversation: () -> Unit,
    onOpenSettings: () -> Unit,
) {
    Scaffold(
        containerColor = JarvisBackground,
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        "J.A.R.V.I.S.",
                        fontFamily = FontFamily.Monospace,
                        fontWeight = FontWeight.Bold,
                        letterSpacing = 4.sp,
                        color = JarvisCyan,
                    )
                },
                actions = {
                    IconButton(onClick = onNewConversation) {
                        Icon(Icons.Default.Refresh, contentDescription = "Nouvelle conversation", tint = JarvisText)
                    }
                    IconButton(onClick = onOpenSettings) {
                        Icon(Icons.Default.Settings, contentDescription = "Réglages", tint = JarvisText)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = JarvisBackground),
            )
        },
    ) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            ChatHistory(state.lines, Modifier.weight(1f))
            BottomPanel(state, onMicClick)
        }
    }
}

@Composable
private fun ChatHistory(lines: List<ChatLine>, modifier: Modifier) {
    val listState = rememberLazyListState()
    // Défile automatiquement vers le dernier message.
    LaunchedEffect(lines.size) {
        if (lines.isNotEmpty()) listState.animateScrollToItem(lines.lastIndex)
    }

    if (lines.isEmpty()) {
        Box(modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
            Text(
                "À votre service, Monsieur.\nAppuyez sur le micro pour parler.",
                color = JarvisText.copy(alpha = 0.6f),
                fontFamily = FontFamily.Monospace,
            )
        }
        return
    }

    LazyColumn(
        modifier.fillMaxWidth(),
        state = listState,
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        items(lines) { line -> ChatBubble(line) }
    }
}

@Composable
private fun ChatBubble(line: ChatLine) {
    val accent = when {
        line.isError -> JarvisError
        line.fromUser -> JarvisOrange
        else -> JarvisCyan
    }
    Row(
        Modifier.fillMaxWidth(),
        horizontalArrangement = if (line.fromUser) Arrangement.End else Arrangement.Start,
    ) {
        Column(
            Modifier
                .widthIn(max = 300.dp)
                .background(JarvisSurface, RoundedCornerShape(12.dp))
                .padding(12.dp)
        ) {
            Text(
                if (line.fromUser) "VOUS" else "JARVIS",
                color = accent,
                fontSize = 11.sp,
                fontFamily = FontFamily.Monospace,
                letterSpacing = 2.sp,
            )
            Spacer(Modifier.height(4.dp))
            Text(line.text, color = JarvisText)
        }
    }
}

@Composable
private fun BottomPanel(state: UiState, onMicClick: () -> Unit) {
    Column(
        Modifier
            .fillMaxWidth()
            .padding(bottom = 24.dp, top = 8.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        // Texte en direct pendant l'écoute
        if (state.partialText.isNotEmpty()) {
            Text(
                "« ${state.partialText} »",
                color = JarvisOrange,
                fontStyle = FontStyle.Italic,
                modifier = Modifier.padding(horizontal = 24.dp, vertical = 8.dp),
            )
        }

        Text(
            statusLabel(state.status),
            color = JarvisCyan.copy(alpha = 0.8f),
            fontFamily = FontFamily.Monospace,
            fontSize = 12.sp,
            letterSpacing = 3.sp,
        )
        Spacer(Modifier.height(12.dp))

        val listening = state.status == JarvisStatus.LISTENING
        FloatingActionButton(
            onClick = onMicClick,
            containerColor = if (listening) JarvisOrange else JarvisCyan,
            contentColor = JarvisBackground,
            modifier = Modifier
                .size(76.dp)
                // Le bouton "respire" avec le volume de la voix pendant l'écoute.
                .scale(if (listening) 1f + state.voiceLevel * 0.25f else 1f),
        ) {
            Icon(
                if (listening) Icons.Default.Stop else Icons.Default.Mic,
                contentDescription = if (listening) "Arrêter l'écoute" else "Parler à Jarvis",
                modifier = Modifier.size(36.dp),
            )
        }
    }
}

private fun statusLabel(status: JarvisStatus) = when (status) {
    JarvisStatus.IDLE -> "EN ATTENTE"
    JarvisStatus.LISTENING -> "ÉCOUTE…"
    JarvisStatus.THINKING -> "RÉFLEXION…"
    JarvisStatus.SPEAKING -> "RÉPONSE"
}
