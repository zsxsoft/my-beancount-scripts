import json
import time
from datetime import datetime, timedelta, tzinfo
from string import Template

import requests
from beancount.core.number import D
from beancount.prices import source
from beancount.utils.date_utils import parse_date_liberally

ZERO = timedelta(0)
BASE_URL_TEMPLATE = Template(
    "http://fund.10jqka.com.cn/$ticker/json/jsondwjz.json")
CURRENCY = "USD"
TIME_DELAY = 1


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

        if date == None:
            date_string = "0"
        else:
            date_string = date.strftime("%Y%m%d")

        url = BASE_URL_TEMPLATE.substitute(ticker=ticker)

        try:
            content = requests.get(url).content
            content = content.split(b"=")[1]
            data = json.loads(content)
            price = 0
            date_int = int(date_string)
            found_date = False

            if date_string != "0":
                for item in data:
                    if item[0] == date_string or int(item[0]) > date_int:
                        date = item[0]
                        price = item[1]
                        found_date = True
                        break

            if not found_date:
                item = data[len(data) - 1]
                price = item[1]
                date = item[0]

            parsed_date = parse_date_liberally(date)
            date = datetime(parsed_date.year, parsed_date.month,
                            parsed_date.day, tzinfo=utc)

            price = D(price)

            return source.SourcePrice(price, date, CURRENCY)

        except KeyError:
            raise CoinmarketcapError(
                "Invalid response from 10jqka: {}".format(repr(content)))
        except AttributeError:
            raise CoinmarketcapError(
                "Invalid response from 10jqka: {}".format(repr(content)))

    def get_latest_price(self, ticker):
        return self._get_price_for_date(ticker, None)

    def get_historical_price(self, ticker, time):
        return self._get_price_for_date(ticker, time)
