# AGENTS.md — ryuk-voo-noturno

Jogo 3D de celular (three.js puro, sem build) + ranking em Python stdlib/SQLite.

- Rodar local: `RYUK_DB=/tmp/ryuk.db python3 api/server.py` → `http://127.0.0.1:8797` (`?todas=1` libera as fases).
- **Mudou algo em `web/`? Suba `VERSAO` em `web/sw.js`** — o service worker serve do cache.
- Sem bundler e sem CDN: dependências ficam em `web/vendor/` (three.js 0.160, MIT).
- O servidor recalcula a pontuação; nunca confie no `score` do cliente.
- `souls` no código/API = bolsas de sangue na tela (nome histórico, não renomear sem migrar o banco).
- Deploy: `bash deploy/deploy.sh` com `deploy/deploy.env` (fora do git). Ver `docs/DEPLOY.md`.
- Testar no navegador com viewport de celular (390×844, touch) antes de publicar.
