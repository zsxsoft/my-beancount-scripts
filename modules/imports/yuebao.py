import calendar
import csv
import datetime
from datetime import date
from io import StringIO

import xlrd
from beancount.core import data
from beancount.core.data import Note, Transaction

from . import (DictReaderStrip, get_account_by_guess,
               get_income_account_by_guess)
from .base import Base
from .deduplicate import Deduplicate

Account余额宝 = 'Assets:Company:Alipay:MonetaryFund'
incomes = ['余额自动转入', '收益', '单次转入']


class YuEBao(Base):

    def __init__(self, filename, byte_content, entries, option_map):
        if not filename.endswith('xls'):
            raise 'Not YuEBao!'
        data = xlrd.open_workbook(filename)
        table = data.sheets()[0]
        rows_value = table.row_values(0)
        if rows_value[0] != '余额宝收支明细查询':
            raise 'Not YuEBao!'
        self.book = data
        self.table = table
        self.deduplicate = Deduplicate(entries, option_map)

    def parse(self):
        table = self.table
        rows = table.nrows
        for i in range(5, rows - 4):
            row = table.row_values(i)
            time = datetime.datetime(
                *xlrd.xldate_as_tuple(table.cell_value(rowx=i, colx=0), self.book.datemode))
            print("Importing {} price = {} balance = {}".format(
                time, row[2], row[3]))
            meta = {}
            amount = float(row[1])

            entry = Transaction(
                meta,
                date(time.year, time.month, time.day),
                '*',
                '余额宝',
                '余额宝',
                data.EMPTY_SET,
                data.EMPTY_SET, []
            )

            if not row[2] in incomes:
                amount = -amount

            if not self.deduplicate.find_duplicate(entry, amount, None, Account余额宝):
                print(
                    "Unknown transaction for {}, check if Alipay transaction exists.".format(time))

        self.deduplicate.apply_beans()
        return []
