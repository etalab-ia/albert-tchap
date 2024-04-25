# SPDX-FileCopyrightText: 2023 Pôle d'Expertise de la Régulation Numérique <contact.peren@finances.gouv.fr>
#
# SPDX-License-Identifier: MIT
import logging
from pathlib import Path

import structlog
from nio.crypto import ENCRYPTION_ENABLED
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BotLibConfig(BaseSettings):
    """
    A class to handle built-in user-configurable settings, including support for saving to and loading from a file.
    Can be inherited from by bot developers to implement custom settings.
    """

    timeout: int = Field(
        default=60_000,
        description="The maximum time that the server should wait for new events before "
        "it should return the request anyways, in milliseconds",
    )
    join_on_invite: bool = Field(default=False, description="Do the bot automatically join when invited")
    encryption_enabled: bool = Field(default=ENCRYPTION_ENABLED)
    ignore_unverified_devices: bool = Field(default=True, description="True by default in Element")
    store_path: Path = Field(default="./store/", description="path in which matrix-nio store will be written")
    session_path: Path = Field(default="/data/session.txt", description="path of the file to store session identifier")
    log_level: int = Field(default=logging.INFO, description="log level for the library")
    salt: bytes = Field(
        default=b"\xce,\xa1\xc6lY\x80\xe3X}\x91\xa60m\xa8N",
        description="Salt to store your session credentials. Should not change between two runs",
    )

    model_config = SettingsConfigDict(env_file=Path(".matrix_bot_env"))


bot_lib_config = BotLibConfig(join_on_invite=True)
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(bot_lib_config.log_level),
)
logger = structlog.get_logger("Matrix bot")
logger.info("starting the bot")
