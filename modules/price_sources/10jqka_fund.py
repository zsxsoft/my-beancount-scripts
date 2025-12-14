import json
from datetime import datetime, timedelta, tzinfo
from string import Template

import requests
from beancount.core.number import D
from beanprice import source
from beanprice.date_utils import parse_date_liberally

ZERO = timedelta(0)
BASE_URL_TEMPLATE = Template("http://fund.10jqka.com.cn/$ticker/json/jsondwjz.json")


class UTCtzinfo(tzinfo):
    def utcoffset(self, dt):
        return ZERO
    def tzname(self, dt):
        return "UTC"
    def dst(self, dt):
        return ZERO


utc = UTCtzinfo()


class FundError(ValueError):
    "An error from the 10jqka API."


class Source(source.Source):
    def __init__(self):
        self._cache = {}
    
    def _load_fund_data(self, ticker):
        """加载并缓存基金数据"""
        if ticker not in self._cache:
            url = BASE_URL_TEMPLATE.substitute(ticker=ticker)
            content = requests.get(url).content
            content = content.split(b"=")[1]
            self._cache[ticker] = json.loads(content)
        return self._cache[ticker]

    def _find_price(self, fund_data, date_string):
        """在基金数据中查找指定日期的价格"""
        if date_string == "0":
            # 获取最新
            item = fund_data[-1]
            return item[0], item[1]
        
        date_int = int(date_string)
        for item in fund_data:
            if item[0] == date_string or int(item[0]) >= date_int:
                return item[0], item[1]
        return None, None

    def get_batch_prices(self, tickers, dates):
        """
        批量获取多个基金在多个日期的价格
        
        Args:
            tickers: [(commodity, ticker), ...] 如 [('F920003', '920003'), ...]
            dates: [datetime, ...] 日期列表
        
        Returns:
            [(commodity, date, price, quote_currency), ...]
        """
        results = []
        
        # 预加载所有基金数据
        for commodity, ticker in tickers:
            try:
                self._load_fund_data(ticker)
            except Exception as e:
                print(f"10jqka: 无法加载基金 {ticker}: {e}")
        
        # 查找每个日期的价格
        for date in dates:
            date_string = date.strftime("%Y%m%d")
            
            for commodity, ticker in tickers:
                if ticker not in self._cache:
                    continue
                
                found_date_str, found_price = self._find_price(self._cache[ticker], date_string)
                
                if found_price and found_date_str:
                    parsed_date = parse_date_liberally(found_date_str)
                    result_date = datetime(parsed_date.year, parsed_date.month, parsed_date.day).date()
                    results.append((commodity, result_date, D(found_price), 'CNY'))
        
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
        try:
            fund_data = self._load_fund_data(ticker)
            found_date_str, found_price = self._find_price(fund_data, "0")
            if found_price:
                parsed_date = parse_date_liberally(found_date_str)
                date = datetime(parsed_date.year, parsed_date.month, parsed_date.day, tzinfo=utc)
                return source.SourcePrice(D(found_price), date, 'CNY')
        except Exception:
            pass
        return None
