#!/bin/bash

set -e -o pipefail

pip install --upgrade pip
pip install uv
pip install --no-cache-dir aiohttp vastai-sdk --disable-pip-version-check
pip install --no-cache-dir fastapi uvicorn --disable-pip-version-check
pip install packaging
