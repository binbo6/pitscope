"""Optional scientific figure dependency: pip install matplotlib."""
import json
from pathlib import Path


def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    root=Path(__file__).resolve().parents[1]
    data=json.loads((root/'examples/output/summary.json').read_text(encoding='utf-8'))
    plt.rcParams['svg.fonttype']='none'
    fig,axes=plt.subplots(1,2,figsize=(12,4.3),dpi=160)
    for ax,key,metric,title,limit,color in zip(axes,['ground','bottom'],['max_downward_mm','max_upward_mm'],
        ['Maximum ground settlement','Maximum bottom uplift'],[20,10],['#ae7935','#24634f']):
        values=[s['regions'][key][metric] for s in data['stages']]
        ax.plot(range(4),values,color=color,linewidth=2.5,marker='o')
        ax.fill_between(range(4),values,color=color,alpha=.06)
        ax.axhline(limit,color='#7a8982',linestyle='--',linewidth=1.3)
        for i,v in enumerate(values):ax.annotate(f'{v:.1f}',(i,v),xytext=(0,9),textcoords='offset points',ha='center',color=color)
        ax.set_title(title,loc='left',fontweight='bold',color='#173f35',pad=18)
        ax.set_xticks(range(4),['S1 / 4m','S2 / 8m','S3 / 12m','S4 / 15.7m'])
        ax.set_ylim(0,max(max(values),limit)*1.35)
        ax.set_ylabel('Cumulative displacement (mm)')
        ax.text(.02,.94,f'Synthetic comparison threshold: {limit} mm',transform=ax.transAxes,color='#7a8982',va='top',fontsize=9)
        ax.grid(axis='y',linestyle=':',alpha=.3);ax.set_axisbelow(True)
        for side in ['top','right']:ax.spines[side].set_visible(False)
    fig.suptitle('Four-stage reproducible example | synthetic data, not field measurements',fontsize=11,color='#647d72')
    fig.tight_layout(pad=2)
    folder=root/'docs/images';folder.mkdir(parents=True,exist_ok=True)
    fig.savefig(folder/'case-trend.svg',bbox_inches='tight',facecolor='white')
    path=folder/'case-trend.svg'
    path.write_text('\n'.join(line.rstrip() for line in path.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')
    plt.close(fig)


if __name__=='__main__':main()
