#!/usr/bin/env python3
"""API do ranking do Ryuk: Voo Noturno.

Só stdlib. Escuta em loopback; o nginx expõe /api/ e o túnel Cloudflare publica.

Rotas:
  POST /api/claim   {"name"}                         -> reserva um apelido único e devolve o token do aparelho
  POST /api/score   {"token","meters","souls","secs"} -> registra a corrida; guarda só o melhor resultado
  GET  /api/top?n=50                                 -> ranking
  GET  /<arquivo>                                    -> arquivos do jogo (web/)
"""
import hashlib
import json
import os
import re
import secrets
import sqlite3
import time
import unicodedata
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

DB = os.environ.get("RYUK_DB", os.path.expanduser("~/.local/share/ryuk/ranking.db"))
PORT = int(os.environ.get("RYUK_PORT", "8797"))
WEB = os.path.realpath(os.environ.get("RYUK_WEB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "web")))
MIME = {
    ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
    ".json": "application/json", ".webmanifest": "application/manifest+json", ".png": "image/png",
    ".glb": "model/gltf-binary", ".svg": "image/svg+xml", ".ico": "image/x-icon",
}

NAME_RE = re.compile(r"^[\w .\-]{3,14}$", re.UNICODE)
# Palavrões e ofensas comuns: o ranking é de crianças.
BAD = {
    "porra", "caralho", "merda", "bosta", "puta", "puto", "viado", "buceta", "piroca",
    "foder", "fodase", "cacete", "otario", "babaca", "corno", "vagabund", "arrombad",
    "desgraca", "fdp", "vsf", "pqp", "tnc", "krl", "crl", "cuzao", "bunda", "penis",
    "vagina", "sexo", "nazi", "hitler", "fuck", "shit", "bitch", "dick", "pussy",
}
LIMITS = {"claim": (8, 3600), "score": (150, 3600)}
_hits = defaultdict(deque)


def key_of(name):
    """Chave de unicidade: sem acento, minúscula, só letras e números (Isa = ísa = I.S.A)."""
    n = unicodedata.normalize("NFKD", name)
    n = "".join(c for c in n if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]", "", n)


def is_bad(key):
    leet = key.translate(str.maketrans("013457", "oieast"))
    return any(w in key or w in leet for w in BAD)


def db():
    con = sqlite3.connect(DB, timeout=10)
    con.row_factory = sqlite3.Row
    return con


def init():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    with db() as con:
        con.execute("PRAGMA journal_mode=WAL")
        con.executescript("""
            CREATE TABLE IF NOT EXISTS players (
                key TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                created_at INTEGER NOT NULL,
                best INTEGER NOT NULL DEFAULT 0,
                best_meters INTEGER NOT NULL DEFAULT 0,
                best_souls INTEGER NOT NULL DEFAULT 0,
                best_at INTEGER,
                runs INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS players_best ON players(best DESC, best_at ASC);
        """)


def limited(ip, kind):
    n, win = LIMITS[kind]
    q = _hits[(ip, kind)]
    now = time.time()
    while q and q[0] < now - win:
        q.popleft()
    if len(q) >= n:
        return True
    q.append(now)
    return False


def rank_of(con, best, best_at):
    return con.execute(
        "SELECT COUNT(*) + 1 FROM players WHERE best > ? OR (best = ? AND best_at < ?)",
        (best, best, best_at or 0),
    ).fetchone()[0]


class H(BaseHTTPRequestHandler):
    server_version = "ryuk"

    def log_message(self, fmt, *args):
        pass

    def ip(self):
        return self.headers.get("CF-Connecting-IP") or self.headers.get("X-Real-IP") or self.client_address[0]

    def send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > 2048:
            return None
        try:
            data = json.loads(self.rfile.read(n))
            return data if isinstance(data, dict) else None
        except ValueError:
            return None

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/api/health":
            return self.send(200, {"ok": True})
        if not u.path.startswith("/api/"):
            return self.static(u.path)
        if u.path != "/api/top":
            return self.send(404, {"erro": "nao_encontrado"})
        try:
            n = max(1, min(100, int(parse_qs(u.query).get("n", ["50"])[0])))
        except ValueError:
            n = 50
        with db() as con:
            rows = con.execute(
                "SELECT name, best, best_meters, best_souls FROM players WHERE best > 0 "
                "ORDER BY best DESC, best_at ASC LIMIT ?", (n,)).fetchall()
            total = con.execute("SELECT COUNT(*) FROM players WHERE best > 0").fetchone()[0]
        top = [{"pos": i + 1, "name": r["name"], "score": r["best"], "meters": r["best_meters"], "souls": r["best_souls"]}
               for i, r in enumerate(rows)]
        self.send(200, {"top": top, "total": total})

    def static(self, path):
        rel = "index.html" if path in ("", "/") else path.lstrip("/")
        full = os.path.realpath(os.path.join(WEB, rel))
        ext = os.path.splitext(full)[1].lower()
        if not full.startswith(WEB + os.sep) or not os.path.isfile(full) or ext not in MIME:
            return self.send(404, {"erro": "nao_encontrado"})
        with open(full, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", MIME[ext])
        self.send_header("Content-Length", str(len(body)))
        # HTML, manifest e service worker sempre frescos; o resto o service worker versiona.
        fresh = ext in (".html", ".webmanifest") or rel == "sw.js"
        self.send_header("Cache-Control", "no-cache" if fresh else "public, max-age=86400")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def do_HEAD(self):
        self.send_response(405)
        self.end_headers()

    def do_POST(self):
        u = urlparse(self.path)
        data = self.body()
        if data is None:
            return self.send(400, {"erro": "corpo_invalido"})
        if u.path == "/api/claim":
            return self.claim(data)
        if u.path == "/api/score":
            return self.score(data)
        self.send(404, {"erro": "nao_encontrado"})

    def claim(self, data):
        if limited(self.ip(), "claim"):
            return self.send(429, {"erro": "muitas_tentativas"})
        name = re.sub(r"\s+", " ", str(data.get("name", ""))).strip()
        key = key_of(name)
        if not NAME_RE.match(name) or len(key) < 3:
            return self.send(400, {"erro": "nome_invalido"})
        if is_bad(key):
            return self.send(400, {"erro": "nome_feio"})
        token = secrets.token_urlsafe(24)
        th = hashlib.sha256(token.encode()).hexdigest()
        try:
            with db() as con:
                con.execute("INSERT INTO players (key, name, token_hash, created_at) VALUES (?, ?, ?, ?)",
                            (key, name, th, int(time.time())))
        except sqlite3.IntegrityError:
            return self.send(409, {"erro": "nome_em_uso"})
        self.send(201, {"name": name, "token": token})

    def score(self, data):
        if limited(self.ip(), "score"):
            return self.send(429, {"erro": "muitas_tentativas"})
        try:
            meters = int(data.get("meters", 0))
            souls = int(data.get("souls", 0))
            secs = float(data.get("secs", 0))
        except (TypeError, ValueError):
            return self.send(400, {"erro": "valores_invalidos"})
        # Sanidade: velocidade máxima do jogo é 26 m/s, e não cabem mais de ~1 alma a cada 2 m.
        if meters < 0 or souls < 0 or secs < 3 or meters > secs * 28 + 30 or souls > meters / 2 + 10:
            return self.send(400, {"erro": "corrida_impossivel"})
        th = hashlib.sha256(str(data.get("token", "")).encode()).hexdigest()
        score = meters + souls * 10
        now = int(time.time())
        with db() as con:
            p = con.execute("SELECT * FROM players WHERE token_hash = ?", (th,)).fetchone()
            if not p:
                return self.send(403, {"erro": "token_desconhecido"})
            record = score > p["best"]
            if record:
                con.execute("UPDATE players SET best=?, best_meters=?, best_souls=?, best_at=?, runs=runs+1 WHERE key=?",
                            (score, meters, souls, now, p["key"]))
                best, best_at = score, now
            else:
                con.execute("UPDATE players SET runs=runs+1 WHERE key=?", (p["key"],))
                best, best_at = p["best"], p["best_at"]
            rank = rank_of(con, best, best_at) if best > 0 else None
        self.send(200, {"score": score, "best": best, "record": record, "rank": rank})


if __name__ == "__main__":
    init()
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
