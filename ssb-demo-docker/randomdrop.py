from concurrent.futures import ThreadPoolExecutor, as_completed
import shutil

import docker
import json
import random
import time
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Tuple
from datetime import datetime
from propagation_demo import propagation_demo, scenario_result
import tarfile
import io


class ssb_network_simulator:
    def __init__ (self, num_nodes: int = 10, friends_mode: str = 'range',
                  friends_range: Tuple[int, int] = (2, 5), friends_fixed: int = 3,
                  log_file: str = None, seed: int = None):
        self.num_nodes = num_nodes
        self.friends_mode = friends_mode # either 'random', 'range', 'fixed'
        self.friends_range = friends_range
        self.friends_fixed = friends_fixed

        #Adding a seed for reproducability! Can be added through cmd arg
        self.seed = seed 
        if seed is None:
            self.seed = random.randint(0, 99999)
        random.seed(self.seed)

        #connecting to the docker daemon
        self.client = docker.from_env()
        self.project_name = "ssb-sim"
        self.nodes: List[Dict] = []

        self.networks = []
        self.router = None
        self.router_ips = {}
        self.connection_details = []

        self.logs_dir = Path('./logs')
        self.logs_dir.mkdir(exist_ok=True)

        if log_file is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_file = self.logs_dir / f'ssb_sim_{timestamp}.log'
        else:
            log_file = Path(log_file)
        self.log_file = log_file
        self._setup_logging()

        self.logger.info("="*80)
        self.logger.info("SSB NETWORK SIMULATOR INITIALIZED")
        self.logger.info("="*80)
        self.logger.info(f"Configuration:")
        self.logger.info(f"  - Number of nodes: {self.num_nodes}")
        self.logger.info(f"  - Friends mode: {self.friends_mode}")
        if self.friends_mode == 'range':
            self.logger.info(f"  - Friends range: {self.friends_range[0]}-{self.friends_range[1]}")
        elif self.friends_mode == 'fixed':
            self.logger.info(f"  - Friends fixed: {self.friends_fixed}")
        self.logger.info(f"  - Random seed: {self.seed}")
        self.logger.info(f"  - Log file: {self.log_file}")
        self.logger.info("="*80)

    def _setup_logging(self):
        # Create logger (level is debug)
        self.logger = logging.getLogger('SSBSimulator')
        self.logger.setLevel(logging.INFO)
        
        # Clear any existing handlers
        self.logger.handlers = []
        
        # File handler (DEBUG level - everything)
        ## mode 'w' write, rather than 'a' append
        file_handler = logging.FileHandler(self.log_file, mode='w', encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        file_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        
        # Console handler (INFO level - less verbose)
        ## don't need to print(), this prints info level logs to console
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter('%(message)s')
        console_handler.setFormatter(console_formatter)
        
        # Add handlers
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        self.logger.debug(f"Logging initialized. File: {self.log_file}")

    def _write_config(self, node, config: dict):
        # new write config method
        # using TARS

        # serialising the Dictionary to JSON 
        config_json = json.dumps(config, indent=2).encode('utf-8')
        
        #creating an in-memory tar file (this io.BytesIO() is like an input stream buffer)
        tarstream = io.BytesIO()
        # 'w' mode is open for uncompressed writing
        with tarfile.open(fileobj=tarstream, mode='w') as tar:
            info = tarfile.TarInfo(name='config')
            info.size = len(config_json)
            tar.addfile(info, io.BytesIO(config_json))
        # .seek(0) moves the cursor back to the start of the buffer
        tarstream.seek(0)
        
        #container.put_archive is a Docker technique of putting a tarfile in there
        node['container'].put_archive('/root/.ssb/', tarstream)
        self.logger.info(f"  {node['name']}: config written")

    def cleanup_existing(self):
        self.logger.info("Cleaning up existing containers and networks...")
        self.logger.debug("Searching for existing containers...")
        for container in self.client.containers.list(all=True):
            if container.name.startswith(f"{self.project_name}-node-") or \
            container.name.startswith(f"{self.project_name}-router"):
                self.logger.info(f"  Removing container: {container.name}")
                try:
                    # Clear the SSB data directory from inside the container
                    # while it's still running, so root-owned files (like
                    # 'secret') can be deleted without Windows permission errors.
                    if container.status == 'running':
                        container.exec_run("rm -rf /root/.ssb", stderr=False)
                        self.logger.debug(f"    Cleared /root/.ssb in {container.name}")

                    container.stop(timeout=10)
                    container.remove()
                except Exception as e:
                    self.logger.error(f"    Error removing {container.name}: {e}")
        
        # Remove networks
        self.logger.debug("Searching for existing networks...")
        for network in self.client.networks.list():
            if network.name.startswith(f"{self.project_name}-"):
                self.logger.info(f"  Removing network: {network.name}")
                self.logger.debug(f"    Network ID: {network.id}")
                try:
                    network.remove()
                    self.logger.debug(f"    Removed {network.name}")
                except Exception as e:
                    self.logger.warning(f"    Could not remove network {network.name}: {e}")

        self.logger.info(f"Cleanup complete.")
        self.logger.debug("-"*80)

    def create_networks(self):
        self.logger.info("Creating Docker networks...")
        
        # Each LAN gets 5 nodes max
        num_lans = (self.num_nodes + 4) // 5
        self.logger.debug(f"Creating {num_lans} LANs for {self.num_nodes} nodes")
        
        for i in range(num_lans):
            network_name = f"{self.project_name}-lan-{i+1}"
            subnet = f"10.10.{i+1}.0/24"
            
            self.logger.debug(f"Creating network: {network_name} ({subnet})")
            
            try:
                network = self.client.networks.create(
                    network_name,
                    driver="bridge",
                    ipam=docker.types.IPAMConfig(
                        pool_configs=[docker.types.IPAMPool(subnet=subnet)]
                    )
                )
                
                self.networks.append({
                    'network': network,
                    'name': network_name,
                    'subnet': subnet,
                    'id': network.id
                })
                
                self.logger.info(f"  Created {network_name} ({subnet})")
                self.logger.debug(f"    Network ID: {network.id}")
                
            except Exception as e:
                self.logger.error(f"  Failed to create {network_name}: {e}")
                raise
        
        self.logger.info(f"Created {len(self.networks)} networks")
        self.logger.debug("-"*80)

    def create_router(self):
        self.logger.info("Creating router container...")

        # Need starting LAN to connect the first network when creating router contaiener
        first_network = self.networks[0]['name']
        try:
            # Creating the router container from the image
            self.router = self.client.containers.run(
                "ssb-router",
                name=f"{self.project_name}-router",
                detach=True,
                network=first_network,
                sysctls={"net.ipv4.ip_forward": "1"},
                cap_add=["NET_ADMIN"],
                remove=False
            )

            # now looping through the other LANs and attaching to them
            for net_info in self.networks[1:]:
                network = net_info['network']
                self.logger.info(f"  Attaching router to {net_info['name']}")
                network.connect(self.router)

            self.logger.info(f"Router attached to {len(self.networks)} networks")
        except Exception as e:
            self.logger.error(f"Failed to create router: {e}")

    def apply_network_conditions(self, bandwidth_kbit: int = None, latency_ms: int = None, jitter_ms: int = 0):

        self.logger.info("Applying network conditions to router...")

        # Get every interface on the router (for each LAN)
        ## CLI: ls /sys/class/net/
        result = self.router.exec_run("ls /sys/class/net/")
        ifaces = [i for i in result.output.decode().split() if i.startswith("eth")]

        for iface in ifaces:
            # Clear any existing qdiscs first
            ## qdisc = queueing discipline, how Linux queues traffic, and what I'm messing with
            ## del(ete) dev(ice) 
            ## root is the outbound queue of the interface: outbound to the LANs
            r = self.router.exec_run(f"tc qdisc del dev {iface} root", stderr=False)
            if r.exit_code != 0:
                self.logger.debug(f"  {iface}: no existing qdisc to clear (ok on first run)")

            if latency_ms is not None and bandwidth_kbit is not None:
                # Combined: tbf (rate limiting) with netem (latency) as child
                ## NOTE ON NAMING QDISC RULES: the handle tag is followed by a major:minor
                ## labelling -- so I'm naming the qdisc 1:
                ## the tbf is a token bucket filter which does RATE LIMITING
                ## tbf needs to be told the maximum number of bits that can be sent 
                ## instantaneously at one time before the rate limit kicks in 
                ## (burst value) and the 'latency' to function 
                ## where the latency is more like a cap to the queue: a maximum
                ## amount of time a packet can sit in the queue before it's dropped
                ## and these values are just unintrusive necessities, not relevant
                cmd_tbf = (
                    f"tc qdisc add dev {iface} root handle 1: tbf "
                    f"rate {bandwidth_kbit}kbit burst 32kbit latency 400ms"
                )
                # this qdisc rule is being added as a child to 1:1
                cmd_netem = (
                    f"tc qdisc add dev {iface} parent 1:1 handle 10: netem "
                    f"delay {latency_ms}ms {jitter_ms}ms"
                )
                self.router.exec_run(cmd_tbf)
                r = self.router.exec_run(cmd_netem)

            elif latency_ms is not None:
                cmd = f"tc qdisc add dev {iface} root netem delay {latency_ms}ms {jitter_ms}ms"
                r = self.router.exec_run(cmd)

            elif bandwidth_kbit is not None:
                cmd = (
                    f"tc qdisc add dev {iface} root tbf "
                    f"rate {bandwidth_kbit}kbit burst 32kbit latency 400ms"
                )
                r = self.router.exec_run(cmd)
            else:
                self.logger.info(f"  {iface}: no conditions applied")
                continue

            if r.exit_code != 0:
                self.logger.warning(f"  {iface}: tc failed — {r.output.decode().strip()}")
            else:
                self.logger.info(f"  {iface}: {bandwidth_kbit}kbit/s, {latency_ms}ms +/- {jitter_ms}ms")

    def get_router_ips(self):
        self.logger.info("Getting router IPs on each LAN...")
        # for each LAN created, i need the IP address assigned to the 'router' container in order to 
        # make it the other containers' Default Gateways
        self.router.reload()

        for net_info in self.networks:
            net_name = net_info['name']
            # You can do #>docker inspect <container> [things you want to know about in CamelCase] https://docs.docker.com/reference/cli/docker/inspect/
            # through container.attrs[things you want to know about in CamelCase]
            # and its a key: value JSON obj returned
            net_data = self.router.attrs['NetworkSettings']['Networks'][net_name]
            ip = net_data['IPAddress']
            self.router_ips[net_name] = ip
            self.logger.debug(f"  Router IP on {net_name}: {ip}")

        return self.router_ips

    def create_nodes(self):
        self.logger.info(f"Creating {self.num_nodes} SSB nodes...")
        
        for i in range(self.num_nodes):
            node_name = f"{self.project_name}-node-{i+1}"
            
            #Assigning nodes to LANs
            lan_index = i % len(self.networks)
            network_name = self.networks[lan_index]['name']
            
            self.logger.info(f"    Creating {node_name}...")
            self.logger.debug(f"    Network: {network_name}")
            
            try:
                container = self.client.containers.run(
                    "ssb-node",
                    name=node_name,
                    hostname=node_name,
                    detach=True,
                    network=network_name,
                    remove=False
                )
                
                node_info = {
                    'name': node_name,
                    'container': container,
                    'lan': lan_index,
                    'lan_name': network_name,
                    'id': i + 1,
                    'container_id': container.id
                }
                
                self.nodes.append(node_info)
        
                self.logger.debug(f"    Created Container with ID: {container.id}")
                
            except Exception as e:
                self.logger.error(f"    Failed to create {node_name}: {e}")
                raise
        
        self.logger.info(f"Created {len(self.nodes)} nodes)")
        self.logger.debug("-"*80)

    def _check_node_ready(self, node:Dict):
        #helper function to be used by thread executor in wait_for_nodes_ready,
        ## as well as configure_ndoes 
        try:
            result = node['container'].exec_run("ssb-server whoami", stderr=False)
            return node['name'], result.exit_code == 0
        except Exception:
            return node['name'], False

    def configure_nodes(self):
        self.logger.info("Writing SSB config to nodes...")

        for node in self.nodes:
            # container.reload() loads the object from the docker daemon again 
            ## with updated attributes (e.g., the ip information that was allocated)
            node['container'].reload()
            # retrieving the NetworkSettings attributes from this node's LAN
            net_data = node['container'].attrs['NetworkSettings']['Networks'][node['lan_name']]
            container_ip = net_data['IPAddress']
            gateway_ip = net_data['Gateway']

            # Store IPs on node dict for later use
            node['cont_ip'] = container_ip
            node['gateway_ip'] = gateway_ip

            config = {
                "allowPrivate": True,
                "gossip": {
                    "connections": 8,
                    "friends": True,
                    "global": True
                },
                "timers": {
                    "connection": 10000,
                    "reconnect": 1000,
                    "ping": 30000,
                    "handshake": 2000
                }

            }
            node_n, ready_code = self._check_node_ready(node)
            while(ready_code == False):
                node_n, ready_code = self._check_node_ready(node)
                self.logger.debug(f"Waiting for node {node['name']} to be ready to write config")
            self._write_config(node, config)

        self.logger.info("Node config complete")

    def configure_node_gateways(self):
        self.logger.info("Configuring gateway route on nodes...")

        #remember the self.networks list looks like 
        #[{ "network" : (the docker network object),
        #   "name": "ssb-sim-lan-(number)",
        #   "subnet": "10.10.(number).0/24",
        #   "id": (the docker network object id)}]
        for node in self.nodes:
            # where node['lan_name'] is in the form 'ssb-sim-lan-(number)'
            lan_name = node['lan_name']
            router_ip = self.router_ips[lan_name]

            # adding all other LANs to this container's routing table
            for net_info in self.networks:
                if net_info['name'] == lan_name:
                    continue

                subnet = net_info['subnet']

                cmd = f"ip route add {subnet} via {router_ip}"
                #the following might not work due to needing to be NET_ADMIN 
                result = node['container'].exec_run(cmd, privileged=True)

                if result.exit_code != 0:
                    self.logger.warning( f" Route failed on {node['name']} : {cmd}")
                else:
                    self.logger.debug(f"    {node['name']}: route to {subnet} via {router_ip}")
    
    def wait_for_nodes_ready(self, timeout: int = 60):
        self.logger.info(f"Waiting for nodes to be ready (timeout: {timeout}s)...")
        wait_start = time.time()
        
        ready_nodes = set()
        check_interval = 2
        last_log_time = time.time()
        
        while len(ready_nodes) < self.num_nodes:
            elapsed = time.time() - wait_start
            
            if elapsed > timeout:
                self.logger.error(f"Timeout after {timeout}s! Only {len(ready_nodes)}/{self.num_nodes} nodes ready")
                self.logger.debug(f"Ready nodes: {ready_nodes}")
                self.logger.debug(f"Not ready: {set(n['name'] for n in self.nodes) - ready_nodes}")
                break
            
            #Changing this part to use THREADING

            pending = []
            for node in self.nodes:
                if node['name'] not in ready_nodes:
                    pending.append(node)

            #initialising a threadpoolexecutor instance
            #the max workers are the maximum amount of threads to use
            # this picks whichever is smaller: 20 or the amount of pending nodes
            with ThreadPoolExecutor(max_workers=min(len(pending), 20)) as executor:

                #futures are threads to be completed?
                #for each node in the pending list,
                # the executor is creating a thread and this dictionary is made out of
                # the results of these threads running the _check_node_ready function?
                futures = {executor.submit(self._check_node_ready, node): node for node in pending}
                for future in as_completed(futures):
                    name, is_ready = future.result()
                    if is_ready:
                        ready_nodes.add(name)
                        self.logger.info(f"{name} is ready ({len(ready_nodes)}/{self.num_nodes})")
                
            if len(ready_nodes) < self.num_nodes:
                # Log progress every 10 seconds
                if time.time() - last_log_time > 10:
                    self.logger.debug(f"Progress: {len(ready_nodes)}/{self.num_nodes} ready after {elapsed:.1f}s")
                    last_log_time = time.time()
                
                time.sleep(check_interval)   
        
        if len(ready_nodes) == self.num_nodes:
            self.logger.info(f"All {len(ready_nodes)} nodes ready")
        else:
            self.logger.warning(f"Only {len(ready_nodes)}/{self.num_nodes} nodes ready")
        
        self.logger.debug("-"*80)
        return len(ready_nodes) == self.num_nodes
    
    def get_node_info(self, node: Dict) -> Dict:
        self.logger.debug(f"Getting info for {node['name']}...")
        
        try:
            # Get ID
            result = node['container'].exec_run(
                'ssb-server whoami | jq -r \'.id\'',
                stderr=False
            )
            
            if result.exit_code != 0:
                self.logger.error(f"  Failed to get whoami for {node['name']}: exit code {result.exit_code}")
                raise Exception(f"Failed to get node ID")
            
            node_id_unparsed = result.output.decode().strip()
            node_id_parsed = json.loads(node_id_unparsed)
            node_id = node_id_parsed['id']
            self.logger.debug(f"  ID: {node_id}")
            
            # Extract key without @ and .ed25519
            key = node_id.replace('@', '').replace('.ed25519', '')

            #getting ip address of node
            node['container'].reload()
            net_data = node['container'].attrs['NetworkSettings']['Networks'][node['lan_name']]
            cont_ip = net_data['IPAddress']
            node['cont_ip'] = cont_ip
            
            address = f"net:{cont_ip}:8008~shs:{key}"
            
            info = {
                'name': node['name'],
                'id': node_id,
                'key': key,
                'host': cont_ip,
                'port': 8008,
                'address': address
            }
            
            node['info'] = info
            self.logger.info(f"  Multi-server address for node {node['name']}: {address}")
            return info
            
        except Exception as e:
            self.logger.error(f"  Error getting info for {node['name']}: {e}")
            raise

    def gossip_and_follow(self, node_a: Dict, node_b: Dict) -> bool:
        self.logger.debug(f"    Connecting {node_a['name']} -> {node_b['name']}...")
        
        #gossip.connect only needs to be used for TCP connectinos, i.e., extra-LAN
        # connections that aren't automatically made via UDP gossip calls
        try:
            if node_a["lan_name"] != node_b["lan_name"]:
                gossip_cmd = f'ssb-server gossip.connect "{node_b["info"]["address"]}"'
                result = node_a['container'].exec_run(gossip_cmd, stderr=True)

                if result.exit_code != 0:
                    self.logger.warning(f"         Gossip failed (exit {result.exit_code})")
                    self.logger.debug(f"         Output: {result.output.decode()[:200]}")
                    return False
            
                self.logger.debug(f"         Gossip successful")
 
            # Follow
            follow_cmd = f'ssb-server publish --type contact --contact "{node_b["info"]["id"]}" --following'
            self.logger.debug(f"      Follow command: {follow_cmd}")
            
            result = node_a['container'].exec_run(follow_cmd, stderr=True)
            
            if result.exit_code != 0:
                self.logger.warning(f"         Follow failed (exit {result.exit_code})")
                self.logger.debug(f"         Output: {result.output.decode()[:200]}")
                return False
            
            self.logger.debug(f"         Follow successful")
            self.logger.info(f"         {node_a['name']} -> {node_b['name']}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"   Error: {node_a['name']} -> {node_b['name']}: {e}")
            return False

    def establish_connections(self):
        #The friends 'mode' stuff: allotting nodes with who they should connect with 
        self.logger.info(f"  Establishing connections (mode: {self.friends_mode})...")
        connections_start = time.time()
        
        # Get info for all nodes
        self.logger.info("  Gathering node information...")      
        node_infos = []
        for node in self.nodes:
            try:
                info = self.get_node_info(node)
                self.logger.debug(f"  Got info for {node['name']}")
            except Exception as e:
                self.logger.error(f"  Failed to get info for {node['name']}: {e}")
         
        # Establish connections
        self.logger.info("  Creating peer connections...")
        connections_made = 0
        connections_failed = 0
        connection_details = []
        
        for i, node in enumerate(self.nodes):
            if 'info' not in node:
                self.logger.warning(f"  Skipping {node['name']} (no info available)")
                continue
            
            # Determine number of friends
            if self.friends_mode == 'random':
                num_friends = random.randint(1, self.num_nodes - 1)
            elif self.friends_mode == 'range':
                num_friends = random.randint(
                    min(self.friends_range[0], self.num_nodes - 1),
                    min(self.friends_range[1], self.num_nodes - 1)
                )
            else:  # fixed
                num_friends = min(self.friends_fixed, self.num_nodes - 1)
            
            self.logger.info(f"     {node['name']}: connecting to {num_friends} peers...")
            self.logger.debug(f"     Mode: {self.friends_mode}, Count: {num_friends}")
            
            # Select random friends (excluding self)
            available_friends = [j for j in range(len(self.nodes)) if j != i and 'info' in self.nodes[j]]
            friend_indices = random.sample(available_friends, min(num_friends, len(available_friends)))
            
            node_connections = []
            for friend_idx in friend_indices:
                friend = self.nodes[friend_idx]
                success = self.gossip_and_follow(node, friend)
                
                if success:
                    connections_made += 1
                    node_connections.append(friend['name'])
                else:
                    connections_failed += 1
            
            connection_details.append({
                'node': node['name'],
                'connections': node_connections,
                'count': len(node_connections)
            })
            
            self.logger.debug(f"     Connected to: {', '.join(node_connections)}")
        
        self.logger.info(f"  Connections complete: {connections_made} successful, {connections_failed} failed")
        
        # Log detailed connection matrix
        self.logger.debug("Connection matrix:")
        for detail in connection_details:
            self.logger.debug(f"  {detail['node']}: {detail['count']} connections -> {detail['connections']}")
        
        self.logger.debug("-"*80)
        self.connection_details = connection_details
        return {
            'successful': connections_made,
            'failed': connections_failed,
            'details': connection_details
        }
      
    def debug_container_status(self):
        self.logger.info("Debugging container status...")
    
        for node in self.nodes:
            container = node['container']
            container.reload()  # Refresh container state
            status = container.status
            self.logger.debug(f"{node['name']} status: {status}")
            
            if status != 'running':
                self.logger.error(f"  {node['name']} is {status}!")
                
                # Get logs
                logs = container.logs(tail=50).decode('utf-8', errors='replace')
                self.logger.error(f"  Last 50 log lines:\n{logs}")

    def run(self):
        print("\n" + "="*80)
        print("SSB NETWORK SIMULATOR")
        print("="*80 + "\n")
        
        self.logger.info("Starting network simulation...")
        
        try:
            #get rid of existing Docker configuration
            self.cleanup_existing()
            #creating Docker networks
            # and filling in the self.networks[{"network": the docker network object
            #                                 "name": 'ssb-sim-lan-1',
            #                                 "subnet": "10.10.1.0/24",
            #                                 "id": the docker network object id}]
            self.create_networks()
            #starts up the router contaienr
            self.create_router()
            #collect the ip addresses assigned to the router in each LAN
            # and filling in the self.router_ips{ "ssb-sim-lan-1": 10.10.1.2,...}
            self.get_router_ips()
            #creates the node containers and fills in self.nodes
            self.create_nodes()
            #puts the /root/.ssb/config file into the node containers
            self.configure_nodes()
            #giving each container a default gaateway of the router container (in that LAN)
            self.configure_node_gateways()
            # ensure the contaienrs are okay
            self.debug_container_status()
            
            if not self.wait_for_nodes_ready():
                self.logger.warning("Some nodes failed to start. Continuing anyway...")
            
            connection_stats = self.establish_connections()
        
            
            print(f"\nNetwork simulation setup complete!)")
            print(f"\nSummary:")
            print(f"  - Nodes created: {len(self.nodes)}")
            print(f"  - Connections: {connection_stats['successful']} successful, {connection_stats['failed']} failed")
            print(f"  - Log file: {self.log_file}")
            
            print(f"\nTo interact with a node:")
            print(f"  docker exec -it {self.project_name}-node-1 bash")
            print(f"\nTo tear down:")
            print(f"  python3 {__file__} --cleanup\n")
            
            self.logger.info("="*80)
            self.logger.info(f"SIMULATION COMPLETE")
            self.logger.info("="*80)
            
        except KeyboardInterrupt:
            print("\n Interrupted by user")
            self.logger.warning("Simulation interrupted by user")
        except Exception as e:
            print(f"\nError: {e}")
            self.logger.error(f"Simulation failed: {e}", exc_info=True)
            import traceback
            traceback.print_exc()

def main():
    parser = argparse.ArgumentParser(
        description='SSB Network Simulator'
    )
    
    parser.add_argument(
        '--nodes', '-n',
        type=int,
        default=10,
        help='Number of nodes to create (default: 10)'
    )
    
    parser.add_argument(
        '--friends-mode', '-m',
        choices=['random', 'range', 'fixed'],
        default='range',
        help='Friend assignment mode (default: range)'
    )
    
    parser.add_argument(
        '--friends-min',
        type=int,
        default=2,
        help='Minimum friends per node (for range mode, default: 2)'
    )
    
    parser.add_argument(
        '--friends-max',
        type=int,
        default=5,
        help='Maximum friends per node (for range mode, default: 5)'
    )
    
    parser.add_argument(
        '--friends-fixed',
        type=int,
        default=3,
        help='Exact number of friends per node (for fixed mode, default: 3)'
    )
    
    parser.add_argument(
        '--base-port',
        type=int,
        default=8000,
        help='Starting port for port mapping (default: 8000)'
    )
    
    parser.add_argument(
        '--host-ip',
        type=str,
        default='192.168.56.1',
        help='Your host machine IP address (default: 192.168.56.1)'
    )
    
    parser.add_argument(
        '--log-file',
        type=str,
        default=None,
        help='Path to log file (default: auto-generated in ./logs/)'
    )
    
    parser.add_argument(
        '--cleanup',
        action='store_true',
        help='Only cleanup existing containers and networks, then exit'
    )

    parser.add_argument(
        '--prop-demo',
        action='store_true',
        help='Run post propagation demonstration'
    )

    parser.add_argument(
        '--seed',
        type = int,
        default = None,
        help = "Random seed for reproducibility (default: auto-generated, see logs for value)"
    )
    
    args = parser.parse_args()
    
    simulator = ssb_network_simulator(
        num_nodes=args.nodes,
        friends_mode=args.friends_mode,
        friends_range=(args.friends_min, args.friends_max),
        friends_fixed=args.friends_fixed,
        log_file=args.log_file,
        seed = args.seed
    )
    
    if args.cleanup:
        print("Cleanup mode")
        simulator.cleanup_existing()
        print("Cleanup complete")
    else:
        simulator.run()
        if args.prop_demo:
            print("Propagation demonstration underway...")
            #adding networking conditions after connections are made, before scenarios
            simulator.apply_network_conditions(bandwidth_kbit=6861, latency_ms=101)


            prop_demo = propagation_demo(simulator)
            stats = prop_demo.run_baseline('ssb-sim-node-1')


            catch_up_stats1, catch_up_stats2 = prop_demo.run_dropout_catchup('ssb-sim-node-1')
  


if __name__ == '__main__':
    main()