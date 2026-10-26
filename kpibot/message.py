"""Turns KPI results into a Telegram message (HTML parse mode)."""
import html

TELEGRAM_LIMIT = 4096


def fmt_value(value, kpi):
    if value is None:
        return 'n/a'
    number = format(value, ',.%df' % kpi.decimals).replace(',', ' ')
    if kpi.unit == 'R':
        return 'R ' + number
    if kpi.unit == '%':
        return number + '%'
    return '%s %s' % (number, kpi.unit) if kpi.unit else number


def fmt_change(pct, kpi):
    if pct is None:
        return ''
    arrow = '▲' if pct > 0 else '▼' if pct < 0 else '▶'
    good = (pct > 0) == kpi.higher_is_better or pct == 0
    # Telegram can't colour text, so the marker has to carry the meaning
    return '%s %+.1f%%%s' % (arrow, pct, '' if good else ' ⚠')


def build(title, results, report_day):
    alerts = [r for r in results if r.alert]
    lines = ['<b>%s</b>' % html.escape(title), report_day.strftime('%A %d %B %Y'), '']

    if alerts:
        lines.append('<b>Needs attention</b>')
        for r in alerts:
            lines.append('• %s: %s' % (html.escape(r.kpi.name), html.escape(r.alert)))
        lines.append('')

    for r in results:
        name = html.escape(r.kpi.name)
        if r.error:
            lines.append('<b>%s</b>  <i>could not be calculated</i>' % name)
            continue
        line = '<b>%s</b>  %s' % (name, html.escape(fmt_value(r.value, r.kpi)))
        day = fmt_change(r.change_pct, r.kpi)
        week = fmt_change(r.week_change_pct, r.kpi)
        detail = '   '.join(p for p in (day and 'vs yesterday ' + day, week and 'vs last week ' + week) if p)
        lines.append(line)
        if detail:
            lines.append('<code>  %s</code>' % detail)

    return '\n'.join(lines).strip()


def split(text, limit=TELEGRAM_LIMIT):
    """Splits on line breaks so no message is over Telegram's limit and no HTML tag is cut in half."""
    if len(text) <= limit:
        return [text]
    parts, current = [], ''
    for line in text.split('\n'):
        if len(line) > limit:
            line = line[:limit - 1] + '…'
        if len(current) + len(line) + 1 > limit:
            parts.append(current.rstrip('\n'))
            current = ''
        current += line + '\n'
    if current.strip():
        parts.append(current.rstrip('\n'))
    return parts
