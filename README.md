<!--
SPDX-FileCopyrightText: 2023 Pôle d'Expertise de la Régulation Numérique <contact.peren@finances.gouv.fr>

SPDX-License-Identifier: MIT
-->

Bot Tchap
=========

La partie bibliothèque (`matrix_bot`) est fortement inspirée de https://github.com/imbev/simplematrixbotlib


## Description

Contient :
- `matrix_bot` : une bibliothèque pour pouvoir faire des bots matrix
- `tchap_bot` : un applicatif contenant quelques fonctionnalités de bots utiles


## Installation


### Avec pip

```bash
pip install tchap-bot --index-url https://code.peren.fr/api/v4/projects/[package_index]/packages/pypi/simple
```


### En local

```bash
# Récupération du code avec Git
git clone ${GITLAB_URL}
cd tchap_bot

# Création d'un virtualenv et installation des dépendances requises
python3 -m venv .venv


# Installation des dépendances via poetry.
poetry install
```

### Configuration

Créer le fichier .env avec les informations de connexion (ou fournissez-les en variables d'environnement)
Vous pouvez vous inspirer du fichier `.dev.env` qui est initialisé avec les valeurs par défaut 

```bash
cp .dev.env .venv
```


## Utilisation tchap_bot

### Utilisation générale

Pour lancer le bot en mode développement :


```bash
./.venv/bin/python3 -m tchap_bot
```

### Utilisation LLM

Pour utiliser le chatbot llm il faut deux choses :
- installer les dépendances [llm] du projet `poetry install --with llm`
- éditer le fichier `.env` pour mettre `llm_active=True` et `group_used=['chatbot']`
- faire tourner un serveur Ollama en arrière-plan (cf https://github.com/jmorganca/ollama/blob/main/docs/linux.md)


## Utilisation matrix_bot

Il faut initialiser un matrixbot et le faire tourner. Un exemple très simple pour avoir une commande qui donne l'heure  :

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
