import copy
import re, random
import networkx as nx
import matplotlib.pyplot as plt

def generate_key_list(key_size: int):
    # if key_size%2 != 0:
    #     raise ValueError("Key size should be a multiple of two")
    
    # random 1:1 combination of zeros and ones
    key_mid = key_size//2
    key_list = [0] * int(key_mid) + [1] *int(key_size-key_mid)
    # If odd keysize is also allowed this should work
    # key_list = [0] * int(key_size/2) + [1] * (key_size - int(key_size/2))
    random.shuffle(key_list)    
    return key_list

def cleanInWireList(inWiresStr: str):
    inWiresStr.strip()
    if inWiresStr[-1] == ",":
        inWiresStr = inWiresStr[:-1]
    return [x.strip() for x in inWiresStr.split(',')]

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
    
    feat, cell, count = '', '', ''
    ML_count = 0   
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
                        
                    feat += f'{' '.join(gateVecDict[gate.lower()])}\n'
                    cell += f'{ML_count} assign for output {outWire}\n'
                    count += f'{ML_count}\n'
                    ML_count+=1
                else:
                    # raise error if not empty line
                    if line.strip() != "":
                        raise Exception('Bad Bench File')
                    
    except FileNotFoundError:
        print(f"Error: The file {bench_file_path} was not found.")
    except Exception as e:
        print(f"An error occurred: {e}")
        
    return tempG, (gateDict, muxDict) #infoDict


def insertMux(tempG:nx.DiGraph, infoDict: list[dict], keySize: int):
    nodeList = list(tempG.nodes)
    gateDict, muxDict = infoDict
    
    key_list = generate_key_list(keySize)
    print(key_list)
    selected_gates = random.sample(nodeList, keySize)
    print(selected_gates)

    c = 0
    fPool = set(nodeList)
    for gateNode in selected_gates:
        muxNode = 'mux_' + str(c)
        keyNode = 'key_' + str(c)
        
        outNodes = list(tempG.successors(gateNode))
        
        # Avoid nodes causing loops(successors) and cycles(decendants of successors)
        badFGates = nx.descendants(tempG, gateNode)
        fPool.difference_update(badFGates)
        # Avoid reselection
        fPool.remove(gateNode)
        
        # MUX replacement
        for oNode in outNodes:
            tempG.remove_edge(gateNode, oNode)
            tempG.add_edge(muxNode, oNode)
            
            # Update the MUX dict if the out node is a MUX
            if oNode in muxDict.keys():
                if muxDict[oNode][0] == gateNode:
                    muxDict[oNode][0] = muxNode
                elif muxDict[oNode][1] == gateNode:
                    muxDict[oNode][1] = muxNode
                else:
                    muxDict[oNode]['key'] = muxNode
            
        # Code breaks here if fPool is zero (all nodes are reachable from the node to be locked)
        # Sampling from set depreciated apparently
        fGate = random.sample(list(fPool), 1)[0]
        
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
        fPool = set(tempG.nodes) # Restore the fake node pool
        

def reconstruct_bench(tempG: nx.DiGraph, infoDict: dict, out_bench_file_path: str = "output.bench"):
    inputs = ""
    outputs = ""
    logicOps = ""
    
    gateDict, muxDict = infoDict
    for node in list(tempG.nodes):
        if tempG.in_degree(node) == 0:
            inputs += f"INPUT({node})\n"
        else:
            if tempG.out_degree(node) == 0:
                outputs += f"OUTPUT({node})\n"
            
            gateName = gateDict[node]
            if gateName.lower() == "mux":
                mux = muxDict[node]
                inWiresStr = f"{mux['key']}, {mux[0]}, {mux[1]}"
            else:
                inWiresStr = ", ".join(tempG.predecessors(node))
                
            logicOps += f"{node} = {gateName}({inWiresStr})\n"
    
    
    try:
        with open(out_bench_file_path, "w") as file:
            file.write(inputs+"\n" + outputs+"\n"+ logicOps)
                
        print(f"Bench file successfully written to {out_bench_file_path}")
    except Exception as e:
        print(f"Error writing file: {e}") 

def draw_graph(tempG: nx.DiGraph, name:str = "Graph"):
    # Draw the graph
    plt.figure(figsize=(6, 4))
    pos = nx.spring_layout(tempG)  # Positions for nodes
    nx.draw(tempG, pos, with_labels=True, node_color="lightblue", edge_color="black", node_size=2000, font_size=12, arrows=True)
    plt.title(name)
    plt.show(block=False)

quickTest = True

if quickTest:
    G, infoDict = parse_ckt('b.bench')
    insertMux(G, infoDict, 4)
else:
    G, infoDict = parse_ckt('b14_C.bench')
    insertMux(G, infoDict, 64)

# reconstruct_bench(G, infoDict, "gOut2.bench")
# draw_graph(G)
# draw_graph(G)
# input("..")
"""
G, infoDict = parse_ckt('b.bench')
# G = parse_ckt('b14_C.bench')
# print(list(G.nodes))
G0 = copy.deepcopy(G)

insertMux(G, infoDict, 2)

reconstruct_bench(G, infoDict, "gOut.bench")

G2, infoDict2 = parse_ckt('gOut.bench')


# Create a figure with 1 row, 2 columns
fig, axes = plt.subplots(1, 3, figsize=(10, 5))

# Draw the first graph
nx.draw(G0, ax=axes[0], with_labels=True, node_color="lightblue", edge_color="gray")
axes[0].set_title("Before")

# Draw the first graph
nx.draw(G, ax=axes[1], with_labels=True, node_color="grey", edge_color="gray")
axes[1].set_title("After 1")

# Draw the second graph
nx.draw(G2, ax=axes[2], with_labels=True, node_color="lightgreen", edge_color="red")
axes[2].set_title("After 2")

# Show both graphs
plt.show()
"""
