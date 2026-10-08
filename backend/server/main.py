import os

from aiohttp import web


async def home(request):
    return web.Response(
        text="Our-Chat server is running!"
    )


async def websocket(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    print("WebSocket connected.")

    try:
        async for message in ws:
            if message.type == web.WSMsgType.TEXT:
                print("Received:", message.data)

                await ws.send_str(
                    message.data
                )

            elif message.type == web.WSMsgType.ERROR:
                print(
                    "WebSocket error:",
                    ws.exception()
                )

    finally:
        print("WebSocket disconnected.")

    return ws


app = web.Application()

app.router.add_get("/", home)
app.router.add_get("/ws", websocket)


port = int(
    os.environ.get(
        "PORT",
        10000
    )
)

web.run_app(
    app,
    host="0.0.0.0",
    port=port
)