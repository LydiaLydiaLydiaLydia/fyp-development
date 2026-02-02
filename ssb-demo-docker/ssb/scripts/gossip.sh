#!/bin/sh
if [ -z "$1" ]; then
  echo "Error: You must provide node address."
  echo "Usage: ./post.sh \"ipaddress:port:publickey\""
  exit 1
fi

ssb-server gossip.connect "$1"