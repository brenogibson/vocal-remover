#!/usr/bin/env python3
"""Servidor web para download das musicas processadas pelo vocal-remover."""

import json
import os
import socket
import sys
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

SEPARATED_DIR = Path(__file__).resolve().parent.parent / "separated"
PORT = 8080

# modelo -> { arquivo -> (label, css_class) }
MODELS = {
    "htdemucs_ft": {
        "label": "Vocal Remover",
        "stems": {
            "no_vocals.mp3": ("Instrumental", "instrumental"),
            "vocals.mp3": ("Vocais", "vocals"),
        },
    },
    "htdemucs_6s": {
        "label": "Guitar Remover",
        "stems": {
            "no_guitar.mp3": ("Sem Guitarra", "no-guitar"),
            "guitar.mp3": ("Guitarra", "guitar"),
        },
    },
}

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vocal Remover - Downloads</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #0f0f0f;
    color: #e0e0e0;
    min-height: 100vh;
    padding: 2rem 1rem;
  }
  .container { max-width: 720px; margin: 0 auto; }
  h1 {
    text-align: center;
    font-size: 1.8rem;
    margin-bottom: .4rem;
    color: #fff;
  }
  .subtitle {
    text-align: center;
    color: #888;
    margin-bottom: 2rem;
    font-size: .95rem;
  }
  .empty {
    text-align: center;
    color: #666;
    margin-top: 4rem;
    font-size: 1.1rem;
  }
  .song {
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    border-radius: 10px;
    padding: 1.2rem 1.5rem;
    margin-bottom: 1rem;
  }
  .song-name {
    font-size: 1.15rem;
    font-weight: 600;
    color: #fff;
    margin-bottom: .8rem;
  }
  .stems { display: flex; gap: .6rem; flex-wrap: wrap; }
  .stem-btn {
    display: inline-flex;
    align-items: center;
    gap: .4rem;
    padding: .5rem 1rem;
    border-radius: 6px;
    text-decoration: none;
    font-size: .9rem;
    font-weight: 500;
    transition: opacity .15s;
  }
  .stem-btn:hover { opacity: .85; }
  .stem-btn.instrumental { background: #1e3a5f; color: #7cb8f0; }
  .stem-btn.vocals { background: #3d1f4e; color: #c88edb; }
  .stem-btn.no-guitar { background: #1e4a3a; color: #7cf0b8; }
  .stem-btn.guitar { background: #4a3a1e; color: #f0c87c; }
  .model-label {
    font-size: .75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: .05em;
    color: #666;
    margin-bottom: .3rem;
  }
  .icon { font-size: 1rem; }
</style>
</head>
<body>
<div class="container">
  <h1>Music Separator</h1>
  <p class="subtitle">Musicas processadas</p>
  {{CONTENT}}
</div>
</body>
</html>
"""

SONG_TEMPLATE = """\
<div class="song">
  <div class="model-label">{{MODEL}}</div>
  <div class="song-name">{{NAME}}</div>
  <div class="stems">{{STEMS}}</div>
</div>
"""

STEM_BUTTON = (
    '<a class="stem-btn {{CLASS}}" href="/download/{{PATH}}" download>'
    '<span class="icon">&#11015;</span> {{LABEL}} <small>({{SIZE}})</small></a>'
)


def format_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def get_songs() -> list[dict]:
    songs = []
    if not SEPARATED_DIR.is_dir():
        return songs
    for model_name, model_info in MODELS.items():
        model_dir = SEPARATED_DIR / model_name
        if not model_dir.is_dir():
            continue
        for song_dir in sorted(model_dir.iterdir()):
            if not song_dir.is_dir():
                continue
            stems = []
            for fname, (label, css_class) in model_info["stems"].items():
                fpath = song_dir / fname
                if fpath.is_file():
                    stems.append(
                        {
                            "file": fname,
                            "label": label,
                            "size": format_size(fpath.stat().st_size),
                            "path": f"{model_name}/{song_dir.name}/{fname}",
                            "css_class": css_class,
                        }
                    )
            if stems:
                songs.append(
                    {
                        "name": song_dir.name,
                        "model": model_info["label"],
                        "stems": stems,
                    }
                )
    return songs


def render_index() -> str:
    songs = get_songs()
    if not songs:
        content = '<p class="empty">Nenhuma musica processada ainda.</p>'
    else:
        parts = []
        for song in songs:
            stems_html = ""
            for s in song["stems"]:
                stems_html += (
                    STEM_BUTTON.replace("{{CLASS}}", s["css_class"])
                    .replace("{{PATH}}", urllib.parse.quote(s["path"]))
                    .replace("{{LABEL}}", s["label"])
                    .replace("{{SIZE}}", s["size"])
                )
            parts.append(
                SONG_TEMPLATE.replace("{{MODEL}}", song["model"])
                .replace("{{NAME}}", song["name"])
                .replace("{{STEMS}}", stems_html)
            )
        content = "\n".join(parts)
    return HTML_TEMPLATE.replace("{{CONTENT}}", content)


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        path = urllib.parse.unquote(self.path)

        if path == "/" or path == "":
            body = render_index().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/api/songs":
            songs = get_songs()
            body = json.dumps(songs, ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path.startswith("/download/"):
            rel = path[len("/download/"):]
            file_path = (SEPARATED_DIR / rel).resolve()
            # impedir path traversal
            if not str(file_path).startswith(str(SEPARATED_DIR)):
                self.send_error(403)
                return
            if not file_path.is_file():
                self.send_error(404)
                return
            size = file_path.stat().st_size
            self.send_response(200)
            self.send_header("Content-Type", "audio/mpeg")
            self.send_header("Content-Length", str(size))
            fname = file_path.name
            self.send_header(
                "Content-Disposition", f'attachment; filename="{fname}"'
            )
            self.end_headers()
            with open(file_path, "rb") as f:
                while chunk := f.read(65536):
                    self.wfile.write(chunk)
            return

        self.send_error(404)

    def log_message(self, format, *args):
        print(f"  {self.address_string()} - {format % args}")


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    local_ip = get_local_ip()

    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"Vocal Remover - Servidor de downloads")
    print(f"  Local:   http://localhost:{port}")
    print(f"  Rede:    http://{local_ip}:{port}")
    print(f"  Musicas: {SEPARATED_DIR}/")
    print()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")
        server.server_close()


if __name__ == "__main__":
    main()
