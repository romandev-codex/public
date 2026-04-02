#!/bin/bash
set -e -o pipefail

# https://github.com/vast-ai/vast-sdk/blob/main/start_server.sh
# https://github.com/vast-ai/vast-sdk/blob/main/examples/server/comfy_worker.py

# https://github.com/vast-ai/pyworker/blob/main/workers/comfyui-json/worker.py
# wget -O - "https://raw.githubusercontent.com/romandev-codex/public/refs/heads/main/gpu/start_vast.sh" | bash

echo "V1.1.3"

# Install deps
pip install --no-cache-dir aiohttp vastai-sdk fastapi uvicorn packaging --disable-pip-version-check

# Start service
wget https://raw.githubusercontent.com/romandev-codex/public/refs/heads/main/gpu/service.py -O service.py
nohup uvicorn service:app --host 0.0.0.0 --port 3010 --reload > uvicorn.log 2>&1 &

# Run worker
# wget https://raw.githubusercontent.com/romandev-codex/public/refs/heads/main/gpu/worker.py -O worker.py
# exec python3 worker.py

# Run worker
wget https://raw.githubusercontent.com/romandev-codex/public/refs/heads/main/gpu/mock-worker.py -O mock-worker.py
exec python3 mock-worker.py

echo "END"
