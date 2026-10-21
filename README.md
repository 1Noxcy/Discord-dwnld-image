# Discord Images

Télécharge automatiquement sur ton téléphone Android les images que tu reçois
en message privé sur Discord, comme le fait WhatsApp. Les images apparaissent
dans ta galerie, rangées dans un album par conversation
(`Pictures/Discord/<nom de la conversation>/`).

- **Temps réel** : chaque image reçue est enregistrée dès son arrivée.
- **Historique** : récupère aussi les images déjà présentes dans tes conversations.
- **Au choix** : toutes tes conversations privées, ou seulement celles que tu sélectionnes.
- **Lecture seule** : l'outil n'envoie jamais de message et ne modifie rien sur ton compte.

## ⚠️ À savoir avant d'utiliser

Discord ne permet pas aux applications externes de lire tes messages privés.
Cet outil se connecte donc **avec le token de ton propre compte**, comme le fait
l'app Discord. C'est contraire aux conditions d'utilisation de Discord :
le risque est faible pour un usage en lecture seule comme celui-ci, mais
**il existe un risque que ton compte soit suspendu**. Tu l'utilises à tes risques.

Ton token donne un accès complet à ton compte : **ne le partage jamais**, ne
le publie nulle part. Il est enregistré uniquement dans `config.json` sur ton
téléphone (ce fichier est exclu de git).

## Installation (Android)

1. Installe **Termux** et **Termux:API** depuis [F-Droid](https://f-droid.org/)
   (les versions du Play Store sont obsolètes). Installe aussi **Termux:Boot**
   si tu veux que l'outil démarre tout seul quand le téléphone s'allume.
2. Ouvre Termux et tape :

   ```sh
   pkg install -y git
   git clone https://github.com/1Noxcy/Discord-dwnld-image.git
   cd Discord-dwnld-image
   bash scripts/install-termux.sh
   ```

   Accepte la demande d'accès au stockage quand elle apparaît.
3. Lance la configuration :

   ```sh
   python discord_images.py setup
   ```

   Colle ton token, valide le dossier proposé, puis choisis tes conversations.

## Récupérer ton token

Le plus simple est de le faire depuis un ordinateur :

1. Ouvre <https://discord.com/app> dans Chrome ou Firefox et connecte-toi.
2. Appuie sur **F12**, puis va dans l'onglet **Réseau** (Network).
3. Tape `api` dans le filtre, puis clique sur n'importe quelle conversation.
4. Clique sur une des requêtes affichées et, dans **En-têtes de la requête**,
   copie la valeur de `Authorization`. C'est ton token.

Envoie-le-toi d'une façon privée (pas dans un MP Discord !) pour le coller sur
ton téléphone. Le token change si tu te déconnectes ou changes ton mot de
passe : il faudra alors relancer `setup`.

## Utilisation

```sh
python discord_images.py watch                    # télécharge les nouvelles images en continu
python discord_images.py watch --backfill-days 7  # rattrape d'abord les 7 derniers jours
python discord_images.py backfill                 # tout l'historique des conversations suivies
python discord_images.py backfill --days 30       # seulement les 30 derniers jours
python discord_images.py select                   # change les conversations suivies
python discord_images.py dms                      # liste tes conversations (* = suivie)
```

Les images déjà enregistrées ne sont jamais téléchargées deux fois : tu peux
relancer `backfill` autant que tu veux.

### Démarrage automatique

Avec **Termux:Boot** installé, le script d'installation a créé
`~/.termux/boot/discord-images.sh`. Ouvre l'app Termux:Boot une fois, puis
redémarre le téléphone : l'outil tourne en arrière-plan et écrit son journal
dans `~/discord-images.log`.

Pour qu'Android ne le coupe pas, va dans **Paramètres → Applications → Termux →
Batterie** et choisis **Sans restriction** (le nom exact varie selon le téléphone).

## Configuration

Tout est dans `config.json` (créé par `setup`, modèle : `config.example.json`) :

| Option | Défaut | Rôle |
|---|---|---|
| `download_dir` | `/storage/emulated/0/Pictures/Discord` | Dossier où enregistrer les images |
| `channels` | `[]` | Ids des conversations suivies ; vide = toutes |
| `include_group_dms` | `true` | Inclure les groupes privés |
| `include_own_messages` | `false` | Enregistrer aussi les images que tu envoies |
| `include_videos` | `false` | Enregistrer aussi les vidéos |
| `include_embeds` | `true` | Enregistrer les images des liens partagés (aperçus) |
| `subfolder_per_conversation` | `true` | Un album par conversation |
| `media_scan` | `true` | Afficher immédiatement les images dans la galerie (Termux:API) |

Le token peut aussi être fourni via la variable d'environnement `DISCORD_TOKEN`.

## Développement

```sh
pip install -r requirements.txt pytest
python -m pytest
```
