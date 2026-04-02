#!/bin/bash
set -e -o pipefail

echo "V1.1.2"

# Install deps
pip install --no-cache-dir aiohttp vastai-sdk fastapi uvicorn packaging --disable-pip-version-check

# Start service
wget https://raw.githubusercontent.com/romandev-codex/public/refs/heads/main/gpu/service.py -O service.py
nohup python service.py > service.log 2>&1 &

# Run worker
wget https://raw.githubusercontent.com/romandev-codex/public/refs/heads/main/gpu/worker.py -O worker.py
python worker.py

echo "END"
