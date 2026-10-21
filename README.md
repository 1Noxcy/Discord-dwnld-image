# Discord Images

Petite application pour enregistrer d'un coup toutes les images de tes
conversations privées Discord dans un dossier.

- Tu choisis les conversations (MP et groupes privés).
- Tu peux limiter à une période (du … au …).
- Les images avec **spoiler** sont incluses (enregistrées sans le préfixe `SPOILER_`).
- Options : un sous-dossier par conversation, tes propres images, les vidéos,
  les images des liens partagés.
- Une image déjà enregistrée n'est jamais téléchargée deux fois.
- Lecture seule : l'application n'envoie jamais de message.

## ⚠️ À savoir avant d'utiliser

Discord ne permet pas aux applications externes de lire tes messages privés.
L'application se connecte donc **avec le token de ton propre compte**. C'est
contraire aux conditions d'utilisation de Discord : le risque est faible pour
un usage en lecture seule, mais **ton compte pourrait être suspendu**. Tu
l'utilises à tes risques.

Ton token donne un accès complet à ton compte : **ne le partage jamais**. Si
tu coches « Se souvenir du token », il est enregistré uniquement sur ton
ordinateur, dans le fichier `.discord_images.json` de ton dossier utilisateur.
En cas de doute, change ton mot de passe Discord : l'ancien token cesse
immédiatement de fonctionner.

## Installation (Windows)

1. Télécharge **`DiscordImages.exe`** depuis la page
   [Releases](https://github.com/1Noxcy/Discord-dwnld-image/releases/tag/latest).
2. Double-clique dessus. Si Windows affiche « Windows a protégé votre
   ordinateur », clique sur **Informations complémentaires** puis **Exécuter
   quand même** (l'application n'est pas signée, c'est normal).

Sur macOS ou Linux : installe Python 3, puis `pip install requests` et
`python discord_images.py`.

## Récupérer ton token

1. Ouvre <https://discord.com/app> dans ton navigateur (Chrome, Firefox,
   Opera GX…) sur ton ordinateur et connecte-toi.
2. Ouvre les outils de développement : **Ctrl + Maj + I**, ou clic droit →
   **Inspecter**. Va dans l'onglet **Réseau** (Network).
3. Tape `messages` dans le filtre, puis clique sur une conversation.
4. Clique sur la ligne `messages?limit=…` et, dans **En-têtes** → **En-têtes
   de requête**, copie la valeur de `authorization`.

## Utilisation

1. Colle ton token et clique sur **Se connecter**.
2. Clique sur les conversations voulues (elles passent en bleu), ou sur **Tout**.
3. Si tu veux, indique une période (format `JJ/MM/AAAA`) et choisis le dossier.
4. Clique sur **Télécharger**. Les fichiers sont nommés
   `date_heure_identifiant_nom.ext`, donc triés par date.

## Développement

```sh
pip install -r requirements.txt pytest
python -m pytest
```
