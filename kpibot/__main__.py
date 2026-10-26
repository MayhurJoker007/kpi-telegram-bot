"""
python -m kpibot kpibot.toml --dry-run              print the message instead of sending it
python -m kpibot kpibot.toml                        send the report for yesterday
python -m kpibot kpibot.toml --day 2026-10-12       report on a specific day (resending a missed report)
python -m kpibot kpibot.toml --daemon               stay running and send every day at send_at
"""
import argparse
import logging
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone

from . import config, message, metrics

log = logging.getLogger('kpibot')


def local_now(offset_hours):
    return datetime.now(timezone(timedelta(hours=offset_hours)))


def run_once(cfg, report_day, dry_run=False, telegram=None):
    conn = metrics.connect(cfg.database_url)
    try:
        results = metrics.collect(conn, cfg.kpis, report_day)
    finally:
        conn.close()
    text = message.build(cfg.title, results, report_day)

    if dry_run:
        print(text)
        return results

    if telegram is None:
        from .telegram import Telegram
        token = os.environ.get(cfg.token_env)
        if not token:
            raise SystemExit('%s is not set' % cfg.token_env)
        telegram = Telegram(token)

    charts = []
    for r in results:
        if r.kpi.chart and r.history and not r.error:
            from . import chart
            charts.append(chart.render(r))

    for chat in cfg.chat_ids:
        for part in message.split(text):
            telegram.send_message(chat, part)
        for png in charts:
            telegram.send_photo(chat, png)
    log.info('sent report for %s to %d chat(s)', report_day, len(cfg.chat_ids))
    return results


def seconds_until(send_at, now):
    hour, minute = map(int, send_at.split(':'))
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    p = argparse.ArgumentParser(prog='kpibot')
    p.add_argument('config')
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--day', type=date.fromisoformat)
    p.add_argument('--daemon', action='store_true')
    args = p.parse_args()
    cfg = config.load(args.config)
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    if not args.daemon:
        day = args.day or (local_now(cfg.timezone_offset_hours).date() - timedelta(days=1))
        run_once(cfg, day, args.dry_run)
        return

    while True:
        wait = seconds_until(cfg.send_at, local_now(cfg.timezone_offset_hours))
        log.info('next report in %.0f minutes', wait / 60)
        time.sleep(wait)
        day = local_now(cfg.timezone_offset_hours).date() - timedelta(days=1)
        try:
            run_once(cfg, day, args.dry_run)
        except Exception:
            log.exception('report for %s failed', day)


if __name__ == '__main__':
    main()
