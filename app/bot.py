# SPDX-FileCopyrightText: 2023 Pôle d'Expertise de la Régulation Numérique <contact.peren@finances.gouv.fr>
# SPDX-FileCopyrightText: 2024 Etalab/Datalab <etalab@modernisation.gouv.fr>
#
# SPDX-License-Identifier: MIT

from commands import command_registry
from config import env_config
from matrix_bot.bot import MatrixBot
from matrix_bot.config import logger

# TODO:
# - catch unknow command ?
# - add dropup with all available commands like when using "/" ?
# - if albert-bot is invited in a salon, make it answer only it is tagged.

def main():
    tchap_bot = MatrixBot(
        env_config.matrix_home_server,
        env_config.matrix_bot_username,
        env_config.matrix_bot_password,
    )
    for callback in [
        feature
        for feature_group in env_config.groups_used
        for feature in command_registry.activate_and_retrieve_group(feature_group)
    ]:
        logger.info("loaded feature", feature=callback.__name__)
        tchap_bot.callbacks.register_on_message_event(callback, tchap_bot.matrix_client)
    tchap_bot.run()
