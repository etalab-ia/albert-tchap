# SPDX-FileCopyrightText: 2021 - 2022 Isaac Beverly <https://github.com/imbev>
# SPDX-FileCopyrightText: 2023 Pôle d'Expertise de la Régulation Numérique <contact.peren@finances.gouv.fr>
#
# SPDX-License-Identifier: MIT
import mimetypes
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import aiofiles.os

import markdown
import requests
from nio import AsyncClient, AsyncClientConfig, RoomMessage, RoomSendResponse
from nio.exceptions import OlmUnverifiedDeviceError
from nio.responses import UploadResponse
from PIL import Image

from .auth import AuthLogin
from .config import bot_lib_config, logger
from .room_utils import room_is_direct_message


def check_valid_homeserver(homeserver: str):
    if not (homeserver.startswith("http://") or homeserver.startswith("https://")):
        raise ValueError(f"Invalid Homeserver, should start with http:// or https://, is {homeserver} instead")
    matrix_version_url = f"{homeserver}/_matrix/client/versions"
    try:
        response = requests.get(matrix_version_url)
        response.raise_for_status()
    except requests.HTTPError as http_error:
        raise ValueError(f"Invalid Homeserver, could not connect to {matrix_version_url}") from http_error


class MatrixClient(AsyncClient):
    """
    A class to interact with the matrix-nio library. Usually used by the Bot class, and sparingly by the bot developer.
    Subclass AsyncClient from nio for ease of use.
    """

    def __init__(self, auth: AuthLogin):
        self.auth = auth
        check_valid_homeserver(self.auth.credentials.homeserver)
        self.matrix_config = bot_lib_config
        self.matrix_config.store_path.mkdir(mode=0o750, exist_ok=True, parents=True)
        client_config = AsyncClientConfig(
            max_limit_exceeded=0,
            max_timeouts=10,
            store_sync_tokens=True,
            encryption_enabled=self.matrix_config.encryption_enabled,
        )
        super().__init__(
            homeserver=self.auth.credentials.homeserver,
            user=self.auth.credentials.username,
            device_id=self.auth.device_id,
            store_path=str(self.matrix_config.store_path.resolve()),
            config=client_config,
        )

    async def automatic_login(self):
        """Login the client to the homeserver"""
        if self.auth.access_token:
            self.access_token = self.auth.access_token
            who_am_i = await self.whoami()
            self.user_id = who_am_i.user_id
            if self.matrix_config.encryption_enabled:
                self.load_store()
        else:
            login_response = await self.login(
                password=self.auth.credentials.password, device_name=self.auth.device_name
            )
            self.auth.device_id = login_response.device_id
            self.auth.access_token = login_response.access_token
            self.auth.write_session_file()

        if self.should_upload_keys:
            await self.keys_upload()

    def get_non_private_rooms(self):
        return {room_id: room for room_id, room in self.rooms.items() if not room_is_direct_message(room)}

    async def get_display_name(self):
        return (await self.get_displayname(self.user_id)).displayname

    async def _send_room(
        self,
        room_id: str,
        content: dict,
        message_type: str = "m.room.message",
        reply_to: Optional[str] = None,
        thread_root: Optional[str] = None,
        ignore_unverified_devices: Optional[bool] = None,
    ):
        """
        Send a custom event in a Matrix room.

        Parameters
        -----------
        room_id : str
            The room id of the destination of the message.

        content : dict
            The content block of the event to be sent.

        message_type : str, optional
            The type of event to send, default m.room.message.

        reply_to : str, optional
            The event id of the message to reply to.

        thread_root : str, optional
            The event id of the message acting as a thread root for the message.

        ignore_unverified_devices : bool, optional
            Whether to ignore that devices are not verified and send the
            message to them regardless on a per-message basis.
            If None is specified, the global config value is used.
        """

        if thread_root:
            content.setdefault("m.relates_to", {})["event_id"] = thread_root
            content["m.relates_to"]["rel_type"] = "m.thread"

        if reply_to:
            content.setdefault("m.relates_to", {}).setdefault("m.in_reply_to", {})["event_id"] = reply_to

        if thread_root and reply_to:
            content["m.relates_to"]["is_falling_back"] = True

        try:
            res = await self.room_send(
                room_id=room_id,
                message_type=message_type,
                content=content,
                ignore_unverified_devices=ignore_unverified_devices or self.matrix_config.ignore_unverified_devices,
            )
            if isinstance(res, RoomSendResponse):
                return res.event_id
        except OlmUnverifiedDeviceError:
            logger.info(
                "Message could not be sent. "
                "Set ignore_unverified_devices = True to allow sending to unverified devices."
            )
            logger.info("Automatically blacklisting the following devices:")
            for user in self.rooms[room_id].users:
                unverified: List[str] = []
                for device_id, device in self.olm.device_store[user].items():
                    if not (self.olm.is_device_verified(device) or self.olm.is_device_blacklisted(device)):
                        self.olm.blacklist_device(device)
                        unverified.append(device_id)
                if len(unverified) > 0:
                    logger.info(f"\tUser {user}: {', '.join(unverified)}")

            res = await self.room_send(
                room_id=room_id,
                message_type=message_type,
                content=content,
                ignore_unverified_devices=ignore_unverified_devices or self.matrix_config.ignore_unverified_devices,
            )
            if isinstance(res, RoomSendResponse):
                return res.event_id

        return None

    async def send_text_message(
        self,
        room_id: str,
        message: str,
        msgtype: str = "m.text",
        reply_to: Optional[str] = None,
        thread_root: Optional[str] = None,
    ):
        """
        Send a text message in a Matrix room.

        Parameters
        -----------
        room_id : str
            The room id of the destination of the message.

        message : str
            The content of the message to be sent.

        msgtype : str, optional
            The type of message to send: m.text (default), m.notice, etc

        reply_to : str, optional
            The event id of the message to reply to.

        thread_root : str, optional
            The event id of the message acting as a thread root for the message.
        """

        return await self._send_room(
            room_id=room_id, content={"msgtype": msgtype, "body": message}, reply_to=reply_to, thread_root=thread_root
        )

    async def send_markdown_message(
        self,
        room_id: str,
        message,
        msgtype: str = "m.text",
        reply_to: Optional[str] = None,
        thread_root: Optional[str] = None,
    ):
        """
        Send a markdown message in a Matrix room.

        Parameters
        -----------
        room_id : str
            The room id of the destination of the message.

        message : str
            The content of the message to be sent.

        msgtype : str, optional
            The type of message to send: m.text (default), m.notice, etc

        reply_to : str, optional
            The event id of the message to reply to.

        thread_root : str, optional
            The event id of the message acting as a thread root for the message.
        """

        return await self._send_room(
            room_id=room_id,
            content={
                "msgtype": msgtype,
                "body": message,
                "format": "org.matrix.custom.html",
                "formatted_body": markdown.markdown(message, extensions=["fenced_code", "nl2br"]),
            },
            reply_to=reply_to,
            thread_root=thread_root,
        )

    async def send_reaction(self, room_id: str, event: RoomMessage, key: str):
        """
        Send a reaction to a message in a Matrix room.

        Parameters
        ----------
        room_id : str
            The room id of the destination of the message.

        event :
            The event object you want to react to.

        key: str
            The content of the reaction. This is usually an emoji, but may technically be any text.
        """

        return await self._send_room(
            room_id=room_id,
            content={
                "m.relates_to": {
                    "event_id": event.event_id,
                    "key": key,
                    "rel_type": "m.annotation",
                }
            },
            message_type="m.reaction",
        )

    async def _upload_file(
        self,
        file_path: Union[str, Path],
        mime_type: Optional[str] = None,
        filename: Optional[str] = None,
        encrypt: bool = False,
    ) -> Tuple[UploadResponse, os.stat_result, str, Optional[Dict[str, Any]]]:
        if not mime_type:
            mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = "application/octet-stream"
        if not filename:
            Path(file_path).name
        file_stat = await aiofiles.os.stat(file_path)
        async with aiofiles.open(file_path, "r+b") as file:
            uploaded_file, maybe_keys = await self.upload(
                file,
                content_type=mime_type,
                filename=filename,
                filesize=file_stat.st_size,
                encrypt=encrypt,
            )
        if not isinstance(uploaded_file, UploadResponse):
            logger.error(f"Failed Upload Response: {uploaded_file}")
        return uploaded_file, file_stat, mime_type, maybe_keys

    async def send_image_message(
        self,
        room_id: str,
        image_filepath: str,
        reply_to: Optional[str] = None,
        thread_root: Optional[str] = None,
    ):
        """
        Send an image message in a Matrix room.

        Parameters
        -----------
        room_id : str
            The room id of the destination of the message.

        image_filepath : str
            The path to the image on your machine.

        reply_to : str, optional
            The event id of the message to reply to.

        thread_root : str, optional
            The event id of the message acting as a thread root for the message.
        """
        encrypt = room_id in self.encrypted_rooms

        uploaded_file, file_stat, mime_type, maybe_keys = await self._upload_file(image_filepath, encrypt=encrypt)

        image = Image.open(image_filepath)
        (width, height) = image.size

        content = {
            "body": os.path.basename(image_filepath),
            "info": {
                "size": file_stat.st_size,
                "mimetype": mime_type,
                "thumbnail_info": None,
                "w": width,
                "h": height,
                "thumbnail_url": None,
            },
            "msgtype": "m.image",
        }

        if encrypt and maybe_keys:
            content["file"] = maybe_keys
            content["file"]["url"] = uploaded_file.content_uri
        else:
            content["url"] = uploaded_file.content_uri

        try:
            return await self._send_room(room_id=room_id, content=content, reply_to=reply_to, thread_root=thread_root)
        except Exception:
            logger.error(f"Failed to send image file {image_filepath}")

    async def send_video_message(
        self,
        room_id: str,
        video_filepath: str,
        reply_to: Optional[str] = None,
        thread_root: Optional[str] = None,
    ):
        """
        Send a video message in a Matrix room.

        Parameters
        ----------
        room_id : str
            The room id of the destination of the message.

        video_filepath : str
            The path to the video on your machine.

        reply_to : str, optional
            The event id of the message to reply to.

        thread_root : str, optional
            The event id of the message acting as a thread root for the message.
        """
        encrypt = room_id in self.encrypted_rooms

        uploaded_file, file_stat, mime_type, maybe_keys = await self._upload_file(video_filepath, encrypt=encrypt)
        content = {
            "body": os.path.basename(video_filepath),
            "info": {
                "size": file_stat.st_size,
                "mimetype": mime_type,
                "thumbnail_info": None,
            },
            "msgtype": "m.video",
        }

        if encrypt and maybe_keys:
            content["file"] = maybe_keys
            content["file"]["url"] = uploaded_file.content_uri
        else:
            content["url"] = uploaded_file.content_uri

        try:
            return await self._send_room(room_id=room_id, content=content, reply_to=reply_to, thread_root=thread_root)
        except Exception:
            logger.error(f"Failed to send video file {video_filepath}")

    async def send_file_message(
        self,
        room_id: str,
        filepath: str,
        mime_type: Optional[str] = None,
        filename: Optional[str] = None,
        reply_to: Optional[str] = None,
        thread_root: Optional[str] = None,
    ):
        """
        Send a file message in a Matrix room.

        Parameters
        -----------
        room_id : str
            The room id of the destination of the message.

        filepath : str
            The path to the image on your machine.

        mime_type : str, optional
            The MIME type of the file. If not specified it will try to
            autodetect it.

        filename (str, optional): The file's original name.

        reply_to : str, optional
            The event id of the message to reply to.

        thread_root : str, optional
            The event id of the message acting as a thread root for the message.
        """
        encrypt = room_id in self.encrypted_rooms

        uploaded_file, file_stat, mime_type, maybe_keys = await self._upload_file(
            filepath, mime_type, filename, encrypt
        )

        if not filename:
            filename = os.path.basename(filepath)

        content = {
            "body": filename,
            "info": {
                "size": file_stat.st_size,
                "mimetype": mime_type,
            },
            "msgtype": "m.file",
        }

        if encrypt and maybe_keys:
            content["file"] = maybe_keys
            content["file"]["url"] = uploaded_file.content_uri
        else:
            content["url"] = uploaded_file.content_uri

        try:
            return await self._send_room(room_id=room_id, content=content, reply_to=reply_to, thread_root=thread_root)
        except Exception:
            logger.error(f"Failed to send file {filepath}")
