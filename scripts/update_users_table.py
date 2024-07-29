#!/usr/bin/env python

import asyncio
import json
import os
import re
import sys
from collections import namedtuple

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../app")))

from iam import AsyncGristDocAPI

# Matrix Config
config = {
    "users_table_id": os.getenv("GRIST_USERS_TABLE_ID"),
    "users_table_name": os.getenv("GRIST_USERS_TABLE_NAME"),
    "api_server": os.getenv("GRIST_API_SERVER"),
    "api_key": os.getenv("GRIST_API_KEY"),
}
Config = namedtuple("Config", config.keys())
config = Config(**config)


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


async def update_users_table(config):
    grclient = AsyncGristDocAPI(config.users_table_id, config.api_server, config.api_key)

    with open("../tchap_users_state.prod.json") as f:
        users_state = json.load(f)

    def map_status(status):
        map_dict = {"active": "allowed"}
        if status in map_dict:
            return map_dict[status]
        return status

    users_state = [
        {"tchap_user": name, "status": map_status(status), "domain":domain_from_sender(name)}
        for status, ids in users_state.items()
        for name in ids
    ]
    users_table = await grclient.fetch_table(config.users_table_name)
    users_table = {r.tchap_user: r for r in users_table}

    new_records = []
    for r in users_state:
        if r["tchap_user"] in users_table:
            continue
        new_records.append(r)

    await grclient.add_records(config.users_table_name, new_records)


asyncio.get_event_loop().run_until_complete(update_users_table(config))
