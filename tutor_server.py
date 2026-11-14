#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
N3 Studio Neural Audio Tutor HTTP Server:
- Supports HTTP 206 Partial Content (Accept-Ranges: bytes) for zero-stall Safari/Android Chrome <audio> playback
- Provides GET /api/state, POST /api/record, POST /api/session for live dual-device sync
"""
import datetime
import http.server
import json
import os
import re
import socketserver

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(BASE_DIR, "practice_log.jsonl")
SESSION_PATH = os.path.join(BASE_DIR, "live_session_state.json")


def load_session_state():
    if os.path.exists(SESSION_PATH):
        try:
            with open(SESSION_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    done_ids = []
    overrides = {}
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                qid = rec.get("id", "")
                pt = rec.get("point", "")
                ok = str(rec.get("correct", "")).lower() == "true"
                again = str(rec.get("ask_again", "")).lower() == "true"
                if ok and not again:
                    if qid and qid not in done_ids:
                        done_ids.append(qid)
                    if pt:
                        overrides[pt] = "done"
                else:
                    if qid in done_ids:
                        done_ids.remove(qid)
                    if pt:
                        overrides[pt] = "todo"
    return {"doneIds": done_ids, "requeuedIds": [], "masteryOverrides": overrides}


class TutorHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def end_headers(self):
        clean = self.path.split("?", 1)[0]
        if clean.endswith(".html") or clean in ("/", "") or clean.endswith("sw.js") or clean.startswith("/api/"):
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    def send_json(self, payload: dict, status: int = 200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        clean = self.path.split("?", 1)[0]
        if clean == "/api/state":
            self.send_json({"ok": True, "session": load_session_state()})
            return

        range_hdr = self.headers.get("Range")
        if range_hdr:
            fs_path = self.translate_path(self.path)
            if os.path.isfile(fs_path):
                m = re.match(r"bytes=(\d*)-(\d*)", range_hdr)
                if m:
                    file_size = os.path.getsize(fs_path)
                    start = int(m.group(1)) if m.group(1) else 0
                    end = int(m.group(2)) if m.group(2) else file_size - 1
                    end = min(end, file_size - 1)
                    if 0 <= start <= end < file_size:
                        length = end - start + 1
                        ctype = self.guess_type(fs_path)
                        self.send_response(206)
                        self.send_header("Content-Type", ctype)
                        self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                        self.send_header("Content-Length", str(length))
                        self.end_headers()
                        with open(fs_path, "rb") as f:
                            f.seek(start)
                            self.wfile.write(f.read(length))
                        return
        super().do_GET()

    def do_POST(self):
        clean = self.path.split("?", 1)[0]
        if clean in ("/api/record", "/api/session"):
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            try:
                data = json.loads(raw)
            except Exception:
                data = {}

            if clean == "/api/record":
                session_obj = data.pop("session", None)
                data["ts"] = datetime.datetime.now().astimezone().isoformat()
                with open(LOG_PATH, "a", encoding="utf-8") as f:
                    f.write(json.dumps(data, ensure_ascii=False) + "\n")
                if isinstance(session_obj, dict):
                    with open(SESSION_PATH, "w", encoding="utf-8") as f:
                        json.dump(session_obj, f, ensure_ascii=False, indent=2)
            elif clean == "/api/session" and isinstance(data, dict):
                with open(SESSION_PATH, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

            self.send_json({"ok": True})
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
