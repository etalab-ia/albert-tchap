# SPDX-FileCopyrightText: 2024 Etalab/Datalab <etalab@modernisation.gouv.fr>
#
# SPDX-License-Identifier: MIT

import json

import requests

from matrix_bot.config import logger


def generate(config:dict, query:str):
    api_token = config.albert_api_token
    url = config.albert_api_url

    # Create Stream:
    headers = {
        "Authorization": f"Bearer {api_token}",
    }
    data = {
        "query": query,
        "model_name": "AgentPublic/albert-light",
        "mode": "rag",
        # "postprocessing": ["check_url", "check_mail", "check_number"],
        # "with_history": True,
    }
    # response = requests.post(f"{url}/stream/chat/1", json=data, headers=headers)
    response = requests.post(f"{url}/stream", json=data, headers=headers)
    print(response)
    if not response.ok:
        error_detail = response.json().get("detail")
        logger.error(f"{error_detail}")
        response.raise_for_status()

    stream_id = response.json()["id"]

    # Start Stream:
    # @TODO: implement non-streaming response
    data = {"stream_id": stream_id}
    response = requests.get(f"{url}/stream/{stream_id}/start", json=data, headers=headers, stream=True)
    if not response.ok:
        error_detail = response.json().get("detail")
        logger.error(f"{error_detail}")
        response.raise_for_status()

    answer = ""
    for line in response.iter_lines():
        if not line:
            continue
        decoded_line = line.decode("utf-8")
        _, _, data = decoded_line.partition("data: ")
        try:
            text = json.loads(data)
            if text == "[DONE]":
                break
            answer += text
        except json.decoder.JSONDecodeError as e:
            # Should never happen...
            print("\nDATA: " + data)
            print("\nERROR:")
            raise e

    return answer
