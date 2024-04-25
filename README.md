<!--
SPDX-FileCopyrightText: 2023 Pôle d'Expertise de la Régulation Numérique <contact.peren@finances.gouv.fr>
SPDX-FileCopyrightText: 2024 Etalab/Datalab <etalab@modernisation.gouv.fr>

SPDX-License-Identifier: MIT
-->

# Albert Tchap Bot

Bot pour Tchap, l'application de messagerie de l'administration française.
Ce bot utilise Albert, l'agent conversationnel (*large language models*, LLM) de l'administration française, pour répondre à des questions sur Tchap.

Le projet est un POC (Proof of Concept - preuve de concept) pour montrer comment un bot peut être utilisé pour répondre à des questions sur Tchap en utilisant Albert.
Il s'agit d'un travail WIP (Work In Progress - en cours de développement) et n'est pas (encore) destiné à être utilisé en production.

Le projet est un fork de [tchap_bot](https://gitlab.incubateur.net/PEREN/tchap_bot) qui est un bot Matrix pour Tchap, conçu par le [Pôle d'Expertise de la Régulation Numérique](https://gitlab.incubateur.net/PEREN). La partie bibliothèque (`matrix_bot`) est fortement inspirée de https://github.com/imbev/simplematrixbotlib.


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

## Configuration

Créez le fichier .env avec les informations de connexion (ou fournissez-les en variables d'environnement).
Vous pouvez vous inspirer du fichier `app/.env.example` qui est initialisé avec les valeurs par défaut 

```bash
cp app/.env.example app/.env
```

Il est conseillé de changer la valeur du sel (`salt`) pour ne pas avoir celle par défaut. Il faudra en revanche qu'elle de change pas entre deux sessions.

Pour que le bot se connecte à l'API d'Albert, il faut renseigner les variables suivantes :
- `albert_api_url` : l'url de l'API Albert à consommer.
- `albert_api_token` : le token API utilisé pour authorisé le bot a consommer l'API Albert.
- `groups_used=['albert']` : permet d'activer toutes les commandes qui font partie du groupe albert.


## Utilisation en dehors de Docker

Pour lancer le bot en dehors de Docker :
```bash
cd app
./.venv/bin/python3 .
```


## Utilisation avec Docker

1. Créez un fichier .env à la racine du projet avec les variables d'environnement mentionnées dans la section *"For docker-compose deployment"* du fichier [.env.example](./.env.example)
   
2. Lancer le container du bot à la racine du projet
   
    ```bash
    docker compose .env up --detach
    ```


## Utilisation de la librairie `matrix_bot`

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


## Troubleshooting

Le premier sync est assez long, et a priori non bloquant. Si vous avez une interaction avec le bot avant qu'il se soit bien sync vous risquez de le laisser dans un état instable (où le bot n'a pas le listing des rooms).


## Contribution

Avant de contribuer au dépôt, il est nécessaire de formatter, linter et trier les imports avec [Ruff](https://docs.astral.sh/ruff/) :
```bash
ruff check --fix --select I .
```


## Licence

Ce projet est sous licence MIT. Une copie intégrale du texte
de la licence se trouve dans le fichier [`LICENSES/MIT.txt`](LICENSES/MIT.txt).
