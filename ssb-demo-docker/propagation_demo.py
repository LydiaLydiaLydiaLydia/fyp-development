from datetime import datetime
import random
from statistics import median
import time
import json
class propagation_demo:
    def __init__(self, ssb_simulator):
        self.simulator = ssb_simulator
        self.nodes = {node['name']: node for node in self.simulator.nodes}
        self.connection_graph = self.get_connection_graph()

    def get_connection_graph(self):
        graph = {}
        for node in self.simulator.nodes:
            graph[node['name']] = set()
        
        #print(f"Connection details whole object :{self.simulator.connection_details}")
        for detail in self.simulator.connection_details:
            for peer_name in detail['connections']:
                graph[detail['node']].add(peer_name)
        
        return graph
    
    def for_humans(self, mili_value):
        seconds, miliseconds = divmod(mili_value, 1000)
        minutes, secs = divmod(seconds, 60)
        return f"{int(minutes)} minutes {int(secs)} seconds {miliseconds:.3f} miliseconds"

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
    
    def poll_propogation(self, direct_cs, message_id, time_posted, timeout_in_mins):
        timeout = time.time() + timeout_in_mins * 60
        timeout_milis = timeout * 1000
        propagation = {}
        for node_name in direct_cs:
            propagation.update({node_name : {'elapsed' : None, 'elapsed_human': self.for_humans(timeout_milis), 'lan' : self.nodes[node_name]['lan_name'], 'received' : False}})

        direct_copy = direct_cs.copy()
        while len(direct_copy) > 0 and time.time() < timeout:
            for node_name in list(direct_copy):
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

    def run_baseline(self, node_name):
        direct, indirect = self.classify_nodes(node_name, self.connection_graph)
        print(f"Direct connections to node 1 are: {direct}")
        print(f"Indirect connections to node 1 are: {indirect}")
        cmd = 'ssb-server publish --type post --text "heya its node 1"'
        result = self.nodes[node_name]['container'].exec_run(cmd, stderr=True)
        if result.exit_code == 0:
            data = json.loads(result.output.decode())
            msg_id = data['key']
            posted_at = data['value']['timestamp']
            #print(msg_id)
        #print(f"Result from post is: {result}")
        propagation = self.poll_propogation(direct, msg_id, posted_at, 2)
        #print(timing)
        return self.write_result('baseline', msg_id, posted_at, None, propagation)
    
    def run_author_dropout(self, node_name):
        direct, indirect = self.classify_nodes(node_name, self.connection_graph)
        print(f"Direct connections to node 1 are: {direct}")
        print(f"Indirect connections to node 1 are: {indirect}")
        cmd = 'ssb-server publish --type post --text "heya its node 1, about to go offline!"'
        result = self.nodes[node_name]['container'].exec_run(cmd, stderr=True)
        self.nodes[node_name]['container'].stop(timeout=0)
        if result.exit_code == 0:
            data = json.loads(result.output.decode())
            msg_id = data['key']
            posted_at = data['value']['timestamp']
            #print(msg_id)
        #print(f"Result from post is: {result}")
        propagation = self.poll_propogation(direct, msg_id, posted_at, 2)
        #print(timing)
        result = self.write_result('author_dropout', msg_id, posted_at, [node_name], propagation)
        self.restart_node(node_name)
        return result

    def run_replicator_dropout(self, node_name):
        direct, indirect = self.classify_nodes(node_name, self.connection_graph)
        direct_copy = direct.copy()
        node_lan = self.nodes[node_name]['lan_name']

        same_lan_nodes = []
        for node in list(direct_copy):
            if self.nodes[node]['lan_name'] == node_lan:
                same_lan_nodes.append(node)
                direct_copy.remove(node)

        print(f"Direct connections to node 1 not in {node_lan} are: {direct}")
        print(f"\nNodes to stop: {same_lan_nodes}")
        print(f"\nExternal nodes: {direct_copy}")
        cmd = 'ssb-server publish --type post --text "heya its node 1, about to go offline!"'
        result = self.nodes[node_name]['container'].exec_run(cmd, stderr=True)
        if result.exit_code == 0:
            data = json.loads(result.output.decode())
            msg_id = data['key']
            posted_at = data['value']['timestamp']
        else:
            print(f"Publish failed: {result.output.decode()}") 
            return None
           
        time.sleep(0.5)
        #self.nodes[node_name]['container'].stop()
        
        for node in list(same_lan_nodes):
            self.nodes[node]['container'].stop(timeout=0)
            print(f"Stopped node {node}")

       
        #print(f"Result from post is: {result}")
        propagation = self.poll_propogation(direct_copy, msg_id, posted_at, 2)
        #print(timing)
        result = self.write_result('replicator_dropout', msg_id, posted_at, same_lan_nodes, propagation)
        for node in same_lan_nodes:
            self.restart_node(node)
        return result

    def run_dropout_catchup(self, node_name):
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
            print("Stopped container {node}")

        
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
        propagation = self.poll_propogation(direct - nodes_to_drop, msg_id, posted_at, 2)
        propagation2 = {}
        restart_time_1 = time.time()
        for node in nodes_to_drop:
            self.restart_node(node)
            restart_time = time.time() * 1000
            propagation2.update(self.poll_propogation([node], msg_id, restart_time, 2))
            

        
        #print(timing)
        return self.write_result('random_dropout', msg_id, posted_at, nodes_to_drop, propagation), self.write_result('random_dropout_catchup_', msg_id, restart_time_1, nodes_to_drop, propagation2)



    def write_result(self, scenario, msg_id, posted_at, nodes_stopped, propagation):
        successes = 0
        list_elapsed = []
        median_elapsed = None
        human_readable = None
        for key, val in propagation.items():
            if val['received']:
                successes += 1
                list_elapsed.append(val['elapsed'])
        if list_elapsed:
            median_elapsed = median(list_elapsed)
            human_readable = self.for_humans(median_elapsed)

        if len(propagation) == 0:
            rate = 0
        else:
            rate = successes/ len(propagation)
        return {'scenario' : scenario, 
                 'message_id' : msg_id,
                 'posted_id': posted_at,
                 'nodes_stopped' : nodes_stopped,
                 'propagation': propagation,
                 'completion_rate' : rate,
                 'median_elapsed' : median_elapsed,
                 'median_elapsed_human' : human_readable if human_readable else None
                } 

    def print_result(self, result):
        print("\n" + "="*50)
        print(f"  SCENARIO: {result['scenario'].upper()}")
        print("="*50)
        print(f"  Message ID : {result['message_id']}")
        print(f"  Posted at  : {datetime.fromtimestamp(result['posted_id'] / 1000).strftime('%H:%M:%S.%f')[:-3]}")
        print(f"  Nodes down : {result['nodes_stopped']}")
        print(f"  Completion : {result['completion_rate']*100:.0f}%")
        print(f"  Median     : {result['median_elapsed_human']}")
        print()
        print(f"  {'NODE':<25} {'LAN':<18} {'RECEIVED':<10} {'ELAPSED'}")
        print(f"  {'-'*24} {'-'*17} {'-'*9} {'-'*15}")
        for node_name, data in result['propagation'].items():
            received = "yes" if data['received'] else "no"
            elapsed = data['elapsed_human'] if data['received'] else "—"
            print(f"  {node_name:<25} {data['lan']:<18} {received:<10} {elapsed}")
        print("="*50 + "\n")  

    def log_result(self, result):
        self.simulator.logger.info("\n" + "="*50)
        self.simulator.logger.info(f"  SCENARIO: {result['scenario'].upper()}")
        self.simulator.logger.info("="*50)
        self.simulator.logger.info(f"  Message ID : {result['message_id']}")
        self.simulator.logger.info(f"  Posted at  : {datetime.fromtimestamp(result['posted_id'] / 1000).strftime('%H:%M:%S.%f')[:-3]}")
        self.simulator.logger.info(f"  Nodes down : {result['nodes_stopped']}")
        self.simulator.logger.info(f"  Completion : {result['completion_rate']*100:.0f}%")
        self.simulator.logger.info(f"  Median     : {result['median_elapsed_human']}")
        self.simulator.logger.info(f"\n")
        self.simulator.logger.info(f"  {'NODE':<25} {'LAN':<18} {'RECEIVED':<10} {'ELAPSED'}")
        self.simulator.logger.info(f"  {'-'*24} {'-'*17} {'-'*9} {'-'*15}")
        for node_name, data in result['propagation'].items():
            received = "yes" if data['received'] else "no"
            elapsed = data['elapsed_human'] if data['received'] else "—"
            self.simulator.logger.info(f"  {node_name:<25} {data['lan']:<18} {received:<10} {elapsed}")
        self.simulator.logger.info("="*50 + "\n")

    def restart_node(self, node_name):
        self.nodes[node_name]['container'].start()
        self.simulator.logger.info(f"Restarted {node_name}, waiting for SSB to be ready...")
        
        # wait for ssb-server to be ready again
        timeout = time.time() + 30
        while time.time() < timeout:
            result = self.nodes[node_name]['container'].exec_run('ssb-server whoami', stderr=False)
            if result.exit_code == 0:
                self.simulator.logger.info(f"{node_name} is ready")
                return True
            time.sleep(2)
        
        self.simulator.logger.info(f"Warning: {node_name} did not become ready in time")
        return False

        