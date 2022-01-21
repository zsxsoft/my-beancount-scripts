import calendar
import csv
from datetime import date
from io import StringIO

import dateparser
import eml_parser
from beancount.core import data
from beancount.core.data import Note, Transaction
from bs4 import BeautifulSoup

from . import (DictReaderStrip, get_account_by_guess,
               get_income_account_by_guess)
from .base import Base
from .deduplicate import Deduplicate

Account民生 = 'Liabilities:CreditCard:CMBC'


class CMBCCredit():

    def __init__(self, filename, byte_content, entries, option_map):
        if not filename.endswith('eml'):
            raise RuntimeError('Not CMBC!')
        parsed_eml = eml_parser.eml_parser.decode_email_b(
            byte_content, include_raw_body=True)
        title = parsed_eml['header']['subject']
        content = ''
        if not '民生信用卡' in title:
            raise RuntimeError('Not CMBC!')
        for body in parsed_eml['body']:
            content += body['content']
        self.soup = BeautifulSoup(content, 'html.parser')
        self.content = content
        self.deduplicate = Deduplicate(entries, option_map)
        self.year = int(title.split('信用卡')[1].split('年')[0])
        self.month = int(title.split('年')[1].split('月')[0])

    def get_currency(self, currency_text):
        currency = currency_text.split("\xa0")[1].strip()
        if currency == 'RMB':
            return 'CNY'
        return currency

    def get_date(self, detail_date):
        splitted_date = detail_date.split('/')
        year = self.year
        if splitted_date[0] == '12' and self.month < 12:
            year -= 1
        return date(year, int(splitted_date[0]), int(splitted_date[1]))

    def parse(self):
        d = self.soup
        tables = d.select('#loopBand2>table>tr')
        currencies_count = int(len(tables) / 4)
        transactions = []
        for x in range(0, currencies_count):
            title = tables[x * 4]
            contents = tables[x * 4 + 3]
            currency = title.select('#fixBand29 td>table td')[1].text.strip()
            currency = self.get_currency(currency)
            bands = contents.select('#loopBand3>table>tr')
            for band in bands:
                tds = band.select(
                    'td>table>tr>td #fixBand9>table>tr>td>table>tr>td')
                time = self.get_date(tds[1].text.strip())
                description = tds[3].text.strip()
                price = tds[4].text.strip()
                print("Importing {} at {}".format(description, time))
                account = get_account_by_guess(description, '', time)
                flag = "*"
                amount = float(price.replace(',', ''))
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
                data.create_simple_posting(entry, account, price, currency)
                data.create_simple_posting(entry, Account民生, None, None)
                if not self.deduplicate.find_duplicate(entry, -amount, None, Account民生):
                    transactions.append(entry)

        self.deduplicate.apply_beans()
        return transactions
