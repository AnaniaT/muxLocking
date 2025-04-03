import random,sys, re
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



def parse_ckt(bench_file_path: str, involveFiles : bool = False) -> nx.DiGraph:
    tempG = nx.DiGraph()
    # Assuming one declaration per line
    # _in_out = re.compile(r"(?i)^\s*(INPUT|OUTPUT)\s*\(\s*(.*?)\s*\)\s*$")
    _input = re.compile(r"(?i)^\s*INPUT\s*\(\s*(.*?)\s*\)\s*$")
    _output = re.compile(r"(?i)^\s*OUTPUT\s*\(\s*(.*?)\s*\)\s*$")
    
    _logicOp = re.compile(r"^\s*(\w+)\s*=\s*(\w+)\s*\(\s*(.*?)\s*\)\s*$")
    # _logicOp = re.compile(r"^(\w+)\s*=\s*(\w+)\s*\(\s*(.*?)\s*\)\s*$")

    gateDict = {}
    muxDict = {}
    
    if involveFiles:
        global feat, cell, count, ML_count
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
                    
                    if involveFiles:
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
    # except Exception as e:
    #     sys.exit(f"An error occurred: {e}")    
    
    if involveFiles:
        global link_train
        for u, v in tempG.edges:
            if 'count' in tempG.nodes[u].keys() and 'count' in tempG.nodes[v].keys():
                link_train += f"{tempG.nodes[u]['count']} {tempG.nodes[v]['count']}\n"
        
    return tempG, (gateDict, muxDict) #infoDict


def reconstruct_bench(tempG: nx.DiGraph, infoDict: dict, keyList:list, outBenchName: str = "output.bench", outDir="data"):
    inputs = ""
    outputs = ""
    logicOps = ""
    
    gateDict, muxDict = infoDict
    for node in list(tempG.nodes):
        if tempG.in_degree(node) == 0: # might catch floating nodes
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
        with open(f"./data/{outBenchName}_DMUX/{outBenchName}.bench", "w") as file:
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
