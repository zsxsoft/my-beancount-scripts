import json
import time
from datetime import datetime, timedelta, tzinfo
from string import Template

from curl_cffi import requests
from beancount.core.number import D
from beanprice import source

ZERO = timedelta(0)
BASE_URL_TEMPLATE = Template("https://api.investing.com/api/financialdata/historical/$ticker")
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
session = requests.Session(impersonate="chrome")


class InvestingError(ValueError):
    "An error from the Investing API."


class Source(source.Source):
    def _fetch_range(self, ticker, start_date, end_date):
        """获取日期范围内的价格数据，返回 {date: price} 映射"""
        url = BASE_URL_TEMPLATE.substitute(ticker=ticker)
        params = {
            'start-date': start_date.strftime("%Y-%m-%d"),
            'end-date': end_date.strftime("%Y-%m-%d"),
            'time-frame': 'Daily',
            'add-missing-rows': 'false'
        }
        headers = {
            'domain-id': 'cn',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:138.0) Gecko/20100101 Firefox/138.0'
        }
        
        response = session.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        if 'data' not in data or not data['data']:
            return {}
        
        date_price_map = {}
        for item in data['data']:
            item_date = datetime.fromisoformat(item['rowDateTimestamp'].replace('Z', '+00:00')).date()
            date_price_map[item_date] = D(item['last_closeRaw'])
        
        time.sleep(TIME_DELAY)
        return date_price_map

    def _find_closest(self, date_price_map, target_date, max_diff=7):
        """找到最接近目标日期的价格"""
        if target_date in date_price_map:
            return target_date, date_price_map[target_date]
        
        closest = None
        min_diff = float('inf')
        for d, p in date_price_map.items():
            diff = abs((d - target_date).days)
            if diff < min_diff:
                min_diff = diff
                closest = (d, p)
        
        if closest and min_diff <= max_diff:
            return closest
        return None, None

    def get_batch_prices(self, tickers, dates):
        """
        批量获取多个股票在多个日期的价格
        
        Args:
            tickers: [(commodity, ticker), ...] 如 [('HK0700', '102047'), ...]
            dates: [datetime, ...] 日期列表
        
        Returns:
            [(commodity, date, price, quote_currency), ...]
        """
        results = []
        
        if not dates:
            return results
        
        min_date = min(dates) - timedelta(days=7)
        max_date = max(dates) + timedelta(days=7)
        
        for commodity, ticker in tickers:
            try:
                date_price_map = self._fetch_range(ticker, min_date, max_date)
                
                for date in dates:
                    target_date = date.date() if isinstance(date, datetime) else date
                    found_date, price = self._find_closest(date_price_map, target_date)
                    if price is not None:
                        results.append((commodity, found_date, price, CURRENCY))
                
            except Exception as e:
                print(f"investing error for {commodity}: {e}")
        
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
