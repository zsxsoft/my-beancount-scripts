import httpx
import ssl
import json
from datetime import datetime, timedelta, tzinfo

from beancount.core.number import D
from beanprice import source
from beanprice.date_utils import parse_date_liberally

context = ssl.create_default_context()
context.options |= ssl.OP_LEGACY_SERVER_CONNECT

ZERO = timedelta(0)
BASE_URL = "https://www.chinamoney.com.cn/ags/ms/cm-u-bk-fx/SddsExchRateSwpHis?dataType=3"


class UTCtzinfo(tzinfo):
    def utcoffset(self, dt):
        return ZERO
    def tzname(self, dt):
        return "UTC"
    def dst(self, dt):
        return ZERO


utc = UTCtzinfo()


class CMError(ValueError):
    "An error from the ChinaMoney."


class Source(source.Source):
    def _fetch_date(self, date):
        """获取指定日期的所有汇率数据"""
        start_time = date.strftime('%Y-%m-%d')
        end_time = (date + timedelta(days=1)).strftime('%Y-%m-%d')
        url = f"{BASE_URL}&startDate={start_time}&endDate={end_time}"
        
        c = httpx.Client(verify=context).post(url).content
        return json.loads(c)

    def get_batch_prices(self, tickers, dates):
        """
        批量获取多个货币在多个日期的价格
        
        Args:
            tickers: [(commodity, ticker), ...] 如 [('USD', 'USD'), ('JPY', '100JPY')]
            dates: [datetime, ...] 日期列表
        
        Returns:
            [(commodity, date, price, quote_currency), ...]
        """
        results = []
        
        for date in dates:
            try:
                json_data = self._fetch_date(date)
                
                if not json_data.get('records'):
                    continue
                
                record = json_data['records'][0]
                heads = json_data["data"]["head"]
                
                parsed_date = parse_date_liberally(record['dateString'])
                result_date = datetime(parsed_date.year, parsed_date.month,
                                       parsed_date.day, tzinfo=utc)
                
                for commodity, ticker in tickers:
                    try:
                        ticker_index = heads.index(ticker + "/CNY")
                        price_str = record["dateMapNew"][ticker_index]
                        if price_str != "---":
                            price = D(price_str)
                            if '100' in ticker:
                                price = price / D(100)
                            results.append((commodity, result_date.date(), price, 'CNY'))
                    except (ValueError, IndexError):
                        pass
                        
            except Exception as e:
                print(f"chinamoney error for {date.strftime('%Y-%m-%d')}: {e}")
        
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
        return self.get_historical_price(ticker, datetime.today())
