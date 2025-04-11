import matplotlib.pyplot as plt
import numpy as np
import matplotlib.gridspec as gridspec
import pandas as pd

df = pd.read_csv('eval.csv')

c_df = df[df['Bench'].str.startswith('c')]

categories = ['c1355', 'c1908', 'c2670', 'c3540', 'c5315', 'c6288', 'c7552']
metrics = ['AC', 'PC', "KPA"]
values_64 = [[0 for _ in categories] for _ in metrics]
values_128 = [[0 for _ in categories] for _ in metrics]
values_256 = [[0 for _ in categories] for _ in metrics]

minVal = 1
for index, row in c_df.iterrows():
    idx = categories.index(row['Bench'])
    if row[' Key Size'] == 64:
        values_64[0][idx] = row[' Acc']
        values_64[1][idx] = row[' Prec']
        values_64[2][idx] = row[' KPA']
        minVal = min(minVal, *values_64[0], *values_64[1], *values_64[2])
    elif row[' Key Size'] == 128:
        values_128[0][idx] = row[' Acc']
        values_128[1][idx] = row[' Prec']
        values_128[2][idx] = row[' KPA']
        minVal = min(minVal, *values_128[0], *values_128[1], *values_128[2])
    else:
        values_256[0][idx] = row[' Acc']
        values_256[1][idx] = row[' Prec']
        values_256[2][idx] = row[' KPA']
        minVal = min(minVal, *values_256[0], *values_256[1], *values_256[2])
print(minVal)
print(values_64)
x = np.arange(len(categories))


fig = plt.figure(figsize=(10, 12))
gs = gridspec.GridSpec(3, 1, height_ratios=[1, 1, 1])

def plot_subplot(ax, idx):
    width = 0.25
    bars1 = ax.bar(x - width, values_64[idx], width, label='K=64', color='#326462')
    bars2 = ax.bar(x , values_128[idx], width, label='K=128', color='#9CC3B7')
    bars3 = ax.bar(x + width, values_256[idx], width, label='K=256', color='#ECD9AA')
    
    # ax.set_title(title)
    ax.set_ylim([0.4, 1.08])
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
    for bars in [bars1, bars2, bars3]:
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
