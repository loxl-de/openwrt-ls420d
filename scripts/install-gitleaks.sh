#!/bin/sh
# SPDX-License-Identifier: MIT
set -eu
[ "$#" -eq 1 ] || { echo 'Usage: install-gitleaks.sh NEW_DIRECTORY' >&2; exit 2; }
case "$(uname -s):$(uname -m)" in Linux:x86_64) ;; *) echo 'Requires Linux x86_64' >&2; exit 2;; esac
# Fail if the destination already exists; never overwrite a caller directory.
umask 077
mkdir -- "$1"
dest=$(CDPATH='' cd -- "$1" && pwd)
curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 \
    https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_linux_x64.tar.gz \
    --output "$dest/gitleaks.tar.gz"
(cd "$dest"; printf '%s  gitleaks.tar.gz\n' \
    551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb | sha256sum -c -)
tar -xzf "$dest/gitleaks.tar.gz" -C "$dest" --no-same-owner --no-same-permissions gitleaks
chmod 700 "$dest/gitleaks"
