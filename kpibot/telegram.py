"""Minimal Telegram Bot API client: just the two calls this needs, with rate-limit handling."""
import time

import requests


class TelegramError(Exception):
    pass


class Telegram:
    def __init__(self, token, session=None, sleep=time.sleep, max_retries=3):
        self.base = 'https://api.telegram.org/bot%s/' % token
        self.session = session or requests.Session()
        self.sleep = sleep
        self.max_retries = max_retries

    def _call(self, method, data, files=None):
        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.post(self.base + method, data=data, files=files, timeout=30)
            except requests.RequestException as e:
                if attempt == self.max_retries:
                    raise TelegramError('%s failed: %s' % (method, e)) from e
                self.sleep(2 ** attempt)
                continue
            body = response.json()
            if body.get('ok'):
                return body['result']
            # Telegram says exactly how long to wait when we send too fast
            retry_after = body.get('parameters', {}).get('retry_after')
            if response.status_code == 429 and retry_after and attempt < self.max_retries:
                self.sleep(retry_after)
                continue
            if response.status_code >= 500 and attempt < self.max_retries:
                self.sleep(2 ** attempt)
                continue
            # Don't put the token in the error: these messages end up in logs
            raise TelegramError('%s: %s %s' % (method, body.get('error_code'), body.get('description')))
        raise TelegramError('%s: gave up after %d retries' % (method, self.max_retries))

    def send_message(self, chat_id, text):
        return self._call('sendMessage', {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML',
                                          'disable_web_page_preview': 'true'})

    def send_photo(self, chat_id, png, caption=''):
        return self._call('sendPhoto', {'chat_id': chat_id, 'caption': caption}, files={'photo': ('chart.png', png)})
