import os, random, sys, re
import networkx as nx
from collections import deque
import matplotlib.pyplot as plt
from networkx.drawing.nx_agraph import graphviz_layout

from utils import generate_key_list, reconstruct_bench, cleanInWireList

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

def alter_gate(gate:str):
    gatePair = {
        'AND': 'NAND',       # 2-input, different logic
        'NAND': 'AND',       # same as above
        'OR': 'NOR',         # 2-input, opposite logic
        'NOR': 'OR',
        'XOR': 'XNOR',       # both 2-inputs, different logic
        'XNOR': 'XOR',
        'NOT': 'BUF',     # 1-input, different logic
        'BUF': 'NOT',     # passes input unchanged
        'MUX': 'AND'
    }
    return gatePair[gate.upper()]

def gen_subgraph(G:nx.DiGraph, start_node, depth=2, dumpFiles=False):
    if dumpFiles:
        global feat, cell, count, ML_count, link_train
        
    current_layer = {start_node}
    targetCkt = set()
    for l in range(depth):
        left_layer = set()
        for origNode in current_layer:
            left_layer.update(G.predecessors(origNode))
            
            if G.nodes[origNode]['type'] != "input":
                artNode = origNode+"_sub"
                artNodeGate = alter_gate(G.nodes[origNode]['gate'])
                G.add_node(artNode, type='gate', isArt=True, gate=artNodeGate)
                
                if dumpFiles:
                    # avoid counting artNodes which were already setup
                    if not 'count' in G.nodes[artNode]:
                        G.nodes[artNode]['count'] = ML_count    
                        feat += f"{' '.join([str(x) for x in gateVecDict[artNodeGate.lower()]])}\n"
                        cell += f"{ML_count} assign for output {artNode}\n"
                        count += f"{ML_count}\n"
                        ML_count+=1
            else:
                artNode = origNode
                            
            if origNode == start_node:
                continue
            
            
            for succ in list(G.successors(origNode)):
                artSuccNode = succ + "_sub"
                if succ in targetCkt:
                    G.add_edge(artNode, artSuccNode)
                    
                    if dumpFiles and G.nodes[origNode]['type'] != "input":
                        link_train += f"{G.nodes[artNode]['count']} {G.nodes[artSuccNode]['count']}\n"
                # else:
                #     G.add_edge(artNode, succ) 
                # although this seems deceptive it actually ruins the functionality of the succ
                # if theres a way to do this without this effect then great to implement
                    
        # if l < depth-1: # avoids adding extra depth to the target ckt
        targetCkt.update(current_layer)
        current_layer = left_layer
        
    # stich last artificial layer to the original ckt
    for origNode in current_layer:
        for succ in list(G.successors(origNode)):
            if succ in targetCkt:
                artSuccNode = succ + "_sub"
                G.add_edge(origNode, artSuccNode)

                if dumpFiles:
                    # Avoids inputs, keyinputs and muxes when stiching the ckt
                    if 'count' in G.nodes[origNode]:
                        link_train += f"{G.nodes[origNode]['count']} {G.nodes[artSuccNode]['count']}\n"

    
    
def get_backward_subgraph(G:nx.DiGraph, start_node, depth=4):
    visited = set()
    queue = deque([(start_node, 0)])
    depth_map = {}
    
    while queue:
        current_node, current_depth = queue.popleft()
        if current_node in visited or current_depth > depth:
            continue
        visited.add(current_node)
        depth_map[current_node] = current_depth
        if current_depth < depth:
            for pred in G.predecessors(current_node):
                queue.append((pred, current_depth + 1))
    
    # Find actual max depth reached
    max_depth = max(depth_map.values())
    deepest_nodes = [node for node, d in depth_map.items() if d == max_depth]
    
    

    
    return G.subgraph(visited).copy(), deepest_nodes


def stitch_subgraph(G:nx.DiGraph, subG:nx.DiGraph, node_list, suffix="_sub"):  
    # Renaming rule for all nodes except the deepest nodes
    mapping = {}
    for node in subG.nodes():
        if node not in node_list:
            mapping[node] = f"{node}{suffix}"
        
    renamed_subG = nx.relabel_nodes(subG, mapping, copy=True)    
    for u, v, data in renamed_subG.edges(data=True):
        # print(data)
        G.add_edge(u, v)

def parse_ckt(bench_file_path: str, dumpFiles:bool) -> nx.DiGraph:
    tempG = nx.DiGraph()
    # Assuming one declaration per line
    # _in_out = re.compile(r"(?i)^\s*(INPUT|OUTPUT)\s*\(\s*(.*?)\s*\)\s*$")
    _input = re.compile(r"(?i)^\s*INPUT\s*\(\s*(.*?)\s*\)\s*$")
    _output = re.compile(r"(?i)^\s*OUTPUT\s*\(\s*(.*?)\s*\)\s*$")
    
    _logicOp = re.compile(r"^\s*(\w+)\s*=\s*(\w+)\s*\(\s*(.*?)\s*\)\s*$")
    # _logicOp = re.compile(r"^(\w+)\s*=\s*(\w+)\s*\(\s*(.*?)\s*\)\s*$")

    gateDict = {}
    muxDict = {}
    
    if dumpFiles:
        global feat, cell, count, ML_count, link_train
        
    
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
                    
                    gateDict[outWire] = gate
                    # Store more mux info (ONLY SUPPORTS 2 TO 1 MUX)
                    if gate.lower() == "mux":
                        k, i0, i1 = cleanInWireList(inWires)
                        muxDict[outWire] = {"key": k, 0:i0, 1:i1 }
                    
                    for inwire in cleanInWireList(inWires):
                        tempG.add_edge(inwire, outWire)
                    
                    # done so that we dont override the output type setting above
                    if not 'type' in tempG.nodes[outWire].keys():
                        tempG.nodes[outWire]['type'] = 'gate'
                    tempG.nodes[outWire]['gate'] = gate
                    
                    if dumpFiles:
                        tempG.nodes[outWire]['count'] = ML_count    
                        feat += f"{' '.join([str(x) for x in gateVecDict[gate.lower()]])}\n"
                        cell += f"{ML_count} assign for output {outWire}\n"
                        count += f"{ML_count}\n"
                        ML_count+=1
                else:
                    # raise error if not empty line
                    if line.strip() != "":
                        raise Exception('Bad Bench File')
                    
    except FileNotFoundError:
        sys.exit(f"Error: The file {bench_file_path} was not found.")
    except Exception as e:
        sys.exit(f"Unknown error occurred: {e}")    
    
    if dumpFiles:
        for u, v in tempG.edges:
            if 'count' in tempG.nodes[u].keys() and 'count' in tempG.nodes[v].keys():
                link_train += f"{tempG.nodes[u]['count']} {tempG.nodes[v]['count']}\n"
        
    return tempG, (gateDict, muxDict) #infoDict

def insertMuxNew(tempG:nx.DiGraph, infoDict: list[dict], keySize: int, dumpFiles:bool):
    # Selection pool must exclude input n outputs since we lock the outedges
    oneOutNodeList = [x for x in tempG.nodes if tempG.out_degree(x) == 1 and tempG.nodes[x]['type'] == 'gate']
    multiOutNodeList = [x for x in tempG.nodes if tempG.out_degree(x) > 1 and tempG.nodes[x]['type'] == 'gate']
    gateDict, muxDict = infoDict
    
    key_list = generate_key_list(keySize)
    print(key_list)
    oneOutSelectedGates = random.sample(oneOutNodeList, keySize//2)
    multiOutSelectedGates = random.sample(multiOutNodeList, keySize//2)
    print("one_out",oneOutSelectedGates)
    print("multi_out",multiOutSelectedGates)

    if dumpFiles:
        global link_train, link_test, link_test_n
    """
    try find a way to avoid locking edges that point to the same endNode
    currently using slightly different mux naming 
    """
    c = 0
    nodeList = oneOutNodeList + multiOutNodeList
    selected_gates = oneOutSelectedGates + multiOutSelectedGates
    fPool = set(nodeList)
    for gateNode in selected_gates:
        # print(gateNode)
        # All nodes next to gateNode except locking muxes (they appear when the gateNode had been selected as false wire)
        # Avoids nested locking
        outNodes = [x for x in tempG.successors(gateNode) if tempG.nodes[x]['type'] == 'gate' or tempG.nodes[x]['type'] == 'output']
        endNode = random.choice(outNodes)
        
        # complicit naming as original dmux 
        # (NOTE: naming no longer complicit better to modify the other temporarily)
        # Remove the gateNode to ensure compliance
        muxNode = endNode+'_from_mux'+gateNode
        keyNode = 'keyinput' + str(c)
        
        if gateNode in oneOutNodeList:
            # Avoid nodes causing loops(successors) and cycles(decendants of successors)
            badFGates = nx.descendants(tempG, endNode)
            fPool.difference_update(badFGates)
            fPool.difference_update(selected_gates)
            # Avoid reselection
            fPool.discard(gateNode)
            # Avoid self-selection
            fPool.discard(endNode)
            
            # Should also remove nodes that already point to the endnode here
            # But this is left intentionally
            
            # Code breaks here if fPool is zero (all nodes are reachable from the node to be locked)
            # Sampling from set depreciated apparently
            fGate = random.choice(list(fPool))
        else:
            suffix = '_sub' # also used in circuit reconstruction
            # First version of newLock
            # subG, deepest_nodes = get_backward_subgraph(tempG, gateNode)
            # stitch_subgraph(tempG, subG, deepest_nodes, suffix)
            # Second version
            gen_subgraph(tempG, gateNode, depth=2, dumpFiles=dumpFiles)
            
            fGate = f"{gateNode}{suffix}"
        
        tempG.remove_edge(gateNode, endNode)
        tempG.add_edge(muxNode, endNode)
        tempG.nodes[muxNode]['type'] = 'mux'
        tempG.nodes[muxNode]['gate'] = 'MUX'
                
        tempG.add_edge(gateNode, muxNode)        
        tempG.add_edge(fGate, muxNode)  
        tempG.add_node(keyNode, type='input', isKey=True)      
        tempG.add_edge(keyNode, muxNode)
        
        if dumpFiles:
            link_train = link_train.replace(f"{tempG.nodes[gateNode]['count']} {tempG.nodes[endNode]['count']}\n", "")
            link_test += f"{tempG.nodes[gateNode]['count']} {tempG.nodes[endNode]['count']}\n"
            link_test_n += f"{tempG.nodes[fGate]['count']} {tempG.nodes[endNode]['count']}\n"
      
        # update the infoDict
        if key_list[c] == 0:
            input0 = gateNode
            input1 = fGate
        else:
            input0 = fGate
            input1 = gateNode
        muxDict[muxNode] = {"key": keyNode, 0: input0 , 1: input1}
        gateDict[muxNode] = "MUX"
        
        c+=1
        fPool = set(nodeList) # Restore the fake node pool
    
    return key_list        

def draw_neat_digraph(G, title=None, node_size=800):
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
    plt.show()

def main(bench, kSize, dumpFiles=False, drawGraph=True):    
    G, infoDict = parse_ckt('./Benchmarks/'+bench+'.bench', dumpFiles)
    kList = insertMuxNew(G, infoDict, kSize, dumpFiles)

    if dumpFiles:
        dumpDir = "./data/"
        if not os.path.exists(dumpDir):
            os.mkdir(dumpDir)

        if not os.path.exists(f"{dumpDir}/{bench}_K{kSize}_DMUX"):
            os.mkdir(f"{dumpDir}/{bench}_K{kSize}_DMUX")
        
        dumpDir = f"{dumpDir}/{bench}_K{kSize}_DMUX"
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

    reconstruct_bench(G, infoDict, kList, f"{bench}_K{kSize}", not dumpFiles)
    if drawGraph:
        draw_neat_digraph(G, "New Lock")

main('b22_C', 256, dumpFiles=True, drawGraph=False)
            