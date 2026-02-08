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
                  base_port: int = 8000, host_ip: str = '192.168.1.7',
                  log_file: str = None):
        self.num_nodes = num_nodes
        self.friends_mode = friends_mode # either 'random', 'range', 'fixed'
        self.friends_range = friends_range
        self.friends_fixed = friends_fixed
        self.base_port = base_port
        self.host_ip = host_ip

        self.client = docker.from_env()
        self.project_name = "ssb-sim"
        self.nodes: List[Dict] = []

        self.data_dir = Path('./data')
        self.discovery_dir = Path('./discovery')
        self.logs_dir = Path('./logs')

        self.data_dir.mkdir(exist_ok=True)
        self.discovery_dir.mkdir(exist_ok=True)
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
        self.logger.info(f"  - Base port: {self.base_port}")
        self.logger.info(f"  - Host IP: {self.host_ip}")
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
            if container.name.startswith(f"{self.project_name}-node-"):
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
        
        self.networks = []
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

    def create_nodes(self):
        self.logger.info(f"Creating {self.num_nodes} SSB nodes...")
        nodes_start = time.time()
        
        for i in range(self.num_nodes):
            node_start = time.time()
            node_name = f"{self.project_name}-node-{i+1}"
            port = self.base_port + i
            
            #Assigning nodes to LANs
            lan_index = i % len(self.networks)
            network = self.networks[lan_index]['network']
            network_name = self.networks[lan_index]['name']
            
            # Create data directory
            node_data_dir = self.data_dir / f"node-{i+1}"
            node_data_dir.mkdir(exist_ok=True)
            
            self.logger.info(f"  Creating {node_name}...")
            self.logger.debug(f"    Port mapping: {port} -> 8008")
            self.logger.debug(f"    Network: {network_name}")
            self.logger.debug(f"    Data directory: {node_data_dir}")
            
            try:
                container = self.client.containers.run(
                    "ssb-demo-docker-alice",
                    name=node_name,
                    hostname=node_name,
                    detach=True,
                    ports={
                        '8008/tcp': port
                    },
                    volumes={
                        str(node_data_dir.absolute()): {'bind': '/root/.ssb', 'mode': 'rw'},
                        str(self.discovery_dir.absolute()): {'bind': '/discovery', 'mode': 'rw'}
                    },
                    network=network.name,
                    remove=False
                )
                
                node_info = {
                    'name': node_name,
                    'container': container,
                    'port': port,
                    'lan': lan_index,
                    'lan_name': network_name,
                    'id': i + 1,
                    'container_id': container.id
                }
                
                self.nodes.append(node_info)
                
                node_duration = time.time() - node_start
                self.logger.info(f"    ✓ Created in {node_duration:.2f}s")
                self.logger.debug(f"    Container ID: {container.id}")
                
            except Exception as e:
                self.logger.error(f"    ✗ Failed to create {node_name}: {e}")
                raise
        
        nodes_duration = time.time() - nodes_start
        self.logger.info(f"✅ Created {len(self.nodes)} nodes ({nodes_duration:.2f}s)")
        self.logger.debug("-"*80)

    def run(self):
        """Main execution flow."""
        overall_start = time.time()
        
        print("\n" + "="*80)
        print("SSB NETWORK SIMULATOR")
        print("="*80 + "\n")
        
        self.logger.info("Starting network simulation...")
        
        try:
            self.cleanup_existing()
            self.create_networks()
            #self.create_nodes()
            
            #if not self.wait_for_nodes_ready():
                #self.logger.warning("Some nodes failed to start. Continuing anyway...")
            
            #connection_stats = self.establish_connections()
            #self.print_network_summary()
            #self.save_network_config()
            
            overall_duration = time.time() - overall_start
            
            print(f"\nNetwork simulation setup complete! ({overall_duration:.2f}s)")
            print(f"\nSummary:")
            #print(f"  - Nodes created: {len(self.nodes)}")
            #print(f"  - Connections: {connection_stats['successful']} successful, {connection_stats['failed']} failed")
            print(f"  - Log file: {self.log_file}")
            
            #print(f"\nTo interact with a node:")
            #print(f"  docker exec -it {self.project_name}-node-1 bash")
            #print(f"\nTo tear down:")
            #print(f"  python3 {__file__} --cleanup\n")
            
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
        description='SSB Network Simulator - Create and manage SSB node networks with extensive logging'
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
        default='192.168.1.7',
        help='Your host machine IP address (default: 192.168.1.7)'
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
        base_port=args.base_port,
        host_ip=args.host_ip,
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