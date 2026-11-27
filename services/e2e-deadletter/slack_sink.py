# Copyright 2026 masa@kugel
"""A stand-in for the Slack webhook in the dead-letter e2e (#230).

POST /hook stores the text of a notification, GET /messages returns every
stored text, DELETE /messages forgets them. Standard library only.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MESSAGES: list[str] = []
LOCK = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def _reply(self, status: int, body: object = None) -> None:
        data = json.dumps(body if body is not None else {}).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:
        if self.path != "/hook":
            self._reply(404)
            return
        payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        texts = [a.get("text", "") for a in payload.get("attachments", [])] or [payload.get("text", "")]
        with LOCK:
            MESSAGES.extend(texts)
        self._reply(200)

    def do_GET(self) -> None:
        if self.path != "/messages":
            self._reply(404)
            return
        with LOCK:
            self._reply(200, list(MESSAGES))

    def do_DELETE(self) -> None:
        with LOCK:
            MESSAGES.clear()
        self._reply(200)

    def log_message(self, *args) -> None:
        return


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8099), Handler).serve_forever()
