#!/bin/bash

ssb-server start --host 0.0.0.0 &

sleep 5

NODE_ID=$(ssb-server whoami | jq -r '.id')
NODE_ADDR=$(ssb-server getAddress | jq -r 'split(";")[0]')

cat > /discovery/${HOSTNAME}.json <<EOF
{
    "hostname": "${HOSTNAME}",
    "id": "${NODE_ID}",
    "address": "${NODE_ADDR}"
}
EOF

wait