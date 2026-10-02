import asyncio

from starlette.responses import JSONResponse

from app.observability.events import emit


class RequestBodyLimit:
    """Bound JSON allocation before FastAPI parsing, including chunked requests."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST":
            return await self.app(scope, receive, send)
        body = bytearray()

        async def reject(status, code, message):
            emit("request_error", code=code, status=status)
            await JSONResponse(status_code=status, content={"error": {
                "code": code, "message": message}})(scope, receive, send)

        try:
            async with asyncio.timeout(10):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    chunk = message.get("body", b"")
                    if len(body) + len(chunk) > 65536:
                        return await reject(413, "request_too_large", "Request exceeds 64 KiB.")
                    body.extend(chunk)
                    if not message.get("more_body", False):
                        break
        except TimeoutError:
            return await reject(408, "request_timeout", "Request body timed out.")

        delivered = False

        async def buffered_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, buffered_receive, send)
