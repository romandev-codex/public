#!/bin/bash

set -e -o pipefail

pip install --upgrade pip
pip install uv
pip install --no-cache-dir aiohttp vastai-sdk --disable-pip-version-check
pip install --no-cache-dir fastapi uvicorn --disable-pip-version-check
pip install packaging

mkdir -p /workspace

wget https://raw.githubusercontent.com/romandev-codex/public/refs/heads/main/gpu/service.py -O /workspace/service.py
nohup python /workspace/service.py > output.log 2>&1 &

wget https://raw.githubusercontent.com/romandev-codex/public/refs/heads/main/gpu/worker.py -O /workspace/worker.py
nohup python /workspace/worker.py > output.log 2>&1 &

echo "END"
