"""A small 14-day chart per KPI, sent as a photo. Optional: needs matplotlib."""
import io


def render(result):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    days = [d for d, _ in result.history]
    values = [v for _, v in result.history]
    fig, ax = plt.subplots(figsize=(6, 2.4), dpi=150)
    ax.plot(days, [v if v is not None else float('nan') for v in values], color='#2563eb', linewidth=2, marker='o',
            markersize=3)
    if values and values[-1] is not None:
        ax.annotate(f'{values[-1]:,.{result.kpi.decimals}f}'.replace(',', ' '), (days[-1], values[-1]),
                    textcoords='offset points', xytext=(0, 8), ha='center', fontsize=8)
    for limit in (result.kpi.alert_below, result.kpi.alert_above):
        if limit is not None:
            ax.axhline(limit, color='#dc2626', linewidth=1, linestyle='--')
    ax.set_title(result.kpi.name + ', last 14 days', fontsize=10, loc='left')
    ax.spines[['top', 'right']].set_visible(False)
    ax.tick_params(labelsize=7)
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter('%d %b'))
    fig.tight_layout()
    buffer = io.BytesIO()
    fig.savefig(buffer, format='png')
    plt.close(fig)
    return buffer.getvalue()
