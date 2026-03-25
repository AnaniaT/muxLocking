
bench = 'c2670_K64'
with open(f"./data/{bench}_DMUX/{bench}.bench") as file:
    locked_f = file.read()
    trueKey = locked_f.strip().splitlines()[0].replace('#key=','')
    
with open(f"./data/{bench}_clean/key_variant_1.txt") as file:
    locked_f = file.read()
    keyV1 = locked_f.strip().splitlines()[0]
    
with open(f"./data/{bench}_clean/key_variant_2.txt") as file:
    locked_f = file.read()
    keyV2 = locked_f.strip().splitlines()[0]
 

K_correct = K_incorrect = K_X = 0
K_correct2 = K_incorrect2 = K_X2 = 0
K_total = len(trueKey)

for i in range(K_total):
    if trueKey[i] == keyV1[i]:
        K_correct+=1
    elif keyV1[i] == "X":
        K_X+=1
    else:
        K_incorrect+=1
        
    if trueKey[i] == keyV2[i]:
        K_correct2+=1
    elif keyV2[i] == "X":
        K_X2+=1
    else:
        K_incorrect2+=1
        
# Compute metrics safely
print('Version 1')
denom = (K_total - K_X) if (K_total - K_X) > 0 else print('Denominator is zero for key var 1')
KPA = 100 * K_correct / denom
AC  = 100 * K_correct / K_total
PC  = 100 * (K_correct + K_X) / K_total

print( {
    "K_correct": K_correct,
    "K_incorrect": K_incorrect,
    "K_X": K_X,
    "K_total": K_total,
    "KPA (%)": round(KPA, 2),
    "AC (%)": round(AC, 2),
    "PC (%)": round(PC, 2)
})
print(bench.split('_')[0], bench.split('_')[1], AC/100, PC/100, KPA/100)        
# Compute metrics safely
print('Version 2')
denom = (K_total - K_X2) if (K_total - K_X2) > 0 else print('Denominator is zero for key var 2')
KPA = 100 * K_correct2 / denom
AC  = 100 * K_correct2 / K_total
PC  = 100 * (K_correct2 + K_X2) / K_total

print( {
    "K_correct": K_correct2,
    "K_incorrect": K_incorrect2,
    "K_X": K_X2,
    "K_total": K_total,
    "KPA (%)": round(KPA, 2),
    "AC (%)": round(AC, 2),
    "PC (%)": round(PC, 2)
})
print(bench.split('_')[0], bench.split('_')[1], AC/100, PC/100, KPA/100)        

