FROM node:18

WORKDIR /app

RUN npm install -g ssb-server

RUN apt-get update && \
    apt-get install -y jq iptables iproute2

COPY scripts/add.sh /usr/local/bin/add
COPY scripts/follow.sh /usr/local/bin/follow
COPY scripts/gossip.sh /usr/local/bin/gossip
COPY scripts/post.sh /usr/local/bin/post
COPY scripts/getinfo.sh /usr/local/bin/getinfo
COPY scripts/viewlog.sh /usr/local/bin/viewlog

RUN chmod +x /usr/local/bin/*

COPY scripts/register_node.sh /app/
RUN chmod +x /app/register_node.sh

WORKDIR /usr/local/lib/node_modules/ssb-server
RUN npm install sodium-native

WORKDIR /app

VOLUME /data

EXPOSE 8008

CMD ["ssb-server", "start"]