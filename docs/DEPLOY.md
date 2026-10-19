# Deploy

O jogo e o ranking rodam num único processo Python (`api/server.py`, só stdlib) atrás de um
Cloudflare Tunnel — nenhuma porta aberta para a internet.

```text
Internet → Cloudflare Tunnel (ryuk.gab.dev.br)
         → ryuk.service — python3 api/server.py em 127.0.0.1:8797 (usuário deploy)
         → web/ (jogo estático)  +  /api/ (ranking em SQLite)
```

## Primeira vez no servidor

Requisitos: Linux com systemd, `python3` ≥ 3.10, `sqlite3`, usuário `deploy` e um túnel do
`cloudflared` com uma regra apontando o hostname para `http://localhost:8797`:

```yaml
ingress:
  - hostname: ryuk.gab.dev.br
    service: http://localhost:8797
  - service: http_status:404
```

```bash
cloudflared tunnel route dns <tunel> ryuk.gab.dev.br
```

## Publicar

```bash
# deploy/deploy.env (fora do git):
#   RYUK_VPS=root@meu-servidor
#   RYUK_SSH_KEY=$HOME/.ssh/minha-chave
git commit ... && bash deploy/deploy.sh
```

O script empacota `api/`, `web/` e `deploy/` do **HEAD** (árvore precisa estar limpa), cria
`/opt/ryuk/releases/<sha>`, instala as units, troca o symlink `/opt/ryuk/current` de forma atômica
e confere `GET /api/health`.

> Mudou qualquer arquivo de `web/`? Suba `VERSAO` em `web/sw.js` — senão o app instalado no
> celular continua servindo a versão antiga do cache.

## Rollback

```bash
ls /opt/ryuk/releases/
ln -sfn /opt/ryuk/releases/<sha-anterior> /opt/ryuk/current && systemctl restart ryuk
```

## Dados e backup

| O quê | Onde |
|---|---|
| Ranking | `/var/lib/ryuk/ranking.db` (SQLite, WAL) |
| Cópia diária | `ryuk-backup.timer` (04:20) → `/var/backups/pg/ryuk-ranking-<data>.db`, guarda 14 dias |

O servidor é tratado como descartável: o código mora no git e a pasta de backup é puxada todo dia
para fora dele. Restaurar = parar `ryuk`, copiar o `.db` escolhido para `/var/lib/ryuk/ranking.db`
(dono `deploy`) e subir `ryuk`.

## Operação

```bash
systemctl status ryuk ryuk-backup.timer
journalctl -u ryuk -f
curl -fsS http://127.0.0.1:8797/api/health
sqlite3 /var/lib/ryuk/ranking.db "SELECT key, name, best FROM players ORDER BY best DESC LIMIT 30;"
sqlite3 /var/lib/ryuk/ranking.db "DELETE FROM players WHERE key='<chave>';"   # tira alguém / libera o apelido
```
