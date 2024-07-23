# SPDX-FileCopyrightText: 2023 Pôle d'Expertise de la Régulation Numérique <contact.peren@finances.gouv.fr>
# SPDX-FileCopyrightText: 2024 Etalab <etalab@modernisation.gouv.fr>
#
# SPDX-License-Identifier: MIT

import logging
import time
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from _version import __version__

COMMAND_PREFIX = "!"

APP_VERSION = __version__


class BaseConfig(BaseSettings):
    # allows us to clean up the imports into multiple parts
    # https://stackoverflow.com/questions/77328900/nested-settings-with-pydantic-settings
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent / ".env", extra="ignore"
    )  # allows nested configs


class Config(BaseConfig):
    # General
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

    # Grist Api Key
    grist_api_server: str = Field("", description="Grist Api Server")
    grist_api_key: str = Field("", description="Grist API Key")
    grist_users_table_id: str = Field("", description="Grist Users doc ID")
    grist_users_table_name: str = Field("", description="Grist Users table name/ID")

    # Albert API settings
    albert_api_url: str = Field("http://localhost:8090", description="Albert API base URL")
    albert_api_token: str = Field("", description="Albert API Token")

    # Albert Conversation settings
    # ============================
    # PER USER SETTINGS !
    # ============================
    albert_model: str = Field(
        "AgentPublic/albertlight-7b",
        description="Albert model name to use (see Albert models hub on HuggingFace)",
    )
    albert_mode: str = Field("rag", description="Albert API mode")
    albert_with_history: bool = Field(True, description="Conversational mode")
    albert_history_lookup: int = Field(0, description="How far we lookup in the history")
    albert_max_rewind: int = Field(20, description="Max history rewind for stability purposes")
    conversation_obsolescence: int = Field(
        15 * 60, description="time after which a conversation is considered obsolete, in seconds"
    )
    last_rag_references: list[dict] | None = Field(None, description="Last sources used for the RAG.")

    @property
    def is_conversation_obsolete(self) -> bool:
        return int(time.time()) - self.last_activity > self.conversation_obsolescence

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
