#!/bin/sh
set -eu

ownership_marker=/workspace/data/.locallife-owner-v1
if [ ! -f "$ownership_marker" ]; then
  chown -R locallife:locallife /workspace/data
  runuser -u locallife -- touch "$ownership_marker"
fi

exec runuser -u locallife -- "$@"
