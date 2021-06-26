import calendar
import csv
from datetime import date
from io import StringIO

import dateparser
import eml_parser
from beancount.core import data
from beancount.core.data import Amount, Balance, Decimal, Transaction
from bs4 import BeautifulSoup

from . import DictReaderStrip, get_account_by_name
from .base import Base
from .deduplicate import Deduplicate

AccountUnknown = 'Assets:Unknown'


class ICBCDebit():

    def __init__(self, filename, byte_content, entries, option_map):
        if not filename.endswith('html') and not filename.endswith('htm'):
            raise 'Not ICBC!'
        content = str(byte_content.decode('gbk'))
        self.soup = BeautifulSoup(content, 'html.parser')
        title = self.soup.select('.title')[0].text
        if '中国工商银行' not in title:
            raise 'Not ICBC!'
        self.content = content
        self.deduplicate = Deduplicate(entries, option_map)

    def change_currency(self, currency):
        if currency == 'RMB':
            return 'CNY'
        return currency

    def parse(self):
        d = self.soup
        transactions = []
        last_account = ''
        date_string = d.text.split('出单日：')[1].split('日期范围')[0].strip()
        balance_date = date(int(date_string[0:4]), int(
            date_string[5:7]), int(date_string[8:10]))
        balances = d.select('[style="busi-cunkuan1.tab3.display"] .table1 tr')
        for balance in balances:
            tds = balance.select('td.dspts')
            if len(tds) == 0 or len(tds) < 3:
                continue
            account = tds[0].text.strip()
            account = last_account if account == '' else account
            last_account = account
            balance_account = get_account_by_name('ICBC_' + account)
            currency = self.change_currency(tds[3].text.strip())
            price = str(tds[5].text.strip().replace(',', ''))
            entry = Balance(
                account=balance_account,
                amount=Amount(Decimal(price), currency),
                meta={},
                tolerance='',
                diff_amount=Amount(Decimal('0'), currency),
                date=balance_date
            )
            transactions.append(entry)

        bands = d.select('[style="busi-other_detail.tab3.display"] .table1 tr')

        for band in bands:
            tds = band.select('td.dspts')
            if len(tds) == 0:
                continue
            trade_date = tds[10].text.strip()
            if trade_date == '':
                continue
            time = date(int(trade_date[0:4]), int(
                trade_date[4:6]), int(trade_date[6:8]))
            description = tds[6].text.strip()
            trade_currency = self.change_currency(tds[3].text.strip())
            trade_price = tds[7].text.strip()
            account = tds[0].text.strip()
            account = last_account if account == '' else account
            last_account = account
            print("Importing {} at {}".format(description, time))
            trade_account = get_account_by_name('ICBC_' + account)
            flag = "*"
            amount = float(trade_price.replace(',', ''))
            if account == "Unknown":
                flag = "!"
            meta = {}
            meta = data.new_metadata(
                'beancount/core/testing.beancount',
                12345,
                meta
            )
            entry = Transaction(
                meta,
                time,
                flag,
                description,
                None,
                data.EMPTY_SET,
                data.EMPTY_SET, []
            )
            data.create_simple_posting(
                entry, trade_account, trade_price, trade_currency)
            data.create_simple_posting(entry, AccountUnknown, None, None)
            if not self.deduplicate.find_duplicate(entry, -amount, None, account):
                transactions.append(entry)

        self.deduplicate.apply_beans()
        return transactions
