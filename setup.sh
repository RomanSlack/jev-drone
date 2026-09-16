#!/usr/bin/env bash
# Fetch the Skydio X2 model and wire up the asset path.
set -euo pipefail
cd "$(dirname "$0")"

python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt

if [ ! -d mujoco_menagerie ]; then
  git clone --depth 1 --filter=blob:none --sparse \
    https://github.com/google-deepmind/mujoco_menagerie.git
  (cd mujoco_menagerie && git sparse-checkout set skydio_x2)
fi

# world.xml includes x2.xml, whose meshdir resolves relative to the main file
ln -sfn mujoco_menagerie/skydio_x2/assets assets

echo "done. now:  cp .env.example .env  && edit it"
