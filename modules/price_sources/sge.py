import time
from datetime import datetime, timedelta, tzinfo

import requests
from bs4 import BeautifulSoup
from beancount.core.number import D
from beanprice import source
from beanprice.date_utils import parse_date_liberally

ZERO = timedelta(0)
BASE_URL = "https://www.sge.com.cn/sjzx/quotation_daily_new"
CURRENCY = "CNY"
TIME_DELAY = 1


class UTCtzinfo(tzinfo):
    def utcoffset(self, dt):
        return ZERO
    def tzname(self, dt):
        return "UTC"
    def dst(self, dt):
        return ZERO


utc = UTCtzinfo()


class SGEError(ValueError):
    "An error from the SGE API."


class Source(source.Source):
    def _find_close_price_column(self, header_row):
        """动态查找收盘价所在的列索引"""
        headers = header_row.find_all(['th', 'td'])
        for i, header in enumerate(headers):
            if '收盘价' in header.get_text(strip=True):
                return i
        return 5

    def _fetch_date(self, ticker, date):
        """获取指定日期的价格"""
        date_str = date.strftime("%Y-%m-%d")
        params = {'start_date': date_str, 'end_date': date_str, 'inst_ids': ticker}
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        
        response = requests.get(BASE_URL, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        table_rows = soup.select('.daily_new_table tr')
        
        if len(table_rows) < 2:
            return None, None
        
        close_price_column = self._find_close_price_column(table_rows[0])
        
        for row in table_rows[1:]:
            cells = row.find_all('td')
            if len(cells) > close_price_column:
                try:
                    row_date = cells[0].get_text(strip=True)
                    contract = cells[1].get_text(strip=True)
                    close_price = cells[close_price_column].get_text(strip=True)
                    
                    if contract == ticker and close_price and close_price != '-':
                        parsed_date = parse_date_liberally(row_date)
                        return datetime(parsed_date.year, parsed_date.month, parsed_date.day).date(), D(str(close_price))
                except (IndexError, ValueError):
                    continue
        
        return None, None

    def get_batch_prices(self, tickers, dates):
        """
        批量获取黄金在多个日期的价格
        
        Args:
            tickers: [(commodity, ticker), ...] 如 [('AU9999', 'Au99.99'), ...]
            dates: [datetime, ...] 日期列表
        
        Returns:
            [(commodity, date, price, quote_currency), ...]
        """
        results = []
        
        for date in dates:
            for commodity, ticker in tickers:
                try:
                    result_date, price = self._fetch_date(ticker, date)
                    if price is not None:
                        results.append((commodity, result_date, price, CURRENCY))
                    time.sleep(TIME_DELAY)
                except Exception as e:
                    print(f"sge error for {ticker} @ {date.strftime('%Y-%m-%d')}: {e}")
        
        return results

    def get_historical_price(self, ticker, time):
        """获取历史价格 - 复用批量方法"""
        results = self.get_batch_prices([('_', ticker)], [time])
        if results:
            _, date, price, currency = results[0]
            return source.SourcePrice(price, datetime.combine(date, datetime.min.time()).replace(tzinfo=utc), currency)
        return None

    def get_latest_price(self, ticker):
        """获取最新价格"""
        return self.get_historical_price(ticker, datetime.now())
