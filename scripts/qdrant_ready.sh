#!/usr/bin/env bash
# Qdrant /readyz is plain text. Check the HTTP status line for 200.
set -eu
exec 3<>/dev/tcp/127.0.0.1/6333
printf 'GET /readyz HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n' >&3
IFS= read -r status <&3 || true
exec 3<&-
exec 3>&-
case "$status" in
  *"200"*) exit 0 ;;
  *) exit 1 ;;
esac
