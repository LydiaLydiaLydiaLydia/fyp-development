The docker-compose file defines 3 services: a machine for alice, bob, and carol, based on the Dockerfile.

The Dockerfile defines a base image with Node.js version 18 (ssb is written in js).
The working directory in the images is /app.
The container uses npm to install the ssb-server globally.
It puts the folder /root/.ssb/flume as the 'mount point'.

Alice links her /data folder to ./data/alice, Bob's is ./data/bob, and Carol's is ./data/carol.

The command each container begins with is ssb-server start, that starts the ssb-server running, creating a secret for each container, essentially creating a user.

Each of their containers is on a different network.
The driver:bridge means a private internal network exists on this machine, and the containers on this network can talk to each other and the internet.
Ipam is ip address management. By alloting net_alice, net_bob, and net_carol three different private subnets with no overlapping communication, and using the bridge driver, the host machine (my Windows machine that is running Docker) acts as the 'router' - each subnet can communicate with the host computer, and thus the traffic is routed that way.
