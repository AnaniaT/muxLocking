import os, random, sys, re, copy
import networkx as nx

from utils import generate_key_list, reconstruct_bench, cleanInWireList, gateVecDict, alter_gate
from tools import *
from multimux import neiSplit

feat, cell, count = '', '', ''
ML_count = 0 
link_train = ''
link_test = ''
link_test_n = ''

    
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
                    if isInput.group(1) in tempG.nodes:
                        print(isInput.group(1), "in")
                        continue
                    tempG.add_node(isInput.group(1))
                    tempG.nodes[isInput.group(1)]['type'] = 'input'
                elif isOutput:
                    if isOutput.group(1) in tempG.nodes:
                        # print(isOutput.group(1), "out")
                        continue
                    tempG.add_node(isOutput.group(1))
                    tempG.nodes[isOutput.group(1)]['type'] = 'output'
                elif isLogicOp:
                    outWire, gate, inWires = isLogicOp.groups()
                    
                    for inwire in cleanInWireList(inWires):
                        tempG.add_edge(inwire, outWire)
                        
                    # gateDict[outWire] = gate
                    # Store more mux info (ONLY SUPPORTS 2 TO 1 MUX)
                    if gate.lower() == "mux":
                        k, i0, i1 = cleanInWireList(inWires)
                        # muxDict[outWire] = {"key": k, 0:i0, 1:i1 }
                        tempG.nodes[outWire]['muxDict'] = {"key": k, 0:i0, 1:i1 }
                    
                    
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


def selectTargetEdges(tempG:nx.DiGraph, allEligibleEdges, keySize: int, hop=4):
    k = keySize // 2
    # Start nodes must exclude input n outputs since we lock the outedges
    # End nodes should except locking muxes (they appear when the gateNode had been selected as false wire)
    # Avoids nested locking

    # Get all input nodes
    input_nodes = {n for n in tempG.nodes if tempG.nodes[n]['type'] == 'input'}
    
    # Compute h-hop fanout from all input nodes
    input_h_hop_fanout = set()
    for inp in input_nodes:
        input_h_hop_fanout.update(nx.ego_graph(tempG, inp, radius=hop, undirected=False).nodes)

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
            # Check if both u and v are close to input nodes (within h-hop)
            if u not in input_h_hop_fanout or v not in input_h_hop_fanout:
                continue
            
            # tempG.remove_edge(u, v)
            # # Compute h-hop fanout of u
            # fanout_u = set(nx.ego_graph(tempG, u, radius=hop, undirected=False).nodes)

            # # Compute h-hop fanin and fanout of v
            # fanin_v = set(nx.ego_graph(tempG.reverse(), v, radius=hop, undirected=False).nodes)
            # fanout_v = set(nx.ego_graph(tempG, v, radius=hop, undirected=False).nodes)

            # tempG.add_edge(u, v)
            # # Ensure no overlap between fanout of u and (v, fanin_v, fanout_v)
            # if v in fanout_u or fanout_u & fanin_v or fanout_u & fanout_v:
            #     continue
            
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


def insertMuxUpdated(tempG:nx.DiGraph, keySize: int, dumpFiles:bool, hop:int=3, alt_percent:float=0.5):
    
    key_list = generate_key_list(keySize)
    print(key_list)
    
    altGateList = key_list[:]
    random.shuffle(altGateList)
    
    allEligibleEdges = [(u,v) for u,v in tempG.edges if tempG.nodes[u]['type'] == 'gate' and (tempG.nodes[v]['type'] == 'gate' or tempG.nodes[v]['type'] == 'output')]
    oneOutSelectedEdges, multiOutSelectedEdges = selectTargetEdges(tempG, allEligibleEdges, keySize)
    print("one_out",oneOutSelectedEdges)
    print("multi_out",multiOutSelectedEdges)

    if dumpFiles:
        global link_train, link_test, link_test_n, feat, cell, count, ML_count 
    """
    try find a way to avoid locking edges that point to the same endNode
    currently using slightly different mux naming 
    """
    c = 0
    selected_edges = oneOutSelectedEdges + multiOutSelectedEdges
    selectedStarts = {u for u,_ in selected_edges}
    nodeList = {u for u,_ in allEligibleEdges if u not in selectedStarts}
    fPool = set(nodeList)
    locked_edges = set()
    for u,v in selected_edges:
        # May not utlize all selected edges if we used multiple muxes for when replicating
        if c >= keySize:
            break
        # Selected edges which happen to be locked during the multi-mux insertion
        if (u,v) in locked_edges:
            continue
        # complicit naming as original dmux 
        # (NOTE: naming no longer complicit better to modify the other temporarily)
        # Remove the gateNode to ensure compliance
        muxNode = v+'_from_mux'
        keyNode = 'keyinput' + str(c)
        
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
        
        # This part for the else section is handled internally by the function call
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


def main(bench, kSize, dumpFiles=False, drawGraph=False):    
    global feat, cell, count, ML_count, link_train, link_test, link_test_n
    feat, cell, count = '', '', ''
    ML_count = 0 
    link_train = ''
    link_test = ''
    link_test_n = ''
    
    G, infoDict = parse_ckt('./Benchmarks/'+bench+'.bench', dumpFiles)
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


main('c1355', 32, dumpFiles=True, drawGraph=False)


print('Done running newLock.py')
    