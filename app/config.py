# SPDX-FileCopyrightText: 2023 Pôle d'Expertise de la Régulation Numérique <contact.peren@finances.gouv.fr>
# SPDX-FileCopyrightText: 2024 Etalab <etalab@modernisation.gouv.fr>
#
# SPDX-License-Identifier: MIT

import logging
import time
import tomllib
from pathlib import Path

from matrix_bot.config import bot_lib_config
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

COMMAND_PREFIX = "!"

APP_VERSION = "unknown"
try:
    with open("pyproject.toml", "rb") as f:
        pyproject: dict = tomllib.load(f)
        APP_VERSION = pyproject["project"]["version"]
except Exception as e:
    logging.warning(f"Error while reading pyproject.toml: {e}")


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
        ["*"],
        description="List of allowed Tchap users email domains allowed to use Albert Tchap",
    )
    groups_used: list[str] = Field(["basic"], description="List of commands groups to use")
    last_activity: int = Field(int(time.time()), description="Last activity timestamp")
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
    albert_history_lookup: int = Field(0, description="How far we lookup in the history")
    albert_max_rewind: int = Field(20, description="Max history rewind for stability purposes")

    @property
    def is_conversation_obsolete(self) -> bool:
        return int(time.time()) - self.last_activity > bot_lib_config.conversation_obsolescence

    def update_last_activity(self) -> None:
        self.last_activity = int(time.time())


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
