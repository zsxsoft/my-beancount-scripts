import requests
import time
from datetime import datetime, tzinfo, timedelta
from string import Template

from bs4 import BeautifulSoup

from beancount.core.number import D
from beancount.prices import source
from beancount.utils.date_utils import parse_date_liberally

ZERO = timedelta(0)
BASE_URL_TEMPLATE = Template("https://coinmarketcap.com/currencies/$ticker/historical-data/?start=$date&end=$date")
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
        paramater = ticker.split("--")
        time.sleep(TIME_DELAY)

        if date == None:
            date_string = ""
        else:
            date_string = date.strftime("%Y%m%d")

        url = BASE_URL_TEMPLATE.substitute(date=date_string, ticker=paramater[0])

        try:
            content = requests.get(url).content
            soup = BeautifulSoup(content,'html.parser')
            table = soup.find('table', {'class': 'table'})
            tr = table.findChildren('tr')[1]
            data = [td.text.strip() for td in tr.findChildren('td')]

            parsed_date = parse_date_liberally(data[0])
            date = datetime(parsed_date.year, parsed_date.month, parsed_date.day, tzinfo=utc)

            price = D(data[4])

            rateDiv = soup.find('div', {'id': 'currency-exchange-rates'})
            rate = D(rateDiv.get('data-' + paramater[1]))
            price = price / rate

            return source.SourcePrice(price, date, CURRENCY)

        except KeyError:
            raise CoinmarketcapError("Invalid response from Coinmarketcap: {}".format(repr(content)))
        except AttributeError:
            raise CoinmarketcapError("Invalid response from Coinmarketcap: {}".format(repr(content)))

    def get_latest_price(self, ticker):
        return self._get_price_for_date(ticker, None)

    def get_historical_price(self, ticker, time):
        return self._get_price_for_date(ticker, time)
