<!--
SPDX-FileCopyrightText: 2023 Pôle d'Expertise de la Régulation Numérique <contact.peren@finances.gouv.fr>

SPDX-License-Identifier: MIT
-->

tchap_bot
=========

La partie bibliothèque (`matrix_bot`) est fortement inspirée de https://github.com/imbev/simplematrixbotlib


## Description

Contient :
- `matrix_bot` : une bibliothèque pour pouvoir faire des bots matrix
- `tchap_bot` : un applicatif contenant des fonctionnalités de bots utiles


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



## Utilisation


### Utilisation générale

Pour lancer le bot en mode développement :

Créer le fichier .env avec les informations de connexion (ou fournissez-les en variables d'environnement)
```python
matrix_home_server="[home server]"
matrix_bot_username="[username]"
matrix_bot_password="[pasword]"
group_used=["basic", "room_utils"]
```

```bash
./.venv/bin/python3 -m tchap_bot
```

### Utilisation LLM

Pour utiliser le chatbot llm il faut deux choses :
- installer les dépendances [llm] du projet `poetry install --with llm`
- rajouter la variable `use_llm=True` au `.env`
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
