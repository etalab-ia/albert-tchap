# SPDX-FileCopyrightText: 2024 Etalab <etalab@modernisation.gouv.fr>
#
# SPDX-License-Identifier: MIT

import json

import requests
from config import Config
from matrix_bot.config import logger


def log_and_raise_for_status(response: requests.Response):
    if not response.ok:
        try:
            error_detail = response.json().get("detail")
        except Exception:
            error_detail = response.text
        logger.error(f"Albert API Error Detail: {error_detail}")
        response.raise_for_status()


def get_available_modes(config: Config) -> list[str] | None:
    api_token = config.albert_api_token
    url = config.albert_api_url
    headers = {"Authorization": f"Bearer {api_token}"}
    response = requests.get(f"{url}/models", headers=headers)
    log_and_raise_for_status(response)
    model_prompts = response.json()

    api_model = config.albert_model_name
    model_config = model_prompts.get(api_model, {})
    if not model_config:
        return None

    modes = [x["mode"] for x in model_config.get("config", {}).get("prompts", []) if "mode" in x]
    return modes


def new_chat(config: Config) -> int:
    api_token = config.albert_api_token
    url = config.albert_api_url
    headers = {"Authorization": f"Bearer {api_token}"}

    data = {
        "chat_type": "qa",
    }
    response = requests.post(f"{url}/chat", headers=headers, json=data)
    log_and_raise_for_status(response)
    chat_id = response.json()["id"]
    return chat_id


def generate(config: Config, query: str) -> str:
    api_token = config.albert_api_token
    api_model = config.albert_model_name
    api_mode = None if config.albert_mode == "norag" else config.albert_mode
    api_url = config.albert_api_url
    with_history = config.albert_with_history

    # Create Stream:
    headers = {"Authorization": f"Bearer {api_token}"}
    data = {
        "query": query,
        "model_name": api_model,
        "mode": api_mode,
        "with_history": with_history,
        # "postprocessing": ["check_url", "check_mail", "check_number"],
    }
    if with_history:
        if not config.albert_chat_id:
            config.albert_chat_id = new_chat(config)
        response = requests.post(
            f"{api_url}/stream/chat/{config.albert_chat_id}", headers=headers, json=data
        )
    else:
        response = requests.post(f"{api_url}/stream", headers=headers, json=data)
    log_and_raise_for_status(response)

    stream_id = response.json()["id"]
    config.albert_stream_id = stream_id

    # Start Stream:
    # @TODO: implement non-streaming response
    data = {"stream_id": stream_id}
    response = requests.get(
        f"{api_url}/stream/{stream_id}/start", headers=headers, json=data, stream=True
    )
    log_and_raise_for_status(response)

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


def generate_sources(config: Config, stream_id: int) -> list[dict]:
    api_token = config.albert_api_token
    api_url = config.albert_api_url

    # Create Stream:
    headers = {"Authorization": f"Bearer {api_token}"}
    response = requests.get(f"{api_url}/stream/{stream_id}", headers=headers)
    log_and_raise_for_status(response)
    stream = response.json()

    # Fetch chunks sources
    if not stream.get("rag_sources"):
        return []
    data = {"uids": stream["rag_sources"]}
    response = requests.post(f"{api_url}/get_chunks", headers=headers, json=data)
    log_and_raise_for_status(response)
    sources = response.json()
    return sources
