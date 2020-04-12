from datetime import date
from beancount.core import data
from beancount.core.data import Transaction, Note
from .deduplicate import Deduplicate
from .base import Base
from . import DictReaderStrip, get_account_by_guess, get_income_account_by_guess
from io import StringIO
import csv
import dateparser
import calendar

Account支付宝 = 'Assets:Company:Alipay:StupidAlipay'


class Alipay(Base):

    def __init__(self, filename, byte_content, entries, option_map):
        content = byte_content.decode('gbk')
        lines = content.split("\n")
        if (lines[0] != '支付宝交易记录明细查询\r'):
            raise 'Not Alipay Trade Record!'
        print('Import Alipay: ' + lines[2])
        content = "\n".join(lines[4:len(lines) - 8])
        self.content = content
        self.deduplicate = Deduplicate(entries, option_map)

    def parse(self):
        content = self.content
        f = StringIO(content)
        reader = DictReaderStrip(f, delimiter=',')
        transactions = []
        for row in reader:
            if row['交易状态'] == '交易关闭' and row['资金状态'] == '':
                continue
            time = row['付款时间']
            if time == '':
                time = row['交易创建时间']
            print("Importing {} at {}".format(row['商品名称'], time))
            meta = {}
            time = dateparser.parse(time)
            meta['alipay_trade_no'] = row['交易号']
            meta['trade_time'] = str(time)
            meta['timestamp'] = str(time.timestamp()).replace('.0', '')
            account = get_account_by_guess(row['交易对方'], row['商品名称'], time)
            flag = "*"
            amount = float(row['金额（元）'])
            if account == "Unknown":
                flag = "!"

            if row['备注'] != '':
                meta['note'] = row['备注']

            if row['商家订单号'] != '':
                meta['shop_trade_no'] = row['商家订单号']

            meta = data.new_metadata(
                'beancount/core/testing.beancount',
                12345,
                meta
            )
            entry = Transaction(
                meta,
                date(time.year, time.month, time.day),
                flag,
                row['交易对方'],
                row['商品名称'],
                data.EMPTY_SET,
                data.EMPTY_SET, []
            )
            data.create_simple_posting(entry, account, row['金额（元）'], 'CNY')
            if row['资金状态'] == '已支出':
                data.create_simple_posting(entry, Account支付宝, None, None)
                amount = -amount
            elif row['资金状态'] == '资金转移':
                data.create_simple_posting(entry, Account支付宝, None, None)
            elif row['资金状态'] == '已收入':
                income = get_income_account_by_guess(
                    row['交易对方'], row['商品名称'], time)
                if income == 'Income:Unknown':
                    entry = entry._replace(flag='!')
                data.create_simple_posting(entry, income, None, None)
            else:
                print('Unknown status')
                print(row)

            if (row['服务费（元）'] != '0.00'):
                data.create_simple_posting(
                    entry, 'Expenses:Fee', row['服务费（元）'], 'CNY')

            #b = printer.format_entry(entry)
            # print(b)
            if not self.deduplicate.find_duplicate(entry, amount, 'alipay_trade_no'):
                transactions.append(entry)

        self.deduplicate.apply_beans()
        return transactions
