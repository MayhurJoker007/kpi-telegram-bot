"""Runs the KPI queries and works out yesterday's value, the change and the 7-day comparison."""
import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from urllib.parse import urlparse


@dataclass
class KpiResult:
    kpi: object
    day: date
    value: float | None
    previous: float | None          # the day before
    same_day_last_week: float | None
    history: list                    # (day, value) for the last 14 days, oldest first
    error: str | None = None

    @property
    def change_pct(self):
        return _pct(self.value, self.previous)

    @property
    def week_change_pct(self):
        return _pct(self.value, self.same_day_last_week)

    @property
    def alert(self):
        if self.error:
            return 'query failed'
        if self.value is None:
            return 'no data'
        k = self.kpi
        if k.alert_below is not None and self.value < k.alert_below:
            return 'below %s' % _num(k.alert_below, k)
        if k.alert_above is not None and self.value > k.alert_above:
            return 'above %s' % _num(k.alert_above, k)
        return None


def _pct(a, b):
    if a is None or b in (None, 0):
        return None
    return round(100 * (a - b) / abs(b), 1)


def _num(v, kpi):
    return format(v, ',.%df' % kpi.decimals).replace(',', ' ')


def connect(url):
    """sqlite:///path or postgresql://... (Postgres needs psycopg installed)."""
    if url.startswith('sqlite:///'):
        return sqlite3.connect(url[len('sqlite:///'):])
    if urlparse(url).scheme.startswith('postgres'):
        import psycopg
        return psycopg.connect(url.replace('postgresql+psycopg://', 'postgresql://'))
    raise ValueError('unsupported database url: %s' % url)


def collect(conn, kpis, report_day):
    """report_day is the day being reported on, normally yesterday."""
    start = report_day - timedelta(days=13)
    results = []
    for kpi in kpis:
        try:
            cur = conn.cursor()
            cur.execute(kpi.sql, {'start': start.isoformat(), 'end': report_day.isoformat()})
            rows = {(_as_date(d)): (float(v) if v is not None else None) for d, v in cur.fetchall()}
        except Exception as e:      # one broken query shouldn't stop the whole report
            if hasattr(conn, 'rollback'):
                conn.rollback()
            results.append(KpiResult(kpi, report_day, None, None, None, [], error=str(e).splitlines()[0]))
            continue
        history = [(start + timedelta(days=i), rows.get(start + timedelta(days=i))) for i in range(14)]
        results.append(KpiResult(
            kpi, report_day,
            value=rows.get(report_day),
            previous=rows.get(report_day - timedelta(days=1)),
            same_day_last_week=rows.get(report_day - timedelta(days=7)),
            history=history,
        ))
    return results


def _as_date(d):
    return d if isinstance(d, date) else date.fromisoformat(str(d)[:10])
