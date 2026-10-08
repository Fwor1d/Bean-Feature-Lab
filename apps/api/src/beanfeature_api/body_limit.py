"""Bound prediction bodies independently of client Content-Length declarations."""

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

PREDICT_BODY_LIMIT = 32_768


class PredictionBodyLimit:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope["method"] != "POST"
            or scope["path"] != "/api/v1/classifier/predict"
        ):
            await self.app(scope, receive, send)
            return
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > PREDICT_BODY_LIMIT:
                await JSONResponse(
                    {
                        "error": {
                            "code": "payload_too_large",
                            "message": "Classifier request exceeds 32 KiB",
                        }
                    },
                    status_code=413,
                )(scope, receive, send)
                return
            body.extend(chunk)
            if not message.get("more_body", False):
                break
        delivered = False

        async def replay():
            nonlocal delivered
            if delivered:
                return await receive()
            delivered = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.app(scope, replay, send)
