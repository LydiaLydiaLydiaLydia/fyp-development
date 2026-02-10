The Python docker API documentation for the network object : https://docker-py.readthedocs.io/en/stable/networks.html#network-objects
and for the containers: https://docker-py.readthedocs.io/en/stable/containers.html

Line 62 to change level of logging 

To do next:

FORMAT ID PROPERLY :) 

Replace ssb-server cli calls with me own scripts:
    whoami: line 262
    whoami: line 300
    gossip.connect: line 424
    publish contact: line 437

On college machine: 
- containers did not stay running once they were spun up 
    - I changed the Dockerfile to run ssb-server just, instead of the register_node.sh
    - It also seemed to be a problem with the /data and /discovery volumes -- I didn't realise they'd be loaded into the machines (if this is true, why aren't I putting my scripts in there like that? oh, because it's shared between all machines? or is it just copied over on startup?)
- is my Dockerfile different than it is at home? Must double check before pulling from github
- added debug_container_status
- I NEED TO MAKE A GITIGNORE
- I made a gitignore but I also need to make a gitattributes thing? is that where I'd tell it not to change my LF into CRLF?