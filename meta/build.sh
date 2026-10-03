#!/bin/sh

set -ex

# `docker compose run` starts a container via dockerd, which applies the
# default sysctl policy and trips runc's cross-device procfs safety check
# in nested-docker (DinD) environments. `docker create` prepares the
# container in containerd without invoking runc, so build + create + cp
# extracts the binary without ever starting a container.
IMAGE=bambi-notes-meta:local
docker build -t "$IMAGE" meta/
CID=$(docker create "$IMAGE")
trap 'docker rm "$CID" >/dev/null 2>&1 || true' EXIT
docker cp "$CID:/meta/bambi-notes" service/bambi-notes
