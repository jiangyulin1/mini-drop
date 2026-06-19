import asyncio
import json
import threading

from server.app.chatops.providers.qqbot import QQBotProvider


class _FakeWebSocket:
    def __init__(self):
        self.sent = []

    async def send(self, payload: str):
        self.sent.append(payload)
        data = json.loads(payload)
        echo = str(data["echo"])
        with QQBotProvider._ws_pending_lock:
            future = QQBotProvider._ws_pending_actions.get(echo)
        if future is not None:
            future.set_result({"echo": data["echo"], "status": "ok"})


def test_qqbot_ws_send_uses_server_loop(monkeypatch):
    loop = asyncio.new_event_loop()
    ready = threading.Event()

    def run_loop():
        asyncio.set_event_loop(loop)
        ready.set()
        loop.run_forever()

    thread = threading.Thread(target=run_loop, daemon=True)
    thread.start()
    ready.wait(timeout=1)

    key = ("127.0.0.1", 5701)
    conn = _FakeWebSocket()
    QQBotProvider._ws_connections[key] = conn
    QQBotProvider._ws_loops[key] = loop
    monkeypatch.setenv("MINI_DROP_QQBOT_TARGET_ID", "123456")

    try:
        provider = QQBotProvider()
        assert provider.send(
            message=type("Msg", (), {
                "title": "done",
                "content": "task done",
                "level": "success",
                "extra_fields": [],
                "link_url": "",
                "link_text": "",
            })(),
            webhook_url="ws://127.0.0.1:5701",
        ) is True

        payload = json.loads(conn.sent[0])
        assert payload["action"] == "send_group_msg"
        assert payload["params"]["group_id"] == 123456
    finally:
        QQBotProvider._ws_connections.pop(key, None)
        QQBotProvider._ws_loops.pop(key, None)
        with QQBotProvider._ws_pending_lock:
            QQBotProvider._ws_pending_actions.clear()
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=1)
        loop.close()
