import re, random

def parse_io(bench_file_path):
    # Assuming one declaration per line
    pattern = re.compile(r"(?i)^\s*(INPUT|OUTPUT)\s*\(\s*(.*?)\s*\)\s*$")
    inputs = []
    outputs = []
    
    try:
        with open(bench_file_path, 'r') as file:
            for line in file:
                match = pattern.match(line.strip())
                if match:
                    if line.strip().lower().startswith('i'):
                        inputs.append(line.strip())
                    else:
                        outputs.append(line.strip())
                    
    except FileNotFoundError:
        print(f"Error: The file {bench_file_path} was not found.")
    except Exception as e:
        print(f"An error occurred: {e}")    
    
    return inputs, outputs


def parse_logic_op(bench_file_path):
    # Assuming one operation per line
    pattern = re.compile(r"^(\w+)\s*=\s*(\w+)\s*\(\s*(.*?)\s*\)\s*$")
    gates = []
    inWires = []
    outWires = []
    
    try:
        with open(bench_file_path, 'r') as file:
            for line in file:
                match = pattern.match(line.strip())
                if match:
                    gates.append(match.group(2))
                    inWires.append(match.group(3))
                    outWires.append(match.group(1))
                    
    except FileNotFoundError:
        print(f"Error: The file {bench_file_path} was not found.")
    except Exception as e:
        print(f"An error occurred: {e}")
    
    
    return gates, inWires, outWires 


class MuxGenerator:
    counter = 0
    
    @staticmethod
    def __unique_name(base):
        MuxGenerator.counter += 1
        return f"{base}{MuxGenerator.counter}"

    @staticmethod
    def generate_mux(select_wire, false_wire, locked_wire, key_val, prev_locked_wire):
        not_select = MuxGenerator.__unique_name("n") 
        select_0 = MuxGenerator.__unique_name("n") 
        select_1 = MuxGenerator.__unique_name("n")
        
        if key_val:
            input_0 = false_wire
            input_1 = locked_wire 
        else:
            input_0 = locked_wire 
            input_1 = false_wire
        
        mux_outWire = prev_locked_wire
        
        gates = ["NOT", "AND", "AND", "OR"]
        inWires = [f"{select_wire}", f"{input_0}, {not_select}", f"{input_1}, {select_wire}", f"{select_0}, {select_1}"]
        outWires = [f"{not_select}", f"{select_0}", f"{select_1}", f"{mux_outWire}"]

        return gates, inWires, outWires


def generate_key_list(key_size: int):
    # Assert key size as a multiple of two
    if key_size%2 != 0:
        raise ValueError("Key size should be a multiple of two")
    
    # random 1:1 combination of zeros and ones
    key_list = [0] * int(key_size/2) + [1] *int(key_size/2)
    # If odd keysize is also allowed this should work
    # key_list = [0] * int(key_size/2) + [1] * (key_size - int(key_size/2))
    random.shuffle(key_list)    
    return key_list


def generate_io(bench_file_path, key_size):
    io_bench_code = ""
    inputs, outputs = parse_io(bench_file_path) # Avoidable second visit to the bench file
    io_bench_code += "\n".join(inputs)
    
    io_bench_code += "\n"
    for i in range(key_size):
        io_bench_code += "INPUT(key_"+str(i)+")\n"
    
    io_bench_code += "\n"
    io_bench_code += "\n".join(outputs)
    io_bench_code += "\n\n"
    
    return io_bench_code


def insertMux(gates, inWires, outWires, selected_gate_ids, key_list):    
    key_idx = 0
    
    new_gates, new_inWires, new_outWires = [], [], []
    g_l = 0
    for i in range(0, len(selected_gate_ids), 2):
        idx1, idx2 = selected_gate_ids[i],selected_gate_ids[i+1]
        
        # Rename locked outWire
        prev_locked_wire = outWires[idx2]
        outWires[idx2] = outWires[idx2] + "_locked"
        
        # Generate Mux bench code
        mux_gates, mux_inWires, mux_outWires = MuxGenerator.generate_mux(
            f"key_{key_idx}", outWires[idx1], outWires[idx2], key_list[key_idx], prev_locked_wire)
        
        # Copy circuit content upto second selected gate    
        new_gates.extend(gates[g_l:idx2 + 1])
        new_inWires.extend(inWires[g_l:idx2 + 1])
        new_outWires.extend(outWires[g_l:idx2 + 1])
        
        # Insert Mux
        new_gates.extend(mux_gates)
        new_inWires.extend(mux_inWires)
        new_outWires.extend(mux_outWires)
        
        # Update left pointer and key index       
        g_l = idx2+1        
        key_idx += 1
    
    # Copy logic operations after the last randomly picked gate
    if g_l < len(gates):
        new_gates.extend(gates[g_l:])
        new_inWires.extend(inWires[g_l:])
        new_outWires.extend(outWires[g_l:])
        
    
    return new_gates, new_inWires, new_outWires


def write_bench_file(gates, inWires, outWires, key_size, src_bench_file_path, out_bench_file_path):
    try:
        with open(out_bench_file_path, "w") as file:
            # Insert input and output declarations
            file.write(generate_io(src_bench_file_path, key_size))
            
            # Insert logic operations
            for i in range(len(gates)):
                file.write(f"{outWires[i]} = {gates[i]}({inWires[i]})\n")
                
        print(f"Bench file successfully written to {out_bench_file_path}")
    except Exception as e:
        print(f"Error writing file: {e}")


def mux2_lock(bench_file_path, key_size, out_bench_file_path="output.bench"):
    # Generate key
    key_list = generate_key_list(key_size)
    print(key_list)
    
    # Extract gates and wires
    gates, inWires, outWires = parse_logic_op(bench_file_path)
    print(gates)
    
    # Assert key_size is not too big for the circuit
    if key_size*2 > len(gates):
        raise ValueError("Key size must be <= half of the number of gates")
    
    # Randomly select wires to be locked or be used as false wires
    selected_gate_ids = random.sample(range((len(gates))), key_size*2)
    selected_gate_ids.sort()
    print(selected_gate_ids)
    
    # Insert muxes in the circuit
    new_gates, new_inWires, new_outWires = insertMux(gates, inWires, outWires, selected_gate_ids, key_list)
    
    # Write updated circuit onto output bench file
    write_bench_file(new_gates, new_inWires, new_outWires, key_size, bench_file_path, out_bench_file_path)
    
    
keySize = 2 
mux2_lock("b.bench", keySize, "output.bench")