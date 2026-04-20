import networkx as nx
import matplotlib.pyplot as plt
#G = nx.petersen_graph()
G = nx.Graph()

nodes = {'ssb-sim-node-1':  ['ssb-sim-node-14', 'ssb-sim-node-3'],
         'ssb-sim-node-2': ['ssb-sim-node-14', 'ssb-sim-node-8', 'ssb-sim-node-3', 'ssb-sim-node-10'],
         'ssb-sim-node-3': ['ssb-sim-node-1', 'ssb-sim-node-8', 'ssb-sim-node-2', 'ssb-sim-node-5', 'ssb-sim-node-15', 'ssb-sim-node-9', 'ssb-sim-node-6', 'ssb-sim-node-14'],
         'ssb-sim-node-4': ['ssb-sim-node-6', 'ssb-sim-node-9'],
         'ssb-sim-node-5': ['ssb-sim-node-13', 'ssb-sim-node-3', 'ssb-sim-node-4', 'ssb-sim-node-11', 'ssb-sim-node-15', 'ssb-sim-node-9', 'ssb-sim-node-8', 'ssb-sim-node-2', 'ssb-sim-node-10', 'ssb-sim-node-1', 'ssb-sim-node-7'],
         'ssb-sim-node-6': ['ssb-sim-node-5', 'ssb-sim-node-4', 'ssb-sim-node-10', 'ssb-sim-node-7', 'ssb-sim-node-9', 'ssb-sim-node-11', 'ssb-sim-node-2', 'ssb-sim-node-13', 'ssb-sim-node-12', 'ssb-sim-node-3', 'ssb-sim-node-8', 'ssb-sim-node-14', 'ssb-sim-node-1', 'ssb-sim-node-15'],
         'ssb-sim-node-7': ['ssb-sim-node-13', 'ssb-sim-node-3'],
         'ssb-sim-node-8': ['ssb-sim-node-5', 'ssb-sim-node-3'],
         'ssb-sim-node-9': ['ssb-sim-node-13', 'ssb-sim-node-10', 'ssb-sim-node-15', 'ssb-sim-node-5', 'ssb-sim-node-1', 'ssb-sim-node-6', 'ssb-sim-node-12', 'ssb-sim-node-8', 'ssb-sim-node-14', 'ssb-sim-node-11'],
         'ssb-sim-node-10': ['ssb-sim-node-1', 'ssb-sim-node-2', 'ssb-sim-node-7', 'ssb-sim-node-12', 'ssb-sim-node-11', 'ssb-sim-node-15', 'ssb-sim-node-13', 'ssb-sim-node-14', 'ssb-sim-node-9', 'ssb-sim-node-4', 'ssb-sim-node-8', 'ssb-sim-node-6', 'ssb-sim-node-5', 'ssb-sim-node-3'],
         'ssb-sim-node-11': ['ssb-sim-node-9', 'ssb-sim-node-4', 'ssb-sim-node-15', 'ssb-sim-node-7', 'ssb-sim-node-10', 'ssb-sim-node-1', 'ssb-sim-node-14', 'ssb-sim-node-3', 'ssb-sim-node-12', 'ssb-sim-node-13', 'ssb-sim-node-5', 'ssb-sim-node-2', 'ssb-sim-node-8'],
         'ssb-sim-node-12': ['ssb-sim-node-8', 'ssb-sim-node-15', 'ssb-sim-node-7', 'ssb-sim-node-4', 'ssb-sim-node-9', 'ssb-sim-node-3', 'ssb-sim-node-11', 'ssb-sim-node-2', 'ssb-sim-node-13', 'ssb-sim-node-1', 'ssb-sim-node-10', 'ssb-sim-node-14', 'ssb-sim-node-6', 'ssb-sim-node-5'],
         'ssb-sim-node-13': ['ssb-sim-node-12', 'ssb-sim-node-2', 'ssb-sim-node-4', 'ssb-sim-node-6', 'ssb-sim-node-3', 'ssb-sim-node-14', 'ssb-sim-node-8'],
         'ssb-sim-node-14': ['ssb-sim-node-1', 'ssb-sim-node-13', 'ssb-sim-node-3', 'ssb-sim-node-5'],
         'ssb-sim-node-15': ['ssb-sim-node-1', 'ssb-sim-node-10', 'ssb-sim-node-6', 'ssb-sim-node-5', 'ssb-sim-node-13', 'ssb-sim-node-11', 'ssb-sim-node-7', 'ssb-sim-node-4']}

G.add_nodes_from(list(nodes.keys()))

edge_list = []

for key in nodes:
    for node_name in nodes[key]:
        edge_list.append((key, node_name))

G.add_edges_from(edge_list)


options = {
    'node_color': 'black',
    'node_size': 100,
    'width': 3,
    'with_labels' : True
}
#subax1 = plt.subplot(121)
#nx.draw(G, with_labels=True, font_weight='bold')
#subax2 = plt.subplot(122)
#nx.draw_shell(G, nlist=[range(5, 10), range(5)], with_labels=True, font_weight='bold')
#subax1 = plt.subplot(221)
#nx.draw_random(G, **options)
#subax2 = plt.subplot(222)
#nx.draw_circular(G, **options)
#subax3 = plt.subplot(223)
#nx.draw_spectral(G, **options)
#subax4 = plt.subplot(224)
#nx.draw_shell(G, nlist=[range(5,10), range(5)], **options)
fig, axes = plt.subplots(1, 1, figsize=(12, 10))
node_list = list(G.nodes())
shell_nlist = [ node_list[:5], node_list[5:10],  node_list[10:]]

#nx.draw_random(G, **options)
#axes[0, 0].set_title("Random")

#plt.sca(axes[0, 1])
#nx.draw_circular(G, **options)
#axes[0, 1].set_title("Circular")

#plt.sca(axes[1, 0])
#nx.draw_spectral(G, **options)
#axes[1, 0].set_title("Spectral")



nx.draw_shell(G, nlist=shell_nlist, **options)

plt.tight_layout()
plt.savefig("path.png", dpi=150)
plt.show()
