# SPDX-FileCopyrightText: 2024 Etalab <etalab@modernisation.gouv.fr>
#
# SPDX-License-Identifier: MIT

import os
from io import BytesIO

import requests
from jinja2 import BaseLoader, Environment, Template, meta
from openai import OpenAI

from config import Config
from utils import log_and_raise_for_status

API_PREFIX_V1 = "v1"


def get_available_models(config: Config) -> dict:
    """Fetch available models"""
    api_key = config.albert_api_token
    url = os.path.join(config.albert_api_url, API_PREFIX_V1)
    headers = {"Authorization": f"Bearer {api_key}"}
    response = requests.get(f"{url}/models", headers=headers)
    log_and_raise_for_status(response)
    data = response.json()
    models = {v["id"]: v for v in data["data"] if v["type"] == "text-generation"}
    return models


def get_available_modes(config: Config) -> list[str]:
    """Fetch available modes for the current model"""
    return ["norag", "rag"]


def generate(
    config: Config, 
    messages: list
) -> str:
    api_key = config.albert_api_token
    url = os.path.join(config.albert_api_url, API_PREFIX_V1)
    model = config.albert_model
    mode = None if config.albert_mode == "norag" else config.albert_mode
    collections = list(config.albert_collections_by_id.keys())
    rag_sources = []
    if not config.albert_with_history:
        messages = messages[-1:]

    # Build prompt
    sampling_params: dict = {}
    aclient = AlbertApiClient(base_url=url, api_key=api_key)
    if mode == "rag":
        messages = aclient.make_rag_prompt(
            model_embedding=config.albert_model_embedding, 
            messages=messages,
            collections=collections,
            limit=7
        )
        rag_sources = aclient.last_sources
    else:
        system_prompt = "Tu es Albert, un bot de l'état français en charge d'informer les agents."
        messages = [
            {
                "role": "system",
                "content": system_prompt,
            }
        ] + messages

    # Generate answer
    print(messages)
    answer = aclient.generate(model=model, messages=messages, **sampling_params)

    # Set the sources used by the rag of empty list.
    config.last_rag_sources = rag_sources

    return answer.strip()


def get_all_public_collections(config: Config) -> dict:
    api_key = config.albert_api_token
    url = os.path.join(config.albert_api_url, API_PREFIX_V1)
    aclient = AlbertApiClient(base_url=url, api_key=api_key)
    return [
        collection
        for collection in aclient.fetch_collections().values()
        if collection['type'] == 'public'
    ]


def get_or_create_collection_with_name(config: Config, collection_name: str) -> dict:
    api_key = config.albert_api_token
    url = os.path.join(config.albert_api_url, API_PREFIX_V1)
    aclient = AlbertApiClient(base_url=url, api_key=api_key)
    # TODO : wait for fetch_collections to be faster
    collections = [] #aclient.fetch_collections().values()
    for collection in collections:
        if collection['name'] == collection_name:
            return collection
    return aclient.create_collection(collection_name, config.albert_model_embedding)


def delete_collections_with_name(config: Config, collection_name: str) -> None:
    api_key = config.albert_api_token
    url = os.path.join(config.albert_api_url, API_PREFIX_V1)
    aclient = AlbertApiClient(base_url=url, api_key=api_key)
    collections = aclient.fetch_collections().values()
    for collection in collections:
        if collection["name"] == collection_name:
            aclient.delete_collection(collection['id'])


def upload_file(config: Config, file: BytesIO, collection_id: str) -> dict:
    api_key = config.albert_api_token
    url = os.path.join(config.albert_api_url, API_PREFIX_V1)
    aclient = AlbertApiClient(base_url=url, api_key=api_key)
    return aclient.upload_file(file, collection_id)


class AlbertApiClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self._last_sources: list[dict] = []  # stores last sources used by a RAG generation.

    @property
    def last_sources(self) -> list[dict]:
        return self._last_sources

    def create_collection(self, collection_name: str, model_embedding: str) -> dict:
        """Call the POST /collections endpoint of the Albert API"""
        url = self.base_url
        headers = {"Authorization": f"Bearer {self.api_key}"}
        data = {"name": collection_name, "model": model_embedding, "type": "private"}
        response = requests.post(f"{url}/collections", json=data, headers=headers)
        log_and_raise_for_status(response)
        data = response.json()
        return data
    
    def delete_collection(self, collection_id: str) -> None:
        """Call the DELETE /collections/{collection_id} endpoint of the Albert API"""
        url = self.base_url
        headers = {"Authorization": f"Bearer {self.api_key}"}
        response = requests.delete(f"{url}/collections/{collection_id}", headers=headers)
        log_and_raise_for_status(response)
    
    def fetch_collections(self) -> dict:
        """Call the GET /collections endpoint of the Albert API"""
        url = self.base_url
        headers = {"Authorization": f"Bearer {self.api_key}"}
        response = requests.get(f"{url}/collections", headers=headers)
        log_and_raise_for_status(response)
        data = response.json()
        collections_by_id = {v["id"]: v for v in data["data"]}
        return collections_by_id

    def generate(self, model: str, messages: list[dict], **sampling_params) -> str:
        result = self.client.chat.completions.create(
            model=model, messages=messages, **sampling_params
        )
        answer = result.choices[0].message.content
        return answer

    def make_rag_prompt(self, 
        model_embedding: str, 
        messages: list[dict],
        collections: list[str],
        limit: int = 7
    ) -> list[dict]:
        system_prompt = "Tu es Albert, un bot de l'état français en charge d'informer les agents."
        messages = [
            {
                "role": "system",
                "content": system_prompt,
            }
        ] + messages
        query = messages[-1]["content"]
        chunks = self.semantic_search(model_embedding, query, limit, collections)
        self._last_sources = chunks
        prompt = self.format_albert_template(query, chunks)
        messages[-1]["content"] = prompt
        return messages

    def semantic_search(
        self, 
        model: str, 
        query: str, 
        limit: int, 
        collections: list[str]
    ) -> list[dict]:
        """Call the /search endpoint of the Albert API"""
        url = self.base_url
        headers = {"Authorization": f"Bearer {self.api_key}"}
        params = {
            "prompt": query,
            "model": model,
            "collections": collections,
            "k": limit,
        }
        response = requests.post(f"{url}/search", headers=headers, json=params)
        log_and_raise_for_status(response)
        data = response.json()
        chunks = [v["chunk"]["metadata"] for v in data["data"]]
        return chunks
    
    def upload_file(
        self, 
        file: BytesIO, 
        collection_id: str
    ) -> list[dict]:
        """Call the /files endpoint of the Albert API"""
        url = self.base_url
        headers = {"Authorization": f"Bearer {self.api_key}"}
        files = {"file": (file.name, file.getvalue(), file.type)}
        data = {"request": '{"collection": "%s"}' % collection_id}
        response = requests.post(f"{url}/files", data=data, files=files, headers=headers)
        log_and_raise_for_status(response)

    def format_albert_template(self, query: str, chunks: list[dict]) -> str:
        # Template configuration
        prompt_template = """Utilisez le contexte suivant comme votre base de connaissances, à l'intérieur des balises XML <context></context>.

<context>
{% for chunk in chunks %}
url: {{chunk.url}}
title: {{chunk.title}} {% if chunk.context %}({{chunk.context}}){% endif %}
text: {{chunk.text}} {% if not loop.last %}{{"\n"}}{% endif %}
{% endfor %}
</context>


Lors de la réponse à l'utilisateur :
- Si vous ne savez pas ou si vous n'êtes pas sûr, demandez une clarification.
- Évitez de mentionner que vous avez obtenu les informations du contexte.

Étant donné les sources d'informations du contexte, répondez à la question.
Question : {{query}}
"""

        conf = {
            "limit": len(chunks),
            "prompt_template": prompt_template,
        }

        conf["query"] = query
        conf["chunks"] = chunks

        # Render template
        env = Environment(loader=BaseLoader())
        t = env.from_string(prompt_template)
        # variables = meta.find_undeclared_variables(env.parse(prompt_template))
        prompt = t.render(**conf)
        return prompt
