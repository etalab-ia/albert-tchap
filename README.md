<!--
SPDX-FileCopyrightText: 2023 Pôle d'Expertise de la Régulation Numérique <contact.peren@finances.gouv.fr>
SPDX-FileCopyrightText: 2024 Etalab <etalab@modernisation.gouv.fr>

SPDX-License-Identifier: MIT
-->

# Albert Tchap

*[English version below](#english-version)*

| <a href="https://github.com/etalab-ia/albert"><b>Albert API sur GitHub</b></a> | <a href="https://huggingface.co/AgentPublic"><b>Modèles Albert sur HuggingFace</b></a> |

## Description du projet

Bot pour [Tchap, l'application de messagerie de l'administration française](https://tchap.beta.gouv.fr/).
Ce bot utilise [Albert](https://github.com/etalab-ia/albert), l'agent conversationnel (*large language models*, LLM) de l'administration française, pour répondre à des questions sur [Tchap, l'application de messagerie de l'administration française](https://tchap.beta.gouv.fr/).

Le projet est un POC (Proof of Concept - preuve de concept) pour montrer comment un bot peut être utilisé pour répondre à des questions sur Tchap en utilisant Albert.
Il s'agit d'un travail WIP (Work In Progress - en cours de développement) et n'est pas (encore) destiné à être utilisé en production.

Le projet est un fork de [tchap_bot](https://code.peren.fr/open-source/tchapbot) qui est un bot Matrix pour Tchap, conçu par le [Pôle d'Expertise de la Régulation Numérique](https://www.peren.gouv.fr/). La partie bibliothèque (`matrix_bot`) est fortement inspirée de https://github.com/imbev/simplematrixbotlib.

Contient :
- `app/.` : la codebase pour le Tchap bot Albert
- `app/matrix_bot` : une bibliothèque qui encapsule [matrix-nio](https://github.com/matrix-nio/matrix-nio) faire des bots Matrix


### Installation locale

Le projet utilise un fichier de dépendances et de config `pyproject.toml` et non un fichier `requirements.txt`. Il est donc nécessaire d'utiliser `pip` en version 19.0 ou supérieure, ou bien avec un package manager comme `pdm`, `pip-tools`, `uv`, `rye`, `hatch` etc. (mais pas `poetry` qui n'utilise pas le standard `pyproject.toml`).

```bash
# Récupération du code avec Git
git clone ${GITHUB_URL}

# Création d'un environnement virtuel Python
python3 -m venv .venv

# Activation de l'environnement virtuel Python
source .venv/bin/activate

# Installation des dépendances
pip install .
```


### Configuration

Créez le fichier d'environnement `app/.env` avec les informations de connexion (ou fournissez-les en variables d'environnement). Vous pouvez vous inspirer du fichier `app/.env.example` qui est initialisé avec les valeurs par défaut :
```bash
cp app/.env.example app/.env
```

L'ensemble des variables d'environements disponibles est documenté dans le fichier suivant : [app/config.py](./app/config.py)


### Lancer le bot

Pour lancer le bot executez :
```bash
python app
```

#### NOTE 1

Cette commande stoppera surement si vous ne la lancez pas en mode sudo car
elle installe par défault le data/store et le data/session.txt à la racine "/".
Vous pouvez lancer l'application pour qu'elle crée ces fichiers dans le dossier du projet directement avec la commande :

```bash
export STORE_PATH='./data/store/' && export SESSION_PATH='./data/session.txt' && python app
```

#### NOTE 2

Si vous voulez développez tout en faisant que le bot reload automatiquement, vous pouvez utiliser par exemple [nodemon](https://github.com/python-nodemon/nodemon) en module global python et lancer la commande suivante dans un terminal :

```bash
nodemon --watch app --ext py --exec "export STORE_PATH='./data/store/' && export SESSION_PATH='./data/session.txt' && python app"
```

#### NOTE 3

Si vous voulez que vos messages engendrés par le bot se distinguent des autres messages, possiblement envoyé par d'autres bots (comme celui de staging):

```bash
nodemon --watch app --ext py --exec "export MESSAGE_PREFIX='[DEV]' && export STORE_PATH='./data/store/' && export SESSION_PATH='./data/session.txt' && python app"
```

#### NOTE 4

Si vous voulez merger votre branche de dev pour la tester sur beta.tchap (branche staging) :

```bash
git checkout staging
git merge <your-branch>
git push origin staging
```

### Troubleshooting

Le premier sync est assez long, et a priori non bloquant. Si vous avez une interaction avec le bot avant qu'il se soit bien sync vous risquez de le laisser dans un état instable (où le bot n'a pas le listing des rooms).


### Contribution

Le projet est en open source, sous [licence MIT](LICENSES/MIT.txt). Toutes les contributions sont bienvenues, sous forme de pull requests ou d'ouvertures d'issues sur le [repo officiel GitHub](https://github.com/etalab-ia/albert-tchapbot).

Pour commencer, consultez [CONTRIBUTING.md](CONTRIBUTING.md).


### Licence

Ce projet est sous licence MIT. Une copie intégrale du texte de la licence se trouve dans le fichier [`LICENSES/MIT.txt`](LICENSES/MIT.txt).


---

# English version

<details>
  <summary>English version</summary>


| <a href="https://github.com/etalab-ia/albert"><b>Albert API on GitHub</b></a> | <a href="https://huggingface.co/AgentPublic"><b>Albert models on HuggingFace</b></a> |

## Project Description

Bot for [Tchap, the French government messaging application](https://tchap.beta.gouv.fr/).
This bot uses [Albert](https://github.com/etalab-ia/albert), the conversational agent (large language models, LLM) of the French government, to answer questions about [Tchap](https://tchap.beta.gouv.fr/).

The project is a Proof of Concept (POC) to show how a bot can be used to answer questions about Tchap using Albert.
It is a Work In Progress (WIP) and is not (yet) intended for production use.

The project is a fork of [tchap_bot](https://code.peren.fr/open-source/tchapbot) which is a Matrix bot for Tchap, designed by the [Pôle d'Expertise de la Régulation Numérique](https://www.peren.gouv.fr/). The library part (`matrix_bot`) is heavily inspired by https://github.com/imbev/simplematrixbotlib.

Contains:
- `app/.`: the codebase for the Albert Tchap bot
- `app/matrix_bot`: a library that wraps [matrix-nio](https://github.com/matrix-nio/matrix-nio) to make Matrix bots


### Local Installation

The project uses a dependencies and config file `pyproject.toml` and not a `requirements.txt` file. It is therefore necessary to use `pip` in version 19.0 or higher, or with a package manager like `pdm`, `pip-tools`, `uv`, `rye`, `hatch` etc. (but not `poetry` which does not use the standard `pyproject.toml`).

```bash
# Getting the code with Git
git clone ${GITHUB_URL}

# Creating a Python virtual environment
python3 -m venv .venv

# Activating the Python virtual environment
source .venv/bin/activate

# Installing dependencies
pip install .
```

### Configuration

Create the environment file `app/.env` with the connection information (or provide them as environment variables). You can use the `app/.env.example` file as inspiration, which is initialized with default values:
```bash
cp app/.env.example app/.env
```

The set of available environment variables is documented in the following file: [app/config.py](./app/config.py)

### Run the bot

To launch the bot:
```bash
python app
```


### Troubleshooting

The first sync is quite long, and apparently non-blocking. If you interact with the bot before it has synced properly, you risk leaving it in an unstable state (where the bot does not have the room listing).

### Contribution

This project is open source, under the [MIT license](LICENSES/MIT.txt). All contributions are welcome, in the form of pull requests or issue openings on the [repo officiel GitHub](https://github.com/etalab-ia/albert-tchapbot).

To get started, take a look at [CONTRIBUTING.md](CONTRIBUTING.md).

### License

This project is licensed under the MIT License. A full copy of the license text can be found in the `LICENSES/MIT.txt` file.

</details>
