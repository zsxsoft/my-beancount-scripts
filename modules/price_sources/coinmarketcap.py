import requests
import time
import json
from datetime import datetime, tzinfo, timedelta
from string import Template

from bs4 import BeautifulSoup

from beancount.core.number import D
from beancount.prices import source
from beancount.utils.date_utils import parse_date_liberally

ZERO = timedelta(0)
BASE_URL_TEMPLATE = Template(
    "https://web-api.coinmarketcap.com/v1/cryptocurrency/ohlcv/historical?convert=$currency&slug=$ticker&time_end=$date_end&time_start=$date_start")
CURRENCY = "USD"


class UTCtzinfo(tzinfo):
    def utcoffset(self, dt):
        return ZERO

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return ZERO


utc = UTCtzinfo()


class CoinmarketcapError(ValueError):
    "An error from the Coinmarketcap API."


class Source(source.Source):
    def _get_price_for_date(self, ticker, date=None):
        paramater = ticker.split("--")
        currency = paramater[1].upper()

        if date == None:
            date = datetime.today().replace(hour=0, minute=0, second=0) + timedelta(days=-1)
        end_date = date + timedelta(days=1)

        url = BASE_URL_TEMPLATE.substitute(
            date_start=int(date.timestamp()),
            date_end=int(end_date.timestamp()),
            ticker=paramater[0],
            currency=currency)

        try:
            content = requests.get(url).content
            ret = json.loads(content)
            quote = ret['data']['quotes'][0]['quote'][currency]
            price = D(quote['close'])
            return source.SourcePrice(price, date, CURRENCY)

        except:
            raise CoinmarketcapError(
                "Invalid response from Coinmarketcap: {}".format(repr(content)))

    def get_latest_price(self, ticker):
        return self._get_price_for_date(ticker, None)

    def get_historical_price(self, ticker, time):
        return self._get_price_for_date(ticker, time)
