import time
from datetime import datetime, timedelta, tzinfo
from string import Template
from urllib.parse import unquote

import requests
from beancount.core.number import D
from beancount.prices import source
from beancount.utils.date_utils import parse_date_liberally
from bs4 import BeautifulSoup

ZERO = timedelta(0)
BASE_URL_TEMPLATE = "https://srh.bankofchina.com/search/whpj/search_cn.jsp"
CURRENCY = "USD"


class UTCtzinfo(tzinfo):
    def utcoffset(self, dt):
        return ZERO

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return ZERO


utc = UTCtzinfo()


class BOCError(ValueError):
    "An error from the BOC."


class Source(source.Source):
    def _get_price_for_date(self, ticker, date=None):

        if date == None:
            start_time = datetime.today().strftime('%Y-%m-%d')
            end_time = (datetime.today() + timedelta(days=1)
                        ).strftime('%Y-%m-%d')
        else:
            start_time = date.strftime('%Y-%m-%d')
            end_time = (date + timedelta(days=1)).strftime('%Y-%m-%d')

        data = {
            'pjname': unquote(ticker.replace('_', '%')),
            'erectDate': start_time,
            'nothing': end_time,
            'head': 'head_620.js',
            'bottom': 'bottom_591.js'
        }

        try:
            content = requests.post(BASE_URL_TEMPLATE, data).content
            soup = BeautifulSoup(content, 'html.parser')
            table = soup.find(
                'div', {'class': 'BOC_main'}).findChildren('table')[0]
            tr = table.findChildren('tr')[1]
            data = [td.text.strip() for td in tr.findChildren('td')]

            parsed_date = parse_date_liberally(data[6])
            date = datetime(parsed_date.year, parsed_date.month,
                            parsed_date.day, tzinfo=utc)

            price = D(data[5]) / D(100)

            return source.SourcePrice(price, date, CURRENCY)

        except Exception as e:
            raise e
        '''except KeyError:
            raise BOCError(
                "Invalid response from BOC: {}".format(repr(content)))
        except AttributeError:
            raise BOCError(
                "Invalid response from BOC: {}".format(repr(content)))'''

    def get_latest_price(self, ticker):
        return self._get_price_for_date(ticker, None)

    def get_historical_price(self, ticker, time):
        return self._get_price_for_date(ticker, time)
