<!--
SPDX-FileCopyrightText: 2023 Pôle d'Expertise de la Régulation Numérique <contact.peren@finances.gouv.fr>
SPDX-FileCopyrightText: 2024 Etalab/Datalab <etalab@modernisation.gouv.fr>

SPDX-License-Identifier: MIT
-->

# Albert Tchap Bot

Le projet est un fork de [tchap_bot](https://gitlab.incubateur.net/PEREN/tchap_bot) qui est un bot matrix pour Tchap, conçu par le [Pôle d'Expertise de la Régulation Numérique](https://gitlab.incubateur.net/PEREN).

La partie bibliothèque (`matrix_bot`) est fortement inspirée de https://github.com/imbev/simplematrixbotlib.


## Description

Contient :
- `app/.` : la codebase pour le Tchap bot Albert
- `app/matrix_bot` : une bibliothèque pour pouvoir faire des bots Matrix


## Installation locale

Le projet utilise un fichier de dépendances et de config `pyproject.toml` et non un fichier `requirements.txt`. Il est donc nécessaire d'utiliser `pip` en version 19.0 ou supérieure, ou bien avec un package manager comme `pdm`, `pip-tools`, `uv`, `rye`, `hatch` etc. (mais pas `poetry` qui n'utilise pas le standard `pyproject.toml`).

```bash
# Récupération du code avec Git
git clone ${GIHUB_URL}

# Création d'un virtualenv
python3 -m venv .venv

# Installation des dépendances
pip install .
```

### Configuration

Créez le fichier .env avec les informations de connexion (ou fournissez-les en variables d'environnement).
Vous pouvez vous inspirer du fichier `app/.env.example` qui est initialisé avec les valeurs par défaut 

```bash
cp app/.env.example app/.env
```

Il est conseillé de changer la valeur du sel (`salt`) pour ne pas avoir celle par défaut. Il faudra en revanche qu'elle de change pas entre deux sessions.


## Utilisation tchap_bot

### Utilisation générale

Pour lancer le bot en mode développement :


```bash
./.venv/bin/python3 .
```

### Utilisation d'Albert

Pour utiliser le chatbot Albert il faut éditer le fichier `.env` pour mettre :
- `albert_api_url`: l'url de l'API Albert à consommer.
- `albert_api_token`: le token API utilisé pour authorisé le bot a consommer l'API Albert.
- `groups_used=['albert']`: permet d'activer toutes les commandes qui font partie du groupe albert.


## Utilisation matrix_bot

Il faut initialiser un matrixbot et le faire tourner. Un exemple très simple pour avoir une commande qui donne l'heure :

```python
import datetime

from nio import MatrixRoom, Event

from matrix_bot.bot import MatrixBot
from matrix_bot.client import MatrixClient
from matrix_bot.callbacks import properly_fail
from matrix_bot.eventparser import MessageEventParser, ignore_when_not_concerned


# le décorateur @properly_fail va permettre à la commande de laisser un message d'erreur si la commande plante et
# d'envoyer le message que le bot n'est plus en train d'écrire
# la fonction va être appelée dans tous les cas, le décorateur @ignore_when_not_concerned 
# permet de laisser event_parser gérer le cas où la commande n'est pas concernée
@properly_fail
@ignore_when_not_concerned
async def heure(room: MatrixRoom, message: Event, matrix_client: MatrixClient):
    # on initialise un event_parser pour décider à quel message cette commande va répondre
    event_parser = MessageEventParser(room=room, event=message, matrix_client=matrix_client)
    # il ne va pas répondre à ses propres messages
    event_parser.do_not_accept_own_message()
    # il ne va répondre qu'au message "!heure"
    event_parser.command("heure")
    heure = f"il est {datetime.datetime.now().strftime('%Hh%M')}"
    # ile envoie l'information qu'il est en train d'écrire
    await matrix_client.room_typing(room.room_id)
    # il envoie le message
    await matrix_client.send_text_message(room.room_id, heure)


tchap_bot = MatrixBot(matrix_home_server, matrix_bot_username, matrix_bot_password)
tchap_bot.callbacks.register_on_message_event(heure, tchap_bot.matrix_client)
tchap_bot.run()
```

D'autres exemples plus complexes sont disponibles dans tchap_bot


## Troubleshooting

Le premier sync est assez long, et a priori non bloquant. Si vous avez une interaction avec le bot avant qu'il se soit bien sync vous risquez de le laisser dans un état instable (où le bot n'a pas le listing des rooms) 

## Contribution


Avant de contribuer au dépôt, il est nécessaire d'initialiser les _hooks_ de _pre-commit_ :

```bash
pre-commit install
```


## Licence

Ce projet est sous licence MIT. Une copie intégrale du texte
de la licence se trouve dans le fichier [`LICENSES/MIT.txt`](LICENSES/MIT.txt).
