import os, random, sys, re, copy
import networkx as nx
from networkx.algorithms import isomorphism
from itertools import combinations
from collections import defaultdict
import matplotlib.pyplot as plt
from networkx.drawing.nx_pydot import graphviz_layout

from utils import generate_key_list, reconstruct_bench, cleanInWireList

# Misc
def parse_bench(bench_file_path: str) -> nx.DiGraph:
    tempG = nx.DiGraph()
    # Assuming one declaration per line
    _input = re.compile(r"(?i)^\s*INPUT\s*\(\s*(.*?)\s*\)\s*$")
    _output = re.compile(r"(?i)^\s*OUTPUT\s*\(\s*(.*?)\s*\)\s*$")
    
    _logicOp = re.compile(r"^\s*(\w+)\s*=\s*(\w+)\s*\(\s*(.*?)\s*\)\s*$")
        
    
    try:
        with open(bench_file_path, 'r') as file:
            for line in file:
                line = line.strip()
                
                isInput = _input.match(line)
                isOutput = _output.match(line)
                isLogicOp = _logicOp.match(line)
                
                if isInput:
                    tempG.add_node(isInput.group(1))
                    tempG.nodes[isInput.group(1)]['type'] = 'input'
                elif isOutput:
                    tempG.add_node(isOutput.group(1))
                    tempG.nodes[isOutput.group(1)]['type'] = 'output'
                elif isLogicOp:
                    outWire, gate, inWires = isLogicOp.groups()
                    
                    # Store more mux info (ONLY SUPPORTS 2 TO 1 MUX)
                    if gate.lower() == "mux":
                        k, i0, i1 = cleanInWireList(inWires)
                        # muxDict[outWire] = {"key": k, 0:i0, 1:i1 }
                        tempG.nodes[outWire]['muxDict'] = {"key": k, 0:i0, 1:i1 }
                    
                    for inwire in cleanInWireList(inWires):
                        tempG.add_edge(inwire, outWire)
                    
                    # done so that we dont override the output type setting above
                    if not 'type' in tempG.nodes[outWire].keys():
                        tempG.nodes[outWire]['type'] = 'gate'
                    tempG.nodes[outWire]['gate'] = gate
                    
                else:
                    # raise error if not empty line
                    if line.strip() != "" and not line.startswith("#"):
                        raise Exception('Bad Bench File')
                    
    except FileNotFoundError:
        sys.exit(f"Error: The file {bench_file_path} was not found.")
    except Exception as e:
        sys.exit(f"Unknown error occurred: {e}")
        
    return tempG

def draw_neat_digraph(G, title=None, name="graph", save=False, node_size=800):
    # pos = nx.spring_layout(G, seed=42)  # seed ensures reproducible layout
    pos = graphviz_layout(G, prog='dot')
    plt.figure(figsize=(8, 6))
    
    nx.draw_networkx_nodes(G, pos, node_size=node_size, node_color='skyblue', edgecolors='black')
    nx.draw_networkx_edges(G, pos, arrowstyle='->', arrowsize=20, edge_color='gray')
    nx.draw_networkx_labels(G, pos, font_size=10, font_weight='bold')

    if title:
        plt.title(title)

    plt.axis('off')
    plt.tight_layout()
    if save:
        plt.savefig(name, format='png', dpi=300)
        plt.close()
    else:
        plt.show()
        
def isogen(G: nx.DiGraph, subgraph_size: int):
    seen = set()
    groups = defaultdict(list)

    # Generate all possible node combinations of the given size
    for nodes in combinations(G.nodes, subgraph_size):
        subG = G.subgraph(nodes).copy()
        
        # Skip disconnected subgraphs if needed:
        if not nx.is_weakly_connected(subG):
            continue

        # Canonical label: use string of sorted edges as a poor man's hash
        label = tuple(sorted(subG.edges()))
        if label in seen:
            continue
        seen.add(label)

        # Check isomorphism against previous groups
        matched = False
        for key in groups:
            gm = isomorphism.DiGraphMatcher(subG, key)
            if gm.is_isomorphic():
                groups[key].append(subG)
                matched = True
                break

        if not matched:
            groups[subG] = [subG]

    return list(groups.values())

def extractSubG(ckt: str, folder = "subgraphs"):
    print("parsing to graph")
    g = parse_bench(ckt)
    # g, _ = parse_ckt('./data/c1355_K64_DMUX/c1355_K64.bench', False)
    print("extracting isomorphic graphs")
    a = isogen(g,3)

    print("saving isomorphic graphs to folder")
    
    os.makedirs(folder, exist_ok=True)

    for i in range(len(a)):
        for j in range(len(a[i])):
            title = f"subG_{i}_{j}"
            draw_neat_digraph(a[i][j], title, folder)

def adjlist2png(_dir):
    # _dir = './data/apex_K4_DMUX'
    for f in os.listdir(_dir):
        if f.endswith('.adjlist'):
            print('A')
            subG = nx.read_adjlist(_dir+"/"+f)
            output = f.split('.')[0].split('-')[2]
            target = f.split('.')[0].split('-')[1]
            with open(_dir+'/links_test.txt') as file:
                content = file.read()
                if target in content:
                    draw_neat_digraph(subG, f"Subgraph {target} -> {output}", f"{_dir}/Subgraph-{output}-True-{target}.png", save=True)
                else:
                    draw_neat_digraph(subG, f"Subgraph {target} -> {output}", f"{_dir}/Subgraph-{output}-False-{target}.png", save=True)
                    

def subgView(G: nx.DiGraph, node, node2, hop):
    G.remove_edge(f"{node2}_from_mux", node2)
    G.remove_edge(node, f"{node2}_from_mux")
    
    primary_inputs = [n for n in G.nodes if G.in_degree(n) == 0]
    G.remove_nodes_from(primary_inputs)
    
    G = G.to_undirected()
    
    hood = nx.ego_graph(
        G, node, radius=hop, undirected=True
    ).nodes
    
    hood2 = nx.ego_graph(
        G, node2, radius=hop, undirected=True
    ).nodes
    # fanin_nodes = nx.ego_graph(
    #     G.reverse(), node, radius=hop, undirected=False
    # ).reverse().nodes
    
    # # Get 4-hop fanout (successors)
    # fanout_nodes = nx.ego_graph(
    #     G, node, radius=hop, undirected=False
    # ).nodes
    # fanin_nodes2 = nx.ego_graph(
    #     G.reverse(), node2, radius=hop, undirected=False
    # ).reverse().nodes
    
    # # Get 4-hop fanout (successors)
    # fanout_nodes2 = nx.ego_graph(
    #     G, node2, radius=hop, undirected=False
    # ).nodes

    # Union of both directions
    # neighborhood_nodes = set(fanin_nodes) | set(fanout_nodes) |set(fanin_nodes2) | set(fanout_nodes2)
    neighborhood_nodes = set(hood) | set(hood2)
    
    # Extract subgraph
    subgraph = G.subgraph(neighborhood_nodes).copy()
    draw_neat_digraph(subgraph)
    
    
if __name__ == "__main__":    
    # g, _ = parse_ckt('./data/mid_K4_DMUX/mid_K4.bench', False)
    # draw_neat_digraph(g, "midK4")

    # main('apex2c', 6, dumpFiles=True, drawGraph=False)
    # extractSubG('./data/c1355_K6_DMUX/c1355_K6.bench', "subgraphs-c1355k6")
    # g = parse_bench('./data/c1355_K6_DMUX-1/c1355_K6.bench')
    # center_node = 'G1261gat_from_mux'
    # subG = get_radius_subgraph(g, center_node, radius=3)
    # a = nx.read_adjlist('./data/c1355_K12_DMUX/graph-293-347.adjlist')
    # b = nx.read_adjlist('./data/c1355_K6_DMUX-3/graph-350-371.adjlist')
    # path = nx.shortest_path(a, source='0', target='1')
    # print("Path from A to D:", path)
    # pathb = nx.shortest_path(b, source='0', target='1')
    # print("Path from A to D:", pathb)
    # draw_neat_digraph(a)
    # draw_neat_digraph(b)
    # adjlist2png('./data/c1355_K4_DMUX-3')
    # adjlist2png('./data/c1355_K12_DMUX')
    
    # main('apex2c', 6, dumpFiles=True, drawGraph=False)
    # center_node = 'G1261gat_from_mux'
    # subG = get_radius_subgraph(g, center_node, radius=3)
    # a = nx.read_adjlist('./data/c1355_K12_DMUX/graph-293-347.adjlist')
    # b = nx.read_adjlist('./data/c1355_K6_DMUX-3/graph-350-371.adjlist')
    # path = nx.shortest_path(a, source='0', target='1')
    # print("Path from A to D:", path)
    # pathb = nx.shortest_path(b, source='0', target='1')
    # print("Path from A to D:", pathb)
    # draw_neat_digraph(a)
    # draw_neat_digraph(b)
    # adjlist2png('./data/c1355_K4_DMUX-3')
    # adjlist2png('./data/c1355_K12_DMUX')
    print("Done running tools.py")