"""Reads kpibot.toml. Each [[kpi]] is a SQL query returning one row per day: (day, value)."""
import os
import tomllib
from dataclasses import dataclass, field


@dataclass
class Kpi:
    name: str
    sql: str
    unit: str = ''            # 'R', '%', or a word like 'audits'
    decimals: int = 0
    higher_is_better: bool = True
    alert_below: float | None = None
    alert_above: float | None = None
    chart: bool = False


@dataclass
class Config:
    title: str
    database_url: str
    chat_ids: list
    kpis: list = field(default_factory=list)
    timezone_offset_hours: int = 2
    send_at: str = '07:30'
    token_env: str = 'TELEGRAM_BOT_TOKEN'


def load(path):
    with open(path, 'rb') as f:
        raw = tomllib.load(f)
    db = raw['database']['url']
    # Secrets (the bot token, database passwords) come from the environment so this file can live in git
    return Config(
        title=raw.get('title', 'Daily KPIs'),
        database_url=os.path.expandvars(db),
        chat_ids=[str(c) for c in raw['telegram']['chat_ids']],
        kpis=[Kpi(**k) for k in raw.get('kpi', [])],
        timezone_offset_hours=raw.get('schedule', {}).get('timezone_offset_hours', 2),
        send_at=raw.get('schedule', {}).get('send_at', '07:30'),
        token_env=raw['telegram'].get('token_env', 'TELEGRAM_BOT_TOKEN'),
    )
