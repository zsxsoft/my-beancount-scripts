from shutil import copyfile
import re

beans = {}

def read_bean(filename):
    if filename in beans:
        return beans[filename]
    with open(filename, 'r') as f:
        text = f.read()
        beans[filename] = text.split('\n')
    return beans[filename]

def apply_beans():
    for filename in beans:
        if filename[0] == '<':
            continue
        #copyfile(filename, filename + '.bak')
        with open(filename, 'w') as f:
            f.write('\n'.join(beans[filename]))

def update_description(location, time, payee, description, tags):
    file_items = location.split(':')
    lineno = int(file_items[1])
    lines = read_bean(file_items[0])
    for i in reversed(range(lineno - 8, lineno - 1)):
        if (re.match(r'^\d{4}-\d{2}', lines[i])):
            lines[i] = '{} * "{}" "{}" {}'.format(time, payee, description, tags)

def update_transaction_account(location, old_account, new_account):
    file_items = location.split(':')
    lineno = int(file_items[1])
    lines = read_bean(file_items[0])
    lines[lineno - 1] = lines[lineno - 1].replace(old_account, new_account)
    print("Updated account from {} to {} at {}".format(
        old_account, new_account, location))

def replace_entire_transaction(location, new_transactions):
    file_items = location.split(':')
    lineno = int(file_items[1])
    lines = read_bean(file_items[0])
    
    # 从 lineno 往前找到当前交易的日期行
    start_line = None
    for i in range(lineno - 1, max(0, lineno - 10) - 1, -1):
        if re.match(r'^\d{4}-\d{2}', lines[i]):
            start_line = i
            break
    
    if start_line is None:
        print(f"Warning: cannot find transaction start for {location}")
        return
    
    # 从 start_line 往后找到交易结束（下一个日期行或空行之后的日期行）
    end_line = start_line + 1
    while end_line < len(lines):
        line = lines[end_line]
        # 遇到新的日期行，说明当前交易结束
        if re.match(r'^\d{4}-\d{2}', line):
            break
        end_line += 1
    
    # 清空 start_line 到 end_line 之间的行
    for i in range(start_line, end_line):
        lines[i] = ''
    lines[start_line] = new_transactions.rstrip('\n')
