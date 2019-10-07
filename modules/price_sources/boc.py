import requests
import time
from datetime import datetime, tzinfo, timedelta
from string import Template

from bs4 import BeautifulSoup

from beancount.core.number import D
from beancount.prices import source
from beancount.utils.date_utils import parse_date_liberally

ZERO = timedelta(0)
BASE_URL_TEMPLATE = "http://srh.bankofchina.com/search/whpj/search.jsp"
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
        time.sleep(TIME_DELAY)

        if date == None:
            start_time = datetime.today().strftime('%Y-%m-%d')
            end_time = (datetime.today() + timedelta(days = 1)).strftime('%Y-%m-%d')
        else:
            start_time = date.strftime('%Y-%m-%d')
            end_time = (date + timedelta(days = 1)).strftime('%Y-%m-%d')
        data = {
          'pjname': ticker,
          'erectDate': start_time,
          'nothing': end_time
        }
        try:
            content = requests.post(BASE_URL_TEMPLATE, data).content
            soup = BeautifulSoup(content,'html.parser')
            table = soup.find('div', {'class': 'BOC_main'}).findChildren('table')[0]
            tr = table.findChildren('tr')[1]
            data = [td.text.strip() for td in tr.findChildren('td')]

            parsed_date = parse_date_liberally(data[6])
            date = datetime(parsed_date.year, parsed_date.month, parsed_date.day, tzinfo=utc)

            price = D(data[5]) / D(100)

            return source.SourcePrice(price, date, CURRENCY)

        except Exception as e:
          raise e
        except KeyError:
            raise CoinmarketcapError("Invalid response from BOC: {}".format(repr(content)))
        except AttributeError:
            raise CoinmarketcapError("Invalid response from BOC: {}".format(repr(content)))

    def get_latest_price(self, ticker):
        return self._get_price_for_date(ticker, None)

    def get_historical_price(self, ticker, time):
        return self._get_price_for_date(ticker, time)
