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


## Utilisation

### Utilisation générale

Pour lancer le bot en mode développement :


```bash
./.venv/bin/python3 -m tchap_bot
```

### Utilisation LLM

Pour utiliser le chatbot llm il faut deux choses :
- installer les dépendances [llm] du projet `poetry install --with llm`
- éditer le fichier `.env` pour mettre `llm_active=True`
- faire tourner un serveur Ollama en arrière-plan (cf https://github.com/jmorganca/ollama/blob/main/docs/linux.md)


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
