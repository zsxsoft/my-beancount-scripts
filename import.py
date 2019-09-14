from datetime import date
from beancount.core import data
from beancount.parser import parser, printer
from beancount import loader
from modules.imports.alipay import Alipay
from modules.imports.wechat import WeChat
from modules.imports.citic_credit import CITICCredit
import re
import argparse

parser = argparse.ArgumentParser("import")
parser.add_argument("path", help = "CSV Path")
parser.add_argument("--entry", help = "Entry bean path (default = main.bean)", default = 'main.bean')
parser.add_argument("--out", help = "Output bean path", default = 'out.bean')
args = parser.parse_args()

entries, errors, option_map = loader.load_file(args.entry)

importers = [Alipay, WeChat, CITICCredit]
instance = None
for importer in importers:
	try:
		with open(args.path, 'rb') as f:
			file_bytes = f.read()
			instance = importer(args.path, file_bytes, entries, option_map)
		break
	except:
		pass

if instance == None:
	print("No suitable importer!")
	exit(1)

new_entries = instance.parse()


with open(args.out, 'w') as f:
	printer.print_entries(new_entries, file = f)

print('Outputed to ' + args.out)
exit(0)

file = parser.parse_one('''
2018/01/15 * "测试" "测试"
	Assets:Test 300 CNY
	Income:Test

''')
print(file.postings)


file.postings[0] = file.postings[0]._replace(units = file.postings[0].units._replace(number = 100))
print(file.postings[0])

data = printer.format_entry(file)
print(data)
