#!/bin/sh
if [ "$#" -ne 3 ]; then
  echo "Error: You must provide node IP, port, and key."
  echo "Usage: ./add.sh \"ipaddress port publickey\""
  exit 1
fi

ssb-server gossip.connect "net:$1:$2~shs:$3"