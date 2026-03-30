#!/usr/bin/env bash
set -euo pipefail

SRC_URL="https://raw.githubusercontent.com/romandev-codex/public/refs/heads/main/gpu/worker.py"
DEST_PATH="/workspace/worker.py"
TMP_PATH="${DEST_PATH}.tmp"

echo "Downloading worker.py from: ${SRC_URL}"

if command -v curl >/dev/null 2>&1; then
  curl -fsSL "${SRC_URL}" -o "${TMP_PATH}"
elif command -v wget >/dev/null 2>&1; then
  wget -qO "${TMP_PATH}" "${SRC_URL}"
else
  echo "Error: neither curl nor wget is available" >&2
  exit 1
fi

if [ ! -s "${TMP_PATH}" ]; then
  echo "Error: downloaded file is empty" >&2
  rm -f "${TMP_PATH}"
  exit 1
fi

mv -f "${TMP_PATH}" "${DEST_PATH}"
chmod 0644 "${DEST_PATH}"

echo "Replaced ${DEST_PATH} successfully"
