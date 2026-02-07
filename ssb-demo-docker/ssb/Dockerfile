FROM node:18

WORKDIR /app

RUN npm install -g ssb-server

VOLUME /data

EXPOSE 8008

CMD ["ssb-server", "start", "--host", "0.0.0.0"]