#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import datetime
import http.server
import json
import os
import socketserver

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(BASE_DIR, "practice_log.jsonl")


class TutorHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def end_headers(self):
        if self.path.endswith(".html") or self.path in ("/", "") or self.path.endswith("sw.js"):
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        super().end_headers()

    def do_POST(self):
        if self.path == "/api/record":
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            try:
                rec = json.loads(raw)
            except Exception:
                rec = {"raw": raw}
            rec["ts"] = datetime.datetime.now().astimezone().isoformat()
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            body = json.dumps({"ok": True}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

    def log_message(self, fmt, *args):
        pass


class ThreadedServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    with ThreadedServer(("127.0.0.1", 8765), TutorHandler) as httpd:
        print("Serving N3 Studio Neural Audio Tutor on http://127.0.0.1:8765/", flush=True)
        httpd.serve_forever()
