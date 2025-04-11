import matplotlib.pyplot as plt
import numpy as np
import matplotlib.gridspec as gridspec
import pandas as pd

# Data
df = pd.read_csv('eval.csv')

b_df = df[df['Bench'].str.startswith('b')]
c_df = df[df['Bench'].str.startswith('c')]

categories = ['b14_C', 'b15_C', 'b20_C', 'b21_C', 'b22_C', 'b17_C']
metrics = ['AC', 'PC', "KPA"]
values_256 = [[0 for _ in categories] for _ in metrics]
values_512 = [[0 for _ in categories] for _ in metrics]

for index, row in b_df.iterrows():
    idx = categories.index(row['Bench'])
    if row[' Key Size'] == 256:
        values_256[0][idx] = row[' Acc']
        values_256[1][idx] = row[' Prec']
        values_256[2][idx] = row[' KPA']
    else:
        values_512[0][idx] = row[' Acc']
        values_512[1][idx] = row[' Prec']
        values_512[2][idx] = row[' KPA']

x = np.arange(len(categories))
width = 0.35

fig = plt.figure(figsize=(10, 12))
gs = gridspec.GridSpec(3, 1, height_ratios=[1, 1, 1])

def plot_subplot(ax, idx):
    bars1 = ax.bar(x - width/2, values_256[idx], width, label='K=256', color='#ECD9AA')
    bars2 = ax.bar(x + width/2, values_512[idx], width, label='K=512', color='#DC8942')
    
    ax.set_ylim([0.88, 1.02])
    ax.set_xticks(x)
    ax.set_ylabel(metrics[idx])
    if idx == len(metrics)-1:
        ax.set_xticklabels(categories)
    else:
        ax.set_xticklabels([])
    
    if idx == 0:
        ax.legend(
            loc='upper center',
            bbox_to_anchor=(0.5, 1.15),
            ncol=4,
            frameon=True,
            fancybox=True,
            shadow=False,
            borderpad=0.8,
            fontsize='large',
            title_fontsize='medium',
            handlelength=1.2,
            handleheight=1.2,
            handletextpad=0.5
        )

    # Add bar labels
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            ax.annotate(f'{height:.3f}',
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3),
                        textcoords="offset points",
                        ha='center', va='bottom')

# Plot three identical subplots
for i in range(len(metrics)):
    ax = fig.add_subplot(gs[i])
    plot_subplot(ax, i)

plt.tight_layout()
plt.show()
