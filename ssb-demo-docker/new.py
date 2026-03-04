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
    def __init__(self, num_nodes: int = 10, friends_mode: str = 'range',
                 friends_range: Tuple[int, int] = (2, 5), friends_fixed: int = 3,
                 log_file: str = None):
        self.num_nodes = num_nodes
        self.friends_mode = friends_mode
        self.friends_range = friends_range
        self.friends_fixed = friends_fixed

        self.client = docker.from_env()
        self.project_name = "ssb-sim"
        self.nodes: List[Dict] = []
        self.networks = []
        self.router = None
        self.router_ips = {}

        self.data_dir = Path('./data')
        self.logs_dir = Path('./logs')
        self.data_dir.mkdir(exist_ok=True)
        self.logs_dir.mkdir(exist_ok=True)

        if log_file is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_file = self.logs_dir / f'ssb_sim_{timestamp}.log'
        self.log_file = Path(log_file) if log_file else log_file
        self._setup_logging()

        self.logger.info("="*80)
        self.logger.info("SSB NETWORK SIMULATOR INITIALIZED")
        self.logger.info("="*80)
        self.logger.info(f"  Nodes: {self.num_nodes}, Friends mode: {self.friends_mode}")
        self.logger.info("="*80)

    def _setup_logging(self):
        self.logger = logging.getLogger('SSBSimulator')
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers = []

        file_handler = logging.FileHandler(self.log_file, mode='w', encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter('%(message)s'))

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def cleanup_existing(self):
        self.logger.info("Cleaning up existing containers and networks...")

        for container in self.client.containers.list(all=True):
            if (container.name.startswith(f"{self.project_name}-node-") or
                    container.name == f"{self.project_name}-router"):
                self.logger.info(f"  Removing container: {container.name}")
                try:
                    container.stop(timeout=10)
                    container.remove()
                except Exception as e:
                    self.logger.error(f"  Error removing {container.name}: {e}")

        for network in self.client.networks.list():
            if network.name.startswith(f"{self.project_name}-"):
                self.logger.info(f"  Removing network: {network.name}")
                try:
                    network.remove()
                except Exception as e:
                    self.logger.warning(f"  Could not remove network {network.name}: {e}")

        self.logger.info("Cleanup complete")

    def create_networks(self):
        self.logger.info("Creating Docker networks...")
        num_lans = (self.num_nodes + 4) // 5

        for i in range(num_lans):
            network_name = f"{self.project_name}-lan-{i+1}"
            subnet = f"10.10.{i+1}.0/24"

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
            except Exception as e:
                self.logger.error(f"  Failed to create {network_name}: {e}")
                raise

        self.logger.info(f"Created {len(self.networks)} networks")

    def create_router(self):
        self.logger.info("Creating router container...")
        first_network = self.networks[0]['name']

        try:
            self.router = self.client.containers.run(
                "ssb-router",
                name=f"{self.project_name}-router",
                detach=True,
                network=first_network,
                sysctls={"net.ipv4.ip_forward": "1"},
                cap_add=["NET_ADMIN"],
                remove=False
            )

            # Attach router to every other LAN
            for net_info in self.networks[1:]:
                self.logger.info(f"  Attaching router to {net_info['name']}")
                net_info['network'].connect(self.router)

            self.logger.info(f"Router attached to {len(self.networks)} networks")

        except Exception as e:
            self.logger.error(f"Failed to create router: {e}")
            raise

    def get_router_ips(self):
        self.logger.info("Getting router IPs on each LAN...")
        self.router.reload()

        for net_info in self.networks:
            net_name = net_info['name']
            net_data = self.router.attrs['NetworkSettings']['Networks'][net_name]
            ip = net_data['IPAddress']
            self.router_ips[net_name] = ip
            self.logger.info(f"  Router on {net_name}: {ip}")

        return self.router_ips

    def create_nodes(self):
        """
        Create node containers and attach them to their LAN.
        No port forwarding - nodes communicate directly via Docker networks.
        Only the .ssb data directory is mounted; config is written by
        configure_nodes() before SSB reads it.
        """
        self.logger.info(f"Creating {self.num_nodes} SSB nodes...")

        for i in range(self.num_nodes):
            node_name = f"{self.project_name}-node-{i+1}"
            lan_index = i // 5  # contiguous assignment - nodes 1-5 on LAN1, 6-10 on LAN2
            network_name = self.networks[lan_index]['name']

            node_data_dir = self.data_dir / f"node-{i+1}"
            node_data_dir.mkdir(exist_ok=True)

            self.logger.info(f"  Creating {node_name} on {network_name}...")

            try:
                container = self.client.containers.run(
                    "ssb-node",
                    name=node_name,
                    hostname=node_name,
                    detach=True,
                    # No ports mapping - direct container-to-container communication only
                    volumes={
                        str(node_data_dir.absolute()): {
                            'bind': '/root/.ssb',
                            'mode': 'rw'
                        }
                    },
                    network=network_name,
                    remove=False
                )

                self.nodes.append({
                    'name': node_name,
                    'container': container,
                    'lan': lan_index,
                    'lan_name': network_name,
                    'id': i + 1,
                    'container_id': container.id
                })

                self.logger.info(f"    Created {node_name}")

            except Exception as e:
                self.logger.error(f"  Failed to create {node_name}: {e}")
                raise

        self.logger.info(f"Created {len(self.nodes)} nodes")

    def configure_nodes(self):
        """
        Write .ssb/config to each node immediately after container creation,
        before SSB has started and cached a wrong address.
        Sets the node's LAN IP as its advertised host so SSB binds and
        announces the correct address for peer discovery and gossip.
        """
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
                "caps": {
                    "shs": "1KHLiKZvAvjbY1ziZEHMXawbCEIM6qwjCDm3VYRan/s="
                }
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

    def configure_node_routes(self):
        """Add routes to each node so cross-LAN traffic is forwarded via the router."""
        self.logger.info("Configuring routes on nodes...")

        for node in self.nodes:
            router_ip = self.router_ips[node['lan_name']]

            for net_info in self.networks:
                if net_info['name'] == node['lan_name']:
                    continue

                subnet = net_info['subnet']
                result = node['container'].exec_run(
                    f"ip route add {subnet} via {router_ip}",
                    privileged=True
                )

                if result.exit_code != 0:
                    self.logger.warning(
                        f"  Route failed on {node['name']} to {subnet}: "
                        f"{result.output.decode().strip()}"
                    )
                else:
                    self.logger.debug(f"  {node['name']}: route to {subnet} via {router_ip}")

        self.logger.info("Route configuration complete")

    def wait_for_nodes_ready(self, timeout: int = 60):
        self.logger.info(f"Waiting for nodes to be ready (timeout: {timeout}s)...")
        wait_start = time.time()
        ready_nodes = set()

        while len(ready_nodes) < self.num_nodes:
            elapsed = time.time() - wait_start
            if elapsed > timeout:
                self.logger.error(f"Timeout! Only {len(ready_nodes)}/{self.num_nodes} nodes ready")
                break

            for node in self.nodes:
                if node['name'] in ready_nodes:
                    continue
                try:
                    result = node['container'].exec_run("ssb-server whoami", stderr=False)
                    if result.exit_code == 0:
                        ready_nodes.add(node['name'])
                        self.logger.info(f"  {node['name']} ready ({len(ready_nodes)}/{self.num_nodes})")
                except Exception as e:
                    self.logger.debug(f"  {node['name']} not ready: {e}")

            if len(ready_nodes) < self.num_nodes:
                time.sleep(2)

        return len(ready_nodes) == self.num_nodes

    def get_node_info(self, node: Dict) -> Dict:
        """
        Get SSB identity info for a node.
        Uses the node's LAN IP directly — no host IP or port forwarding.
        """
        try:
            result = node['container'].exec_run(
                "ssb-server whoami",
                stderr=False
            )

            if result.exit_code != 0:
                raise Exception(f"whoami failed with exit code {result.exit_code}")

            whoami = json.loads(result.output.decode().strip())
            node_id = whoami['id']
            key = node_id.replace('@', '').replace('.ed25519', '')

            # Address uses the container's LAN IP, not the host machine
            lan_ip = node.get('lan_ip')
            if not lan_ip:
                node['container'].reload()
                net_data = node['container'].attrs['NetworkSettings']['Networks'][node['lan_name']]
                lan_ip = net_data['IPAddress']

            address = f"net:{lan_ip}:8008~shs:{key}"

            info = {
                'name': node['name'],
                'id': node_id,
                'key': key,
                'host': lan_ip,
                'port': 8008,
                'address': address
            }

            node['info'] = info
            self.logger.debug(f"  {node['name']}: {address}")
            return info

        except Exception as e:
            self.logger.error(f"  Error getting info for {node['name']}: {e}")
            raise

    def establish_connections(self):
        self.logger.info(f"Establishing connections (mode: {self.friends_mode})...")

        self.logger.info("  Gathering node information...")
        for node in self.nodes:
            try:
                self.get_node_info(node)
            except Exception as e:
                self.logger.error(f"  Failed to get info for {node['name']}: {e}")

        connections_made = 0
        connections_failed = 0
        self.connection_details = []

        for i, node in enumerate(self.nodes):
            if 'info' not in node:
                self.logger.warning(f"  Skipping {node['name']} (no info)")
                continue

            if self.friends_mode == 'random':
                num_friends = random.randint(1, self.num_nodes - 1)
            elif self.friends_mode == 'range':
                num_friends = random.randint(
                    min(self.friends_range[0], self.num_nodes - 1),
                    min(self.friends_range[1], self.num_nodes - 1)
                )
            else:
                num_friends = min(self.friends_fixed, self.num_nodes - 1)

            available = [j for j in range(len(self.nodes)) if j != i and 'info' in self.nodes[j]]
            friend_indices = random.sample(available, min(num_friends, len(available)))

            node_connections = []
            for friend_idx in friend_indices:
                friend = self.nodes[friend_idx]
                if self.gossip_and_follow(node, friend):
                    connections_made += 1
                    node_connections.append(friend['name'])
                else:
                    connections_failed += 1

            self.connection_details.append({
                'node': node['name'],
                'connections': node_connections,
                'count': len(node_connections)
            })

        self.logger.info(f"Connections: {connections_made} successful, {connections_failed} failed")
        return {'successful': connections_made, 'failed': connections_failed}

    def gossip_and_follow(self, node_a: Dict, node_b: Dict) -> bool:
        try:
            result = node_a['container'].exec_run(
                f'ssb-server gossip.connect "{node_b["info"]["address"]}"',
                stderr=True
            )
            if result.exit_code != 0:
                self.logger.warning(f"  Gossip failed: {node_a['name']} -> {node_b['name']}")
                return False

            result = node_a['container'].exec_run(
                f'ssb-server publish --type contact --contact "{node_b["info"]["id"]}" --following',
                stderr=True
            )
            if result.exit_code != 0:
                self.logger.warning(f"  Follow failed: {node_a['name']} -> {node_b['name']}")
                return False

            self.logger.info(f"  {node_a['name']} -> {node_b['name']}")
            return True

        except Exception as e:
            self.logger.error(f"  Error: {node_a['name']} -> {node_b['name']}: {e}")
            return False

    def debug_container_status(self):
        for node in self.nodes:
            node['container'].reload()
            status = node['container'].status
            if status != 'running':
                self.logger.error(f"{node['name']} is {status}")
                logs = node['container'].logs(tail=20).decode('utf-8', errors='replace')
                self.logger.error(f"  Logs:\n{logs}")

    def run(self):
        overall_start = time.time()
        print("\n" + "="*80)
        print("SSB NETWORK SIMULATOR")
        print("="*80 + "\n")

        try:
            self.cleanup_existing()
            self.create_networks()
            self.create_router()
            self.get_router_ips()
            self.create_nodes()
            self.configure_nodes()       # write config before SSB reads it
            self.configure_node_routes() # add cross-LAN routes via router
            self.debug_container_status()

            if not self.wait_for_nodes_ready():
                self.logger.warning("Some nodes not ready, continuing anyway...")

            connection_stats = self.establish_connections()

            duration = time.time() - overall_start
            print(f"\nSimulation setup complete ({duration:.2f}s)")
            print(f"  Nodes: {len(self.nodes)}")
            print(f"  Connections: {connection_stats['successful']} successful, {connection_stats['failed']} failed")
            print(f"  Log: {self.log_file}")
            print(f"\nTo interact: docker exec -it {self.project_name}-node-1 bash")
            print(f"To teardown: python3 {__file__} --cleanup\n")

        except KeyboardInterrupt:
            print("\nInterrupted")
            self.logger.warning("Interrupted by user")
        except Exception as e:
            self.logger.error(f"Simulation failed: {e}", exc_info=True)
            raise


def main():
    parser = argparse.ArgumentParser(description='SSB Network Simulator')

    parser.add_argument('--nodes', '-n', type=int, default=10)
    parser.add_argument('--friends-mode', '-m',
                        choices=['random', 'range', 'fixed'], default='range')
    parser.add_argument('--friends-min', type=int, default=2)
    parser.add_argument('--friends-max', type=int, default=5)
    parser.add_argument('--friends-fixed', type=int, default=3)
    parser.add_argument('--log-file', type=str, default=None)
    parser.add_argument('--cleanup', action='store_true')

    args = parser.parse_args()

    simulator = ssb_network_simulator(
        num_nodes=args.nodes,
        friends_mode=args.friends_mode,
        friends_range=(args.friends_min, args.friends_max),
        friends_fixed=args.friends_fixed,
        log_file=args.log_file
    )

    if args.cleanup:
        simulator.cleanup_existing()
        print("Cleanup complete")
    else:
        simulator.run()


if __name__ == '__main__':
    main()
```

The critical ordering in `run()` is:
```
create_nodes()        # container exists, SSB not yet responsive
configure_nodes()     # config written while SSB is still starting up
configure_node_routes()
wait_for_nodes_ready()  # NOW poll — SSB will start with the correct config already in place