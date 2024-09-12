#!/usr/bin/env python
import asyncio
import os
from collections import namedtuple

from nio import AsyncClient, LoginResponse

# Matrix Config
config = {
    "server": os.getenv("MATRIX_HOME_SERVER"),
    "username": os.getenv("MATRIX_BOT_USERNAME"),
    "password": os.getenv("MATRIX_BOT_PASSWORD"),
    "errors_room_id": os.getenv("ERRORS_ROOM_ID"),
}
Config = namedtuple("Config", list(config.keys()))
config = Config(**config)

message = "Hi, this is a test."


async def send_to_room(config: Config, message: str):
    # Create an instance of the AsyncClient
    client = AsyncClient(config.server, config.username)

    # Log in to the Matrix server
    response = await client.login(config.password)
    if isinstance(response, LoginResponse):
        print("Logged in successfully")

        # Send a message to the room
        await client.room_send(
            room_id=config.errors_room_id,
            message_type="m.room.message",
            content={"msgtype": "m.text", "body": message},
        )
        print("Message sent successfully")

        # Log out from the Matrix server
        await client.logout()
    else:
        print(f"Failed to log in: {response}")

    # Close the client session
    await client.close()


# Run the main function using asyncio
asyncio.get_event_loop().run_until_complete(send_to_room(config, message))
