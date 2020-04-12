import argparse
import json
import os
import re
import tempfile
import time
from datetime import date
from os import path
from shutil import copyfile
from string import Template

import requests
from beancount import loader
from beancount.query import query

currency = 'F111111'  # 该基金在Beancount里记录的货币单位
ticker = '111111'  # 基金代码
price = 1000  # 定投金额
fee = 0.0013  # 手续费
FeeAccount = 'Expenses:Finance:TradeFee'  # 手续费账户
DeviationAccount = 'Equity:Deviation'  # 误差舍入账户
FundAccount = 'Assets:Company:Alipay:Fund'  # 基金账户
transactionTemplate = Template(
    '''  $fundAccount $fundCount $fundCurrency { $costPrice CNY }
  $feeAccount $fee CNY
  $deviationAccount
  $otherAccount -$originalPrice CNY''')

cache_file = path.join(tempfile.gettempdir() + '/fund-temp.json')
fund_data = {}
if path.exists(cache_file):
    content = open(cache_file, 'r').read()
    fund_data = json.loads(content)
else:
    content = requests.get(
        "http://fund.10jqka.com.cn/{}/json/jsondwjz.json".format(ticker)).content
    content = content.split(b"=")[1]
    f = open(cache_file, 'wb')
    f.write(content)
    f.close()
    fund_data = json.loads(str(content))


class Fund:

    def __init__(self, entries, option_map):
        self.entries = entries
        self.option_map = option_map
        self.beans = {}

    def find_funds(self, price):
        bql = "SELECT flag, filename, lineno, location, account, other_accounts, year, month, day, number, currency where account = \"{}\" and currency = \"CNY\" and number = {}".format(
            FundAccount, price)
        items = query.run_query(self.entries, self.option_map, bql)
        # length = len(items[1])
        feePrice = round(price * fee, 2)

        for item in items[1]:
            current_date = date(item.year, item.month, item.day)
            date_string = current_date.strftime("%Y%m%d")
            print('Updating ' + date_string)
            for fund_item in fund_data:
                if fund_item[0] == date_string:
                    fund_price = float(fund_item[1])
                    count = (price - feePrice) / fund_price
                    self.update_line_to_new_line(item.location, transactionTemplate.substitute(
                        fundAccount=FundAccount,
                        fundCount=round(count, 2),
                        fundCurrency=currency,
                        costPrice=round(fund_price, 5),
                        feeAccount=FeeAccount,
                        fee=feePrice,
                        deviationAccount=DeviationAccount,
                        otherAccount=item.other_accounts[0],
                        originalPrice=price
                    ), 1)

    def read_bean(self, filename):
        if filename in self.beans:
            return self.beans[filename]
        with open(filename, 'r') as f:
            text = f.read()
            self.beans[filename] = text.split('\n')
        return self.beans[filename]

    def update_line_to_new_line(self, location, new_line, expand_index=0):
        file_items = location.split(':')
        lineno = int(file_items[1])
        lines = self.read_bean(file_items[0])
        lines[lineno - 1] = new_line
        for i in range(0, expand_index):
            lines[lineno + i] = ''

    def apply_beans(self):
        for filename in self.beans:
            #copyfile(filename, filename + '.bak')
            with open(filename, 'w') as f:
                f.write('\n'.join(self.beans[filename]))


parser = argparse.ArgumentParser("import")
parser.add_argument(
    "--entry", help="Entry bean path (default = main.bean)", default='main.bean')
args = parser.parse_args()

entries, errors, option_map = loader.load_file(args.entry)
f = Fund(entries, option_map)
f.find_funds(price)
f.apply_beans()
