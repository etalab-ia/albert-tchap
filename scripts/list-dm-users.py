#!/usr/bin/env python
import asyncio
import json
import os
from collections import namedtuple

from nio import AsyncClient, InviteMemberEvent, JoinedRoomsResponse, SyncResponse

# Matrix Config
config = {
    "server": os.getenv("MATRIX_HOME_SERVER"),
    "username": os.getenv("MATRIX_BOT_USERNAME"),
    "password": os.getenv("MATRIX_BOT_PASSWORD"),
    "errors_room_id": os.getenv("ERRORS_ROOM_ID"),
}
Config = namedtuple("Config", config.keys())
config = Config(**config)


async def get_users_state(config: Config, client: AsyncClient):
    # Sync with the server to get the latest state
    sync_response = await client.sync(full_state=True)
    if not isinstance(sync_response, SyncResponse):
        raise ValueError("Failed to sync the client")

    direct_chat_users = set()
    pending_chat_users = set()

    # Get the direct chats from the account data
    response = await client.joined_rooms()
    if isinstance(response, JoinedRoomsResponse):
        rooms = response.rooms
    else:
        raise ValueError("Failed to fetch joined room")

    for room_id in rooms:
        room = client.rooms.get(room_id)
        if room:
            # Check if the room is a direct chat (has exactly two members)
            members = room.users.values()
            if len(members) == 2:
                # Add the other user (not the client) to the set
                other_user = next(member for member in members if member.user_id != client.user_id)
                direct_chat_users.add(other_user.user_id)

    # Check for pending invitations
    for room_id, invite_state in sync_response.rooms.invite.items():
        for event in invite_state.invite_state:
            if isinstance(event, InviteMemberEvent) and event.sender != client.user_id:
                pending_chat_users.add(event.sender)

    # Due to invitation on room (not DM) ?
    pending_chat_users = pending_chat_users - direct_chat_users
    return {"active": list(direct_chat_users), "pending": list(pending_chat_users)}


async def main(config: Config):
    client = AsyncClient(config.server, config.username)
    await client.login(config.password)

    users_state = await get_users_state(config, client)
    with open("users_state.json", "w") as f:
        json.dump(users_state, f, indent=2)

    await client.close()


asyncio.get_event_loop().run_until_complete(main(config))
