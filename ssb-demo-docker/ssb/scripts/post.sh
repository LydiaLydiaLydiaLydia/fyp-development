#!/bin/sh
if [ -z "$1" ]; then
  echo "Error: You must provide post content."
  echo "Usage: ./post.sh \"your message here\""
  exit 1
fi

ssb-server publish --type post --text "$1"