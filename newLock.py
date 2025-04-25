import os, random, sys, re
import networkx as nx

from utils import generate_key_list, reconstruct_bench, cleanInWireList

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
                    
                    tempG.nodes[outWire]['type'] = 'gate'
                    
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
    print(oneOutSelectedGates)
    print(multiOutSelectedGates)

    if dumpFiles:
        global link_train, link_test, link_test_n
    
    c = 0
    nodeList = oneOutNodeList + multiOutNodeList
    selected_gates = oneOutSelectedGates + multiOutSelectedGates
    fPool = set(nodeList)
    for gateNode in selected_gates:
        # All nodes next to gateNode except locking muxes (they appear when the gateNode had been selected as false wire)
        # Avoids nested locking
        outNodes = [x for x in tempG.successors(gateNode) if tempG.nodes[x]['type'] == 'gate']
        
        endNode = random.choice(outNodes)
        
        # Complicent naming as original dmux
        muxNode = endNode+'_from_mux'
        keyNode = 'keyinput' + str(c)
        
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
        tempG.nodes[muxNode]['type'] = 'mux'
                
        tempG.add_edge(gateNode, muxNode)        
        tempG.add_edge(fGate, muxNode)        
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


def main(bench, kSize, dumpFiles=False):    
    G, infoDict = parse_ckt('./Benchmarks/'+bench+'.bench', dumpFiles)
    kList = insertMuxNew(G, infoDict, kSize, dumpFiles)

    if dumpFiles:
        dumpDir = "./data/new"
        if not os.path.exists(dumpDir):
            os.mkdir(dumpDir)

        if not os.path.exists(f"{dumpDir}/{bench}_K{kSize}_DMUX"):
            os.mkdir(f"{dumpDir}/{bench}_K{kSize}_DMUX")
            
        with open(f'{dumpDir}/{bench}_K{kSize}_DMUX/cell.txt', "w") as f:
            f.write(cell)
        with open(f'{dumpDir}/{bench}_K{kSize}_DMUX/feat.txt', "w") as f:
            f.write(feat)
        with open(f'{dumpDir}/{bench}_K{kSize}_DMUX/count.txt', "w") as f:
            f.write(count)
        with open(f'{dumpDir}/{bench}_K{kSize}_DMUX/links_train.txt', "w") as f:
            f.write(link_train)
        with open(f'{dumpDir}/{bench}_K{kSize}_DMUX/links_test.txt', "w") as f:
            f.write(link_test)
        with open(f'{dumpDir}/{bench}_K{kSize}_DMUX/link_test_n.txt', "w") as f:
            f.write(link_test_n)

    reconstruct_bench(G, infoDict, kList, f"{bench}_K{kSize}", True)

main('b', 4)
            