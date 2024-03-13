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

    timeout: int = Field(65_536, description="Timeout for event ?")
    join_on_invite: bool = Field(False, description="Do the bot automatically join when invited")
    encryption_enabled: bool = Field(ENCRYPTION_ENABLED)
    ignore_unverified_devices: bool = Field(True, description="True by default in Element")
    store_path: str = Field("./store/", description="path in which matrix-nio store will be written")
    log_level: int = Field(logging.INFO, description="log level for the library")

    model_config = SettingsConfigDict(env_file=Path(".matrix_bot_env"))


bolt_lib_config = BotLibConfig()
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(bolt_lib_config.log_level),
)
logger = structlog.get_logger("Matrix bot")
logger.info("starting the bot")
