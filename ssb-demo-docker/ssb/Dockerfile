#Creating a Base Image (Linux by default?) that starts with Node.js 18 
#   (SSB is written in JavaScript)
FROM node:18

#Setting the Working Directory (inside the container) to a folder called /app
WORKDIR /app

#Using node package manager to install the ssb server globally (called the Build Phase)
RUN npm install -g ssb-server

#Copying the post script to a folder in the system PATH
COPY scripts/* /usr/local/bin/

#Making sure the post script is executable
RUN chmod +x /usr/local/bin/*

#Called a Mount Point -- it puts a Volume on my actual machine (the /data folder I just made 
#   in the container will be persisted)
VOLUME /data

#The Runtime Command: runs when the container starts
#Then using ssb: starting the server, listen to connections from any host, the path to the 
#   ssb info folder
CMD ["ssb-server", "start"]