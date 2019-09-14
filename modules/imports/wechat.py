from datetime import date
from beancount.core import data
from beancount.core.data import Transaction, Note
from .deduplicate import Deduplicate
from .base import Base
from . import DictReaderStrip, get_account_by_guess, get_income_account_by_guess, replace_flag
from io import StringIO
from ..accounts import accounts
import csv
import dateparser
import calendar

Account零钱通 = 'Assets:Company:WeChat:MonetaryFund'
Account红包 = 'Income:RedBag'
Account余额 = 'Assets:Balances:WeChat'

class WeChat(Base):

	def __init__ (self, filename, byte_content, entries, option_map):
		content = byte_content.decode("utf-8-sig")
		lines = content.split("\n")
		if (lines[0].replace(',', '') != '微信支付账单明细\r'):
			raise 'Not WeChat Trade Record!'

		print('Import WeChat: ' + lines[2])
		content = "\n".join(lines[16:len(lines)])
		self.content = content
		self.deduplicate = Deduplicate(entries, option_map)

	def parse(self):
		content = self.content
		f = StringIO(content)
		reader = DictReaderStrip(f, delimiter=',')
		transactions = []
		for row in reader:
			print("Importing {} at {}".format(row['商品'], row['交易时间']))
			meta = {}
			time = dateparser.parse(row['交易时间'])
			meta['wechat_trade_no'] = row['交易单号']
			meta['trade_time'] = row['交易时间']
			meta['timestamp'] = str(time.timestamp()).replace('.0', '')
			account = get_account_by_guess(row['交易对方'], row['商品'], time)
			flag = "*"
			amount_string = row['金额(元)'].replace('¥', '')
			amount = float(amount_string)

			if row['商户单号'] != '/':
				meta['shop_trade_no'] = row['商户单号']

			if row['备注'] != '/':
				meta['note'] = row['备注']

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
				row['商品'],
				data.EMPTY_SET,
				data.EMPTY_SET, []
			)

			if row['当前状态'] == '支付成功':
				if '转入零钱通' in row['交易类型']:
					entry = entry._replace(payee = '')
					entry = entry._replace(narration = '转入零钱通')
					data.create_simple_posting(entry, Account零钱通, amount_string, 'CNY')
				else:
					account = get_account_by_guess(row['交易对方'], row['商品'], time)
					if account == "Unknown":
						entry = replace_flag(entry, '!')
					data.create_simple_posting(entry, account, amount_string, 'CNY')
				data.create_simple_posting(entry, accounts[row['支付方式']], None, None)
				amount = -amount
			elif row['当前状态'] == '已存入零钱':
				if '微信红包' in row['交易类型']:
					data.create_simple_posting(entry, Account红包, amount_string, 'CNY')
				else:
					income = get_income_account_by_guess(row['交易对方'], row['商品'], time)
					if income == 'Income:Unknown':
						entry = replace_flag(entry, '!')
					data.create_simple_posting(entry, income, amount_string, 'CNY')
				data.create_simple_posting(entry, Account余额, None, None)
			else:
				print('Unknown row', row)
			
			#b = printer.format_entry(entry)
			#print(b)
			if not self.deduplicate.find_duplicate(entry, amount):
				transactions.append(entry)
				
		self.deduplicate.apply_beans()
		return transactions
