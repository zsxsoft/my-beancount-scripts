from typing import NamedTuple
import re
import camelot

from functools import reduce
from datetime import date
from pprint import pprint

import dateparser
from beancount.core import data
from beancount.core.data import Amount, Balance, Decimal, Posting, Transaction

from . import (DictReaderStrip, get_account_by_guess,
               get_income_account_by_guess)
from ..accounts import accounts
from .base import Base
from .deduplicate import Deduplicate

Account招商 = 'Liabilities:CreditCard:CMB'
trade_area_list = {
    'CN': 'CNY',
    'US': 'USD',
    'JP': 'JPY',
    'HK': 'HKD',
    'SG': 'SGD'
}

cell_rules = [
    lambda rows: len(rows) == 6,
    lambda rows: rows[0] == '' or re.search(r'\d{2}/\d{2}', rows[0]) != None,
    lambda rows: re.search(r'\d{2}/\d{2}', rows[1]) != None,
    lambda rows: re.search(r'-?[0-9,]+\.\d{2}', rows[3]) != None,
    lambda rows: re.search(r'\d{4}', rows[4]) != None,
    lambda rows: re.search(r'-?[0-9,]+\.\d{2}(\([A-Z]{2}\))?', rows[5]) != None,
]

class CMBRow(NamedTuple):
    sold: str
    posted: str
    description: str
    rmb_amount: str
    card_no: str
    original_tran_amount: str

class CMBPdfCredit(Base):
    def __init__(self, filename, byte_content, entries, option_map):
        if not filename.endswith('pdf'):
            raise RuntimeError('Not CMB!')
        filename_search = re.search(r'(\d{4})年(\d{2})月信用卡账单.pdf$', filename)
        if not filename_search:
            raise RuntimeError('Not CMB!')
        self.year = filename_search.group(1)
        tables = camelot.read_pdf(filename, pages='1-end', flavor='stream')
        self.balance_date = tables[0].df.values.tolist()[2][1]
        self.balance_value = tables[0].df.values.tolist()[8][1]
        def test_row_rule(table):
            for rule in cell_rules:
                if not rule(table):
                    return False
            return True
        tables = map(lambda table: list(filter(test_row_rule, table.df.values.tolist())), tables)
        table = reduce(lambda a, b: a + b, tables)
        table = list(map(lambda row: CMBRow(*row), table))

        self.content = table
        self.deduplicate = Deduplicate(entries, option_map)
        self.date = date.today()

    def change_currency(self, currency):
        if currency == None or currency == '':
            return 'CNY'
        if currency not in trade_area_list:
            print('Unknown trade area: ' + currency +
                  ', please append it to ' + __file__)
            return currency
        return trade_area_list[currency]

    # def get_date(self, detail_date):
    #     month = detail_date[0:2]
    #     day = detail_date[2:4]
    #     year = self.date.year
    #     ret = date(year, int(month), int(day))
    #     if month == '12' and ret > self.date:
    #         ret = ret.replace(ret.year - 1)
    #     return ret

    def parse(self):
        content = self.content
        transactions = []
        date_search = re.search(r'(\d{4})年(\d{2})月(\d{2})日$', self.balance_date)
        balance = '-' + self.balance_value.replace('¥', '').replace(',', '').strip()
        entry = Balance(
            account=Account招商,
            amount=Amount(Decimal(balance), 'CNY'),
            meta={},
            tolerance='',
            diff_amount=Amount(Decimal('0'), 'CNY'),
            date = date(int(date_search.group(1)), int(date_search.group(2)), int(date_search.group(3)))
        )
        transactions.append(entry)
        for row in content:
            
            month, day = row.sold.split('/')[0:2] if len(row.sold.split('/')) >= 2 else row.posted.split('/')[0:2]
            transaction_date = date(int(self.year), int(month), int(day))
            payee_desc = row.description.split('-')
            if len(payee_desc) != 2:
                payee_desc = list(map(lambda d: d.strip(), row.description.split('*')))
            if len(payee_desc) != 2:
                payee_desc = [row.description, row.description]
            payee, description = payee_desc
            currency_search = re.search(r'[^\(]*\(([^\)]*)\)', row.original_tran_amount)
            trade_currency = self.change_currency(currency_search.group(1) if currency_search != None else None)
            trade_price = re.sub(r'\([A-Z]+\)', '', row.original_tran_amount).replace(',', '').strip()
            real_currency = 'CNY'
            real_price = row.rmb_amount.replace(',', '').strip()
            print("Importing {} at {}".format(description, transaction_date))
            account = get_account_by_guess(description, '', transaction_date)
            flag = "*"
            amount = float(real_price)
            if account == "Unknown":
                flag = "!"
            meta = {}
            meta = data.new_metadata(
                'beancount/core/testing.beancount', 12345, meta)
            entry = Transaction(meta, transaction_date, flag, payee,
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
