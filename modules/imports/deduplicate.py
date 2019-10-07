from beancount.query import query
from shutil import copyfile
from ..accounts import public_accounts

class Deduplicate:

  def __init__(self, entries, option_map):
    self.entries = entries
    self.option_map = option_map
    self.beans = {}

  def find_duplicate(self, entry, money, unique_no = None, replace_account = '', currency = 'CNY'):
    # 要查询的是实际付款的账户，而不是支出信息
    bql = "SELECT flag, filename, lineno, location, account, year, month, day, str(entry_meta('timestamp')) as timestamp, metas() as metas WHERE year = {} AND month = {} AND day = {} AND number(convert(units(position), '{}')) = {} ORDER BY timestamp ASC".format(entry.date.year, entry.date.month, entry.date.day, currency, money)
    items = query.run_query(self.entries, self.option_map, bql)
    length = len(items[1])
    if (length == 0):
      return False
    updated_items = []
    for item in items[1]:
      same_trade = False
      item_timestamp = item.timestamp.replace("'", '')
      # 如果已经被录入了，且unique_no相同，则判定为是同导入器导入的同交易，啥都不做
      if unique_no != None:
        if unique_no in entry.meta and unique_no in item.metas:
          if item.metas[unique_no] == entry.meta[unique_no]:
            same_trade = True
          # unique_no存在但不同，那就绝对不是同一笔交易了
          # 这个时候就直接返回不存在同订单
          else:
            return False
      if same_trade:
        return True
      # 否则，可能是不同账单的同交易，此时判断时间
      # 如果时间戳相同，或某个导入器的数据没有时间戳，则判断其为「还需进一步处理」的同笔交易
      # 例如，手工输入的交易，打上支付宝订单号。
      # 另外因为支付宝的傻逼账单，这里还需要承担支付手段更新的功能
      if (
        (not 'timestamp' in entry.meta) or
        item_timestamp == entry.meta['timestamp'] or
        item.timestamp == 'None' or
        item.timestamp == ''
      ):
        updated_items.append(item)
        if replace_account != '' and item.account in public_accounts:
          self.update_transaction_account(item.location, item.account, replace_account)
        for key, value in entry.meta.items():
          if key == 'filename' or key == 'lineno':
            continue
          if not key in item.metas:
            self.append_text_to_transaction(item.filename, item.lineno, '{}: "{}"'.format(key, value))
        # 如果有时间戳，且时间戳相同，则判定为同交易
        # 100%确认是同一笔交易后，就没必要再给其他的「金额相同」的交易加信息了
        if 'timestamp' in entry.meta and item_timestamp == entry.meta['timestamp']:
          break
    if len(updated_items) > 1:
      for item in updated_items:
        self.update_transaction_flag(item.location, item.flag, '!')
    return len(updated_items) > 0

  def read_bean(self, filename):
    if filename in self.beans:
      return self.beans[filename]
    with open(filename, 'r') as f:
      text = f.read()
      self.beans[filename] = text.split('\n')
    return self.beans[filename]

  def update_transaction_account(self, location, old_account, new_account):
    file_items = location.split(':')
    lineno = int(file_items[1])
    lines = self.read_bean(file_items[0])
    lines[lineno - 1] = lines[lineno - 1].replace(old_account, new_account)
    print("Updated account from {} to {} at {}".format(old_account, new_account, location))

  def append_text_to_transaction(self, filename, lineno, text):
    lines = self.read_bean(filename)
    lines[lineno - 1] += '\n	' + text
    print("Appended meta {} to {}:{}".format(text, filename, lineno))

  def update_transaction_flag(self, location, old_flag, new_flag):
    file_items = location.split(':')
    lineno = int(file_items[1])
    lines = self.read_bean(file_items[0])
    lines[lineno - 1] = lines[lineno - 1].replace(old_flag, new_flag, 1)
    print("Updated flag to {} at {}".format(new_flag, location))

  def apply_beans(self):
    for filename in self.beans:
      copyfile(filename, filename + '.bak')
      with open(filename, 'w') as f:
        f.write('\n'.join(self.beans[filename]))
