#!/bin/bash
# Publica o commit atual (HEAD) no servidor como release novo e troca o symlink.
#
# Configuração (variáveis de ambiente ou deploy/deploy.env, que não vai para o git):
#   RYUK_VPS       destino SSH, ex.: root@meu-servidor
#   RYUK_SSH_KEY   chave SSH (opcional)
#
# Uso: bash deploy/deploy.sh   (de dentro do repo, árvore limpa)
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
[ -f deploy/deploy.env ] && . deploy/deploy.env
: "${RYUK_VPS:?defina RYUK_VPS (ex.: root@meu-servidor) no ambiente ou em deploy/deploy.env}"
SSH=(ssh -o ConnectTimeout=20)
[ -n "${RYUK_SSH_KEY:-}" ] && SSH+=(-i "$RYUK_SSH_KEY")
[ -z "$(git status --porcelain)" ] || { echo "árvore suja: commite antes" >&2; exit 1; }
SHA=$(git rev-parse HEAD)
REL="/opt/ryuk/releases/$SHA"
git archive --format=tar HEAD api web deploy | "${SSH[@]}" "$RYUK_VPS" "
  set -e
  install -d -o deploy -g deploy -m 0755 /opt/ryuk/releases /var/lib/ryuk
  rm -rf '$REL.tmp' && mkdir -p '$REL.tmp' && tar -x -C '$REL.tmp'
  chown -R deploy:deploy '$REL.tmp' && rm -rf '$REL' && mv '$REL.tmp' '$REL'
  install -m 0644 '$REL/deploy/ryuk.service' '$REL/deploy/ryuk-backup.service' '$REL/deploy/ryuk-backup.timer' /etc/systemd/system/
  systemctl daemon-reload
  systemctl enable --now ryuk-backup.timer >/dev/null
  ln -sfn '$REL' /opt/ryuk/current.new && mv -T /opt/ryuk/current.new /opt/ryuk/current
  systemctl enable --now ryuk.service >/dev/null
  systemctl restart ryuk.service
  sleep 1
  curl -fsS http://127.0.0.1:8797/api/health
"
echo
echo "release $SHA no ar"
