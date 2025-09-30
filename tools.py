import os, sys, re
import networkx as nx
from networkx.algorithms import isomorphism
from itertools import combinations
from collections import defaultdict
import matplotlib.pyplot as plt
from networkx.drawing.nx_pydot import graphviz_layout

def cleanInWireList(inWiresStr: str):
    inWiresStr.strip()
    if inWiresStr[-1] == ",":
        inWiresStr = inWiresStr[:-1]
    return [x.strip() for x in inWiresStr.split(',')]

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

    neighborhood_nodes = set(hood) | set(hood2)
    
    # Extract subgraph
    subgraph = G.subgraph(neighborhood_nodes).copy()
    draw_neat_digraph(subgraph)

# Used to generate training files for manually locked bench
def gen_modelFiles(bench_file_path: str) -> nx.DiGraph:    
    feat, cell, count = '', '', ''
    ML_count = 0 
    link_train = ''
    link_test = ''
    link_test_n = ''
    gateVecDict = {
                'xor':[0,1,0,0,0,0,0,0],
                'or':[0,0,1,0,0,0,0,0],
                'xnor':[0,0,0,1,0,0,0,0],
                'and':[0,0,0,0,1,0,0,0],
                'nand':[0,0,0,0,0,1,0,0],
                'buf':[0,0,0,0,0,0,0,1],
                'not':[0,0,0,0,0,0,1,0],
                'nor':[1,0,0,0,0,0,0,0],
            }
    
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
                    
                    if gate.lower() != "mux":
                        tempG.nodes[outWire]['count'] = ML_count 
                        feat += f"{' '.join([str(x) for x in gateVecDict[gate.lower()]])}\n"
                        cell += f"{ML_count} assign for output {outWire}\n"
                        count += f"{ML_count}\n"
                        ML_count+=1
                    
                else:
                    # raise error if not empty line
                    if line.strip() != "" and not line.startswith("#"):
                        raise Exception('Bad Bench File')
                    
    except FileNotFoundError:
        sys.exit(f"Error: The file {bench_file_path} was not found.")
    except Exception as e:
        sys.exit(f"Unknown error occurred: {e}")
    
    for u, v in tempG.edges:
        if 'count' in tempG.nodes[u].keys() and 'count' in tempG.nodes[v].keys():
            link_train += f"{tempG.nodes[u]['count']} {tempG.nodes[v]['count']}\n"
    
    with open(bench_file_path, "r") as f:
        line = f.readline().strip()

    line = line.split('=')[1]
    keyList = [int(ch) for ch in line]
    
    for n in tempG.nodes:
        if tempG.nodes[n]["type"] == "output" or tempG.nodes[n]["type"] == "gate":
            if tempG.nodes[n]["gate"].lower() == "mux":
                idx = int(tempG.nodes[n]["muxDict"]["key"][-1])
                key = keyList[idx]
                
                truGate = tempG.nodes[n]["muxDict"][key]
                falGate = tempG.nodes[n]["muxDict"][1-key]
                
                outGate = n.replace("_from_mux", "")
                
                link_test += f"{tempG.nodes[truGate]['count']} {tempG.nodes[outGate]['count']}\n"
                link_test_n += f"{tempG.nodes[falGate]['count']} {tempG.nodes[outGate]['count']}\n"
                    
    
    dumpDir = "./data/"
    if not os.path.exists(dumpDir):
        os.mkdir(dumpDir)

    benchName = bench_file_path.split('/')[-1].replace('.bench', "")
    if not os.path.exists(f"{dumpDir}/{benchName}_DMUX"):
        os.mkdir(f"{dumpDir}/{benchName}_DMUX")
    
    dumpDir = f"{dumpDir}/{benchName}_DMUX"
    with open(f'{dumpDir}/cell.txt', "w") as f:
        f.write(cell)
    with open(f'{dumpDir}/feat.txt', "w") as f:
        f.write(feat)
    with open(f'{dumpDir}/count.txt', "w") as f:
        f.write(count)
    with open(f'{dumpDir}/links_train.txt', "w") as f:
        f.write(link_train)
    with open(f'{dumpDir}/links_test.txt', "w") as f:
        f.write(link_test)
    with open(f'{dumpDir}/link_test_n.txt', "w") as f:
        f.write(link_test_n)
    
if __name__ == "__main__":    
    # View into the bench file 
    # g = parse_bench('./data/c1355_K4_DMUX/c1355_K4.bench')
    # g = g.to_undirected()
    # path = list(nx.all_simple_paths(g, source='G886gat', target='G952gat', cutoff=7))
    # print("True Path: \nlength: ", len(path))
    # print(path)
    # path2 = list(nx.all_simple_paths(g, source='G886gat_sub_G952gat', target='G952gat', cutoff=7))
    # print("False Path: \nlength: ", len(path2))
    # print(path2)
    
    # # Veiw into the adjlist files from MuxLink
    # a = nx.read_adjlist('./data/c1355_K4_DMUX/graph-610-310.adjlist')
    # b = nx.read_adjlist('./data/c1355_K4_DMUX/graph-292-310.adjlist')
    # patha = list(nx.all_simple_paths(a, source='0', target='1', cutoff=7))
    # print("Path a: length: ", len(patha))
    # print(patha)
    # pathb = list(nx.all_simple_paths(b, source='0', target='1', cutoff=7))
    # print("Path b: length: ", len(pathb))
    # print(pathb)
    
    # Generate files for externally locked bench
    gen_modelFiles("G3_K8.bench")
    
    # Generate png from adjlist in data dir
    # for fldr in os.listdir('./data'):
    #     if fldr.startswith('c1355'):
    #         adjlist2png('./data/'+fldr)
            
    print("Done running tools.py")