import calendar
import csv
from datetime import date
from io import StringIO

import dateparser
import xlrd
from beancount.core import data
from beancount.core.data import Note, Transaction

from ..accounts import accounts
from . import (DictReaderStrip, get_account_by_guess,
               get_income_account_by_guess, replace_flag)
from .base import Base
from .deduplicate import Deduplicate

AccountCCB = 'Assets:Bank:CCB'


class CCBDebit(Base):

    def __init__(self, filename, byte_content, entries, option_map):
        if not filename.endswith('xls'):
            raise 'Not CCB!'
        data = xlrd.open_workbook(filename)
        table = data.sheets()[0]
        rows_value = table.row_values(0)
        if rows_value[0] != 'China Construction Bank':
            raise 'Not CCB!'
        self.book = data
        self.table = table
        self.deduplicate = Deduplicate(entries, option_map, self.__class__.__name__)

    def get_currency(self, currency):
        if currency == '人民币':
            return 'CNY'
        return currency

    def get_date(self, detail_date):
        year = detail_date[0:4]
        month = detail_date[4:6]
        day = detail_date[6:8]
        ret = date(int(year), int(month), int(day))
        return ret

    def parse(self):
        table = self.table
        rows = table.nrows
        transactions = []
        for i in range(6, rows - 1):
            row = table.row_values(i)
            time = self.get_date(row[1])
            meta = {}
            flag = "*"
            meta['trade_time'] = '%s-%s-%s %s' % (
                time.year, time.month, time.day, row[2])
            if row[10] != '':
                meta['note'] = row[10]
            account = get_account_by_guess(row[9], '', time)
            currency = self.get_currency(row[6])
            income_amount = round(float(row[4]), 2)
            expense_amount = round(float(row[3]), 2)
            meta = data.new_metadata(
                'beancount/core/testing.beancount', 12345, meta)
            payee = row[9] if row[9] != '' else row[7]
            entry = Transaction(
                meta,
                date(time.year, time.month, time.day),
                flag,
                payee,
                None,
                data.EMPTY_SET,
                data.EMPTY_SET, []
            )
            if income_amount > 0:
                data.create_simple_posting(
                    entry, AccountCCB, str(income_amount), currency)
            if expense_amount > 0:
                data.create_simple_posting(
                    entry, AccountCCB, str(-expense_amount), currency)
            data.create_simple_posting(entry, account, None, None)
            print("Importing {} at {}".format(row[9], time))

            if not (income_amount != 0 and expense_amount != 0):
                amount = -income_amount if expense_amount == 0 else expense_amount
                if not self.deduplicate.find_duplicate(entry, str(-amount), None, AccountCCB):
                    transactions.append(entry)
            else:
                transactions.append(entry)

        self.deduplicate.apply_beans()
        return transactions
