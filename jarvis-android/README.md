# Jarvis : assistant vocal IA pour Android

Assistant vocal façon Iron Man, propulsé par Claude (Anthropic). Testé pour un Honor 600 Pro (MagicOS).

## Avancement

| Phase | Contenu | État |
|---|---|---|
| 1 | Conversation vocale (micro → Claude → voix), historique, réglages | ✅ |
| 2 | Assistant par défaut (appui long sur le bouton d'alimentation) | à venir |
| 3 | Outils : alarme, minuteur, agenda, météo, heure, ouvrir une app | à venir |
| 4 | Mémoire (Room) + écran des souvenirs | à venir |
| 5 | Mot d'activation « Jarvis » | à venir |
| 6 | Interface HUD animée | à venir |
| 7 | Voix premium ElevenLabs (optionnel) | à venir |

## Structure du projet

```
jarvis-android/
├── app/build.gradle.kts            ← bibliothèques utilisées, version de l'app
├── app/src/main/AndroidManifest.xml← permissions (Internet, micro)
└── app/src/main/java/com/jarvis/assistant/
    ├── MainActivity.kt             ← point d'entrée, demande du micro
    ├── brain/JarvisBrain.kt        ← dialogue avec Claude + personnalité (prompt système)
    ├── voice/SpeechListener.kt     ← micro → texte
    ├── voice/Speaker.kt            ← texte → voix
    ├── data/SecureStore.kt         ← stockage chiffré des clés API
    ├── data/Settings.kt            ← réglages (clé, modèle)
    └── ui/                         ← écrans (conversation, réglages) et logique d'écran
```

## Installer Jarvis sur le téléphone

### Option A : sans rien installer sur le PC (recommandé pour tester)

Chaque fois que le code change, GitHub compile l'application tout seul.

1. Sur le téléphone, ouvre la page **Releases** du dépôt GitHub, puis la release **« Jarvis (Android) »**.
2. Touche **Jarvis.apk** pour le télécharger.
3. Ouvre le fichier téléchargé. MagicOS te demande d'autoriser l'installation depuis cette source
   (le navigateur ou « Fichiers ») : accepte, puis touche **Installer**.
4. Si un écran « Protection » ou « Analyse de sécurité » s'affiche, choisis **Continuer l'installation**.
   L'app n'est simplement pas publiée sur un store.

Pour les mises à jour, refais la même chose : la nouvelle version s'installe par-dessus l'ancienne.

### Option B : avec Android Studio (pour modifier le code toi-même)

1. **Installer Android Studio** : télécharge-le sur `developer.android.com/studio`, lance l'installateur
   et garde toutes les options par défaut. Au premier lancement, laisse-le télécharger le « SDK Android »
   (quelques Go).
2. **Ouvrir le projet** : *File › Open*, puis choisis le dossier `jarvis-android`. Attends la fin de la
   « Gradle sync » (barre en bas de l'écran, plusieurs minutes la première fois).
3. **Activer le débogage USB sur le Honor** :
   - *Paramètres › À propos du téléphone*, puis touche **7 fois** « Numéro de build ». Entre ton code :
     « Vous êtes maintenant développeur ».
   - *Paramètres › Système et mises à jour › Options pour les développeurs*, puis active
     **Débogage USB**.
   - Branche le téléphone au PC en USB. Choisis le mode **Transfert de fichiers**, puis accepte
     **« Autoriser le débogage USB »** (coche « Toujours autoriser »).
4. **Lancer** : dans Android Studio, le téléphone apparaît en haut à côté du bouton ▶. Clique sur ▶ (Run) :
   l'app est compilée, installée et lancée.

## Premier lancement

1. **Clé API** : crée une clé sur `console.anthropic.com` (*API Keys › Create Key*) et ajoute un peu
   de crédit (*Billing*). Jarvis ouvre les Réglages tout seul au premier lancement : colle la clé et
   touche **Enregistrer**.
2. **Modèle** : `claude-haiku-5-5` par défaut (rapide et très économique). Tu peux mettre
   `claude-sonnet-5-5` pour plus d'intelligence, mais c'est plus cher.
3. Reviens en arrière, touche le **micro**, puis accepte l'accès au micro.

## En cas de problème

| Message | Que faire |
|---|---|
| « Clé API invalide » | Recopie la clé (sans espace) dans les Réglages. |
| « Crédit API épuisé » | Ajoute du crédit sur console.anthropic.com › Billing. |
| « Pas de connexion Internet » | Vérifie le Wi-Fi ou les données mobiles. |
| « Aucun moteur de reconnaissance vocale » | Installe ou mets à jour l'app **Google** depuis le Play Store. |
| Jarvis ne parle pas, ou avec un accent anglais | *Paramètres › Accessibilité › Synthèse vocale* : choisis le moteur **Google**, langue **Français**, et télécharge la voix française. |
| Micro refusé | *Paramètres › Applications › Jarvis › Autorisations › Micro › Autoriser*. |
