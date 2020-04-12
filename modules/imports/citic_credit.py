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

Account中信 = 'Liabilities:CreditCard:CITIC'


class CITICCredit():

    def __init__(self, filename, byte_content, entries, option_map):
        if not filename.endswith('eml'):
            raise 'Not CITIC!'
        parsed_eml = eml_parser.eml_parser.decode_email_b(
            byte_content, include_raw_body=True)
        if not '中信银行' in parsed_eml['header']['subject']:
            raise 'Not CITIC!'
        content = parsed_eml['body'][1]['content']
        # for body in parsed_eml['body']:
        #content += body['content']
        self.soup = BeautifulSoup(content, 'html.parser')
        self.content = content
        self.deduplicate = Deduplicate(entries, option_map)

    def change_currency(self, currency):
        if currency == 'RMB':
            return 'CNY'
        return currency

    def parse(self):
        d = self.soup
        balance = d.select('#fixBand16')[0].text.replace('RMB', '').strip()
        bands = d.select('#fixBand7')
        transactions = []
        for band in bands:
            tds = band.select('td>table>tbody>tr>td')
            trade_date = tds[1].text.strip()
            if trade_date == '':
                continue
            time = date(int(trade_date[0:4]), int(
                trade_date[4:6]), int(trade_date[6:8]))
            description = tds[4].text.strip()
            trade_currency = self.change_currency(tds[5].text.strip())
            trade_price = tds[6].text.strip()
            real_currency = self.change_currency(tds[7].text.strip())
            real_price = tds[8].text.strip()
            print("Importing {} at {}".format(description, time))
            account = get_account_by_guess(description, '', time)
            flag = "*"
            amount = float(real_price.replace(',', ''))
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
                entry, account, trade_price, trade_currency)
            data.create_simple_posting(entry, Account中信, None, None)
            if not self.deduplicate.find_duplicate(entry, -amount, None, Account中信):
                transactions.append(entry)

        self.deduplicate.apply_beans()
        return transactions
