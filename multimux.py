import networkx as nx
from utils import gateVecDict, alter_gate
import sys, random

def ratio_gate_list(gate_composition: dict, len_multi_inputs:int):
    # Multi input gates in the whole original circuit
    multi_in_dist = [k_v for k_v in gate_composition.items() if k_v[0] not in {'not', 'buf', 'mux'}]
    multi_in_dist.sort(reverse=True, key=lambda k_v:k_v[1])
    (g1, c1), (g2, c2) = multi_in_dist[:2]

    # Construct list of gate type with ratio preserved
    total = c1 + c2
    n1 = round(len_multi_inputs * (c1/total))
    n2 = len_multi_inputs - n1
    result = [g1] * n1 + [g2] * n2
    random.shuffle(result)
    
    return result

def replace_gate(current_gate, gate_composition):
    """Replaces with gate with the most frequent and suitable gate to corrcupt funcitonality"""
    gate_input_map = {
        'xor': 2,
        'xnor': 2,
        'mux': 'many',
        'or': 'many',
        'and': 'many',
        'nand': 'many',
        'nor': 'many',
    }
    
    # Multi input gates in the whole original circuit in decreasing order of frequency
    multi_in_dist = [k_v for k_v in gate_composition.items() if k_v[0] not in {'not', 'buf', 'mux'}]
    multi_in_dist.sort(reverse=True, key=lambda k_v:k_v[1])
    
    current_gate = current_gate.lower()
    # Inputs to the gate to replaced
    num_inputs = gate_input_map[current_gate]
    
    for g, _ in multi_in_dist:
        if g == current_gate:
            continue  # must be different
        
        req = gate_input_map[g]

        # Case 1: current gate has 2 inputs
        if num_inputs == 2:
            # can replace with ANY gate (2-input OR many-input)
            return g

        # Case 2: current gate has > 2 inputs
        else:
            # only replace with a many-input type
            if req == 'many':
                return g
    raise Exception(f'Gate type could not be replaced by any other gate type. Gate: {current_gate}')

def neiSplit(G: nx.DiGraph, u:str, v:str, h:int, key_list: list[int], k_c:int, dumpFiles=False, alt_percent:float=0.5, getFileDump=None, gate_composition=None):
    if dumpFiles:
        global feat, cell, count, ML_count, link_train, link_test, link_test_n
        ML_count, feat, cell, count, link_train, link_test, link_test_n = getFileDump()
        
    nei_u = set(nx.ego_graph(G, u, radius=h, undirected=True).nodes)
    nei_v = set(nx.ego_graph(G, v, radius=h, undirected=True).nodes) 

    # Exclude inputs(includes keyinpus by default) and MUXs as MuxLink inherently would not 'see' them 
    # (prevents from locking outedges of inputs and encolsing subgraph region resembles MuxLink's exactly)
    region = G.subgraph(nei_u.union(nei_v)).copy()
    inps_and_muxes = [q for q in region.nodes if region.nodes[q]['type'] == "input" or region.nodes[q]['type'] == "mux"]
    region.remove_nodes_from(inps_and_muxes)
    
    lkd = {(u,v)}
    mux_outs = {v}
    visited = {u}
    curr_level = {u}
    
    # Remove u - a first step to separate u-side nodes from v-side nodes
    nei_v_g = region.subgraph(nei_v).copy()
    nei_v_g.remove_nodes_from(curr_level)
    
    lvl = 1
    while lvl <= h:
        # Traverse one hop on from the current level
        new_level = set()
        for n in curr_level:
            imm_nei = set(nx.ego_graph(region, n, radius=1, undirected=True).nodes)
            # Avoid traversing to where the mux is going to be inserted (determined to be on v-side already)
            imm_nei.difference_update(mux_outs)
            # Avoid already visited nodes in the new level (at this moment, visited also includes the curr_level nodes)
            imm_nei.difference_update(visited)
            # Avoid inputs (instead shared with the true ckt after stitiching; adding fakes inputs is useless as inputs are removed in MuxLink)
            imm_nei = {nd for nd in imm_nei if G.nodes[nd]['type'] != "input"}
            new_level.update(imm_nei)
        curr_level = new_level
        visited.update(curr_level)
        
        # Identify the new neighbourhood of v
        nei_v_g.remove_nodes_from(curr_level)
        # might consider removing the ancestors of the curr level nodes -- think it thru tho
        new_nei_v = set(nx.ego_graph(nei_v_g, v, radius=h, undirected=True).nodes)
        
        # Identify edges pointing from curr_level to the new nei of v
        for n in curr_level:
            v_side_nodes = set(G.successors(n)).intersection(new_nei_v)
            lkd.update((n, b) for b in v_side_nodes)
            mux_outs.update(v_side_nodes)
        
        # print(curr_level)
        # Increment hop level
        lvl += 1    
    
    nodeTag = "_sub_"+v
    mapping = {}
    for n in visited:
        if "isKey" in G.nodes[n]:
            # Prevent postprocessing from picking this as real keyinput
            mapping[n] = n.replace("keyinput", "key_input")+nodeTag
            print(f'Warning: A Primary Input ({n}) found in visited of {u} -> {v} enclosing subgraph.')
        else:                
            mapping[n] = n+nodeTag
    
    # Alter gates based on set percent
    # num_alted_gates = int(len(visited)*alt_percent)
    # altArr = [True] * num_alted_gates + [False]* (len(visited) - num_alted_gates)
    # random.shuffle(altArr)
    altCounter = 0
    
    # Alter gate based on the ratio of the two most frequent multi-input gates in the circuit
    multi_in_gates = [mapping[gate] for gate in visited if G.in_degree(gate) > 1] # Multi input gates in the neibourhood of u in the encolsing subgraph
    # gateTypeArr = ratio_gate_list(gate_composition, len(multi_in_gates))

    # relabeled_region = nx.relabel_nodes(region, mapping) 
    visited_region = G.subgraph(visited).copy()
    subG = nx.relabel_nodes(visited_region, mapping)
    for node in subG.nodes:
        # Skip non-replicated nodes (aka non-visited) / using mapping values since we relabelled visited nodes
        if not node in mapping.values():
            continue
        
        if subG.nodes[node]['type'] == "input":
            subG.nodes[node].clear()
            subG.nodes[node].update({"type": "input", "isArt": True})
            print('Warning: This should not have happend (investigation advised!). ', node, 'is a fake input')
        else:
            # Alter gates based on ratio if they are multi_inputs otherwise dont alter
            if node in multi_in_gates:
                artNodeGate = replace_gate(subG.nodes[node]['gate'], gate_composition)
                # artNodeGate = gateTypeArr[altCounter]
                # altCounter += 1 # When using gate_composition
            else:
                artNodeGate = subG.nodes[node]['gate']  
            # Alter gates based on set percent 
            # if altArr[altCounter]:
            #     artNodeGate = alter_gate(subG.nodes[node]['gate'])
            # else:
            #     artNodeGate = subG.nodes[node]['gate']   
            
            if artNodeGate.upper() == "MUX":  
                # Only runs if if haven't altered gate and gate is MUX             
                mDict = {}
                for k,val in subG.nodes[node]['muxDict'].items():
                    if k == "key":
                        mDict["key"] = val.replace("keyinput", "key_input")+nodeTag
                    else:
                        mDict[k] = val+nodeTag
                        
                subG.nodes[node].clear()
                subG.nodes[node].update({"type": "mux", "isArt": True, "gate": artNodeGate, "muxDict": mDict})
                    
            else:
                subG.nodes[node].clear()
                subG.nodes[node].update({"type": "gate", "isArt": True, "gate": artNodeGate})
        
                if dumpFiles:
                    subG.nodes[node]['count'] = ML_count    
                    feat += f"{' '.join([str(x) for x in gateVecDict[artNodeGate.lower()]])}\n"
                    cell += f"{ML_count} assign for output {node}\n"
                    count += f"{ML_count}\n"
                    ML_count+=1
        
        #altCounter += 1 #When using alt_percent
            
    # Add new replicated edges to the link_train
    if dumpFiles:
        for a, b in subG.edges:
            # Filter only replicated nodes (aka non-visited) / using mapping values since we relabelled visited nodes
            if a in mapping.values() or b in mapping.values():
                if 'count' in subG.nodes[a].keys() and 'count' in subG.nodes[b].keys():
                    link_train += f"{subG.nodes[a]['count']} {subG.nodes[b]['count']}\n"

    # Merge the subgraph into the original graph G
    G.add_nodes_from(subG.nodes(data=True))
    G.add_edges_from(subG.edges(data=True))

    # Stitch subgraph and add stiching edges to link_train
    for n in visited:
        if n not in mapping.keys():
            continue
        for pred in G.predecessors(n):
            if pred not in visited:
                fake_n = mapping[n]
                G.add_edge(pred, fake_n)
                if dumpFiles:
                    if 'count' in G.nodes[pred].keys() and 'count' in G.nodes[fake_n].keys():
                        link_train += f"{G.nodes[pred]['count']} {G.nodes[fake_n]['count']}\n"
    
    print(len(lkd))
    # Insert muxes
    m_c = 2 # Add count num on the extra muxes' names
    for a, b in lkd:
        fake_a = mapping[a]
        G.remove_edge(a, b)
        # G.remove_edge(fake_a, b) # There should be no outedge from the fake nodes if we are coping them first 
        muxName = b + "_m1" + "_from_mux"
        if not (a == u and b == v): # name overwritten for the extra muxes
            muxName = b + "_m" + str(m_c) + "_from_mux"
            m_c += 1
        G.add_edge(muxName, b)
        G.nodes[muxName]['type'] = 'mux'
        G.nodes[muxName]['gate'] = 'MUX'
        
                
        G.add_edge(a, muxName)        
        G.add_edge(fake_a, muxName)  
        
        keyNode = 'keyinput' + str(k_c)
        G.add_node(keyNode, type='input', isKey=True)      
        G.add_edge(keyNode, muxName)
        
        
        
        if dumpFiles:
            try:
                link_train = link_train.replace(f"{G.nodes[a]['count']} {G.nodes[b]['count']}\n", "")
                link_train = link_train.replace(f"{G.nodes[fake_a]['count']} {G.nodes[b]['count']}\n", "")
                link_test += f"{G.nodes[a]['count']} {G.nodes[b]['count']}\n"
                link_test_n += f"{G.nodes[fake_a]['count']} {G.nodes[b]['count']}\n"
            except Exception as err:
                print("Error trying to insert mux from ", a, "to", b)
                sys.exit()

              
        # update the muxDict
        if key_list[k_c] == 0:
            input0 = a
            input1 = fake_a
        else:
            input0 = fake_a
            input1 = a

        G.nodes[muxName]['muxDict'] = {"key": keyNode, 0: input0 , 1: input1}
        k_c += 1
    
    # return the next key count and files data
    if dumpFiles:
        data = {
            "feat" : feat,
            "cell" : cell,
            "count" : count,
            "ML_count" : ML_count,
            "link_train" : link_train,
            "link_test" : link_test,
            "link_test_n" : link_test_n
        }    
    else:
        data = {}
    
    return k_c, data, lkd