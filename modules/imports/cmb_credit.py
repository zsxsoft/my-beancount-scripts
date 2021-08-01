import calendar
import csv
from datetime import date
from io import StringIO

import dateparser
import eml_parser
from beancount.core import data
from beancount.core.data import Amount, Balance, Decimal, Posting, Transaction
from bs4 import BeautifulSoup

from . import (DictReaderStrip, get_account_by_guess,
               get_income_account_by_guess)
from .base import Base
from .deduplicate import Deduplicate

Account招商 = 'Liabilities:CreditCard:CMB'
trade_area_list = {
    'CN': 'CNY',
    'US': 'USD',
    'JP': 'JPY',
    'HK': 'HKD'
}


class CMBCredit():

    def __init__(self, filename, byte_content, entries, option_map):
        if not filename.endswith('eml'):
            raise 'Not CMB!'
        parsed_eml = eml_parser.eml_parser.decode_email_b(
            byte_content, include_raw_body=True)
        if not '招商银行信用卡' in parsed_eml['header']['subject']:
            raise 'Not CMB!'
        content = parsed_eml['body'][0]['content']
        # for body in parsed_eml['body']:
        #content += body['content']
        self.soup = BeautifulSoup(content, 'html.parser')
        self.content = content
        self.deduplicate = Deduplicate(entries, option_map)
        self.date = date.today()

    def change_currency(self, currency):
        if currency == '':
            return 'CNY'
        if currency not in trade_area_list:
            print('Unknown trade area: ' + currency +
                  ', please append it to ' + __file__)
            return currency
        return trade_area_list[currency]

    def get_date(self, detail_date):
        month = detail_date[0:2]
        day = detail_date[2:4]
        year = self.date.year
        ret = date(year, int(month), int(day))
        if month == '12' and ret > self.date:
            ret = ret.replace(ret.year - 1)
        return ret

    def parse(self):
        d = self.soup
        transactions = []
        # balance = d.select('#fixBand16')[0].text.replace('RMB', '').strip()
        # date_range = d.select('#fixBand38 div font')[0].text.strip()
        date_range = d.select('#fixBand6 div font')[0].text.strip()
        transaction_date = dateparser.parse(
            date_range.split('-')[1].split('(')[0])
        transaction_date = date(transaction_date.year,
                                transaction_date.month, transaction_date.day)
        self.date = transaction_date
        balance = '-' + \
            d.select('#fixBand18 div font')[0].text.replace(
                '￥', '').replace(',', '').strip()
        entry = Balance(
            account=Account招商,
            amount=Amount(Decimal(balance), 'CNY'),
            meta={},
            tolerance='',
            diff_amount=Amount(Decimal('0'), 'CNY'),
            date=self.date
        )
        transactions.append(entry)

        bands = d.select('#fixBand29 #loopBand2>table>tr')
        for band in bands:
            tds = band.select('td #fixBand15 table table td')
            if len(tds) == 0:
                continue
            trade_date = tds[1].text.strip()
            if trade_date == '':
                trade_date = tds[2].text.strip()
            time = self.get_date(trade_date)
            full_descriptions = tds[3].text.strip().split('-')
            payee = full_descriptions[0]
            description = '-'.join(full_descriptions[1:])
            trade_currency = self.change_currency(tds[6].text.strip())
            trade_price = tds[7].text.replace('\xa0', '').strip()
            real_currency = 'CNY'
            real_price = tds[4].text.replace(
                '￥', '').replace('\xa0', '').strip()
            print("Importing {} at {}".format(description, time))
            account = get_account_by_guess(description, '', time)
            flag = "*"
            amount = float(real_price.replace(',', ''))
            if account == "Unknown":
                flag = "!"
            meta = {}
            meta = data.new_metadata(
                'beancount/core/testing.beancount', 12345, meta)
            entry = Transaction(meta, time, flag, payee,
                                description, data.EMPTY_SET, data.EMPTY_SET, [])

            if real_currency == trade_currency:
                data.create_simple_posting(
                    entry, account, trade_price, trade_currency)
            else:
                trade_amount = Amount(Decimal(trade_price), trade_currency)
                real_amount = Amount(Decimal(abs(round(float(
                    real_price), 2))) / Decimal(abs(round(float(trade_price), 2))), real_currency)
                posting = Posting(account, trade_amount,
                                  None, real_amount, None, None)
                entry.postings.append(posting)

            data.create_simple_posting(entry, Account招商, None, None)
            if not self.deduplicate.find_duplicate(entry, -amount, None, Account招商):
                transactions.append(entry)

        self.deduplicate.apply_beans()
        return transactions
