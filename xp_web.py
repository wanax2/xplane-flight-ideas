"""
xp_web.py - hand the briefing to your phone or tablet, and back up your data.

The briefing sheet the app already builds is served from a tiny web server on your
own network, so you can open it on a phone next to the yoke. The server only runs
while you leave the window open, serves that one page, and is reachable only from
your own network - but it is reachable by anything on that network, so don't leave
it running on a network you don't trust.
"""
from __future__ import annotations

import http.server
import socket
import threading
import time
import zipfile
from pathlib import Path

BACKUP_FILES = ["config.json", "logbook.json", "trips.json", "spots.json", "career.json",
                "profiles.json", "aircraft.json"]


def lan_ip():
    """This machine's address on the local network (no packets are actually sent)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"
    finally:
        s.close()


class BriefingServer:
    """Serves one page (and its little icon) until you stop it."""

    def __init__(self, html, port=8731, title="Flight briefing"):
        self.html = html.encode("utf-8")
        self.title = title
        self.hits = 0
        self.started = time.time()
        self.httpd = None
        self.port = port
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):                                   # noqa: N802
                if self.path in ("/", "/index.html", "/briefing.html"):
                    outer.hits += 1
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(outer.html)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(outer.html)
                else:
                    self.send_error(404)

            def log_message(self, *a):                          # keep the console quiet
                pass

        for p in range(port, port + 20):
            try:
                self.httpd = http.server.ThreadingHTTPServer(("0.0.0.0", p), Handler)
                self.port = p
                break
            except OSError:
                continue
        if self.httpd is None:
            raise OSError("No free port for the briefing server.")
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    @property
    def url(self):
        return f"http://{lan_ip()}:{self.port}/"

    def stop(self):
        if self.httpd:
            try:
                self.httpd.shutdown()
                self.httpd.server_close()
            except Exception:
                pass
            self.httpd = None


# ==========================================================================
# Backup and restore
# ==========================================================================
def backup(cache_dir: Path, out_file: Path):
    """Everything you'd hate to lose: settings, logbook, trips, spots, career."""
    cache_dir, out_file = Path(cache_dir), Path(out_file)
    n = 0
    with zipfile.ZipFile(out_file, "w", zipfile.ZIP_DEFLATED) as z:
        for name in BACKUP_FILES:
            f = cache_dir / name
            if f.exists():
                z.write(f, name)
                n += 1
        for f in cache_dir.glob("*.json"):
            if f.name not in BACKUP_FILES:
                z.write(f, f.name)
                n += 1
    return n


def restore(cache_dir: Path, in_file: Path):
    """Put a backup back. Existing files are kept as .bak first."""
    cache_dir, in_file = Path(cache_dir), Path(in_file)
    cache_dir.mkdir(parents=True, exist_ok=True)
    done = []
    with zipfile.ZipFile(in_file) as z:
        for name in z.namelist():
            if "/" in name or "\\" in name or not name.endswith(".json"):
                continue                     # only the flat .json files we wrote
            target = cache_dir / name
            if target.exists():
                try:
                    target.replace(target.with_suffix(".json.bak"))
                except OSError:
                    pass
            target.write_bytes(z.read(name))
            done.append(name)
    return done
