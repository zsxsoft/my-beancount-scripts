from shutil import copyfile
from itertools import combinations
from collections import namedtuple
from beancount import loader
from beancount.parser import printer

from beanquery import query

from ..accounts import public_accounts


def _get_object_bql_result(ret):
    """内部使用的BQL结果转换函数，避免循环导入"""
    rtypes, rvalues = ret
    result = []
    keys = [k[0] for k in rtypes]
    for v in rvalues:
        d = {}
        for i, vv in enumerate(v):
            if isinstance(vv, int) or isinstance(vv, float) or vv is None:
                vv = str(vv)
            d[keys[i]] = vv
        t = namedtuple('Struct', keys)(**d)
        result.append(t)
    return result


# 全局未匹配交易收集器
_unmatched_imported = []  # 导入账单中未匹配的交易
_unmatched_beancount = []  # Beancount账本中未匹配的交易
_matched_beancount_locations = set()  # 已匹配的Beancount交易位置


def get_unmatched_imported():
    return _unmatched_imported


def get_unmatched_beancount():
    return _unmatched_beancount


def clear_unmatched():
    global _unmatched_imported, _unmatched_beancount, _matched_beancount_locations
    _unmatched_imported = []
    _unmatched_beancount = []
    _matched_beancount_locations = set()


def write_unmatched_report(output_file='out-unmatched.bean'):
    """将未匹配的交易输出到文件"""
    all_unmatched = []
    
    # 添加导入账单中未匹配的交易
    for entry, source in _unmatched_imported:
        all_unmatched.append((entry.date, 'imported', source, entry))
    
    # 添加Beancount账本中未匹配的交易
    for item, account in _unmatched_beancount:
        all_unmatched.append((item.date, 'beancount', account, item))
    
    # 按日期倒序排序
    all_unmatched.sort(key=lambda x: x[0], reverse=True)
    if len(all_unmatched) == 0:
        return
    
    with open(output_file, 'w') as f:
        f.write("; 未匹配交易报告\n")
        f.write("; ================\n\n")
        
        for date, side, source, entry in all_unmatched:
            if side == 'imported':
                f.write(f"; [导入账单多余] 来源: {source}\n")
                f.write(printer.format_entry(entry))
                f.write("\n")
            else:
                f.write(f"; [Beancount账本多余] 账户: {source}\n")
                f.write(f"; 位置: {entry.location}\n")
                f.write(f"; 日期: {entry.date}, 金额: {entry.amount}\n\n")
    
    print(f"未匹配交易报告已写入: {output_file}")
    print(f"  - 导入账单多余: {len(_unmatched_imported)} 笔")
    print(f"  - Beancount账本多余: {len(_unmatched_beancount)} 笔")


class Deduplicate:

    def __init__(self, entries, option_map, source_name=''):
        self.entries = entries
        self.option_map = option_map
        self.beans = {}
        self.source_name = source_name  # 用于标识导入来源

    def find_duplicate(self, entry, money, unique_no=None, replace_account='', currency='CNY'):
        # 要查询的是实际付款的账户，而不是支出信息
        bql = "SELECT flag, filename, lineno, location, account, year, month, day, str(entry_meta('timestamp')) as timestamp, metas() as metas WHERE year = {} AND month = {} AND day = {} AND number(convert(units(position), '{}')) = {} ORDER BY timestamp ASC".format(
            entry.date.year, entry.date.month, entry.date.day, currency, money)
        items = query.run_query(self.entries, self.option_map, bql)
        items = _get_object_bql_result(items)
        length = len(items)
        if (length == 0):
            # 精确匹配失败，尝试子集和匹配
            if replace_account != '':
                subset_matched = self.find_subset_sum_match(entry, money, replace_account, currency)
                if subset_matched:
                    return True
            # 仍未匹配，记录为未匹配的导入交易
            _unmatched_imported.append((entry, self.source_name))
            return False
        updated_items = []
        for item in items:
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
                        # 精确匹配失败，尝试子集和匹配
                        if replace_account != '':
                            subset_matched = self.find_subset_sum_match(entry, money, replace_account, currency)
                            if subset_matched:
                                return True
                        _unmatched_imported.append((entry, self.source_name))
                        return False
            if same_trade:
                # 标记为已匹配
                _matched_beancount_locations.add(item.location)
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
                # 标记为已匹配
                _matched_beancount_locations.add(item.location)
                if replace_account != '' and item.account in public_accounts:
                    self.update_transaction_account(
                        item.location, item.account, replace_account)
                for key, value in entry.meta.items():
                    if key == 'filename' or key == 'lineno':
                        continue
                    if not key in item.metas:
                        self.append_text_to_transaction(
                            item.filename, int(item.lineno), '{}: "{}"'.format(key, value))
                # 如果有时间戳，且时间戳相同，则判定为同交易
                # 100%确认是同一笔交易后，就没必要再给其他的「金额相同」的交易加信息了
                if 'timestamp' in entry.meta and item_timestamp == entry.meta['timestamp']:
                    break
        if len(updated_items) > 1:
            for item in updated_items:
                self.update_transaction_flag(item.location, item.flag, '!')
        return len(updated_items) > 0

    def find_subset_sum_match(self, entry, target_amount, replace_account, currency='CNY'):
        """
        查找同一天内、隶属于replace_account的交易，
        若某几笔金额相加等于target_amount，则视为匹配。
        使用动态规划子集和算法。
        """
        # 查询同一天、同账户的所有交易
        bql = """SELECT flag, filename, lineno, location, account, year, month, day, 
                 number(convert(units(position), '{}')) as amount,
                 str(entry_meta('timestamp')) as timestamp, metas() as metas 
                 WHERE year = {} AND month = {} AND day = {} 
                 AND account = '{}' 
                 ORDER BY timestamp ASC""".format(
            currency, entry.date.year, entry.date.month, entry.date.day, replace_account)
        
        items = query.run_query(self.entries, self.option_map, bql)
        items = _get_object_bql_result(items)
        
        if len(items) == 0:
            return False
        
        # 过滤掉已经匹配的交易
        available_items = [item for item in items if item.location not in _matched_beancount_locations]
        
        if len(available_items) == 0:
            return False
        
        # 提取金额列表
        amounts_with_items = []
        for item in available_items:
            try:
                amount = float(item.amount)
                amounts_with_items.append((amount, item))
            except (ValueError, TypeError):
                continue
        
        if len(amounts_with_items) == 0:
            return False
        
        target = round(target_amount, 2)
        
        # 使用动态规划查找子集和
        # 将金额转换为整数（乘以100）以避免浮点精度问题
        int_amounts = [(int(round(a * 100)), item) for a, item in amounts_with_items]
        int_target = int(round(target * 100))
        
        # 动态规划：dp[sum] = 组成该sum的item索引列表，或None表示不可达
        # 为了处理负数，使用字典而不是数组
        dp = {0: []}
        
        for idx, (amount, item) in enumerate(int_amounts):
            # 从大到小遍历避免重复使用同一个元素
            new_dp = {}
            for s, indices in dp.items():
                new_sum = s + amount
                if new_sum not in dp and new_sum not in new_dp:
                    new_dp[new_sum] = indices + [idx]
            dp.update(new_dp)
            
            # 检查是否找到目标（允许1分钱误差）
            for offset in [-1, 0, 1]:
                check_target = int_target + offset
                if check_target in dp:
                    matched_indices = dp[check_target]
                    matched_locations = []
                    matched_amounts = []
                    for i in matched_indices:
                        _, item = int_amounts[i]
                        _matched_beancount_locations.add(item.location)
                        matched_locations.append(item.location)
                        matched_amounts.append(amounts_with_items[i][0])
                    
                    print(f"子集和匹配成功: {target_amount} = {' + '.join(str(a) for a in matched_amounts)}")
                    print(f"  匹配的交易数量: {len(matched_locations)}")
                    return True
        
        return False

    def collect_unmatched_beancount(self, replace_account, start_date=None, end_date=None, currency='CNY'):
        """
        收集Beancount账本中未匹配的交易（属于replace_account的）
        """
        date_filter = ""
        if start_date:
            date_filter += f" AND date >= {start_date}"
        if end_date:
            date_filter += f" AND date <= {end_date}"
        
        bql = """SELECT flag, filename, lineno, location, account, date,
                 number(convert(units(position), '{}')) as amount,
                 str(entry_meta('timestamp')) as timestamp, metas() as metas 
                 WHERE account = '{}' {}
                 ORDER BY date DESC""".format(currency, replace_account, date_filter)
        
        items = query.run_query(self.entries, self.option_map, bql)
        items = _get_object_bql_result(items)
        
        for item in items:
            if item.location not in _matched_beancount_locations:
                _unmatched_beancount.append((item, replace_account))

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
        print("Updated account from {} to {} at {}".format(
            old_account, new_account, location))

    def append_text_to_transaction(self, filename, lineno, text):
        if filename[0] == '<':
            return
        lines = self.read_bean(filename)
        lines[lineno - 1] += '\n	' + text
        print("Appended meta {} to {}:{}".format(text, filename, lineno))

    def update_transaction_flag(self, location, old_flag, new_flag):
        if len(location) <= 0:
            return
        if location[0] == '<':
            return
        file_items = location.split(':')
        lineno = int(file_items[1])
        lines = self.read_bean(file_items[0])
        lines[lineno - 1] = lines[lineno - 1].replace(old_flag, new_flag, 1)
        print("Updated flag to {} at {}".format(new_flag, location))

    def apply_beans(self):
        for filename in self.beans:
            if filename[0] == '<':
                continue
            copyfile(filename, filename + '.bak')
            with open(filename, 'w') as f:
                f.write('\n'.join(self.beans[filename]))
