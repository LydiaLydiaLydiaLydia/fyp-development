class propagation_demo:
    def __init__(self, ssb_simulator):
        self.simulator = ssb_simulator
        self.connection_graph = self.get_connection_graph
        print("okay")

    def get_connection_graph(simulator):
        graph = {}
        for node in simulator.nodes:
            graph[node['name']] = set()
        
        for detail in simulator.connection_details:
            for peer_name in detail['connections']:
                graph[detail['node']].add(peer_name)
        
        return graph

    def classify_nodes(self, author_name: str, graph: dict):
        direct = {
            peer for peer in graph[author_name]
        } | {
            name for name, peers in graph.items() if author_name in peers
        }
        
        indirect = {
            node['name'] for node in self.nodes
            if node['name'] != author_name
            and node['name'] not in direct
        }
        
        return direct, indirect