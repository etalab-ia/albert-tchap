import asyncio
import json
import re
from collections import namedtuple
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import aiohttp

from bot_msg import AlbertMsg


# from grist_api import GristDocAPI => is not async
class AsyncGristDocAPI:
    def __init__(self, doc_id: str, server: str, api_key: str):
        self.doc_id = doc_id
        self.server = server
        self.api_key = api_key
        self.base_url = f"{server}/api"

    async def _request(self, method, endpoint, json_data=None):
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with aiohttp.ClientSession() as session:
            if method in ["GET"]:
                data = {"params": json_data}
            else:
                headers["Content-Type"] = "application/json"
                data = {"json": json_data}

            async with session.request(
                method, self.base_url + endpoint, headers=headers, **data
            ) as response:
                response.raise_for_status()
                return await response.json()

    async def fetch_table(self, table_id, filters=None) -> list[namedtuple]:
        endpoint = f"/docs/{self.doc_id}/tables/{table_id}/records"
        data = {}
        if filters:
            data["filter"] = json.dumps(filters)
        result = await self._request("GET", endpoint, data)

        if not result["records"]:
            return []
        Record = namedtuple("Record", ["id"] + list(result["records"][0]["fields"].keys()))
        records = [Record(**{"id": r["id"], **r["fields"]}) for r in result["records"]]
        return records

    async def add_records(self, table_id, records):
        endpoint = f"/docs/{self.doc_id}/tables/{table_id}/records"
        data = {"records": [{"fields": r} for r in records]}
        result = await self._request("POST", endpoint, data)
        return result

    async def update_records(self, table_id, records):
        endpoint = f"/docs/{self.doc_id}/tables/{table_id}/records"
        records = [r.copy() for r in records]
        data = {"records": [{"id": r.pop("id"), "fields": r} for r in records]}
        result = await self._request("PATCH", endpoint, data)
        return result


class TchapIam:
    REFRESH_DELTA = 3600
    TZ = timezone(timedelta(hours=2))

    def __init__(self, config):
        self.config = config
        self.users_table_id = config.grist_users_table_id
        self.users_table_name = config.grist_users_table_name
        self.iam_client = AsyncGristDocAPI(
            self.users_table_id,
            server=config.grist_api_server,
            api_key=config.grist_api_key,
        )

        # White-listed users
        self.users_allowed = {}
        # Users that have been adde to the pendings list.
        # Used to send notification for new pending users.
        self.users_not_allowed = {}

        self.last_refresh = None
        asyncio.run(self._refresh())

    @staticmethod
    def domain_from_sender(sender: str) -> str:
        """
        Sender IDs are formatted like this: "@<mail_username>-<mail_domain>:<matrix_server>
        e.g. @john.doe-ministere_example.gouv.fr1:agent.ministere_example.tchap.gouv.frmerci
        """
        match = re.search(
            r"(?<=\-)[^\-\:]+[0-9]*(?=\:)", sender
        )  # match the domain name (between the last "-" and ":", with optional numbers to ignore at the end of the domain) WARNING: this regex is not perfect and doesn't work for domain names with dashes in it like "developpement-durable.gouv.fr"
        if match:
            return match.group(0)

        print("Could not extract domain from sender: %s" % sender)

    async def _refresh(self):
        ttl = datetime.utcnow() - timedelta(seconds=self.REFRESH_DELTA)
        if not self.last_refresh or self.last_refresh < ttl:
            # Build allowed users list
            users_table = await self.iam_client.fetch_table(
                self.users_table_name, filters={"status": ["allowed"]}
            )
            self.users_allowed.clear()
            for record in users_table:
                self.users_allowed[record.tchap_user] = record

            # Build not allowed users list
            users_table = await self.iam_client.fetch_table(
                self.users_table_name, filters={"status": ["pending", "forbidden"]}
            )
            self.users_not_allowed.clear()
            for record in users_table:
                self.users_not_allowed[record.tchap_user] = record

            self.last_refresh = datetime.utcnow()
            print("User table (IAM) updated")

    async def is_user_allowed(self, config, username, refresh=False) -> tuple[bool, str]:
        """Check if user is allowed to use the tchap bot:
        1. User should be in the whitelist, otherwise send user_not_allowed message
        2. User should be in allowed_domain, otherwise domain_not_allowed_message message
        """
        if refresh:
            await self._refresh()
        is_allowed = False
        msg = ""

        # 1. check user
        is_allowed = username in self.users_allowed
        if not is_allowed:
            msg = AlbertMsg.user_not_allowed

        # 2. Check domains
        if is_allowed:
            if "*" in config.user_allowed_domains:
                is_allowed = True
            elif self.domain_from_sender(username) in config.user_allowed_domains:
                is_allowed = True
            else:
                is_allowed = False
                msg = AlbertMsg.domain_not_allowed

        return is_allowed, msg

    async def add_pending_user(self, config, username) -> bool:
        """Return True if the used as been added to the list"""
        if username in list(self.users_allowed) + list(self.users_not_allowed):
            return False

        record = {
            "tchap_user": username,
            "status": "pending",
            "domain": self.domain_from_sender(username),
        }
        await self.iam_client.add_records(self.users_table_name, [record])
        return True

    async def increment_user_question(self, username, n=1, update_last_activity=True):
        try:
            record = self.users_allowed[username]
        except Exception as err:
            raise ValueError("User not found in grist") from err

        updates = {"n_questions": record.n_questions + n}
        if update_last_activity:
            updates["last_activity"] = str(datetime.now(self.TZ))

        await self.iam_client.update_records(self.users_table_name, [{"id": record.id, **updates}])

        self.users_allowed[username] = record._replace(**updates)
