import os, random, sys, re
import networkx as nx

from utils import generate_key_list, reconstruct_bench, cleanInWireList

feat, cell, count = '', '', ''
ML_count = 0 
link_train = ''
link_test = ''
link_test_n = ''


def parse_ckt(bench_file_path: str) -> nx.DiGraph:
    tempG = nx.DiGraph()
    # Assuming one declaration per line
    # _in_out = re.compile(r"(?i)^\s*(INPUT|OUTPUT)\s*\(\s*(.*?)\s*\)\s*$")
    _input = re.compile(r"(?i)^\s*INPUT\s*\(\s*(.*?)\s*\)\s*$")
    _output = re.compile(r"(?i)^\s*OUTPUT\s*\(\s*(.*?)\s*\)\s*$")
    
    _logicOp = re.compile(r"^\s*(\w+)\s*=\s*(\w+)\s*\(\s*(.*?)\s*\)\s*$")
    # _logicOp = re.compile(r"^(\w+)\s*=\s*(\w+)\s*\(\s*(.*?)\s*\)\s*$")

    gateDict = {}
    muxDict = {}
    
    global feat, cell, count, ML_count, link_train
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
    
    try:
        with open(bench_file_path, 'r') as file:
            for line in file:
                line = line.strip()
                
                isInput = _input.match(line)
                isOutput = _output.match(line)
                isLogicOp = _logicOp.match(line)
                
                if isInput:
                    tempG.add_node(isInput.group(1))
                elif isOutput:
                    tempG.add_node(isOutput.group(1))
                elif isLogicOp:
                    outWire, gate, inWires = isLogicOp.groups()
                    
                    gateDict[outWire] = gate
                    # Store more mux info (ONLY SUPPORTS 2 TO 1 MUX)
                    if gate.lower() == "mux":
                        k, i0, i1 = cleanInWireList(inWires)
                        muxDict[outWire] = {"key": k, 0:i0, 1:i1 }
                    
                    for inwire in cleanInWireList(inWires):
                        tempG.add_edge(inwire, outWire)
                    
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
    
    for u, v in tempG.edges:
        if 'count' in tempG.nodes[u].keys() and 'count' in tempG.nodes[v].keys():
            link_train += f"{tempG.nodes[u]['count']} {tempG.nodes[v]['count']}\n"
        
    return tempG, (gateDict, muxDict) #infoDict

def insertMux(tempG:nx.DiGraph, infoDict: list[dict], keySize: int):
    # Selection pool excludes inputs and outputs
    nodeList = [x for x in tempG.nodes if 'count' in tempG.nodes[x].keys() and tempG.out_degree(x) > 0]
    gateDict, muxDict = infoDict
    
    key_list = generate_key_list(keySize)
    print(key_list)
    selected_gates = random.sample(nodeList, keySize)
    print(selected_gates)

    global link_train, link_test, link_test_n
    
    c = 0
    fPool = set(nodeList)
    for gateNode in selected_gates:
        muxNode = 'mux_' + str(c)
        keyNode = 'key_' + str(c)
        
        # All nodes next to gateNode except locking muxes (they appear when the gateNode had been selected as false wire)
        outNodes = list([x for x in tempG.successors(gateNode) if 'count' in tempG.nodes[x].keys()])
        
        # Avoid nodes causing loops(successors) and cycles(decendants of successors)
        badFGates = nx.descendants(tempG, gateNode)
        fPool.difference_update(badFGates)
        # Avoid reselection
        fPool.remove(gateNode)
        # Code breaks here if fPool is zero (all nodes are reachable from the node to be locked)
        # Sampling from set depreciated apparently
        fGate = random.sample(list(fPool), 1)[0]
        
        # MUX replacement
        for oNode in outNodes:
            tempG.remove_edge(gateNode, oNode)
            tempG.add_edge(muxNode, oNode)
            
            link_train = link_train.replace(f"{tempG.nodes[gateNode]['count']} {tempG.nodes[oNode]['count']}\n", "")
            link_test += f"{tempG.nodes[gateNode]['count']} {tempG.nodes[oNode]['count']}\n"
            link_test_n += f"{tempG.nodes[fGate]['count']} {tempG.nodes[oNode]['count']}\n"
        
            # Update the MUX dict if the out node is a MUX
            if oNode in muxDict.keys():
                if muxDict[oNode][0] == gateNode:
                    muxDict[oNode][0] = muxNode
                elif muxDict[oNode][1] == gateNode:
                    muxDict[oNode][1] = muxNode
                else:
                    muxDict[oNode]['key'] = muxNode
            
        
        tempG.add_edge(fGate, muxNode)        
        tempG.add_edge(keyNode, muxNode)        
        tempG.add_edge(gateNode, muxNode)
        
        
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


def insertMux2(tempG:nx.DiGraph, infoDict: list[dict], keySize: int):
    # Selection pool must exclude input n outputs since we lock the outedges
    nodeList = [x for x in tempG.nodes if tempG.out_degree(x) > 0 and 'count' in tempG.nodes[x].keys()]
    gateDict, muxDict = infoDict
    
    key_list = generate_key_list(keySize)
    print(key_list)
    selected_gates = random.sample(nodeList, keySize)
    print(selected_gates)

    global link_train, link_test, link_test_n
    
    c = 0
    fPool = set(nodeList)
    for gateNode in selected_gates:
        muxNode = 'mux_' + str(c)
        keyNode = 'key_' + str(c)
        
        # All nodes next to gateNode except locking muxes (they appear when the gateNode had been selected as false wire)
        # Avoids nested locking
        outNodes = [x for x in tempG.successors(gateNode) if 'count' in tempG.nodes[x].keys()]
        
        endNode = random.choice(outNodes)
        
        # Avoid nodes causing loops(successors) and cycles(decendants of successors)
        badFGates = nx.descendants(tempG, endNode)
        fPool.difference_update(badFGates)
        # Avoid reselection
        fPool.discard(gateNode)
        # Avoid self-selection
        fPool.discard(endNode)
        
        # Should also remove nodes that already point to the endnode here
        # But this is left intentionally
        
        # Code breaks here if fPool is zero (all nodes are reachable from the node to be locked)
        # Sampling from set depreciated apparently
        fGate = random.choice(list(fPool))
        
        tempG.remove_edge(gateNode, endNode)
        tempG.add_edge(muxNode, endNode)
                
        tempG.add_edge(gateNode, muxNode)        
        tempG.add_edge(fGate, muxNode)        
        tempG.add_edge(keyNode, muxNode)
        
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
        


longTest = bool(sys.argv[1] == "1")

if not longTest:
    G, infoDict = parse_ckt('b.bench')
    insertMux2(G, infoDict, 4)
else:
    G, infoDict = parse_ckt('b14_C.bench')
    insertMux2(G, infoDict, 64)

if not os.path.exists("./data"):
    os.mkdir("./data")
with open('./data/cell.txt', "w") as f:
    f.write(cell)
with open('./data/feat.txt', "w") as f:
    f.write(feat)
with open('./data/count.txt', "w") as f:
    f.write(count)
with open('./data/linkTrain.txt', "w") as f:
    f.write(link_train)
with open('./data/linkTest.txt', "w") as f:
    f.write(link_test)
with open('./data/linkTestN.txt', "w") as f:
    f.write(link_test_n)

reconstruct_bench(G, infoDict, "gOut3.bench")
