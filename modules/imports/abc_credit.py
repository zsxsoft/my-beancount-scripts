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

Account农行 = 'Liabilities:CreditCard:ABC'


class ABCCredit():

    def __init__(self, filename, byte_content, entries, option_map):
        if not filename.endswith('eml'):
            raise 'Not ABC!'
        # fix encoding
        byte_content = byte_content.replace(b'charset=""', b'charset="gbk"')
        parsed_eml = eml_parser.decode_email_b(byte_content, include_raw_body=True)
        title = parsed_eml['header']['subject']
        content = ''
        if not '金穗信用卡' in title:
            raise 'Not ABC!'
        for body in parsed_eml['body']:
            content += body['content']
        self.soup = BeautifulSoup(content, 'html.parser')
        self.content = content
        self.deduplicate = Deduplicate(entries, option_map)

    def get_date(self, detail_date):
        year = int(detail_date[0:4])
        month = int(detail_date[4:6])
        day = int(detail_date[6:8])
        return date(year, month, day)

    def parse(self):
        d = self.soup
        table = d.select("#reportPanel3 #loopBand1")[1]
        trs = table.select('#fixBand10 td tr')
        transactions = []
        for tr in trs:
            tds = tr.select('td')
            time = self.get_date(tds[1].text.strip())
            description = tds[5].text.strip()
            price_text = tds[7].text.strip()
            prices = price_text.split('/')
            print("Importing {} at {}".format(description, time))
            account = get_account_by_guess(description, '', time)
            flag = "*"
            amount = float(prices[0].replace(',', ''))
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
            data.create_simple_posting(entry, account, None, None)
            data.create_simple_posting(entry, Account农行, prices[0], prices[1])
            if not self.deduplicate.find_duplicate(entry, -amount, None, Account农行):
                transactions.append(entry)

        self.deduplicate.apply_beans()
        transactions.reverse()
        return transactions
