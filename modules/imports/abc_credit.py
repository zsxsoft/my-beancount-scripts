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

Account农行 = 'Liabilities:CreditCard:ABC'


class ABCCredit():

    def __init__(self, filename, byte_content, entries, option_map):
        if not filename.endswith('eml'):
            raise 'Not ABC!'
        # fix encoding
        byte_content = byte_content.replace(b'charset=""', b'charset="gbk"')
        ep = eml_parser.EmlParser()
        ep.include_raw_body = True
        parsed_eml = ep.decode_email_bytes(byte_content)
        title = parsed_eml['header']['subject']
        content = ''
        if not '金穗信用卡' in title:
            raise 'Not ABC!'
        for body in parsed_eml['body']:
            content += body['content']
        content = content.split('Sett Amt')[1].split('<img')[0]
        self.soup = BeautifulSoup(content, 'html.parser')
        self.content = content
        self.deduplicate = Deduplicate(entries, option_map, self.__class__.__name__)

    def get_date(self, detail_date):
        year = int('20' + detail_date[0:2])
        month = int(detail_date[2:4])
        day = int(detail_date[4:6])
        return date(year, month, day)

    def parse(self):
        d = self.soup
        trs = d.select('tr')
        transactions = []
        for tr in trs:
            tds = tr.select('td')
            if len(tds) < 4:
                continue
            time = self.get_date(tds[1].text.strip())
            description = tds[3].text.strip()
            price_text = tds[5].text.strip()
            prices = price_text.split('/')
            if ',' in description:
                d = description.split(',')
                payee = d[0]
                description = d[1]
            elif '，' in description:
                d = description.split('，')
                payee = d[0]
                description = d[1]
            else:
                payee = ''
            print("Importing {}: {} at {}".format(payee, description, time))
            account = get_account_by_guess(payee, description, time)
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
                payee,
                description,
                data.EMPTY_SET,
                data.EMPTY_SET, []
            )
            data.create_simple_posting(entry, account, None, None)
            data.create_simple_posting(entry, Account农行, prices[0], prices[1])
            if not self.deduplicate.find_duplicate(entry, amount, None, Account农行):
                transactions.append(entry)

        self.deduplicate.apply_beans()
        transactions.reverse()
        return transactions
