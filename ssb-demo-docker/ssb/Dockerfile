FROM node:18

WORKDIR /app

RUN npm install -g ssb-server

COPY scripts/add.sh /usr/local/bin/add
COPY scripts/follow.sh /usr/local/bin/follow
COPY scripts/gossip.sh /usr/local/bin/gossip
COPY scripts/post.sh /usr/local/bin/post
COPY scripts/getinfo.sh /usr/local/bin/getinfo
COPY scripts/viewlog.sh /usr/local/bin/viewlog

RUN chmod +x /usr/local/bin/*

VOLUME /data

EXPOSE 8008

CMD ["ssb-server", "start", "--host", "0.0.0.0"]