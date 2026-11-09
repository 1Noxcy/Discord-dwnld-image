package com.jarvis.assistant.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material.icons.filled.VisibilityOff
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import com.jarvis.assistant.data.Settings
import com.jarvis.assistant.ui.theme.JarvisBackground
import com.jarvis.assistant.ui.theme.JarvisCyan
import com.jarvis.assistant.ui.theme.JarvisText

/** Écran Réglages : clé API (stockée chiffrée) et nom du modèle. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(settings: Settings, onBack: () -> Unit) {
    var apiKey by remember { mutableStateOf(settings.anthropicApiKey) }
    var model by remember { mutableStateOf(settings.model) }
    var showKey by remember { mutableStateOf(false) }
    var saved by remember { mutableStateOf(false) }

    Scaffold(
        containerColor = JarvisBackground,
        topBar = {
            TopAppBar(
                title = { Text("Réglages", color = JarvisText) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Retour", tint = JarvisText)
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
                .padding(16.dp)
                .verticalScroll(rememberScrollState())
        ) {
            Text("Clé API Anthropic", color = JarvisCyan)
            Text(
                "Créez-la sur console.anthropic.com › API Keys. Elle commence par « sk-ant- ». " +
                    "Elle est chiffrée sur ce téléphone et n'est envoyée qu'à Anthropic.",
                color = JarvisText.copy(alpha = 0.7f),
            )
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(
                value = apiKey,
                onValueChange = { apiKey = it; saved = false },
                label = { Text("sk-ant-…") },
                singleLine = true,
                visualTransformation = if (showKey) VisualTransformation.None else PasswordVisualTransformation(),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                trailingIcon = {
                    IconButton(onClick = { showKey = !showKey }) {
                        Icon(
                            if (showKey) Icons.Default.VisibilityOff else Icons.Default.Visibility,
                            contentDescription = if (showKey) "Masquer" else "Afficher",
                        )
                    }
                },
                modifier = Modifier.fillMaxWidth(),
            )

            Spacer(Modifier.height(24.dp))
            Text("Modèle Claude", color = JarvisCyan)
            Text(
                "Par défaut : ${Settings.DEFAULT_MODEL} (rapide et économique). " +
                    "Pour plus d'intelligence : claude-sonnet-5-5.",
                color = JarvisText.copy(alpha = 0.7f),
            )
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(
                value = model,
                onValueChange = { model = it; saved = false },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            TextButton(onClick = { model = Settings.DEFAULT_MODEL; saved = false }) {
                Text("Revenir au modèle par défaut")
            }

            Spacer(Modifier.height(24.dp))
            Button(
                onClick = {
                    settings.anthropicApiKey = apiKey
                    settings.model = model
                    saved = true
                },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(if (saved) "Enregistré ✓" else "Enregistrer")
            }
        }
    }
}
