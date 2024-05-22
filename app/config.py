# SPDX-FileCopyrightText: 2023 Pôle d'Expertise de la Régulation Numérique <contact.peren@finances.gouv.fr>
# SPDX-FileCopyrightText: 2024 Etalab <etalab@modernisation.gouv.fr>
#
# SPDX-License-Identifier: MIT

import logging
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PACKAGE_PATH = Path(__file__).resolve().parent
SRC_PATH = PACKAGE_PATH.parent
_ROOT_PATH = PACKAGE_PATH.parent.parent  # Accessible from clone of the project, not from package
DOCUMENTATION_DIR = _ROOT_PATH / "docs"
README_PATH = _ROOT_PATH / "README.md"

COMMAND_PREFIX = "!"


class BaseConfig(BaseSettings):
    # allows us to clean up the imports into multiple parts
    # https://stackoverflow.com/questions/77328900/nested-settings-with-pydantic-settings
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent / ".env", extra="ignore"
    )  # allows nested configs


class Config(BaseConfig):
    verbose: bool = Field(False, description="Enable / disable verbose logging")
    systemd_logging: bool = Field(
        True, description="Enable / disable logging with systemd.journal.JournalHandler"
    )
    matrix_home_server: str = Field("", description="Tchap home server URL")
    matrix_bot_username: str = Field("", description="Username of our matrix bot")
    matrix_bot_password: str = Field("", description="Password of our matrix bot")
    errors_room_id: str | None = Field(None, description="Room ID to send errors to")
    user_allowed_domains: list[str] = Field(
        [], description="List of allowed Tchap users email domains allowed to use Albert Tchap bot"
    )
    groups_used: list[str] = Field(["basic"], description="List of commands groups to use")
    # Albert API settings
    albert_api_url: str = Field("http://localhost:8090/api/v2", description="Albert API base URL")
    albert_api_token: str = Field("", description="Albert API Token")
    albert_model_name: str = Field(
        "AgentPublic/albertlight-7b",
        description="Albert model name to use (see Albert models hub on HuggingFace)",
    )
    albert_mode: str = Field("rag", description="Albert API mode")
    ## Albert Conversational settings
    albert_with_history: bool = Field(True, description="Conversational mode")
    albert_chat_id: int | None = Field(None, description="Current chat id")
    albert_stream_id: int | None = Field(None, description="Current stream id")


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
    logging_handler = (
        journal.JournalHandler() if env_config.systemd_logging else logging.StreamHandler()
    )
    logging.getLogger().addHandler(logging_handler)
