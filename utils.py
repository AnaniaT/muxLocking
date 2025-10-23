import random,sys, re
import networkx as nx
import matplotlib.pyplot as plt

def generate_key_list(key_size: int):
    if key_size%2 != 0:
        raise ValueError("Key size should be a multiple of two")
    
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



def reconstruct_bench(tempG: nx.DiGraph, infoDict: dict, keyList:list, outBenchName: str = "output.bench", dumpHere=False):
    inputs = ""
    outputs = ""
    logicOps = ""
    
    outDir = f"./data/{outBenchName}_DMUX"
    if dumpHere:
        outDir = "."
    
    # gateDict, muxDict = infoDict
    for node in list(tempG.nodes):
        if tempG.in_degree(node) == 0: # might catch floating nodes
            inputs += f"INPUT({node})\n"
        else:
            if tempG.out_degree(node) == 0:
                outputs += f"OUTPUT({node})\n"
            
            # gateName = gateDict[node]
            gateName = tempG.nodes[node]['gate'].upper()
            if gateName == "MUX":
                # mux = muxDict[node]
                mux = tempG.nodes[node]['muxDict']
                inWiresStr = f"{mux['key']}, {mux[0]}, {mux[1]}"
            else:
                inWiresStr = ", ".join(tempG.predecessors(node))
                
            logicOps += f"{node} = {gateName}({inWiresStr})\n"
    
    try:
        with open(f"{outDir}/{outBenchName}.bench", "w") as file:
            strKList = map(lambda k: str(k), keyList)
            file.write(f"#key={''.join(strKList)}\n")
            file.write(inputs+"\n" + outputs+"\n"+ logicOps)
                
        print(f"Bench file successfully written to {outBenchName}.bench")
    except Exception as e:
        print(f"Error writing file: {e}") 
        


def draw_graph(tempG: nx.DiGraph, name:str = "Graph"):
    # Draw the graph
    plt.figure(figsize=(6, 4))
    pos = nx.spring_layout(tempG)  # Positions for nodes
    nx.draw(tempG, pos, with_labels=True, node_color="lightblue", edge_color="black", node_size=2000, font_size=12, arrows=True)
    plt.title(name)
    plt.show(block=False)

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