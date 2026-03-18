import docker
import json
import random
import time
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Tuple
from datetime import datetime

class ssb_network_simulator:
    def __init__ (self, num_nodes: int = 10, friends_mode: str = 'range',
                  friends_range: Tuple[int, int] = (2, 5), friends_fixed: int = 3, 
                  base_port: int = 8000, host_ip: str = '192.168.56.1',
                  log_file: str = None):
        self.num_nodes = num_nodes
        self.friends_mode = friends_mode # either 'random', 'range', 'fixed'
        self.friends_range = friends_range
        self.friends_fixed = friends_fixed
        #self.base_port = base_port
        #self.host_ip = host_ip

        self.client = docker.from_env()
        self.project_name = "ssb-sim"
        self.nodes: List[Dict] = []

        self.networks = []
        self.router = None
        self.router_ips = {}

        self.data_dir = Path('./data')
        #self.discovery_dir = Path('./discovery')
        self.logs_dir = Path('./logs')

        self.data_dir.mkdir(exist_ok=True)
        #self.discovery_dir.mkdir(exist_ok=True)
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
        #self.logger.info(f"  - Base port: {self.base_port}")
        #self.logger.info(f"  - Host IP: {self.host_ip}")
        self.logger.info(f"  - Log file: {self.log_file}")
        self.logger.info("="*80)

    def _setup_logging(self):
        """Setup logging configuration."""
        # Create logger
        self.logger = logging.getLogger('SSBSimulator')
        self.logger.setLevel(logging.DEBUG)
        
        # Clear any existing handlers
        self.logger.handlers = []
        
        # File handler (DEBUG level - everything)
        file_handler = logging.FileHandler(self.log_file, mode='w', encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        
        # Console handler (INFO level - less verbose)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter('%(message)s')
        console_handler.setFormatter(console_formatter)
        
        # Add handlers
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        self.logger.debug(f"Logging initialized. File: {self.log_file}")

    def cleanup_existing(self):
        """Remove any existing containers and networks from previous runs."""
        self.logger.info("Cleaning up existing containers and networks...")
        cleanup_start = time.time()
        
        containers_removed = 0
        networks_removed = 0
        
        # Stop and remove containers
        self.logger.debug("Searching for existing containers...")
        for container in self.client.containers.list(all=True):
            if container.name.startswith(f"{self.project_name}-node-") or container.name.startswith(f"{self.project_name}-router"):
                self.logger.info(f"  Removing container: {container.name}")
                self.logger.debug(f"    Container ID: {container.id}")
                try:
                    container.stop(timeout=10)
                    self.logger.debug(f"    Stopped {container.name}")
                    container.remove()
                    self.logger.debug(f"    Removed {container.name}")
                    containers_removed += 1
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
                    networks_removed += 1
                except Exception as e:
                    self.logger.warning(f"    Could not remove network {network.name}: {e}")
        

        cleanup_duration = time.time() - cleanup_start
        self.logger.info(f"Cleanup complete: {containers_removed} containers, {networks_removed} networks removed ({cleanup_duration:.2f}s)")
        self.logger.debug("-"*80)

    def create_networks(self):
        self.logger.info("Creating Docker networks...")
        network_start = time.time()
        
        # Each LAN gets 5 nodes max
        num_lans = (self.num_nodes + 4) // 5
        self.logger.debug(f"Creating {num_lans} LANs for {self.num_nodes} nodes")
        
        #self.networks = []
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
        
        network_duration = time.time() - network_start
        self.logger.info(f"Created {len(self.networks)} networks ({network_duration:.2f}s)")
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

    def get_router_ips(self):
        self.logger.info("Getting router IPs on each LAN...")
        # for each LAN created, i need the IP address assigned to the 'router' container in order to 
        # make it the other containers' Default Gateways
        self.router.reload()
        #router_ips = {}

        for net_info in self.networks:
            net_name = net_info['name']
            # You can do #>docker inspect <container> [things you want to know about in CamelCase] https://docs.docker.com/reference/cli/docker/inspect/
            # through container.attrs[things you want to know about in CamelCase]
            # and its a key: value JSON thing returned
            net_data = self.router.attrs['NetworkSettings']['Networks'][net_name]
            ip = net_data['IPAddress']
            self.router_ips[net_name] = ip
            self.logger.debug(f"  Router IP on {net_name}: {ip}")

        #self.router_ips = router_ips
        return self.router_ips
    
    


    def create_nodes(self):
        self.logger.info(f"Creating {self.num_nodes} SSB nodes...")
        nodes_start = time.time()
        
        for i in range(self.num_nodes):
            node_start = time.time()
            node_name = f"{self.project_name}-node-{i+1}"
            #port = self.base_port + i
            
            #Assigning nodes to LANs
            lan_index = i % len(self.networks)
            #network = self.networks[lan_index]['network']
            network_name = self.networks[lan_index]['name']
            
            # Create data directory - like I did in first example, but unsure if I should continue to do so. I suppose for sake of being able to check it later?
            # Would doing so slow everything down and effect how Docker runs the simulation, if I'm saving data to my local machine?
            # Or, as this is happening at build time, is it okay? Should I just share the data from the nodes' logs once the entire simulation is over
            # just to make sure this isn't a factor?
            node_data_dir = self.data_dir / f"node-{i+1}"
            node_data_dir.mkdir(exist_ok=True)
            
            self.logger.info(f"  Creating {node_name}...")
            #self.logger.debug(f"    Port mapping: {port} -> 8008")
            self.logger.debug(f"    Network: {network_name}")
            self.logger.debug(f"    Data directory: {node_data_dir}")
            
            try:
                container = self.client.containers.run(
                    "ssb-node",
                    name=node_name,
                    hostname=node_name,
                    detach=True,
                    #ports={
                    #    '8008/tcp': port
                    #},
                    volumes={
                        str(node_data_dir.absolute()): {'bind': '/root/.ssb', 'mode': 'rw'}
                        #,
                        #str(self.discovery_dir.absolute()): {'bind': '/discovery', 'mode': 'rw'}
                    },
                    network=network_name,
                    remove=False
                )
                
                node_info = {
                    'name': node_name,
                    'container': container,
                    #'port': port,
                    'lan': lan_index,
                    'lan_name': network_name,
                    'id': i + 1,
                    'container_id': container.id
                }
                
                self.nodes.append(node_info)
                
                node_duration = time.time() - node_start
                self.logger.info(f"    Created in {node_duration:.2f}s")
                self.logger.debug(f"    Container ID: {container.id}")
                
            except Exception as e:
                self.logger.error(f"    Failed to create {node_name}: {e}")
                raise
        
        nodes_duration = time.time() - nodes_start
        self.logger.info(f"Created {len(self.nodes)} nodes ({nodes_duration:.2f}s)")
        self.logger.debug("-"*80)

    def configure_nodes(self):
        self.logger.info("Writing SSB config to nodes...")

        for node in self.nodes:
            node['container'].reload()
            net_data = node['container'].attrs['NetworkSettings']['Networks'][node['lan_name']]
            container_ip = net_data['IPAddress']
            gateway_ip = net_data['Gateway']

            # Store IPs on node dict for later use
            node['lan_ip'] = container_ip
            node['gateway_ip'] = gateway_ip

            config = {
                "host": container_ip,
                "port": 8008,
                "allowPrivate": True,
                #"caps": {
                #    "shs": "1KHLiKZvAvjbY1ziZEHMXawbCEIM6qwjCDm3VYRan/s="
                #}
            }

            config_json = json.dumps(config, indent=2)

            # Write config before SSB process reads it
            # Using printf rather than echo to avoid shell escaping issues with JSON
            result = node['container'].exec_run(
                f"sh -c 'mkdir -p /root/.ssb && printf \"%s\" {repr(config_json)} > /root/.ssb/config'"
            )

            if result.exit_code != 0:
                self.logger.error(f"  Failed to write config to {node['name']}: {result.output.decode()}")
            else:
                self.logger.info(f"  {node['name']}: config written ({container_ip})")

        self.logger.info("Node config complete")

    def configure_node_gateways(self):
            self.logger.info("Configuring gateway route on nodes...")

            for node in self.nodes:
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
                        self.logger.warning( f" ROute failed on {node['name']} : {cmd}")
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
            
            for node in self.nodes:
                if node['name'] in ready_nodes:
                    continue
                
                try:
                    self.logger.debug(f"Checking if {node['name']} is ready...")
                    
                    result = node['container'].exec_run(
                        "ssb-server whoami",
                        stderr=False
                    )
                    
                    if result.exit_code == 0:
                        ready_nodes.add(node['name'])
                        self.logger.info(f"    {node['name']} is ready ({len(ready_nodes)}/{self.num_nodes})")
                        self.logger.debug(f"    Response: {result.output.decode().strip()[:100]}...")
                    else:
                        self.logger.debug(f"    Not ready yet (exit code: {result.exit_code})")
                        
                except Exception as e:
                    self.logger.debug(f"    Error checking {node['name']}: {e}")
            
            if len(ready_nodes) < self.num_nodes:
                # Log progress every 10 seconds
                if time.time() - last_log_time > 10:
                    self.logger.debug(f"Progress: {len(ready_nodes)}/{self.num_nodes} ready after {elapsed:.1f}s")
                    last_log_time = time.time()
                
                time.sleep(check_interval)
        
        wait_duration = time.time() - wait_start
        
        if len(ready_nodes) == self.num_nodes:
            self.logger.info(f"All {len(ready_nodes)} nodes ready ({wait_duration:.2f}s)")
        else:
            self.logger.warning(f"Only {len(ready_nodes)}/{self.num_nodes} nodes ready after {wait_duration:.2f}s")
        
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
            lan_ip = node.get('lan_ip')
            if not lan_ip:
                node['container'].reload()
                net_data = node['container'].attrs['NetworkSettings']['Networks'][node['lan_name']]
                lan_ip = net_data['IPAddress']

            #lan_name = node['lan_name']
            #network_data = node['container'].attrs['NetworkSettings']['Networks'][lan_name]
            #LAN_address = network_data['Gateway']
            #IP_address = network_data['IPAddress']
            #print(f"LAN address is {LAN_address} and IP address is {IP_address}")
            
            address = f"net:{lan_ip}:8008~shs:{key}"
            #lan_gossip_address = f"net:{IP_address}:8000~shs:{key}"
            
            info = {
                'name': node['name'],
                'id': node_id,
                'key': key,
                'host': lan_ip,
                'port': 8008,
                'address': address#,
                #'ip_address' : IP_address,
                #'lan_gossip_address': lan_gossip_address,
                #'lan_name' : lan_name
            }
            
            node['info'] = info
            self.logger.debug(f"  Address: {address}")
            return info
            
        except Exception as e:
            self.logger.error(f"  Error getting info for {node['name']}: {e}")
            raise

    def establish_connections(self):
        #The friends 'mode' stuff: allotting nodes with who they should connect with 
        self.logger.info(f"  Establishing connections (mode: {self.friends_mode})...")
        connections_start = time.time()
        
        # Get info for all nodes
        self.logger.info("  Gathering node information...")
        info_start = time.time()
        
        node_infos = []
        for node in self.nodes:
            try:
                info = self.get_node_info(node)
                #node_infos.append(info)
                #node['info'] = info
                self.logger.debug(f"  Got info for {node['name']}")
            except Exception as e:
                self.logger.error(f"  Failed to get info for {node['name']}: {e}")
        
        info_duration = time.time() - info_start
        #self.logger.info(f"    Gathered info for {len(node_infos)} nodes ({info_duration:.2f}s)")
        
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
            
            self.logger.info(f"  {node['name']}: connecting to {num_friends} peers...")
            self.logger.debug(f"    Mode: {self.friends_mode}, Count: {num_friends}")
            
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
            
            self.logger.debug(f"    Connected to: {', '.join(node_connections)}")
        
        connections_duration = time.time() - connections_start
        
        self.logger.info(f"  Connections complete: {connections_made} successful, {connections_failed} failed ({connections_duration:.2f}s)")
        
        # Log detailed connection matrix
        self.logger.debug("Connection matrix:")
        for detail in connection_details:
            self.logger.debug(f"  {detail['node']}: {detail['count']} connections -> {detail['connections']}")
        
        self.logger.debug("-"*80)
        
        return {
            'successful': connections_made,
            'failed': connections_failed,
            'details': connection_details
        }
    
    def gossip_and_follow(self, node_a: Dict, node_b: Dict) -> bool:
        self.logger.debug(f"    Connecting {node_a['name']} -> {node_b['name']}...")
        
        try:
            #if they're in the same LAN, try somehting new and fun (use local address)
            if node_a["lan_name"] != node_b["lan_name"]:
                gossip_cmd = f'ssb-server gossip.connect "{node_b["info"]["address"]}"'
                result = node_a['container'].exec_run(gossip_cmd, stderr=True)

                if result.exit_code != 0:
                    self.logger.warning(f"         Gossip failed (exit {result.exit_code})")
                    self.logger.debug(f"      Output: {result.output.decode()[:200]}")
                    return False
            
                self.logger.debug(f"        Gossip successful")
                #gossip_cmd = f'ssb-server gossip.connect "{node_b["info"]["lan_gossip_address"]}"'
            # Gossip connect
            #else:
                #gossip_cmd = f'ssb-server gossip.connect "{node_b["info"]["address"]}"'
            #self.logger.debug(f"      Gossip command: {gossip_cmd}")
            
            
            
            
            # Follow
            follow_cmd = f'ssb-server publish --type contact --contact "{node_b["info"]["id"]}" --following'
            self.logger.debug(f"      Follow command: {follow_cmd}")
            
            result = node_a['container'].exec_run(follow_cmd, stderr=True)
            
            if result.exit_code != 0:
                self.logger.warning(f"         Follow failed (exit {result.exit_code})")
                self.logger.debug(f"      Output: {result.output.decode()[:200]}")
                return False
            
            self.logger.debug(f"        Follow successful")
            self.logger.info(f"      {node_a['name']} -> {node_b['name']}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"      Error: {node_a['name']} -> {node_b['name']}: {e}")
            return False
        
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
        overall_start = time.time()
        
        print("\n" + "="*80)
        print("SSB NETWORK SIMULATOR")
        print("="*80 + "\n")
        
        self.logger.info("Starting network simulation...")
        
        try:
            self.cleanup_existing()
            self.create_networks()
            self.create_router()
            self.get_router_ips()
            self.create_nodes()
            self.configure_nodes()
            self.configure_node_gateways()
            self.debug_container_status()
            
            if not self.wait_for_nodes_ready():
                self.logger.warning("Some nodes failed to start. Continuing anyway...")
            
            connection_stats = self.establish_connections()
            #self.print_network_summary()
            #self.save_network_config()
            
            overall_duration = time.time() - overall_start
            
            print(f"\nNetwork simulation setup complete! ({overall_duration:.2f}s)")
            print(f"\nSummary:")
            print(f"  - Nodes created: {len(self.nodes)}")
            print(f"  - Connections: {connection_stats['successful']} successful, {connection_stats['failed']} failed")
            print(f"  - Log file: {self.log_file}")
            
            print(f"\nTo interact with a node:")
            print(f"  docker exec -it {self.project_name}-node-1 bash")
            print(f"\nTo tear down:")
            print(f"  python3 {__file__} --cleanup\n")
            
            self.logger.info("="*80)
            self.logger.info(f"SIMULATION COMPLETE - Total time: {overall_duration:.2f}s")
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
    
    args = parser.parse_args()
    
    simulator = ssb_network_simulator(
        num_nodes=args.nodes,
        friends_mode=args.friends_mode,
        friends_range=(args.friends_min, args.friends_max),
        friends_fixed=args.friends_fixed,
        #base_port=args.base_port,
        #host_ip=args.host_ip,
        log_file=args.log_file
    )
    
    if args.cleanup:
        print("Cleanup mode")
        simulator.cleanup_existing()
        print("Cleanup complete")
    else:
        simulator.run()

if __name__ == '__main__':
    main()