import calendar
import csv
import re
from pyzipper import AESZipFile
from datetime import date
from io import BytesIO, StringIO

import dateparser
from beancount.core import data
from beancount.core.data import Note, Transaction

from ..accounts import accounts
from . import (DictReaderStrip, get_account_by_guess,
               get_income_account_by_guess, replace_flag)
from .base import Base
from .deduplicate import Deduplicate

AccountAssetUnknown = 'Assets:Unknown'
Account余利宝 = accounts['余利宝'] if '余利宝' in accounts else 'Assets:Bank:MyBank'
Account余额 = accounts['支付宝余额'] if '支付宝余额' in accounts else 'Assets:Balance:Alipay'

class AlipayProve(Base):

    def __init__(self, filename, byte_content, entries, option_map):
        if re.search(r'alipay_record_\d{8}_\d{6}.zip$', filename):
            password = input('支付宝账单密码：')
            z = AESZipFile(BytesIO(byte_content), 'r')
            z.setpassword(bytes(password.strip(), 'utf-8'))
            filelist = z.namelist()
            if len(filelist) == 1 and re.search(r'alipay_record.*\.csv$', filelist[0]):
                byte_content = z.read(filelist[0])
        content = byte_content.decode("gbk")
        lines = content.split("\n")
        if not re.search(r'支付宝（中国）网络技术有限公司', lines[0]):
            raise ValueError('Not Alipay Proven Record!')

        print('Import Alipay')
        content = "\n".join(lines[1:len(lines) - 30])
        self.content = content
        self.deduplicate = Deduplicate(entries, option_map)

    def parse(self):
        content = self.content
        f = StringIO(content)
        reader = DictReaderStrip(f, delimiter=',')
        transactions = []
        for row in reader:
            print("Importing {} at {}".format(row['商品说明'], row['交易时间']))
            meta = {}
            time = dateparser.parse(row['交易时间'])
            meta['alipay_trade_no'] = row['交易订单号']
            meta['trade_time'] = row['交易时间']
            meta['timestamp'] = str(time.timestamp()).replace('.0', '')
            account = get_account_by_guess(row['交易对方'], row['商品说明'], time)
            flag = "*"
            amount_string = row['金额']
            amount = float(amount_string)

            if row['商家订单号'] != '/':
                meta['shop_trade_no'] = row['商家订单号']

            meta = data.new_metadata(
                'beancount/core/testing.beancount',
                12345,
                meta
            )
            entry = Transaction(
                meta,
                date(time.year, time.month, time.day),
                '*',
                row['交易对方'],
                row['商品说明'],
                data.EMPTY_SET,
                data.EMPTY_SET, []
            )

            status = row['交易状态']
            trade_type = row['收/支']
            trade_account_original = row['收/付款方式']
            if trade_account_original == '余额':
                trade_account_original = '支付宝余额'
            trade_account = accounts[trade_account_original] if trade_account_original in accounts else AccountAssetUnknown

            if trade_type == '支出':
                if status in ['交易成功', '支付成功', '代付成功', '亲情卡付款成功', '等待确认收货', '等待对方发货', '交易关闭'] :
                    data.create_simple_posting(
                        entry, trade_account, '-' + amount_string, 'CNY')
                    data.create_simple_posting(
                        entry, account, None, None)
                else:
                    print(status)
                    exit(0)
            elif trade_type == '其他':
                if (  status == '退款成功' or
                      ('蚂蚁财富' in row['交易对方']    and status == '交易成功') or
                      ('红包' == trade_account_original and status == '交易成功') or
                      ('基金组合' in row['商品说明']    and status == '交易成功') or
                      ('理财赎回' in row['商品说明']    and status == '交易成功') or
                      ('退款资金提取' == row['商品说明']    and status == '提取成功')
                ):
                    data.create_simple_posting(
                        entry, trade_account, amount_string, 'CNY')
                    data.create_simple_posting(
                        entry, account, None, None)
                elif (trade_account_original == '余额宝') and status == '交易成功':
                    data.create_simple_posting(
                        entry, get_income_account_by_guess(
                            row['交易对方'], row['商品说明'], time
                        ), '-' + amount_string, 'CNY')
                    data.create_simple_posting(
                        entry, account, None, None)
                elif '转入到余利宝' in row['商品说明'] and status == '交易成功':
                    data.create_simple_posting(
                        entry, Account余利宝, amount_string, 'CNY')
                    data.create_simple_posting(
                        entry, account, None, None)
                elif '余利宝-转出到银行卡' in row['商品说明'] and status == '转出成功':
                    data.create_simple_posting(
                        entry, Account余利宝, '-' + amount_string, 'CNY')
                    data.create_simple_posting(
                        entry, account, None, None)
                elif (
                      (status == '交易成功' and '余额宝' in row['商品说明']) or
                      status == '还款成功'
                    ):
                    data.create_simple_posting(
                        entry, account, amount_string, 'CNY')
                    data.create_simple_posting(
                        entry, trade_account, None, None)
                elif (status == '交易关闭' or status == '已关闭') and trade_account_original == '':
                    #ignore it?
                    pass
                elif status == '解冻成功' or status == '信用服务使用成功':
                    # maybe should add to Liabilities?
                    pass
                else:
                    print(row)
                    exit(0)
            elif trade_type == '收入':
                if trade_account_original == '':
                    trade_account = Account余额
                if status == '交易成功':
                    data.create_simple_posting(
                        entry, get_income_account_by_guess(
                            row['交易对方'], row['商品说明'], time
                        ), '-' + amount_string, 'CNY')
                    data.create_simple_posting(
                        entry, trade_account, None, None)
                elif status == '交易关闭':
                    pass
                else:
                    print(row)
                    exit(0)
            else:
                print(row)
                exit(0)

            if not self.deduplicate.find_duplicate(entry, amount, 'alipay_trade_no'):
                transactions.append(entry)

        self.deduplicate.apply_beans()
        return transactions
