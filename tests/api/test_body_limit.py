import asyncio

from beanfeature_api.body_limit import PredictionBodyLimit


def invoke(chunks):
    called, messages = [], []
    incoming = iter(
        {"type": "http.request", "body": body, "more_body": i < len(chunks) - 1}
        for i, body in enumerate(chunks)
    )

    async def receive():
        return next(incoming)

    async def send(message):
        messages.append(message)

    async def app(scope, receive, send):
        called.append(await receive())

    asyncio.run(
        PredictionBodyLimit(app)(
            {"type": "http", "method": "POST", "path": "/api/v1/classifier/predict"},
            receive,
            send,
        )
    )
    return called, messages


def test_chunked_prediction_is_bounded_without_content_length():
    called, messages = invoke([b"a" * 16_384, b"b" * 16_385])
    assert not called and messages[0]["status"] == 413
    assert b"payload_too_large" in messages[1]["body"]


def test_small_prediction_is_replayed_unchanged():
    called, messages = invoke([b'{"features":', b"{}}"])
    assert called == [{"type": "http.request", "body": b'{"features":{}}', "more_body": False}]
    assert not messages


def test_missing_runtime_file_returns_safe_error(api_client, monkeypatch):
    def unavailable():
        raise FileNotFoundError("/Users/private/model.joblib")

    monkeypatch.setattr(api_client.app.state.container.service, "classifier_info", unavailable)
    response = api_client.get("/api/v1/classifier/model")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "artifact_unavailable"
    assert "/Users/" not in response.text


def test_body_limit_errors_keep_allowed_browser_cors(api_client):
    response = api_client.post(
        "/api/v1/classifier/predict",
        content=iter([b" " * 20_000, b" " * 20_000]),
        headers={"Content-Type": "application/json", "Origin": "http://localhost:3000"},
    )
    assert response.status_code == 413
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
