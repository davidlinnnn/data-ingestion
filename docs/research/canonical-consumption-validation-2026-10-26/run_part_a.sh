#!/bin/sh
# Writes its virtualenv, cache and results next to this script.
# Set PART_A_PG_PASSWORD to any throwaway password for the temporary container.
set -eu
validation_dir=$(dirname "$0")
pg_password=${PART_A_PG_PASSWORD:?set PART_A_PG_PASSWORD}
export CODEX55_DSN="postgresql://postgres:$pg_password@127.0.0.1:55455/postgres"
mkdir -p "$validation_dir"
uv venv --python /usr/bin/python3 --cache-dir "$validation_dir/.uv-cache" "$validation_dir/.venv"
uv pip install --python "$validation_dir/.venv/bin/python" --cache-dir "$validation_dir/.uv-cache" 'psycopg[binary]==3.2.13'
# Do not remove an existing container owned by another run.
if docker container inspect codex55pg >/dev/null 2>&1; then
    printf '%s\n' 'codex55pg already exists; refusing to replace it.' >&2
    exit 1
fi
docker run -d --name codex55pg -e POSTGRES_PASSWORD="$pg_password" \
    -p 127.0.0.1:55455:5432 --tmpfs /var/lib/postgresql postgres:18 \
    -c track_commit_timestamp=on
trap 'docker rm -f codex55pg' EXIT HUP INT TERM
attempt=0
until docker exec codex55pg pg_isready -h 127.0.0.1 -U postgres >/dev/null 2>&1; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 60 ]; then
        docker logs codex55pg
        exit 1
    fi
    sleep 1
done
"$validation_dir/.venv/bin/python" -B "$validation_dir/part_a.py" \
    --seeds 5501 5502 5503 --writers 8 --transactions 400
