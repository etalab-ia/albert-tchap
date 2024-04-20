# SPDX-FileCopyrightText: 2023 Pôle d'Expertise de la Régulation Numérique <contact.peren@finances.gouv.fr>
# SPDX-FileCopyrightText: 2024 Etalab/Datalab <etalab@modernisation.gouv.fr>
#
# SPDX-License-Identifier: MIT

from commands import command_registry
from config import env_config
from matrix_bot.bot import MatrixBot
from matrix_bot.config import logger

# TODO/IMPROVE:
# - catch unknow command ?
# - add dropup with all available commands like when using "/" ?
# - if albert-bot is invited in a salon, make it answer only when it is tagged.


def main():
    tchap_bot = MatrixBot(
        env_config.matrix_home_server,
        env_config.matrix_bot_username,
        env_config.matrix_bot_password,
    )

    for feature in [
        feature
        for feature_group in env_config.groups_used
        for feature in command_registry.activate_and_retrieve_group(feature_group)
    ]:
        callback = feature["func"]
        onEvent = feature["onEvent"]
        tchap_bot.callbacks.register_on_custom_event(callback, onEvent, feature)
        logger.info("loaded feature", feature=feature["name"])

    # To send message if Albert is updated for example...
    #async def startup_action(room_id):
    #    await tchap_bot.matrix_client.send_markdown_message(room_id, command_registry.get_help())
    #tchap_bot.callbacks.register_on_startup(startup_action)

    tchap_bot.run()
