from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from statistics import median
from pathlib import Path
import random
import time
import json
import matplotlib.pyplot as plt

#each scenario run will have a set of results in the same form and will need to be logged and plotted
#so I've made a class for it
class scenario_result:

    def __init__(self, name, message_id, posted_at, nodes_down, propagation_results, logs_dir, logger):
        self.logger = logger
        self.logs_dir = Path(logs_dir) if logs_dir else Path('./logs')
        self.name = name
        self.message_id = message_id
        self.posted_at = posted_at
        self.nodes_down = nodes_down
        self.propagation_results = propagation_results
        self.successes = self._get_successes()
        self.elapsed_list = self._get_elapsed_list()
        self.median_elapsed = self._get_median_elapsed()
        self.median_for_humans = self._for_humans(self.median_elapsed)
        self.propagation_rate = self._get_prop_rate()

    def report(self):
        self._log_result()
        self._print_result()
        self._plot_scenario()

    def _get_successes(self):
        return sum(1 for val in self.propagation_results.values() if val['received'])

    #public accessor
    def get_successes(self):
        return self._get_successes()

    def _get_elapsed_list(self):
        return [
            val['elapsed']
            for val in self.propagation_results.values()
            if val['received']
        ]

    def _get_median_elapsed(self):
        if not self.elapsed_list:
            return 0
        return median(self.elapsed_list)

    def _get_prop_rate(self):
        if len(self.propagation_results) == 0:
            return 0
        return self.successes / len(self.propagation_results)


    #for displaying the timestamps in a human readable way!
    def _for_humans(self, mili_value):
        seconds, miliseconds = divmod(mili_value, 1000)
        minutes, secs = divmod(seconds, 60)
        return f"{int(minutes)} minutes {int(secs)} seconds {miliseconds:.3f} miliseconds"

    def _log_result(self):
        if self.logger is not None:
            self.logger.info("\n" + "=" * 50)
            self.logger.info(f"  SCENARIO: {self.name.upper()}")
            self.logger.info("=" * 50)
            self.logger.info(f"  Message ID : {self.message_id}")
            self.logger.info(f"  Posted at  : {datetime.fromtimestamp(self.posted_at / 1000).strftime('%H:%M:%S.%f')[:-3]}")
            self.logger.info(f"  Nodes down : {self.nodes_down}")
            self.logger.info(f"  Completion : {self.propagation_rate * 100:.0f}%")
            self.logger.info(f"  Median     : {self.median_for_humans}")
            self.logger.info(f"\n")
            self.logger.info(f"  {'NODE':<25} {'LAN':<18} {'RECEIVED':<10} {'ELAPSED'}")
            self.logger.info(f"  {'-' * 24} {'-' * 17} {'-' * 9} {'-' * 15}")
            for node_name, data in self.propagation_results.items():
                received = "yes" if data['received'] else "no"
                elapsed = data['elapsed_human'] if data['received'] else "—"
                self.logger.info(f"  {node_name:<25} {data['lan']:<18} {received:<10} {elapsed}")
            self.logger.info("=" * 50 + "\n")

    def _print_result(self):
        print("\n" + "=" * 50)
        print(f"  SCENARIO: {self.name.upper()}")
        print("=" * 50)
        print(f"  Message ID : {self.message_id}")
        print(f"  Posted at  : {datetime.fromtimestamp(self.posted_at / 1000).strftime('%H:%M:%S.%f')[:-3]}")
        print(f"  Nodes down : {self.nodes_down}")
        print(f"  Completion : {self.propagation_rate * 100:.0f}%")
        print(f"  Median     : {self.median_for_humans}")
        print()
        print(f"  {'NODE':<25} {'LAN':<18} {'RECEIVED':<10} {'ELAPSED'}")
        print(f"  {'-' * 24} {'-' * 17} {'-' * 9} {'-' * 15}")
        for node_name, data in self.propagation_results.items():
            received = "yes" if data['received'] else "no"
            elapsed = data['elapsed_human'] if data['received'] else "—"
            print(f"  {node_name:<25} {data['lan']:<18} {received:<10} {elapsed}")
        print("=" * 50 + "\n")

    def _plot_scenario(self):
        nodes = list(self.propagation_results.keys())
        lan_colour_map = {}
        colour_cycle = plt.cm.tab10.colors

        for node_name, data in self.propagation_results.items():
            lan = data['lan']
            if lan not in lan_colour_map:
                lan_colour_map[lan] = colour_cycle[len(lan_colour_map) % len(colour_cycle)]

        received_times = [
            data['elapsed'] / 1000
            for data in self.propagation_results.values()
            if data['received']
        ]

        x_max = max(received_times) * 1.2 if received_times else 10

        fig, ax = plt.subplots(figsize=(10, max(4, len(nodes) * 0.4)))

        for i, (node_name, data) in enumerate(self.propagation_results.items()):
            lan = data['lan']
            colour = lan_colour_map[lan]
            if not data['received']:
                ax.barh(i, x_max, color='lightgrey', alpha=0.5)
                ax.text(0.2, i, 'NOT RECEIVED', va='center', color='red', fontsize=8)
            else:
                ax.barh(i, data['elapsed'] / 1000, color=colour, alpha=0.5)

        ax.set_xlim(0, x_max)
        ax.set_yticks(range(len(nodes)))
        ax.set_yticklabels(nodes, fontsize=8)
        ax.set_xlabel('Elapsed time (seconds)')
        ax.set_title(f'Propagation -- {self.name}')

        legend_handles = [
            plt.Rectangle((0, 0), 1, 1, color=c, label=lan)
            for lan, c in lan_colour_map.items()
        ]
        ax.legend(handles=legend_handles, title='LAN', loc='lower right')

        if self.median_elapsed:
            ax.axvline(self.median_elapsed / 1000, color='black', linestyle='--', label='Median')

        plt.tight_layout()

        # Save plots alongside logs rather than scattering them in the working directory
        output_path = self.logs_dir / f"{self.name}_{int(time.time())}.png"
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        if self.logger:
            self.logger.info(f"  Plot saved: {output_path}")


class propagation_demo:
    def __init__(self, ssb_simulator):
        self.simulator = ssb_simulator
        self.nodes = {node['name']: node for node in self.simulator.nodes}
        self.connection_graph = self._get_connection_graph()
        self.lan_graph = self._get_lan_graph()

    def _for_humans(self, mili_value):
        seconds, miliseconds = divmod(mili_value, 1000)
        minutes, secs = divmod(seconds, 60)
        return f"{int(minutes)} minutes {int(secs)} seconds {miliseconds:.3f} miliseconds"

    def _get_connection_graph(self):
        graph = {node['name']: set() for node in self.simulator.nodes}

        for detail in self.simulator.connection_details:
            for peer_name in detail['connections']:
                graph[detail['node']].add(peer_name)

        return graph

    def _get_lan_graph(self):
        lan_graph = {}
        for node in self.simulator.nodes:
            lan_name = node['lan_name']
            if lan_name not in lan_graph:
                lan_graph[lan_name] = set()
            lan_graph[lan_name].add(node['name'])
        return lan_graph

    #creating a scenario_result
    def _make_result(self, name, msg_id, posted_at, nodes_down, propagation):
        
        result = scenario_result(
            name, msg_id, posted_at, nodes_down, propagation,
            self.simulator.logs_dir, self.simulator.logger
        )
        result.report()
        return result

    def classify_nodes(self, author_name: str, graph: dict):

        direct = {
            peer for peer in graph[author_name]
        } | {
            name for name, peers in graph.items() if author_name in peers
        }

        indirect = {
            node['name'] for node in self.simulator.nodes
            if node['name'] != author_name
            and node['name'] not in direct
        }

        return direct, indirect

    def _poll_propagation(self, node_set, message_id, time_posted, timeout_in_mins):

        timeout = time.time() + timeout_in_mins * 60
        propagation = {
            node_name: {
                'elapsed': None,
                'elapsed_human': self._for_humans(timeout_in_mins * 60 * 1000),
                'lan': self.nodes[node_name]['lan_name'],
                'received': False
            }
            for node_name in node_set
        }

        pending = set(node_set)

        def check_one(node_name):
            cmd = f'ssb-server get "{message_id}"'
            result = self.nodes[node_name]['container'].exec_run(cmd, stderr=True)
            return node_name, result.exit_code == 0

        while pending and time.time() < timeout:
            with ThreadPoolExecutor(max_workers=min(len(pending), 20)) as executor:
                futures = {executor.submit(check_one, name): name for name in list(pending)}
                for future in as_completed(futures):
                    node_name, found = future.result()
                    self.simulator.logger.info(f"Polling {node_name} for post...")
                    if found:
                        time_found = time.time() * 1000
                        elapsed = time_found - time_posted
                        print(f"Post found on {node_name} at {time_found}")
                        propagation[node_name].update({
                            'elapsed': elapsed,
                            'elapsed_human': self._for_humans(elapsed),
                            'received': True
                        })
                        pending.discard(node_name)

            if pending:
                time.sleep(3)

        return propagation

    def _get_bootstrap_peers(self, node_name, nodes_down):
        direct, _ = self.classify_nodes(node_name, self.connection_graph)
        b_peers = [node for node in direct if node not in nodes_down]
        b_peers.append(node_name)
        return b_peers

    def restart_node(self, node_name, bootstrap_peers=None, feeds_to_request=None):
        self.nodes[node_name]['container'].start()
        self.simulator.logger.info(f"Restarted {node_name}, waiting for SSB to be ready...")

        timeout = time.time() + 30
        while time.time() < timeout:
            result = self.nodes[node_name]['container'].exec_run('ssb-server whoami', stderr=False)
            if result.exit_code == 0:
                self.simulator.logger.info(f"{node_name} is awake")
                break
            time.sleep(2)

        self.nodes[node_name]['container'].exec_run('ssb-server start', stderr=False)

        if bootstrap_peers:
            for peer in bootstrap_peers:
                peer_addr = self.nodes[peer]['info']['address']
                ready = 1
                while ready != 0:
                    self.simulator.logger.info(f"Attempt to bootstrap {node_name} by contacting {peer}")
                    peer_reconnect_attempt = self.nodes[node_name]['container'].exec_run(
                        f'ssb-server gossip.reconnect "{peer_addr}"'
                    )
                    ready = peer_reconnect_attempt.exit_code
                    if ready == 0:
                        break
                    time.sleep(2)
                self.simulator.logger.info(f"{node_name} successfully contacted {peer}")

        # Explicitly request replication of specific feeds rather than waiting
        # for SSB's gossip scheduler to decide to sync them. Without this,
        # ssb-replicate only syncs the connecting peer's own feed on reconnect
        # and then waits passively, meaning the author's feed may never arrive
        # within the polling window.
        if feeds_to_request:
            for feed_id in feeds_to_request:
                result = self.nodes[node_name]['container'].exec_run(
                    f'ssb-server replicate.request --id "{feed_id}" --replicate true'
                )
                self.simulator.logger.info(
                    f"{node_name}: requested replication of {feed_id[:20]}... "
                    f"(exit {result.exit_code})"
                )

    # ------------------------------------------------------------------ #
    #  Scenarios
    # ------------------------------------------------------------------ #

    def run_baseline(self, node_name) -> scenario_result:
        direct, indirect = self.classify_nodes(node_name, self.connection_graph)
        self.simulator.logger.info(f"Direct connections to {node_name}: {direct}")
        self.simulator.logger.info(f"Indirect connections to {node_name}: {indirect}")

        cmd = 'ssb-server publish --type post --text "heya its node 1"'
        result = self.nodes[node_name]['container'].exec_run(cmd, stderr=True)
        if result.exit_code == 0:
            data = json.loads(result.output.decode())
            msg_id = data['key']
            posted_at = data['value']['timestamp']

        propagation = self._poll_propagation(direct, msg_id, posted_at, 5)
        return self._make_result('baseline', msg_id, posted_at, None, propagation)

    def run_author_dropout(self, node_name) -> scenario_result:
        direct, indirect = self.classify_nodes(node_name, self.connection_graph)
        print(f"Direct connections to {node_name}: {direct}")
        print(f"Indirect connections to {node_name}: {indirect}")

        cmd = 'ssb-server publish --type post --text "heya its node 1, about to go offline!"'
        result = self.nodes[node_name]['container'].exec_run(cmd, stderr=True)

        if result.exit_code == 0:
            data = json.loads(result.output.decode())
            msg_id = data['key']
            posted_at = data['value']['timestamp']

        self.nodes[node_name]['container'].stop(timeout=0)

        propagation = self._poll_propagation(direct, msg_id, posted_at, 5)
        result = self._make_result('author_dropout', msg_id, posted_at, [node_name], propagation)

        bootstrap_peers = self._get_bootstrap_peers(node_name, [node_name])
        if bootstrap_peers is None:
            bootstrap_peers = [node_name]
        peer_ids = [
            self.nodes[peer]['info']['id']
            for peer in bootstrap_peers
        ]
        self.restart_node(node_name, bootstrap_peers, feeds_to_request=peer_ids)
        return result

    def run_lan_dropout(self, node_name):
        direct, indirect = self.classify_nodes(node_name, self.connection_graph)
        direct_copy = direct.copy()
        node_lan = self.nodes[node_name]['lan_name']
        same_lan_nodes = self.lan_graph[node_lan]

        same_lan_direct = []
        for node in list(direct_copy):
            if self.nodes[node]['lan_name'] == node_lan:
                same_lan_direct.append(node)
                direct_copy.remove(node)

        #added safeguard for nonsense
        if not direct_copy and not same_lan_direct:
            self.simulator.logger.warning(
                f"run_lan_dropout: node-1 has no cross-LAN or same-LAN direct connections "
                f"— skipping scenario as it would produce no meaningful data"
            )
            return None, None

        print(f"Direct connections to {node_name} not in {node_lan}: {direct_copy}")

        print(f"Direct connections to {node_name} not in {node_lan}: {direct_copy}")
        print(f"Nodes in same LAN as author: {same_lan_nodes}")
        print(f"External nodes: {direct_copy}")

        cmd = 'ssb-server publish --type post --text "heya its node 1, alone in my LAN!"'
        result = self.nodes[node_name]['container'].exec_run(cmd, stderr=True)
        if result.exit_code == 0:
            data = json.loads(result.output.decode())
            msg_id = data['key']
            posted_at = data['value']['timestamp']
        else:
            print(f"Publish failed: {result.output.decode()}")
            return None

        # Wait for at least one cross-LAN node to receive the post before pulling
        # the LAN down. Without this wait, node 1 goes offline before its message
        # has had any chance to propagate cross-LAN, making the scenario untestable.
        self.simulator.logger.info(
            "Waiting for cross-LAN propagation before stopping LAN nodes..."
        )
        pre_poll_timeout = time.time() + 30
        cross_lan_received = False
        while time.time() < pre_poll_timeout and not cross_lan_received:
            for node in direct_copy:
                check = self.nodes[node]['container'].exec_run(
                    f'ssb-server get "{msg_id}"', stderr=True
                )
                if check.exit_code == 0:
                    cross_lan_received = True
                    self.simulator.logger.info(
                        f"Cross-LAN node {node} has the post — proceeding with LAN dropout"
                    )
                    break
            if not cross_lan_received:
                time.sleep(2)

        if not cross_lan_received:
            self.simulator.logger.warning(
                "No cross-LAN node received the post within 30s pre-poll — "
                "LAN dropout result may not be meaningful"
            )

        # Stop all nodes on the same LAN (including the author)
        for node in list(same_lan_nodes):
            self.nodes[node]['container'].stop(timeout=0)
            print(f"Stopped node {node}")

        # Poll cross-LAN nodes
        non_lan_propagation = self._poll_propagation(direct_copy, msg_id, posted_at, 5)

        # Restart LAN nodes and measure catch-up
        author_id = self.nodes[node_name]['info']['id']
        for node in same_lan_nodes:
            bootstrap_peers = self._get_bootstrap_peers(node_name, same_lan_nodes)
            self.restart_node(node, bootstrap_peers, feeds_to_request=[author_id])

        restarted_at = time.time() * 1000
        nodes_to_catchup = same_lan_nodes - {node_name}
        same_lan_propagation = self._poll_propagation(nodes_to_catchup, msg_id, restarted_at, 5)

        non_lan_result = self._make_result(
            'same_lan_dropout', msg_id, posted_at, same_lan_nodes, non_lan_propagation
        )
        same_lan_result = self._make_result(
            'same_lan_catchup', msg_id, restarted_at, same_lan_nodes, same_lan_propagation
        )
        original_non_lan_result = non_lan_result

        # If no cross-LAN nodes received it, attempt a manual reconnect and retry
        # with a bounded retry limit to avoid infinite looping
        author_id = self.nodes[node_name]['info']['id']

        if non_lan_result.get_successes() == 0:
            for node in direct_copy:
                self.nodes[node]['container'].exec_run(
                    f'ssb-server gossip.reconnect "{self.nodes[node_name]["info"]["address"]}"'
                )
                self.nodes[node]['container'].exec_run(
                    f'ssb-server replicate.request "{author_id}"'
                ) 

            max_retries = 5
            for attempt in range(max_retries):
                self.simulator.logger.info(
                    f"Retrying cross-LAN propagation (attempt {attempt + 1}/{max_retries})..."
                )
                non_lan_propagation = self._poll_propagation(direct_copy, msg_id, posted_at, 5)
                non_lan_result = self._make_result(
                    'same_lan_dropout_rerun', msg_id, posted_at, same_lan_nodes, non_lan_propagation
                )
                if non_lan_result.get_successes() > 0:
                    break
            else:
                self.simulator.logger.error(
                    "Cross-LAN propagation failed after max retries — "
                    "the message may not have escaped the LAN before dropout"
                )

        return original_non_lan_result, same_lan_result

    def run_dropout_catchup(self, node_name):
        direct, indirect = self.classify_nodes(node_name, self.connection_graph)

        k = max(1, len(direct) // 2)
        nodes_to_drop = set(random.sample(list(direct), k=k))

        for node in nodes_to_drop:
            self.nodes[node]['container'].stop(timeout=0)
            print(f"Stopped container {node}")

        cmd = 'ssb-server publish --type post --text "heya its node 1 again. hope everyones having a great day"'
        result = self.nodes[node_name]['container'].exec_run(cmd, stderr=True)
        if result.exit_code == 0:
            data = json.loads(result.output.decode())
            msg_id = data['key']
            posted_at = data['value']['timestamp']
        else:
            print("Failed to publish, exiting")
            return None

        # Poll nodes that stayed up
        propagation = self._poll_propagation(direct - nodes_to_drop, msg_id, posted_at, 5)

        # If no cross-LAN nodes received it, nudge gossip
        non_lan_online_results = [
            propagation[node]['received']
            for node in propagation
            if self.nodes[node]['lan_name'] != self.nodes[node_name]['lan_name']
        ]
        author_id = self.nodes[node_name]['info']['id']

        if True not in non_lan_online_results:
            for node in propagation:
                self.nodes[node]['container'].exec_run(
                    f'ssb-server gossip.reconnect "{self.nodes[node_name]["info"]["address"]}"'
                )
                self.nodes[node]['container'].exec_run(
                    f'ssb-server replicate.request "{author_id}"'
                )



        # Restart dropped nodes and measure catch-up
        author_id = self.nodes[node_name]['info']['id']
        restart_time = time.time() * 1000
        
        for node in nodes_to_drop:
            bootstrap_peers = self._get_bootstrap_peers(node_name, nodes_to_drop)
            self.restart_node(node, bootstrap_peers, feeds_to_request=[author_id])

        dropout_propagation = self._poll_propagation(nodes_to_drop, msg_id, restart_time, 5)

        # Same nudge for dropped nodes if no cross-LAN reception
        non_lan_dropout_results = [
            dropout_propagation[node]['received']
            for node in dropout_propagation
            if self.nodes[node]['lan_name'] != self.nodes[node_name]['lan_name']
        ]
        if True not in non_lan_dropout_results:
            for node in dropout_propagation:
                self.nodes[node]['container'].exec_run(
                    f'ssb-server gossip.reconnect "{self.nodes[node_name]["info"]["address"]}"'
                )
                self.nodes[node]['container'].exec_run(
                    f'ssb-server replicate.request "{author_id}"'
                )

        return (
            self._make_result('random_dropout', msg_id, posted_at, nodes_to_drop, propagation),
            self._make_result('random_dropout_catchup', msg_id, restart_time, nodes_to_drop, dropout_propagation)
        )

    def run_lan_migration(self, node_name) -> scenario_result:
        node = self.nodes[node_name]
        direct, indirect = self.classify_nodes(node_name, self.connection_graph)

        # stopping the ssb-server process
        node['container'].exec_run("pkill -f ssb-server")
        
        # Polling until the process is gone
        deadline = time.time() + 15
        while time.time() < deadline:
            check = node['container'].exec_run("pgrep -f ssb-server")
            if check.exit_code != 0:  # pgrep returns 1 if no process found
                self.simulator.logger.info(f"{node_name}: ssb-server process confirmed dead")
                break
            time.sleep(0.5)
        else:
            self.simulator.logger.warning(f"{node_name}: ssb-server did not die cleanly, trying SIGKILL")
            node['container'].exec_run("pkill -9 -f ssb-server")
            time.sleep(2)

        # Having to explicityly remove lock files, as it was a problem before :(
        node['container'].exec_run("rm -f /root/.ssb/LOCK /root/.ssb/blobs_push/LOCK")

        old_lan = node['lan_name']
        old_lan_network = self.simulator.client.networks.get(old_lan)
        # using the docker network object disconnect() to remove the container from the LAN
        old_lan_network.disconnect(node['container'])
        self.simulator.logger.info(f"{node_name}: disconnected from {old_lan}")

        # Find an alternate LAN
        new_lan = next(lan for lan in self.lan_graph if lan != old_lan)

        new_lan_network = self.simulator.client.networks.get(new_lan)
        new_lan_network.connect(node['container'])
        node['container'].reload()
        new_ip = node['container'].attrs['NetworkSettings']['Networks'][new_lan]['IPAddress']
        self.simulator.logger.info(f"{node_name}: connected to {new_lan}, new IP address {new_ip}")

        self.simulator._write_config(node, {
            "host": new_ip,
            "port": 8008,
            "allowPrivate": True
        })

        time.sleep(2)
        # Starting the ssb-server process with the new IP
        node['container'].exec_run(
            f'ssb-server start --host {new_ip} &', detach=True
        )
        
        # Waiting for it to actually be responsive before proceeding
        deadline = time.time() + 30
        while time.time() < deadline:
            result = node['container'].exec_run('ssb-server whoami', stderr=False)
            if result.exit_code == 0:
                self.simulator.logger.info(f"{node_name}: ssb-server is up on {new_ip}")
                break
            time.sleep(1)
        else:
            self.simulator.logger.error(f"{node_name}: ssb-server failed to come up after migration")
            return None
        time.sleep(3)

        key = node['info']['key']
        new_address = f"net:{new_ip}:8008~shs:{key}"
        node['info']['address'] = new_address
        node['lan_name'] = new_lan

        # Re-gossip to one known peer so the new address propagates
        # (should i go through all peers?)
        for peer_name in direct:
            peer_address = self.nodes[peer_name]['info']['address']
            node['container'].exec_run(f'ssb-server gossip.connect "{peer_address}"')
            self.simulator.logger.info(f"{node_name}: re-gossiped to {peer_name} at {new_ip}")
            break

        migration_time = time.time() * 1000
        cmd = 'ssb-server publish --type post --text "Hi its me and ive changed LAN!!!"'
        result = node['container'].exec_run(cmd, stderr=True)
        if result.exit_code != 0:
            self.simulator.logger.error(f"Post failed after migration: {result.output.decode()}")
            return None

        data = json.loads(result.output.decode())
        msg_id = data['key']
        posted_at = data['value']['timestamp']

        propagation = self._poll_propagation(direct, msg_id, posted_at, 5)
        return self._make_result('lan_migration', msg_id, posted_at, [], propagation)
