import matplotlib
matplotlib.rcParams['pdf.fonttype'] = 42
matplotlib.rcParams['ps.fonttype'] = 42

import matplotlib.pyplot as plt
import numpy as np
import matplotlib.gridspec as gridspec
import pandas as pd

df = pd.read_csv('eval.csv')

c_df = df[df['Bench'].str.startswith('c')]

categories = ['c1355', 'c1908', 'c2670', 'c3540', 'c5315', 'c6288']
metrics = ['AC', 'PC', "KPA"]
values_64 = [[0 for _ in categories] for _ in metrics]
values_128 = [[0 for _ in categories] for _ in metrics]
# values_256 = [[0 for _ in categories] for _ in metrics]

dmux_values_64 = [
  # AC
  [1.00, 0.82, 0.93, 0.90, 0.98, 0.97],
  # PC
  [1.00, 0.83, 0.93, 0.90, 0.98, 1.00],
  # KPA
  [1.00, 0.83, 0.93, 0.90, 0.98, 1.00]
]

dmux_values_128 = [
  # AC
  [0.91, 0.93, 0.94, 0.90, 0.95, 1.00],
  # PC
  [0.94, 0.94, 0.94, 0.90, 0.95, 1.00],
  # KPA
  [0.94, 0.94, 0.94, 0.90, 0.95, 1.00]
]

simLL_values_64 = [
  # AC (Accuracy)
  [0.546, np.nan, 0.797, 0.625, 0.687, 0.609],

  # PC (Precision)
  [0.671, np.nan, 0.843, 0.641, 0.718, 0.781],

  # KPA
  [0.625, np.nan, 0.836, 0.635, 0.709, 0.736]
]
# simLL_values_64 = [
#   # AC (Accuracy)
#   [0.453, np.nan, 0.703, 0.625, 0.594, 0.609],

#   # PC (Precision)
#   [0.578, np.nan, 0.734, 0.641, 0.625, 0.781],

#   # KPA
#   [0.518, np.nan, 0.726, 0.635, 0.613, 0.736]
# ]

# --- compute minVal including DMUX values as well ---
minVal = min(
    min(min(row) for row in dmux_values_64),
    min(min(row) for row in dmux_values_128),
)

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
        print("Error")

print(minVal)
print(values_64)

x = np.arange(len(categories))

fig = plt.figure(figsize=(10, 12))
gs = gridspec.GridSpec(3, 1, height_ratios=[1, 1, 1])

def plot_subplot(ax, idx):
    # 4 bars per category
    width = 0.15
    # width = 0.18
    # width = 0.22

    dmux64  = dmux_values_64[idx]
    simLL64 = simLL_values_64[idx]
    data64  = values_64[idx]
    dmux128 = dmux_values_128[idx]
    data128 = values_128[idx]

    # Key=64 → hatched; Key=128 → solid
    # DMUX vs Data → contrasting colors
    bars1 = ax.bar(
        x - 2*width, dmux64, width,
        label='DMUX (K=64)',
        color='#1f77b4', hatch='//', edgecolor='black'
    )
    bars1b = ax.bar(   # ← NEW simLL bar
        x - 1*width, simLL64, width,
        label='simLL (K=64)',
        color='#2ca02c', hatch='//', edgecolor='black'
    )
    bars2 = ax.bar(
        x - 0*width, data64, width,
        label='Proposed (K=64)',
        color='#ff7f0e', hatch='//', edgecolor='black'
    )
    bars3 = ax.bar(
        x + 1*width, dmux128, width,
        label='DMUX (K=128)',
        color='#1f77b4', edgecolor='black'
    )
    bars4 = ax.bar(
        x + 2*width, data128, width,
        label='Proposed (K=128)',
        color='#ff7f0e', edgecolor='black'
    )

    ax.set_ylim([minVal, 1.08])
    ax.set_xticks(x)
    ax.set_ylabel(metrics[idx], fontsize='large')

    if idx == len(metrics) - 1:
        ax.set_xticklabels(categories, fontsize='large')
    else:
        ax.set_xticklabels([])

    if idx == 0:
        # One legend for all four bar types
        handles = [bars1[0], bars1b[0], bars2[0], bars3[0], bars4[0]]
        labels = ['DMUX (K=64)', 'SimLL (K=64)', 'Proposed (K=64)', 'DMUX (K=128)', 'Proposed (K=128)']
        ax.legend(
            handles, labels,
            loc='upper center',
            bbox_to_anchor=(0.5, 1.70),
            # bbox_to_anchor=(0.5, 1.25),
            ncol=4,
            frameon=True,
            fancybox=True,
            shadow=False,
            borderpad=0.8,
            # fontsize='large',
            title_fontsize='medium',
            # handlelength=1.2,
            # handleheight=1.2,
            # handletextpad=0.5
        )

    # Add bar labels
    for bars in [bars1, bars1b, bars2, bars3, bars4]:
        for bar in bars:
            height = bar.get_height()
            if np.isnan(height):
                print('ds')
                ax.text(
                    x[1] - width,   # simLL bar position
                    minVal + 0.05,
                    'N/A',
                    ha='center',
                    va='bottom',
                    rotation=90
                )
                continue
            ax.annotate(
                f'{height:.2f}',
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3),
                textcoords="offset points",
                ha='center', va='bottom',
                rotation=90
            )

# Plot three identical subplots (AC, PC, KPA)
for i in range(len(metrics)):
    ax = fig.add_subplot(gs[i])
    ax.grid(axis='y', linestyle='--', alpha=0.4)
    ax.set_axisbelow(True)
    ax.axhline(0)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['bottom'].set_visible(False)
    plot_subplot(ax, i)
    

plt.tight_layout()
plt.subplots_adjust(top=0.85, hspace=0.35)
plt.show()
