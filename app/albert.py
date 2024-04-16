import requests


def create_stream(api_url: str, token: str) -> str:
    """
    Create a user stream on Albert API
    Returns the stream_id
    """
    url = f"{api_url}/stream"
    headers = {
        "Authorization ": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    data = {
        "model_name": "albert",
        "mode": "stream",
        "query": "",
        "limit": 0,
        "with_history": True,
        "context": "",
        "institution": "",
        "links": "",
        "temperature": 20,
        "sources": ["service-public"],
        "should_sids": [],
        "must_not_sids": [],
        "response": "",
        "rag_sources": [],
        "postprocessing": [],
    }
    response: requests.Response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    return response.json()["stream_id"]
