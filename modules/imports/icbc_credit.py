import calendar
import csv
from datetime import date, datetime
from io import StringIO

import eml_parser
from beancount.core import data
from beancount.core.data import Note, Transaction
from bs4 import BeautifulSoup

from . import (DictReaderStrip, get_account_by_guess,
               get_income_account_by_guess)
from .base import Base
from .deduplicate import Deduplicate

Account工商 = 'Liabilities:CreditCard:ICBC'


class ICBCCredit():

    def __init__(self, filename, byte_content, entries, option_map):
        if not filename.endswith('eml'):
            raise 'Not ICBC!'
        parsed_eml = eml_parser.eml_parser.decode_email_b(
            byte_content, include_raw_body=True)
        title = parsed_eml['header']['subject']
        content = ''
        if not '中国工商银行' in title:
            raise 'Not CMBC!'
        for body in parsed_eml['body']:
            content += body['content']
        self.soup = BeautifulSoup(content, 'html.parser')
        self.content = content
        self.deduplicate = Deduplicate(entries, option_map)

    def get_currency(self, currency_text):
        currency = currency_text.strip()
        if currency == 'RMB':
            return 'CNY'
        return currency

    def parse(self):
        transactions = []
        d = self.soup
        table = d.find(lambda a:a.name == "table" and "商户名称" in a.text and a.find('table') == None)
        trs = table.select('tr')
        for x in range(2, len(trs)):
            tds = trs[x].select('td')
            time = datetime.strptime(tds[1].text.strip(), '%Y-%m-%d')
            description = tds[4].text.strip()
            price_array = tds[5].text.strip().split('/')
            price = price_array[0]
            currency = self.get_currency(price_array[1])
            print("Importing {} at {}".format(description, time))
            account = get_account_by_guess(description, '', time)
            flag = "*"
            amount = float(price.replace(',', ''))
            if not '支出' in tds[6].text:
                amount = -amount
            if account == "Expenses:Unknown":
                flag = "!"
            meta = {}
            meta = data.new_metadata(
                'beancount/core/testing.beancount',
                12345,
                meta
            )
            counterparty = description
            if '-' in description:
                counterparty = description.split('-')[0]
                description = '-'.join(description.split('-')[1:])
            else:
                description = ''
            entry = Transaction(
                meta,
                date(time.year, time.month, time.day),
                flag,
                counterparty,
                description,
                data.EMPTY_SET,
                data.EMPTY_SET, []
            )
            data.create_simple_posting(entry, account, price, currency)
            data.create_simple_posting(entry, Account工商, None, None)
            if not self.deduplicate.find_duplicate(entry, -amount, None, Account工商):
                transactions.append(entry)

        self.deduplicate.apply_beans()
        transactions.reverse()
        return transactions
