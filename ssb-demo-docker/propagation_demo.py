from datetime import datetime
import random
from statistics import median
import time
import json
import matplotlib.pyplot as plt
import numpy as np

class scenario_result:
    
    def __init__(self, name, message_id, posted_at, nodes_down, propagation_results, logger):
        self.logger = logger
        self.name = name
        self.message_id = message_id
        self.posted_at = posted_at
        self.nodes_down = nodes_down
        self.propagation_results = propagation_results
        self.successes = self.get_successes()
        self.elapsed_list = self.get_elapsed_list()
        self.median_elapsed = self.get_median_elapsed()
        self.median_for_humans = self.for_humans(self.median_elapsed)
        self.propagation_rate = self.get_prop_rate()
        self.log_result()
        self.print_result()
        self.plot_scenario()

    def get_successes(self):
        successes = 0
        for key, val in self.propagation_results.items():
            if val['received']:
                successes += 1
        return successes
    
    def get_elapsed_list(self):
        list_elapsed = []
        for key, val in self.propagation_results.items():
            if val['received']:
                list_elapsed.append(val['elapsed'])

        return list_elapsed
    
    def get_median_elapsed(self):
        if not self.elapsed_list:
            return 0
        return median(self.elapsed_list)
    
    def get_prop_rate(self):
        if len(self.propagation_results) == 0:
            return 0
        else:
            return self.successes / len(self.propagation_results)

    def for_humans(self, mili_value):
        seconds, miliseconds = divmod(mili_value, 1000)
        minutes, secs = divmod(seconds, 60)
        return f"{int(minutes)} minutes {int(secs)} seconds {miliseconds:.3f} miliseconds"
    
    def log_result(self):
        if self.logger != None:
            self.logger.info("\n" + "="*50)
            self.logger.info(f"  SCENARIO: {self.name.upper()}")
            self.logger.info("="*50)
            self.logger.info(f"  Message ID : {self.message_id}")
            self.logger.info(f"  Posted at  : {datetime.fromtimestamp(self.posted_at / 1000).strftime('%H:%M:%S.%f')[:-3]}")
            self.logger.info(f"  Nodes down : {self.nodes_down}")
            self.logger.info(f"  Completion : {self.propagation_rate*100:.0f}%")
            self.logger.info(f"  Median     : {self.median_for_humans}")
            self.logger.info(f"\n")
            self.logger.info(f"  {'NODE':<25} {'LAN':<18} {'RECEIVED':<10} {'ELAPSED'}")
            self.logger.info(f"  {'-'*24} {'-'*17} {'-'*9} {'-'*15}")
            for node_name, data in self.propagation_results.items():
                received = "yes" if data['received'] else "no"
                elapsed = data['elapsed_human'] if data['received'] else "—"
                self.logger.info(f"  {node_name:<25} {data['lan']:<18} {received:<10} {elapsed}")
            self.logger.info("="*50 + "\n")

    def print_result(self):
        print("\n" + "="*50)
        print(f"  SCENARIO: {self.name.upper()}")
        print("="*50)
        print(f"  Message ID : {self.message_id}")
        print(f"  Posted at  : {datetime.fromtimestamp(self.posted_at / 1000).strftime('%H:%M:%S.%f')[:-3]}")
        print(f"  Nodes down : {self.nodes_down}")
        print(f"  Completion : {self.propagation_rate*100:.0f}%")
        print(f"  Median     : {self.median_for_humans}")
        print()
        print(f"  {'NODE':<25} {'LAN':<18} {'RECEIVED':<10} {'ELAPSED'}")
        print(f"  {'-'*24} {'-'*17} {'-'*9} {'-'*15}")
        for node_name, data in self.propagation_results.items():
            received = "yes" if data['received'] else "no"
            elapsed = data['elapsed_human'] if data['received'] else "—"
            print(f"  {node_name:<25} {data['lan']:<18} {received:<10} {elapsed}")
        print("="*50 + "\n") 

    def plot_scenario(self):
        nodes = list(self.propagation_results.keys())
        lan_colour_map = {}
        colour_cycle = plt.cm.tab10.colors
        received_times = []

        for node_name, data in self.propagation_results.items():
            # each lan colour
            lan = data['lan']
            if lan not in lan_colour_map:
                lan_colour_map[lan] = colour_cycle[len(lan_colour_map) % len(colour_cycle)]

            if data['received']:
                received_times.append(data['elapsed'] / 1000)
    
        #finding the max out of received times
        if received_times:

            x_max = max(received_times) * 1.2  
        else:
            x_max = 10

        fig, ax = plt.subplots(figsize=(10, max(4, len(nodes) * 0.4)))

        for i, (node_name, data) in enumerate(self.propagation_results.items()):
            lan = data['lan']
            colour = lan_colour_map[lan]
            if not data['received']:
                ax.barh(i, x_max, color = 'lightgrey', alpha = 0.5)
                ax.text(0.2, i, 'NOT RECEIVED', va='center', color = 'red', fontsize = 8)
            else:
                ax.barh(i, data['elapsed']/ 1000, color = colour, alpha = 0.5)
                

        ax.set_xlim(0, x_max)
        ax.set_yticks(range(len(nodes)))
        ax.set_yticklabels(nodes, fontsize = 8)
        ax.set_xlabel('Elapsed time (seconds)')
        ax.set_title(f'Propagation -- {self.name}')

        legend_handles = [
            plt.Rectangle((0, 0), 1, 1, color = c, label = lan)
            for lan, c in lan_colour_map.items()
        ]
        ax.legend(handles=legend_handles, title='LAN', loc = 'lower right')

        if self.median_elapsed:
            ax.axvline(self.median_elapsed / 1000, color = 'black', linestyle = '--', label = 'Median')

        plt.tight_layout()
        plt.savefig(f"{self.name}{time.time()}.png", dpi = 150, bbox_inches = 'tight')
        plt.close()





class propagation_demo:
    def __init__(self, ssb_simulator):
        self.simulator = ssb_simulator
        self.nodes = {node['name']: node for node in self.simulator.nodes}
        self.connection_graph = self.get_connection_graph()
        self.lan_graph = self.get_lan_graph()

    def for_humans(self, mili_value):
        seconds, miliseconds = divmod(mili_value, 1000)
        minutes, secs = divmod(seconds, 60)
        return f"{int(minutes)} minutes {int(secs)} seconds {miliseconds:.3f} miliseconds"
    def get_connection_graph(self):
        
        graph = {}
        #going through each node and making a key pair of the node name and a set
        for node in self.simulator.nodes:
            graph[node['name']] = set()
        
        #print(f"Connection details whole object :{self.simulator.connection_details}")

        #adding the direct connections of a node to it's corresponding set()
        for detail in self.simulator.connection_details:
            for peer_name in detail['connections']:
                graph[detail['node']].add(peer_name)
        
        return graph
    
    def get_lan_graph(self):
        lan_graph = {}
        #going through each node, get the lan name
        #if not in graph, add it, and add node name to set() 
        #if it is, add node name to set
        for node in self.simulator.nodes:
            lan_name = node['lan_name']
            if(lan_name not in lan_graph):
                lan_graph[lan_name] = set()
            lan_graph[lan_name].add(node['name'])

        return lan_graph

    def classify_nodes(self, author_name: str, graph: dict):
        #direct nodes are in the connection graph already listed
        # and double checking if the direct conneciton is 'one-sided'
        # they are peers in each others tables, even if there is no direct follow
        # irrespective of follows, propagation will occur 
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
      
    def poll_propogation(self, direct_cs, message_id, time_posted, timeout_in_mins):
        timeout = time.time() + timeout_in_mins * 60
        timeout_milis = timeout * 1000
        propagation = {}
        for node_name in direct_cs:
            propagation.update({node_name : {'elapsed' : None, 'elapsed_human': self.for_humans(timeout_milis), 'lan' : self.nodes[node_name]['lan_name'], 'received' : False}})

        direct_copy = direct_cs.copy()
        while len(direct_copy) > 0 and time.time() < timeout:
            for node_name in list(direct_copy):
                self.simulator.logger.info(f"Polling {node_name} for post...")
                cmd = f'ssb-server get "{message_id}"'
                result = self.nodes[node_name]['container'].exec_run(cmd, stderr=True)
                #print(f"Result from get message id is: {result}")

                if result.exit_code == 0:
                    time_found = time.time() * 1000
                    print(f"Post found on {node_name} at {time_found}")
                    propagation[node_name].update({'elapsed' : time_found - time_posted, 'elapsed_human': self.for_humans(time_found - time_posted), 'received' : True})
                    direct_copy.remove(node_name)
                
            if direct_copy:
                time.sleep(3)

        return propagation

    def run_baseline(self, node_name) -> scenario_result: 

        direct, indirect = self.classify_nodes(node_name, self.connection_graph)
        self.simulator.logger.info(f"Direct connections to node 1 are: {direct}")
        
        self.simulator.logger.info(f"Indirect connections to node 1 are: {indirect}")
        cmd = 'ssb-server publish --type post --text "heya its node 1"'
        result = self.nodes[node_name]['container'].exec_run(cmd, stderr=True)
        if result.exit_code == 0:
            data = json.loads(result.output.decode())
            msg_id = data['key']
            posted_at = data['value']['timestamp']
            
        propagation = self.poll_propogation(direct, msg_id, posted_at, 5)

        return scenario_result('baseline', msg_id, posted_at, None, propagation, self.simulator.logger)
    
    def get_bootstrap_peers(self, node_name, nodes_down):
        direct, indirect = self.classify_nodes(node_name, self.connection_graph)
        peers = []
        for node in direct:
            if node not in nodes_down:
                peers.append(node)
            
        return peers

    
    def run_author_dropout(self, node_name) -> scenario_result:
        direct, indirect = self.classify_nodes(node_name, self.connection_graph)
        print(f"Direct connections to node 1 are: {direct}")
        print(f"Indirect connections to node 1 are: {indirect}")
        cmd = 'ssb-server publish --type post --text "heya its node 1, about to go offline!"'
        result = self.nodes[node_name]['container'].exec_run(cmd, stderr=True)

        if result.exit_code == 0:
            data = json.loads(result.output.decode())
            msg_id = data['key']
            posted_at = data['value']['timestamp']
            #print(msg_id)
        self.nodes[node_name]['container'].stop(timeout=0)
        #print(f"Result from post is: {result}")
        propagation = self.poll_propogation(direct, msg_id, posted_at, 5)
        #print(timing)
        result = scenario_result('author_dropout', msg_id, posted_at, [node_name], propagation, self.simulator.logger)
        bootstrap_peers = self.get_bootstrap_peers(node_name, [node_name])
        self.restart_node(node_name, bootstrap_peers)
        return result

    def run_lan_dropout(self, node_name):

        direct, indirect = self.classify_nodes(node_name, self.connection_graph)
        direct_copy = direct.copy()
        node_lan = self.nodes[node_name]['lan_name']

        #getting the set of node names from lan_graph
        same_lan_nodes = self.lan_graph[node_lan]
        same_lan_direct = []
        for node in list(direct_copy):
            if self.nodes[node]['lan_name'] == node_lan:
                same_lan_direct.append(node)
                direct_copy.remove(node)

        print(f"Direct connections to node 1 not in {node_lan} are: {direct_copy}")
        print(f"\nNodes in same LAN as author: {same_lan_nodes}")
        print(f"\nExternal nodes: {direct_copy}")
        cmd = 'ssb-server publish --type post --text "heya its node 1, alone in my LAN!"'
        result = self.nodes[node_name]['container'].exec_run(cmd, stderr=True)
        if result.exit_code == 0:
            data = json.loads(result.output.decode())
            msg_id = data['key']
            posted_at = data['value']['timestamp']
        else:
            print(f"Publish failed: {result.output.decode()}") 
            return None
           
        time.sleep(0.5)
        
        #stopping all nodes in the same LAN
        for node in list(same_lan_nodes):
            self.nodes[node]['container'].stop(timeout=0)
            print(f"Stopped node {node}")

       
        #propagation for non-LAN
        non_lan_propagation = self.poll_propogation(direct_copy, msg_id, posted_at, 5)


        for node in same_lan_nodes:
            bootstrap_peers = self.get_bootstrap_peers(node_name, same_lan_nodes)
            self.restart_node(node, bootstrap_peers)

        restarted_at = time.time() * 1000
        same_lan_propagation = self.poll_propogation(same_lan_direct, msg_id, restarted_at, 5)
        
        non_lan_result = scenario_result('same_lan_dropout', msg_id, posted_at, same_lan_nodes, non_lan_propagation, self.simulator.logger)
        same_lan_result = scenario_result('same_lan_catchup', msg_id, restarted_at, same_lan_nodes, same_lan_propagation, self.simulator.logger)
        original_non_lan_result = non_lan_result

        if non_lan_result.get_successes() == 0:
            for node in direct_copy:
                self.nodes[node]['container'].exec_run(
                    f'ssb-server gossip.reconnect "{self.nodes[node_name]['info']['address']}"'
                )

            while non_lan_result.get_successes() == 0:
                non_lan_propagation = self.poll_propogation(direct_copy, msg_id, posted_at, 5)
                non_lan_result = scenario_result('same_lan_dropout_rerun', msg_id, posted_at, same_lan_nodes, non_lan_propagation, self.simulator.logger)

        return original_non_lan_result, same_lan_result

    def run_dropout_catchup(self, node_name) -> scenario_result:
        ##Running catch up simulator
        #Node1 makes a post
        #Randomly select Node1’s connections and shut down their containers
        #While all of Node1’s followers that haven’t been shut down don’t have the post or until timeout has been exceeded:
        #    For each of Node1’s still-running followers:
        #        Poll to see if post has been received
        #        If it has:
        #            Save timestamp
        #Turn Node1’s turned-off connections back on
        #While the recently-turned-off connections don’t have the post or until timeout has been exceeded:
        #    For each of the recently-turned-off connections:
        #        Poll to see if post has been received
        #        If it has:
        #            Save timestamp

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
            #print(msg_id)
        else:
            print("Failed to publish, exiting")
            return None
        #print(f"Result from post is: {result}")
        #checking the propagation of those nodes that weren't dropped
        propagation = self.poll_propogation(direct - nodes_to_drop, msg_id, posted_at, 5)

        #restarting the dropped nodes 
        restart_time = time.time() * 1000
        for node in nodes_to_drop:
            bootstrap_peers = self.get_bootstrap_peers(node_name, nodes_to_drop)
            self.restart_node(node, bootstrap_peers)

        

        dropout_propagation = self.poll_propogation(nodes_to_drop, msg_id, restart_time, 5)

        #going through results, if only same-lan nodes found the post, try to find it by saying hello from the other node

        #pr.update({"ssb-sim-node-14" : {'elapsed' : 879.644, 'elapsed_human': "0 minutes 0 seconds 879.644 miliseconds", 'lan' : "ssb-sim-lan-2", 'received' : True}})
        non_lan_dropout_results = []
        for node in propagation:
            if node['lan'] != self.nodes[node_name]['lan_name']:
                non_lan_dropout_results.append(node['received'])
        if True not in non_lan_dropout_results:
            for node in propagation:
                self.nodes[node]['container'].exec_run(
                    f'ssb-server gossip.reconnect "{self.nodes[node_name]['info']['address']}"'
                )

        #do it for the dropouts too
        non_lan_dropout_results = []
        for node in dropout_propagation:
            if node['lan'] != self.nodes[node_name]['lan_name']:
                non_lan_dropout_results.append(node['received'])
        if True not in non_lan_dropout_results:
            for node in dropout_propagation:
                self.nodes[node]['container'].exec_run(
                    f'ssb-server gossip.reconnect "{self.nodes[node_name]['info']['address']}"'
                )


        
        #print(timing)
        return scenario_result('random_dropout', msg_id, posted_at, nodes_to_drop, propagation, self.simulator.logger), scenario_result('random_dropout_catchup', msg_id, restart_time, nodes_to_drop, dropout_propagation, self.simulator.logger) 

    def restart_node(self, node_name, bootstrap_peers = None):
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

        

        for peer in bootstrap_peers:
            peer_addr = self.nodes[peer]['info']['address']
            ready = 1
            while ready != 0:
                self.simulator.logger.info(f"Attempt to bootstrap {node_name} by contacting {peer}")    
                peer_reconnect_attempt = self.nodes[node_name]['container'].exec_run(
                    f'ssb-server gossip.reconnect "{peer_addr}"'
                )
                ready = peer_reconnect_attempt.exit_code
                self.simulator.logger.debug(f"Result: {peer_reconnect_attempt.output.decode()}")
                if ready == 0:
                    break

                time.sleep(2)
            self.simulator.logger.info(f"{node_name} successfully contacted {peer}")    
                
        

    def run_lan_migration(self, node_name) -> scenario_result:
        node = self.nodes[node_name]
        
        direct, indirect = self.classify_nodes(node_name, self.connection_graph)

        node['container'].exec_run("pkill -f ssb-server")

        # step 1: disconnect from current LAN
        old_lan = node['lan_name']
        #get network object from docker client
        old_lan_network = self.simulator.client.networks.get(old_lan)
        old_lan_network.disconnect(node['container'])
        self.simulator.logger.info(f"{node_name}: disconnected from {old_lan}")

        # step 2: connect to new LAN
        # find an alternate LAN
        for lan in self.lan_graph:
            if lan != old_lan:
                new_lan = lan
                break

        new_lan_network = self.simulator.client.networks.get(new_lan)
        new_lan_network.connect(node['container'])
        node['container'].reload()
        new_ip = node['container'].attrs['NetworkSettings']['Networks'][new_lan]['IPAddress']
        self.simulator.logger.info(f"{node_name}: connected to {new_lan}, new IP address {new_ip}")

        # step 3: the config file for ssb needs to be updated
        
        config = {"host" : new_ip, "port": 8008, "allowPrivate" : True}
        config_json = json.dumps(config, indent=2)
        # i want to run the command in a new shell (sh -c)
        # and the command i want to run is to put the config_json into
        # the file /root/.ssb.config
        # and u do that in sh by printf-ing into the file
        # so fingers crossed this works??
        #node['container'].exec_run(
        #    f"sh -c 'printf \"%s\" {repr(config_json)} > /root/.ssb/config'"
        #)
        #now restart to make config file take effect
        
        time.sleep(2)
        node['container'].exec_run(f'ssb-server start "{new_ip}"&', detach=True)
        time.sleep(3)

        #updating the node info dictionary
        key = node['info']['key']
        new_address = f"net:{new_ip}:8008~shs:{key}"
        node['info']['address'] = new_address
        node['lan_name'] = new_lan

        
        #step 5: regossiping to ONE known peer so address propagates
       
        for peer_name in direct:
            peer = self.nodes[peer_name]
            peer_address = peer['info']['address']
            node['container'].exec_run(f'ssb-server gossip.connect "{peer_address}"')
            self.simulator.logger.info(f"{node_name}: re-gossiped to {peer_name} at {new_ip}")
            break
        
        # instead of measuring 
        migration_time = time.time() * 1000
        cmd = f'ssb-server publish --type post --text "Hi its me and ive changed LAN!!!"'
        result = node['container'].exec_run(cmd, stderr=True)
        if result.exit_code != 0:
            self.simulator.logger.error(f"Post failed after migration: {result.output.decode()}")
            return None
        
        data = json.loads(result.output.decode())
        msg_id = data['key']
        posted_at = data['value']['timestamp']

        propagation = self.poll_propogation(direct, msg_id, posted_at, 5)
        return scenario_result('lan_migration', msg_id, posted_at, [], propagation, self.simulator.logger)
    

    