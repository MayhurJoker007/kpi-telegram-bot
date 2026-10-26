import sqlite3
from datetime import date, datetime, timedelta, timezone

import pytest

from kpibot import message, metrics
from kpibot.__main__ import run_once, seconds_until
from kpibot.config import Config, Kpi
from kpibot.telegram import Telegram, TelegramError

DAY = date(2026, 10, 13)


@pytest.fixture
def conn():
    c = sqlite3.connect(':memory:')
    c.execute('create table sales (day text, amount real)')
    rows = {DAY: 1200, DAY - timedelta(days=1): 1000, DAY - timedelta(days=7): 1500, DAY - timedelta(days=3): 900}
    c.executemany('insert into sales values (?, ?)', [(d.isoformat(), v) for d, v in rows.items()])
    c.commit()   # collect() rolls back after a failed query, which would otherwise wipe uncommitted fixtures
    return c


SALES = Kpi(name='Sales', unit='R', sql='select day, sum(amount) from sales where day between :start and :end group by day')


def test_day_and_week_comparisons(conn):
    r = metrics.collect(conn, [SALES], DAY)[0]
    assert r.value == 1200
    assert r.change_pct == 20.0
    assert r.week_change_pct == -20.0
    assert len(r.history) == 14 and r.history[-1] == (DAY, 1200)
    assert r.history[0][1] is None                      # missing days stay visible as gaps


def test_alerts():
    low = Kpi(name='Audits', alert_below=40, sql='')
    high = Kpi(name='Cancels', unit='%', decimals=1, alert_above=15, higher_is_better=False, sql='')
    assert metrics.KpiResult(low, DAY, 31, None, None, []).alert == 'below 40'
    assert metrics.KpiResult(low, DAY, 41, None, None, []).alert is None
    assert metrics.KpiResult(high, DAY, 15.5, None, None, []).alert == 'above 15.0'
    assert metrics.KpiResult(low, DAY, None, None, None, []).alert == 'no data'


def test_a_broken_query_does_not_stop_the_report(conn):
    broken = Kpi(name='Broken', sql='select nope from nowhere')
    results = metrics.collect(conn, [broken, SALES], DAY)
    assert results[0].error and results[0].alert == 'query failed'
    assert results[1].value == 1200
    text = message.build('Daily', results, DAY)
    assert '<b>Broken</b>  <i>could not be calculated</i>' in text


def test_formatting():
    assert message.fmt_value(1234567.891, Kpi(name='x', unit='R', sql='')) == 'R 1 234 568'
    assert message.fmt_value(87.25, Kpi(name='x', unit='%', decimals=1, sql='')) == '87.2%'
    assert message.fmt_value(31, Kpi(name='x', unit='audits', sql='')) == '31 audits'
    assert message.fmt_value(None, Kpi(name='x', sql='')) == 'n/a'


def test_change_marker_depends_on_direction():
    cancels = Kpi(name='Cancels', higher_is_better=False, sql='')
    assert message.fmt_change(-10, cancels) == '▼ -10.0%'          # fewer cancellations is good
    assert message.fmt_change(10, cancels) == '▲ +10.0% ⚠'
    assert message.fmt_change(None, cancels) == ''


def test_names_are_html_escaped(conn):
    kpi = Kpi(name='Spaza <Gauteng> & KZN', sql=SALES.sql)
    text = message.build('R&D', metrics.collect(conn, [kpi], DAY), DAY)
    assert 'Spaza &lt;Gauteng&gt; &amp; KZN' in text
    assert '<b>R&amp;D</b>' in text


def test_long_messages_are_split_on_lines():
    text = '\n'.join('<b>line %d</b> %s' % (i, 'x' * 80) for i in range(200))
    parts = message.split(text)
    assert len(parts) > 1
    assert all(len(p) <= message.TELEGRAM_LIMIT for p in parts)
    assert all(p.count('<b>') == p.count('</b>') for p in parts)
    assert '\n'.join(parts) == text


class FakeResponse:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body

    def json(self):
        return self._body


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, data=None, files=None, timeout=None):
        self.calls.append((url, data, files))
        return self.responses.pop(0)


def test_waits_for_retry_after_on_429():
    waits = []
    session = FakeSession([
        FakeResponse(429, {'ok': False, 'error_code': 429, 'parameters': {'retry_after': 7}}),
        FakeResponse(200, {'ok': True, 'result': {'message_id': 1}}),
    ])
    Telegram('123:abc', session=session, sleep=waits.append).send_message('42', 'hi')
    assert waits == [7]
    assert len(session.calls) == 2


def test_errors_do_not_leak_the_token():
    session = FakeSession([FakeResponse(400, {'ok': False, 'error_code': 400, 'description': 'chat not found'})])
    with pytest.raises(TelegramError) as e:
        Telegram('123:SECRET', session=session, sleep=lambda s: None).send_message('42', 'hi')
    assert 'SECRET' not in str(e.value)
    assert 'chat not found' in str(e.value)


def test_run_once_sends_every_part_to_every_chat(tmp_path):
    db = tmp_path / 'k.db'
    c = sqlite3.connect(db)
    c.execute('create table sales (day text, amount real)')
    c.execute('insert into sales values (?, 100)', (DAY.isoformat(),))
    c.commit()
    c.close()

    sent = []

    class Recorder:
        def send_message(self, chat, text):
            sent.append((chat, text))

        def send_photo(self, chat, png):
            sent.append((chat, 'photo'))

    cfg = Config(title='Daily', database_url='sqlite:///%s' % db, chat_ids=['1', '2'], kpis=[SALES])
    run_once(cfg, DAY, telegram=Recorder())
    assert [chat for chat, _ in sent] == ['1', '2']


def test_next_send_time():
    sast = timezone(timedelta(hours=2))
    assert seconds_until('07:30', datetime(2026, 10, 14, 7, 0, tzinfo=sast)) == 30 * 60
    assert seconds_until('07:30', datetime(2026, 10, 14, 8, 0, tzinfo=sast)) == 23.5 * 3600
