#!/bin/sh
# Install boox-sync as a systemd user timer.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
dest=$HOME/.local/share/boox-sync
mkdir -p "$dest" "$HOME/.config/systemd/user"
cp "$here"/tools/pbdump.py "$here"/tools/booxnote.py "$here"/tools/render.py "$here"/tools/sync.py "$dest"/
cp "$here"/systemd/boox-sync.service "$here"/systemd/boox-sync.timer "$HOME/.config/systemd/user/"
if [ ! -f "$here/boox-sync.env" ]; then
    echo "Missing boox-sync.env: cp boox-sync.env.sample boox-sync.env, edit it, then re-run this script." >&2
    exit 1
fi
cp "$here"/boox-sync.env "$HOME/.config/boox-sync.env"
systemctl --user daemon-reload
systemctl --user enable --now boox-sync.timer
echo "Installed. Logs: journalctl --user -u boox-sync -f"
