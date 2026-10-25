#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
echo "== tests =="; python3 -m pytest tests -q
echo "== demo =="; python3 demo.py
echo "== viewer =="; python3 make_viewer.py
echo "VERIFY_ALL_OK"
