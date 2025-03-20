import networkx as nx
from utils import generate_key_list, parse_ckt

print('---Attack---')
def saam(g: nx.DiGraph, iDict: dict):
    # Deep Copy the graph to prevent changes to the original graph
    tempG = nx.DiGraph(g)
    muxList = [x for x in tempG.nodes if x.startswith('mux')]
    
    keyList = generate_key_list(len(muxList))
    print(keyList)

    looseNCount = 0
    looseNodes = []
    gateDict, muxDict = iDict
    for i, muxNode in enumerate(muxList):
        key = keyList[i]
        offNode = muxDict[muxNode][1-key]
        print(f"{offNode} -> {list(tempG.successors(offNode))}")
        
        # Can remove this line and check if offNode has only 1 out edge
        tempG.remove_edge(offNode, muxNode)
        
        if tempG.out_degree(offNode) == 0:
            looseNCount += 1
            looseNodes.append(offNode)

    
    print(looseNCount)
    print(looseNodes)

# Doesnt modify the graph and in doing so, it test each key independently unlike the above            
def saam2(g: nx.DiGraph, iDict: dict):
    # Deep Copy the graph to prevent changes to the original graph
    tempG = nx.DiGraph(g)
    muxList = [x for x in tempG.nodes if x.startswith('mux')]
    
    keyList = generate_key_list(len(muxList))
    print(keyList)

    looseNCount = 0
    looseNodes = []
    gateDict, muxDict = iDict
    for i in range(len(keyList)):
        key = keyList[i]
        muxNode = "mux_"+str(i)
        
        offNode = muxDict[muxNode][1-key]
        print(f"{offNode} -> {list(tempG.successors(offNode))}")
        
        # Can remove this line and check if offNode has only 1 out edge
        # tempG.remove_edge(offNode, muxNode)
        
        # offNode has only 1 out edge which is to the mux
        if tempG.out_degree(offNode) == 1:
            looseNCount += 1
            keyList[i] = 1 - keyList[i] # Invert the key
            looseNodes.append(offNode)
        else:
            keyList[i] = 'x'

    
    print(looseNCount)
    print(looseNodes)
    print(keyList)
    print(f"{(looseNCount*100/len(keyList)):.2f}% of keys resolved!")

G, infoDict = parse_ckt('gOut3.bench')
saam2(G, infoDict)