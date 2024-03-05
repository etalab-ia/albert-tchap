# SPDX-FileCopyrightText: 2023 Pôle d'Expertise de la Régulation Numérique <contact.peren@finances.gouv.fr>
#
# SPDX-License-Identifier: MIT

import logging
from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PACKAGE_PATH = Path(__file__).resolve().parent
SRC_PATH = PACKAGE_PATH.parent
_ROOT_PATH = PACKAGE_PATH.parent.parent  # Accessible from clone of the project, not from package
DOCUMENTATION_DIR = _ROOT_PATH / "docs"
README_PATH = _ROOT_PATH / "README.md"


class LlmConfig(BaseSettings):
    pre_prompt: str = Field(
        (
            "Je suis une intelligence artificielle basé sur le modèle neural-chat. "
            "Je reste poli avec mes interlocuteurs, et je réponds à la requête suivante du mieux que je peux :"
        ),
        description="preprompt",
    )
    ollama_address: str = Field("http://localhost:11434", description="adresse du serveur ollama")
    model: str = Field("neural-chat", description="modèle à utiliser")
    active: bool = Field(False, description="do we use a llm ?")


class Config(BaseSettings):
    verbose: bool = Field(False, description="Enable / disable verbose logging")
    systemd_logging: bool = Field(True, description="Enable / disable logging with systemd.journal.JournalHandler")
    matrix_home_server: str = Field("https://matrix.agent.finances.tchap.gouv.fr", description="adresse du serveur")
    matrix_bot_username: str = Field("", description="username of our matrix bot")
    matrix_bot_password: str = Field("", description="password of our matrix bot")
    group_used: List[str] = Field(["basic"], description="listes des groupes à utiliser")
    llm: LlmConfig = Field(default_factory=LlmConfig, description="llm configuration")

    model_config = SettingsConfigDict(env_file=Path(".env"))


env_config = Config()


def use_systemd_config():
    if not env_config.systemd_logging:
        return

    from systemd import journal

    # remove the default handler, if already initialized
    existing_handlers = logging.getLogger().handlers
    for handlers in existing_handlers:
        logging.getLogger().removeHandler(handlers)
    # Sending logs to systemd-journal if run via systemd, printing out on console otherwise.
    logging_handler = journal.JournalHandler() if env_config.systemd_logging else logging.StreamHandler()
    logging.getLogger().addHandler(logging_handler)
