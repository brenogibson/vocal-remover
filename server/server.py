#!/usr/bin/env python3
"""Servidor web para upload, processamento e download de musicas separadas."""

import cgi
import io
import json
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

REPO_DIR      = Path(__file__).resolve().parent.parent
SEPARATED_DIR = REPO_DIR / "separated"
UPLOADS_DIR   = REPO_DIR / "uploads"
PORT          = 8080

MODELS = {
    "htdemucs_ft": {
        "label":  "Vocal Remover",
        "script": REPO_DIR / "remove_vocals.sh",
        "stems": {
            "no_vocals.mp3": ("Instrumental", "instrumental"),
            "vocals.mp3":    ("Vocais",        "vocals"),
        },
    },
    "htdemucs_6s": {
        "label":  "Guitar Remover",
        "script": REPO_DIR / "remove_guitar.sh",
        "stems": {
            "no_guitar.mp3": ("Sem Guitarra", "no-guitar"),
            "guitar.mp3":    ("Guitarra",     "guitar"),
        },
    },
}

JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()

# ──────────────────────────────────────────────────────────────────────────────
# HTML
# ──────────────────────────────────────────────────────────────────────────────

HTML = """\
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Music Separator</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: #0f0f0f; color: #e0e0e0;
  min-height: 100vh; padding: 2rem 1rem;
}
.container { max-width: 760px; margin: 0 auto; }
h1 { text-align:center; font-size:1.8rem; color:#fff; margin-bottom:.3rem; }
.subtitle { text-align:center; color:#888; margin-bottom:2.5rem; font-size:.95rem; }
h2 { font-size:1.05rem; color:#aaa; margin-bottom:.8rem; text-transform:uppercase; letter-spacing:.05em; }

.card {
  background:#1a1a1a; border:1px solid #2a2a2a;
  border-radius:10px; padding:1.5rem; margin-bottom:1.5rem;
}

/* upload */
.upload-area {
  border:2px dashed #333; border-radius:8px; padding:1.8rem;
  text-align:center; cursor:pointer;
  transition:border-color .2s, background .2s;
}
.upload-area:hover, .upload-area.drag { border-color:#555; background:#222; }
.upload-area input[type=file] { display:none; }
.upload-area .hint { color:#666; font-size:.85rem; margin-top:.3rem; }
#upload-status { font-size:.85rem; color:#7cb8f0; margin-top:.8rem; min-height:1.2em; text-align:center; }

/* uploads list */
.upload-item {
  background:#111; border:1px solid #2a2a2a; border-radius:8px;
  padding:.9rem 1.1rem; margin-bottom:.6rem;
  display:flex; align-items:center; gap:1rem; flex-wrap:wrap;
}
.upload-item-name { flex:1; font-weight:600; font-size:.95rem; min-width:0; word-break:break-all; }
.upload-item-size { font-size:.8rem; color:#666; white-space:nowrap; }
.mode-btns { display:flex; gap:.5rem; flex-wrap:wrap; }
.mode-btn {
  padding:.4rem .85rem; border-radius:6px; border:none;
  font-size:.82rem; font-weight:600; cursor:pointer;
  transition:opacity .15s;
}
.mode-btn:hover { opacity:.8; }
.mode-btn.vocals { background:#3d1f4e; color:#c88edb; }
.mode-btn.guitar { background:#4a3a1e; color:#f0c87c; }
.mode-btn.both   { background:#1e3a5f; color:#7cb8f0; }
.mode-btn:disabled { opacity:.3; cursor:not-allowed; }

/* jobs */
.job {
  background:#1a1a1a; border:1px solid #2a2a2a; border-radius:8px;
  padding:.9rem 1.1rem; margin-bottom:.6rem;
  display:flex; align-items:flex-start; gap:.8rem;
}
.job-info { flex:1; }
.job-name  { font-weight:600; font-size:.95rem; }
.job-model { font-size:.75rem; color:#666; margin-top:.1rem; }
.job-log {
  font-size:.73rem; color:#888; white-space:pre-wrap;
  max-height:72px; overflow-y:auto; margin-top:.4rem; font-family:monospace;
}
.badge {
  font-size:.72rem; font-weight:700; padding:.22rem .55rem;
  border-radius:4px; white-space:nowrap; text-transform:uppercase; flex-shrink:0;
}
.badge.running { background:#1e3a5f; color:#7cb8f0; }
.badge.done    { background:#1e4a3a; color:#7cf0b8; }
.badge.error   { background:#4a1e1e; color:#f07c7c; }

/* downloads */
.song {
  background:#1a1a1a; border:1px solid #2a2a2a;
  border-radius:10px; padding:1.1rem 1.4rem; margin-bottom:.8rem;
}
.song-model { font-size:.72rem; color:#555; text-transform:uppercase; letter-spacing:.05em; margin-bottom:.3rem; }
.song-name  { font-size:1rem; font-weight:600; color:#fff; margin-bottom:.7rem; }
.stems { display:flex; gap:.5rem; flex-wrap:wrap; }
.stem-btn {
  display:inline-flex; align-items:center; gap:.35rem;
  padding:.45rem .9rem; border-radius:6px;
  text-decoration:none; font-size:.85rem; font-weight:500;
  transition:opacity .15s;
}
.stem-btn:hover { opacity:.85; }
.stem-btn.instrumental { background:#1e3a5f; color:#7cb8f0; }
.stem-btn.vocals       { background:#3d1f4e; color:#c88edb; }
.stem-btn.no-guitar    { background:#1e4a3a; color:#7cf0b8; }
.stem-btn.guitar       { background:#4a3a1e; color:#f0c87c; }
.empty { text-align:center; color:#555; padding:1.5rem 0; font-size:.9rem; }
</style>
</head>
<body>
<div class="container">
  <h1>Music Separator</h1>
  <p class="subtitle">Separe vocais e guitarras com IA</p>

  <!-- 1. Upload -->
  <div class="card">
    <h2>Upload</h2>
    <div class="upload-area" id="drop-zone">
      <label style="cursor:pointer; display:block;">
        <div style="font-size:2rem;">&#127925;</div>
        <div style="margin-top:.4rem;">Clique ou arraste o arquivo aqui</div>
        <div class="hint">MP3, WAV, FLAC, OGG, M4A</div>
        <input type="file" id="audio-input" accept=".mp3,.wav,.flac,.ogg,.m4a" multiple>
      </label>
    </div>
    <div id="upload-status"></div>
  </div>

  <!-- 2. Arquivos enviados -->
  <div class="card" id="uploads-card">
    <h2>Arquivos enviados</h2>
    <div id="uploads-list"><p class="empty">Nenhum arquivo enviado ainda.</p></div>
  </div>

  <!-- 3. Jobs -->
  <div class="card" id="jobs-card" style="display:none">
    <h2>Processando</h2>
    <div id="jobs-list"></div>
  </div>

  <!-- 4. Downloads -->
  <div class="card">
    <h2>Arquivos processados</h2>
    <div id="songs-list">{{SONGS_HTML}}</div>
  </div>
</div>

<script>
// ── upload via drag/click ──
const audioInput   = document.getElementById('audio-input');
const dropZone     = document.getElementById('drop-zone');
const uploadStatus = document.getElementById('upload-status');

audioInput.addEventListener('change', () => uploadFiles(audioInput.files));

dropZone.addEventListener('dragover',  e => { e.preventDefault(); dropZone.classList.add('drag'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag'));
dropZone.addEventListener('drop', e => {
  e.preventDefault(); dropZone.classList.remove('drag');
  uploadFiles(e.dataTransfer.files);
});

async function uploadFiles(files) {
  for (const file of files) {
    uploadStatus.textContent = `Enviando ${file.name}...`;
    const fd = new FormData();
    fd.append('audio', file);
    const res  = await fetch('/upload', { method:'POST', body:fd });
    const data = await res.json();
    if (data.error) {
      uploadStatus.textContent = `Erro: ${data.error}`;
    } else {
      uploadStatus.textContent = `${file.name} enviado!`;
      refreshUploads();
    }
  }
}

// ── uploads list ──
async function refreshUploads() {
  const r     = await fetch('/api/uploads');
  const files = await r.json();
  const el    = document.getElementById('uploads-list');

  if (!files.length) {
    el.innerHTML = '<p class="empty">Nenhum arquivo enviado ainda.</p>';
    return;
  }

  el.innerHTML = files.map(f => `
    <div class="upload-item">
      <span class="upload-item-name">&#127925; ${f.name}</span>
      <span class="upload-item-size">${f.size}</span>
      <div class="mode-btns">
        <button class="mode-btn vocals" onclick="process('${f.name}','vocals',this)">&#127908; Vocais</button>
        <button class="mode-btn guitar" onclick="process('${f.name}','guitar',this)">&#127928; Guitarra</button>
        <button class="mode-btn both"   onclick="process('${f.name}','both',this)">&#10024; Ambos</button>
      </div>
    </div>`).join('');
}

async function process(filename, mode, btn) {
  btn.disabled = true;
  const res  = await fetch('/process', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename, mode }),
  });
  const data = await res.json();
  btn.disabled = false;
  if (data.job_ids) data.job_ids.forEach(id => pollJob(id));
}

// ── job polling ──
function pollJob(id) {
  document.getElementById('jobs-card').style.display = '';
  const list = document.getElementById('jobs-list');

  const el = document.createElement('div');
  el.className = 'job';
  el.innerHTML = `<div class="job-info">
    <div class="job-name"></div>
    <div class="job-model"></div>
    <div class="job-log"></div>
  </div><span class="badge running">aguardando</span>`;
  list.prepend(el);

  const iv = setInterval(async () => {
    const r = await fetch('/api/job/' + id);
    const j = await r.json();
    el.querySelector('.job-name').textContent  = j.song  ?? '';
    el.querySelector('.job-model').textContent = j.model ?? '';
    const logEl = el.querySelector('.job-log');
    logEl.textContent = j.log ?? '';
    logEl.scrollTop   = logEl.scrollHeight;
    const badge = el.querySelector('.badge');
    badge.className   = 'badge ' + j.status;
    badge.textContent = { running:'processando', done:'concluido', error:'erro' }[j.status] ?? j.status;
    if (j.status === 'done' || j.status === 'error') {
      clearInterval(iv);
      if (j.status === 'done') refreshSongs();
    }
  }, 1500);
}

// ── songs / downloads ──
async function refreshSongs() {
  const r     = await fetch('/api/songs');
  const songs = await r.json();
  const el    = document.getElementById('songs-list');
  if (!songs.length) { el.innerHTML = '<p class="empty">Nenhuma musica processada ainda.</p>'; return; }
  el.innerHTML = songs.map(s => `
    <div class="song">
      <div class="song-model">${s.model}</div>
      <div class="song-name">${s.name}</div>
      <div class="stems">${s.stems.map(st =>
        `<a class="stem-btn ${st.css_class}" href="/download/${encodeURIComponent(st.path)}" download>
          &#11015; ${st.label} <small>(${st.size})</small></a>`
      ).join('')}</div>
    </div>`).join('');
}

// load uploads on page ready
refreshUploads();
</script>
</body>
</html>
"""


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

AUDIO_EXTS = {".mp3", ".wav", ".flac", ".ogg", ".m4a"}


def format_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def get_uploads() -> list[dict]:
    if not UPLOADS_DIR.is_dir():
        return []
    files = []
    for f in sorted(UPLOADS_DIR.iterdir()):
        if f.is_file() and f.suffix.lower() in AUDIO_EXTS:
            files.append({"name": f.name, "size": format_size(f.stat().st_size)})
    return files


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
                    stems.append({
                        "file":      fname,
                        "label":     label,
                        "size":      format_size(fpath.stat().st_size),
                        "path":      f"{model_name}/{song_dir.name}/{fname}",
                        "css_class": css_class,
                    })
            if stems:
                songs.append({"name": song_dir.name, "model": model_info["label"], "stems": stems})
    return songs


def render_songs_html(songs: list[dict]) -> str:
    if not songs:
        return '<p class="empty">Nenhuma musica processada ainda.</p>'
    parts = []
    for s in songs:
        stems_html = "".join(
            f'<a class="stem-btn {st["css_class"]}" '
            f'href="/download/{urllib.parse.quote(st["path"])}" download>'
            f'&#11015; {st["label"]} <small>({st["size"]})</small></a>'
            for st in s["stems"]
        )
        parts.append(
            f'<div class="song">'
            f'<div class="song-model">{s["model"]}</div>'
            f'<div class="song-name">{s["name"]}</div>'
            f'<div class="stems">{stems_html}</div>'
            f'</div>'
        )
    return "\n".join(parts)


def start_job(job_id: str, script: Path, audio_path: Path, model_label: str, song_name: str):
    with JOBS_LOCK:
        JOBS[job_id] = {"status": "running", "model": model_label, "song": song_name, "log": ""}

    def run():
        status = "error"
        try:
            proc = subprocess.Popen(
                ["bash", str(script), str(audio_path), str(SEPARATED_DIR)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            log_lines: list[str] = []
            for line in proc.stdout:
                log_lines.append(line)
                with JOBS_LOCK:
                    JOBS[job_id]["log"] = "".join(log_lines[-40:])
            proc.wait()
            status = "done" if proc.returncode == 0 else "error"
        except Exception as exc:
            with JOBS_LOCK:
                JOBS[job_id]["log"] += f"\n{exc}"
        finally:
            with JOBS_LOCK:
                JOBS[job_id]["status"] = status

    threading.Thread(target=run, daemon=True).start()


# ──────────────────────────────────────────────────────────────────────────────
# HTTP handler
# ──────────────────────────────────────────────────────────────────────────────

class Handler(SimpleHTTPRequestHandler):

    def do_GET(self):
        path = urllib.parse.unquote(self.path.split("?", 1)[0])

        if path in ("/", ""):
            songs_html = render_songs_html(get_songs())
            body = HTML.replace("{{SONGS_HTML}}", songs_html).encode()
            self._respond(200, "text/html; charset=utf-8", body)
            return

        if path == "/api/uploads":
            body = json.dumps(get_uploads(), ensure_ascii=False).encode()
            self._respond(200, "application/json; charset=utf-8", body)
            return

        if path == "/api/songs":
            body = json.dumps(get_songs(), ensure_ascii=False).encode()
            self._respond(200, "application/json; charset=utf-8", body)
            return

        if path.startswith("/api/job/"):
            job_id = path[len("/api/job/"):]
            with JOBS_LOCK:
                job = dict(JOBS.get(job_id, {"status": "unknown"}))
            body = json.dumps(job, ensure_ascii=False).encode()
            self._respond(200, "application/json; charset=utf-8", body)
            return

        if path.startswith("/download/"):
            self._serve_file(path[len("/download/"):])
            return

        self.send_error(404)

    def do_POST(self):
        path = urllib.parse.unquote(self.path.split("?", 1)[0])

        if path == "/upload":
            self._handle_upload()
            return

        if path == "/process":
            self._handle_process()
            return

        self.send_error(404)

    # ── /upload — save file only ──────────────────────────────────────────────

    def _handle_upload(self):
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self.send_error(400)
            return

        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)

        environ = {
            "REQUEST_METHOD": "POST",
            "CONTENT_TYPE":   content_type,
            "CONTENT_LENGTH": str(length),
        }
        fs = cgi.FieldStorage(fp=io.BytesIO(raw), environ=environ, keep_blank_values=True)

        audio_field = fs["audio"] if "audio" in fs else None
        if audio_field is None or not getattr(audio_field, "filename", None):
            self._json_error(400, "Nenhum arquivo enviado.")
            return

        orig_name = Path(audio_field.filename).name
        if Path(orig_name).suffix.lower() not in AUDIO_EXTS:
            self._json_error(400, "Formato nao suportado.")
            return

        safe_name = "".join(c if c.isalnum() or c in "-_." else "_" for c in orig_name)
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        dest = UPLOADS_DIR / safe_name
        with open(dest, "wb") as f:
            f.write(audio_field.file.read())

        body = json.dumps({"ok": True, "name": safe_name}).encode()
        self._respond(200, "application/json; charset=utf-8", body)

    # ── /process — start job for an already-uploaded file ────────────────────

    def _handle_process(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(length))
        except Exception:
            self._json_error(400, "JSON invalido.")
            return

        filename = payload.get("filename", "").strip()
        mode     = payload.get("mode", "").strip()

        if not filename or mode not in ("vocals", "guitar", "both"):
            self._json_error(400, "Parametros invalidos.")
            return

        safe_name = "".join(c if c.isalnum() or c in "-_." else "_" for c in Path(filename).name)
        src = UPLOADS_DIR / safe_name
        if not src.is_file():
            self._json_error(404, "Arquivo nao encontrado.")
            return

        ts      = str(int(time.time()))
        job_ids = []

        if mode in ("vocals", "both"):
            jid = f"{ts}_vocals"
            job_ids.append(jid)
            audio = src
            if mode == "both":
                audio = UPLOADS_DIR / f"{src.stem}_voc_copy{src.suffix}"
                shutil.copy2(src, audio)
            start_job(jid, MODELS["htdemucs_ft"]["script"], audio,
                      MODELS["htdemucs_ft"]["label"], src.stem)

        if mode in ("guitar", "both"):
            jid = f"{ts}_guitar"
            job_ids.append(jid)
            audio = src
            if mode == "both":
                audio = UPLOADS_DIR / f"{src.stem}_git_copy{src.suffix}"
                shutil.copy2(src, audio)
            start_job(jid, MODELS["htdemucs_6s"]["script"], audio,
                      MODELS["htdemucs_6s"]["label"], src.stem)

        body = json.dumps({"ok": True, "job_ids": job_ids}).encode()
        self._respond(200, "application/json; charset=utf-8", body)

    # ── file download ─────────────────────────────────────────────────────────

    def _serve_file(self, rel: str):
        file_path = (SEPARATED_DIR / rel).resolve()
        if not str(file_path).startswith(str(SEPARATED_DIR.resolve())):
            self.send_error(403)
            return
        if not file_path.is_file():
            self.send_error(404)
            return
        size = file_path.stat().st_size
        self.send_response(200)
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Content-Length", str(size))
        self.send_header("Content-Disposition", f'attachment; filename="{file_path.name}"')
        self.end_headers()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                self.wfile.write(chunk)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _respond(self, code: int, content_type: str, body: bytes):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json_error(self, code: int, msg: str):
        body = json.dumps({"error": msg}).encode()
        self._respond(code, "application/json; charset=utf-8", body)

    def log_message(self, fmt, *args):
        print(f"  {self.address_string()} - {fmt % args}")


# ──────────────────────────────────────────────────────────────────────────────

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
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    local_ip = get_local_ip()
    server = HTTPServer(("0.0.0.0", port), Handler)
    print("Music Separator")
    print(f"  Local: http://localhost:{port}")
    print(f"  Rede:  http://{local_ip}:{port}")
    print()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")
        server.server_close()


if __name__ == "__main__":
    main()
