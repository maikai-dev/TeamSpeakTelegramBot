#!/usr/bin/env bash
set -euo pipefail

if [[ "${RUN_MIGRATIONS:-1}" == "1" ]]; then
  alembic upgrade head
fi

python -m app.main
