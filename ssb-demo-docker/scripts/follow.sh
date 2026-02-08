#!/bin/sh
if [ -z "$1" ]; then
  echo "Error: You must provide node key."
  echo "Usage: ./follow.sh \"publickey\""
  exit 1
fi

ssb-server publish --type contact --contact "@$1.ed25519" --following