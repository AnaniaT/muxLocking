import os, random, sys, re
import networkx as nx
from collections import deque
import matplotlib.pyplot as plt
from networkx.drawing.nx_pydot import graphviz_layout

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
def gen_subgraphUpdated(
    G: nx.DiGraph,
    start_node, nodeTag, dumpFiles=False, altGates=True
) -> nx.DiGraph:
    if dumpFiles:
        global feat, cell, count, ML_count, link_train
    # Step 1: Get all nodes reachable from start_node
    nodes_to_copy = nx.ancestors(G, start_node)
    nodes_to_copy.add(start_node)

    # Step 2: Create a mapping of old -> new node IDs
    mapping = {}
    for n in nodes_to_copy:
        if "isKey" in G.nodes[n]:
            # Prevent postprocessing from picking this as real keyinput
            mapping[n] = n.replace("keyinput", "key_input")+nodeTag
        else:                
            mapping[n] = n+nodeTag 

    # Step 3: Create the subgraph copy
    subG = G.subgraph(nodes_to_copy).copy()

    # Step 4: Relabel nodes
    subG = nx.relabel_nodes(subG, mapping)

    # Step 5: Edit node attributes
    for node in subG.nodes:
        if subG.nodes[node]['type'] == "input":
            # G.add_node(artNode, type='input', isArt=True)
            subG.nodes[node].clear()
            subG.nodes[node].update({"type": "input", "isArt": True})
        else:
            if altGates:
                artNodeGate = alter_gate(subG.nodes[node]['gate'])
            else:
                artNodeGate = subG.nodes[node]['gate']   
            
            if artNodeGate.upper() == "MUX":               
                # G.add_node(artNode, type='mux', isArt=True, gate=artNodeGate)
                mDict = {}
                for k,v in subG.nodes[node]['muxDict'].items():
                    if k == "key":
                        mDict["key"] = v.replace("keyinput", "key_input")+nodeTag
                    else:
                        mDict[k] = v+nodeTag
                        
                # G.nodes[artNode]['muxDict'] = mDict
                subG.nodes[node].clear()
                subG.nodes[node].update({"type": "mux", "isArt": True, "gate": artNodeGate, "muxDict": mDict})
                    
            else:
                # G.add_node(artNode, type='gate', isArt=True, gate=artNodeGate)
                subG.nodes[node].clear()
                subG.nodes[node].update({"type": "gate", "isArt": True, "gate": artNodeGate})
        
                if dumpFiles:
                    subG.nodes[node]['count'] = ML_count    
                    feat += f"{' '.join([str(x) for x in gateVecDict[artNodeGate.lower()]])}\n"
                    cell += f"{ML_count} assign for output {node}\n"
                    count += f"{ML_count}\n"
                    ML_count+=1
                        
    # Step 6: Add edges to the link_train
    for u, v in subG.edges:
        # Avoid adding the fake start_node to the link_train
        if u != mapping[start_node]:
            if 'count' in subG.nodes[u].keys() and 'count' in subG.nodes[v].keys():
                link_train += f"{subG.nodes[u]['count']} {subG.nodes[v]['count']}\n"

    # Step 7: Merge the subgraph into the original graph G
    G.add_nodes_from(subG.nodes(data=True))
    G.add_edges_from(subG.edges(data=True))

def gen_subgraph(G:nx.DiGraph, start_node, nodeTag, dumpFiles=False, altGates=True):
    if dumpFiles:
        global feat, cell, count, ML_count, link_train
        
    current_layer = {start_node}
    targetCkt = set()
    while len(current_layer) > 0:
        left_layer = set()
        for origNode in current_layer:
            left_layer.update(G.predecessors(origNode))
            
            if "isKey" in G.nodes[origNode]:
                # Prevent postprocessing from picking this as real keyinput
                artNode = origNode.replace("keyinput", f"key_input")+nodeTag
            else:                
                artNode = origNode+nodeTag
            
            if G.nodes[origNode]['type'] == "input":
                G.add_node(artNode, type='input', isArt=True)
            else:
                if altGates:
                    artNodeGate = alter_gate(G.nodes[origNode]['gate'])
                else:
                    artNodeGate = G.nodes[origNode]['gate']     
                
                if artNodeGate.upper() == "MUX":               
                    G.add_node(artNode, type='mux', isArt=True, gate=artNodeGate)
                    mDict = {}
                    for k,v in G.nodes[origNode]['muxDict'].items():
                        if k == "key":
                            mDict["key"] = v.replace("keyinput", f"key_input")+nodeTag
                        else:
                            mDict[k] = v+nodeTag
                            
                    G.nodes[artNode]['muxDict'] = mDict
                        
                else:
                    G.add_node(artNode, type='gate', isArt=True, gate=artNodeGate)
            
            if dumpFiles and G.nodes[artNode]['type'] != "input":
                # avoid counting artNodes which were already setup
                if not 'count' in G.nodes[artNode] and artNodeGate.lower() != "mux":
                    G.nodes[artNode]['count'] = ML_count    
                    feat += f"{' '.join([str(x) for x in gateVecDict[artNodeGate.lower()]])}\n"
                    cell += f"{ML_count} assign for output {artNode}\n"
                    count += f"{ML_count}\n"
                    ML_count+=1
                            
            if origNode == start_node:
                continue
            
            
            for succ in list(G.successors(origNode)):
                artSuccNode = succ + nodeTag
                if succ in targetCkt:
                    G.add_edge(artNode, artSuccNode)
                    
                    if dumpFiles:
                        if 'count' in G.nodes[artNode].keys() and 'count' in G.nodes[artSuccNode].keys():
                            link_train += f"{G.nodes[artNode]['count']} {G.nodes[artSuccNode]['count']}\n"

        targetCkt.update(current_layer)
        current_layer = left_layer

    
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
                    
                    # gateDict[outWire] = gate
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
                    
                    if dumpFiles:
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
    
    if dumpFiles:
        for u, v in tempG.edges:
            if 'count' in tempG.nodes[u].keys() and 'count' in tempG.nodes[v].keys():
                link_train += f"{tempG.nodes[u]['count']} {tempG.nodes[v]['count']}\n"
        
    return tempG, (gateDict, muxDict) #infoDict


def selectTargetEdges(tempG:nx.DiGraph, allEligibleEdges, keySize: int):
    k = keySize // 2
    # Start nodes must exclude input n outputs since we lock the outedges
    # End nodes should except locking muxes (they appear when the gateNode had been selected as false wire)
    # Avoids nested locking

    # Shuffle the list to ensure randomness
    random.shuffle(allEligibleEdges)

    # Track used start and end nodes
    used_starts = set()
    used_ends = set()

    # Final result list
    unique_1Edges = []
    unique_mEdges = []

    for u, v in allEligibleEdges:
        if len(unique_1Edges) == k and len(unique_mEdges) == k:
            break
        
        if u not in used_starts and v not in used_ends:
            if tempG.out_degree(u) == 1 and len(unique_1Edges) < k:
                unique_1Edges.append((u,v))
                used_starts.add(u)
                used_ends.add(v)
            elif tempG.out_degree(u) > 1 and len(unique_mEdges) < k:
                unique_mEdges.append((u,v))
                used_starts.add(u)
                used_ends.add(v)
    
    if len(unique_1Edges) != k or len(unique_mEdges) != k:
        raise Exception("Graph is not suitable for locking")
    
    return unique_1Edges, unique_mEdges


def insertMuxUpdated(tempG:nx.DiGraph, keySize: int, dumpFiles:bool):
    
    key_list = generate_key_list(keySize)
    print(key_list)
    
    altGateList = key_list[:]
    random.shuffle(altGateList)
    
    allEligibleEdges = [(u,v) for u,v in tempG.edges if tempG.nodes[u]['type'] == 'gate' and (tempG.nodes[v]['type'] == 'gate' or tempG.nodes[v]['type'] == 'output')]
    oneOutSelectedEdges, multiOutSelectedEdges = selectTargetEdges(tempG, allEligibleEdges, keySize)
    print("one_out",oneOutSelectedEdges)
    print("multi_out",multiOutSelectedEdges)

    if dumpFiles:
        global link_train, link_test, link_test_n
    """
    try find a way to avoid locking edges that point to the same endNode
    currently using slightly different mux naming 
    """
    c = 0
    selected_edges = oneOutSelectedEdges + multiOutSelectedEdges
    selectedStarts = {u for u,_ in selected_edges}
    nodeList = {u for u,_ in allEligibleEdges if u not in selectedStarts}
    fPool = set(nodeList)
    
    for u,v in selected_edges:
        # complicit naming as original dmux 
        # (NOTE: naming no longer complicit better to modify the other temporarily)
        # Remove the gateNode to ensure compliance
        muxNode = v+'_from_mux'
        keyNode = 'keyinput' + str(c)
        
        if c < keySize//2: # first half of selectedGates is oneOut
            # Avoid nodes causing loops(successors) and cycles(decendants of successors)
            badFGates = nx.descendants(tempG, v)
            fPool.difference_update(badFGates)
            fPool.difference_update(selectedStarts)
            # Avoid reselection
            # fPool.discard(u) # Already included in selectedStarts
            # Avoid self-selection
            fPool.discard(v)
            
            # Should also remove nodes that already point to the endnode here
            # But this is left intentionally
            
            # Should also remove nodes that are already picked as fGate here
            # But this is left intentionally as well
            
            # Code breaks here if fPool is zero (all nodes are reachable from the node to be locked)
            # Sampling from set depreciated apparently i.e used list()
            fGate = random.choice(list(fPool))
        else:
            suffix = '_sub_'+v 
            print('c')
            # alter gates randomly half of the time  
            gen_subgraphUpdated(tempG, u, suffix, dumpFiles=dumpFiles, altGates=bool(altGateList[c]))
            print('d')
            
            fGate = f"{u}{suffix}"
        
        tempG.remove_edge(u, v)
        tempG.add_edge(muxNode, v)
        tempG.nodes[muxNode]['type'] = 'mux'
        tempG.nodes[muxNode]['gate'] = 'MUX'
                
        tempG.add_edge(u, muxNode)        
        tempG.add_edge(fGate, muxNode)  
        tempG.add_node(keyNode, type='input', isKey=True)      
        tempG.add_edge(keyNode, muxNode)
        
        if dumpFiles:
            link_train = link_train.replace(f"{tempG.nodes[u]['count']} {tempG.nodes[v]['count']}\n", "")
            link_test += f"{tempG.nodes[u]['count']} {tempG.nodes[v]['count']}\n"
            link_test_n += f"{tempG.nodes[fGate]['count']} {tempG.nodes[v]['count']}\n"
      
        # update the infoDict
        if key_list[c] == 0:
            input0 = u
            input1 = fGate
        else:
            input0 = fGate
            input1 = u

        tempG.nodes[muxNode]['muxDict'] = {"key": keyNode, 0: input0 , 1: input1}
        
        c+=1
        fPool = set(nodeList) # Restore the fake node pool
       
    return key_list        


def insertMuxNew(tempG:nx.DiGraph, infoDict: list[dict], keySize: int, dumpFiles:bool):
    # Selection pool must exclude input n outputs since we lock the outedges
    oneOutNodeList = [x for x in tempG.nodes if tempG.out_degree(x) == 1 and tempG.nodes[x]['type'] == 'gate']
    multiOutNodeList = [x for x in tempG.nodes if tempG.out_degree(x) > 1 and tempG.nodes[x]['type'] == 'gate']
    # gateDict, muxDict = infoDict
    
    key_list = generate_key_list(keySize)
    altGateList = list(key_list)
    random.shuffle(altGateList)
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
    
    alreadyLocked = set()
    skippedOneOutGates = 0
    skippedMultiOutGates = 0
    for gateNode in selected_gates:
        # print(gateNode)
        # All nodes next to gateNode except locking muxes (they appear when the gateNode had been selected as false wire)
        # Avoids nested locking
        outNodes = [x for x in tempG.successors(gateNode) if tempG.nodes[x]['type'] == 'gate' or tempG.nodes[x]['type'] == 'output']
        endNode = random.choice(outNodes)
        
        # A temporary fix for the common-endNode problem
        retries = 0
        while endNode in alreadyLocked:
            print('a')
            outNodes.remove(endNode)
            if len(outNodes) > 0:
                endNode = random.choice(outNodes)
            elif retries >= 1: # if you change this make sure you remove already checked gate when choosing the gateNode again
                raise Exception("""
                No suitable gate found for locking. Try running the script again. If the issue persists, the circuit may be too simple to support logic locking."""
                )
            else:
                retries += 1
                if gateNode in oneOutNodeList:
                    newNodeList = set(oneOutNodeList).difference(oneOutSelectedGates)
                else:
                    newNodeList = set(multiOutNodeList).difference(multiOutSelectedGates)
                if len(newNodeList) == 0:
                    # will force the program reach the exception
                    outNodes.append(endNode)
                    continue 
                print(f"Gate [{gateNode}] swapped by gate ", end="")
                gateNode = random.choice(list(newNodeList))
                print(f"[{gateNode}]")
                outNodes = [x for x in tempG.successors(gateNode) if tempG.nodes[x]['type'] == 'gate' or tempG.nodes[x]['type'] == 'output']
                endNode = random.choice(outNodes)
                
        alreadyLocked.add(endNode)
        print('b')
        # complicit naming as original dmux 
        # (NOTE: naming no longer complicit better to modify the other temporarily)
        # Remove the gateNode to ensure compliance
        muxNode = endNode+'_from_mux'
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
            suffix = '_sub_'+endNode # alter gates randomly half of the time  
            print('c')
            gen_subgraph(tempG, gateNode, suffix, dumpFiles=dumpFiles, altGates=bool(altGateList[c]))
            print('d')
            
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
        # muxDict[muxNode] = {"key": keyNode, 0: input0 , 1: input1}
        # gateDict[muxNode] = "MUX"
        tempG.nodes[muxNode]['muxDict'] = {"key": keyNode, 0: input0 , 1: input1}
        
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
    # plt.show()
    plt.savefig("te.png", format='png', dpi=300)
    plt.close()

def main(bench, kSize, dumpFiles=False, drawGraph=False):    
    global feat, cell, count, ML_count, link_train, link_test, link_test_n
    feat, cell, count = '', '', ''
    ML_count = 0 
    link_train = ''
    link_test = ''
    link_test_n = ''
    
    G, infoDict = parse_ckt('./Benchmarks/'+bench+'.bench', dumpFiles)
    # kList = insertMuxNew(G, infoDict, kSize, dumpFiles)
    kList = insertMuxUpdated(G, kSize, dumpFiles)

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

# main('mid', 4, dumpFiles=True, drawGraph=True)
g, _ = parse_ckt('./data/mid_K4_DMUX/mid_K4.bench', False)
draw_neat_digraph(g, "midK4")
# d = [('c1355', 64)]
# r = []
# for f in os.listdir('./Benchmarks'):
#     if os.path.isfile('./Benchmarks/'+f):
#         if f != 'b.bench' and f != 'mid.bench':
#             if f.startswith('b'):
#                 continue
#                 for k in [256, 512]:
#                     sk = False
#                     for ff,kk in d:
#                         if f.startswith(ff) and k == kk:
#                             print("Skipping", f, k)
#                             sk = True
#                             break
#                     if sk:
#                         continue
#                     main(f.split('.')[0], k, True)
#                     # try:
#                     #     main(f.split('.')[0], k, True)
#                     # except Exception as e:
#                     #     print("Error: ", f, k)
#                     #     print(e)
#                     #     r.append([f.split('.')[0], k])
#             else:
#                 for k in [64, 128, 256]:
#                     sk = False
#                     for ff,kk in d:
#                         if f.startswith(ff) and k == kk:
#                             print("Skipping", f, k)
#                             sk = True
#                             break
#                     if sk:
#                         continue
                    
#                     if f.startswith('c13') and k == 256:
#                         continue
#                     main(f.split('.')[0], k, True)
#                     # try:
#                     #     main(f.split('.')[0], k, True)
#                     # except Exception as e:
#                     #     print("Error: ", f, k)
#                     #     print(e)
#                     #     r.append([f.split('.')[0], k])
# print("Done...", r)
# try:
# main('mid', 4, False, True)
# except Exception as e:
#     print(e)

# while len(r) > 0:
#     a = []
#     for i in r:
#         noErr = True
#         try:
#             main(i[0], i[1], True)
#         except Exception as e:
#             print(e)
#             print(i)
#             noErr = False
        
#         if noErr:
#             a.append(i)
            
#     for x in a:
#         r.remove(x)
    