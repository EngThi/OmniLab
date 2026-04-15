#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

# Install Playwright browser only (deps are not allowed to install via sudo on Render)
playwright install chromium
