import os
import subprocess

def verify_bench_with_abc(bench_file, abc_path="C:\\Dev\\RS\\abcEXE\\abc10216.exe"):
    if not os.path.exists(bench_file):
        raise FileNotFoundError(f"Bench file not found: {bench_file}")

    commands = [
        f"read_bench {bench_file}",
    ]

    abc_input = "\n".join(commands) + "\nquit\n"

    result = subprocess.run(
        [abc_path],
        input=abc_input.encode(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    stdout = result.stdout.decode()
    stderr = result.stderr.decode()
    
    eMsg = 'Reading network from file has failed.'
    if eMsg in stdout or eMsg in stderr:
        print('Failed', bench_file)
    else:
        print('Pass', bench_file)
        return
    print("ABC Output:\n", stdout)
    print("ABC Errors:\n", stderr)
    print("--------------")

# for f in os.listdir('./data'):
#     if f.startswith('c1355_K64'):
#         bench = f"./data/{f}/{f.split('_D')[0]}.bench"
#         verify_bench_with_abc(bench)


for f in os.listdir('./Benchmarks'):
    if os.path.isfile('./Benchmarks/'+f):
        # if f != 'b.bench' and f != 'mid.bench':
        #     if f.startswith('b'):
        #         for k in [256, 512]:
        #             bench = f"./data-20/{f.split('.')[0]}_K{k}_DMUX/{f.split('.')[0]}_K{k}.bench"
        #             verify_bench_with_abc(bench)
        #             # break
        #         # break
        #     else:
        #         for k in [64, 128, 256]:
        #             if f.startswith('c13') and k == 256:
        #                 continue
        #             bench = f"./data-20/{f.split('.')[0]}_K{k}_DMUX/{f.split('.')[0]}_K{k}.bench"
        #             # print(f"{f.split('.')[0]}_K{k}_DMUX")
        #             verify_bench_with_abc(bench)
        verify_bench_with_abc('./Benchmarks/'+f)

verify_bench_with_abc("./b_K4.bench")