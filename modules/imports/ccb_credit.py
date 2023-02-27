import calendar
import csv
from datetime import date
from io import StringIO

import dateparser
from eml_parser import eml_parser
from beancount.core import data
from beancount.core.data import Note, Transaction
from bs4 import BeautifulSoup

from . import (DictReaderStrip, get_account_by_guess,
               get_income_account_by_guess)
from .base import Base
from .deduplicate import Deduplicate

Account = 'Liabilities:CreditCard:CCB'


class CCBCredit():

    def __init__(self, filename, byte_content, entries, option_map):
        if not filename.endswith('eml'):
            raise 'Not CCB!'
        parsed_eml = eml_parser.decode_email_b(byte_content, include_raw_body=True)
        title = parsed_eml['header']['subject']
        content = ''
        if not '中国建设银行信用卡' in title:
            raise 'Not CCB!'
        for body in parsed_eml['body']:
            content += body['content']
        self.soup = BeautifulSoup(content, 'html.parser')
        self.content = content
        self.deduplicate = Deduplicate(entries, option_map)

    def get_date(self, detail_date):
        year = int(detail_date[0:4])
        month = int(detail_date[5:7])
        day = int(detail_date[8:10])
        return date(year, month, day)

    def parse(self):
        d = self.soup
        table = d.find(lambda a:a.name == "table" and "【交易明细】" in a.text and a.find('table') == None)
        trs = table.find_all(lambda a:a.name == "tr" and len(a.select('td')) == 8)
        transactions = []
        for tr in trs:
            tds = tr.select('td')
            time = self.get_date(tds[0].text.strip())
            description = tds[3].text.strip()
            currency = tds[6].text.strip()
            price = tds[7].text.strip()
            print("Importing {} at {}".format(description, time))
            account = get_account_by_guess(description, '', time)
            flag = "*"
            amount = float(price.replace(',', ''))
            if account == "Unknown":
                flag = "!"
            meta = {}
            meta = data.new_metadata('a', 12345, meta)
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
            data.create_simple_posting(entry, Account, None, None)
            if not self.deduplicate.find_duplicate(entry, -amount, None, Account):
                transactions.append(entry)

        self.deduplicate.apply_beans()
        transactions.reverse()
        return transactions
