# SPDX-FileCopyrightText: 2021 - 2022 Isaac Beverly <https://github.com/imbev>
# SPDX-FileCopyrightText: 2023 Pôle d'Expertise de la Régulation Numérique <contact.peren@finances.gouv.fr>
#
# SPDX-License-Identifier: MIT

import asyncio

from nio import SyncResponse

from .auth import AuthLogin, Credentials
from .callbacks import Callbacks
from .client import MatrixClient
from .config import bot_lib_config, logger


class MatrixBot:
    """
    A class for the bot library user to interact with.
    """

    def __init__(self, homeserver: str, username: str, password: str):
        self.matrix_client = MatrixClient(
            AuthLogin(Credentials(homeserver=homeserver, username=username, password=password))
        )
        self.callbacks = Callbacks(self.matrix_client)

    async def main(self):
        await self.matrix_client.automatic_login()
        sync = await self.matrix_client.sync(timeout=bot_lib_config.timeout, full_state=False)  # Ignore prior messages
        self.print_sync_response(sync)
        await self.callbacks.setup_callbacks()

        for action in self.callbacks.startup:
            for room_id in self.matrix_client.rooms:
                await action(room_id)
        await self.matrix_client.sync_forever(timeout=3000, full_state=True)

    def print_sync_response(self, sync):
        if not isinstance(sync, SyncResponse):
            return
        logger.info(
            "Connected",
            server=self.matrix_client.homeserver,
            user_id=self.matrix_client.user_id,
            device_id=self.matrix_client.device_id,
        )
        if bot_lib_config.encryption_enabled:
            key = self.matrix_client.olm.account.identity_keys["ed25519"]
            logger.info(
                f'This bot\'s public fingerprint ("Session key") for one-sided verification is: '
                f"{' '.join([key[i:i+4] for i in range(0, len(key), 4)])}"
            )

    def run(self):
        """Runs the bot."""
        asyncio.run(self.main())
