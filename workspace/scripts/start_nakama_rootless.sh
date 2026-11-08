#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NAKAMA="$ROOT/ORCH/crew-dojo/Nakama"
SOCKET="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/docker.sock"

if ! docker --host "unix://$SOCKET" info >/dev/null 2>&1; then
  systemctl --user start docker
fi

if [[ ! -f "$NAKAMA/go.mod" ]]; then
  (cd "$NAKAMA" && go mod init example.com/go-project)
fi
if [[ ! -d "$NAKAMA/vendor" ]]; then
  (cd "$NAKAMA" && go get github.com/heroiclabs/nakama-common/runtime@v1.26.0 && go mod vendor)
fi

# Nakama 3.15's plugin builder uses Go 1.19 and rejects patch components in
# the go directive written by newer Go releases.
(cd "$NAKAMA" && go mod edit -go=1.20)

export DOCKER_HOST="unix://$SOCKET"
docker compose -p dojo-nakama-server -f "$NAKAMA/docker-compose.yml" up -d --build

# The upstream compose file has start ordering but no PostgreSQL health
# dependency. Retry once Postgres is ready if Nakama lost that race.
for _ in $(seq 1 30); do
  status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' dojo-nakama-server-nakama-1 2>/dev/null || true)"
  [[ "$status" == "healthy" ]] && break
  if [[ "$status" == "exited" || -z "$status" ]]; then
    docker compose -p dojo-nakama-server -f "$NAKAMA/docker-compose.yml" up -d nakama
  fi
  sleep 2
done

docker compose -p dojo-nakama-server -f "$NAKAMA/docker-compose.yml" ps
curl --fail --silent --show-error --max-time 5 http://127.0.0.1:7350/ >/dev/null
echo "Nakama rootless service is healthy on 127.0.0.1:7350"
