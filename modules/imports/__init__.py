from beancount.query import query, query_compile
from beancount.query.query_env import TargetsEnvironment
from ..accounts import *
import csv


def replace_flag(entry, flag):
    return entry._replace(flag='!')


def get_account_by_guess(from_user, description, time=None):
    if description != '':
        for key, value in descriptions.items():
            if description_res[key].findall(description):
                if callable(value):
                    return value(from_user, description, time)
                else:
                    return value
                break
    for key, value in anothers.items():
        if another_res[key].findall(from_user):
            if callable(value):
                return value(from_user, description, time)
            else:
                return value
            break
    return "Expenses:Unknown"


def get_income_account_by_guess(from_user, description, time=None):
    for key, value in incomes.items():
        if income_res[key].findall(description):
            return value
    return "Income:Unknown"


def get_account_by_name(name, time=None):
    if accounts.get(name, '') == '':
        return "Unknown:" + name
    else:
        return accounts.get(name)


class DictReaderStrip(csv.DictReader):
    @property
    def fieldnames(self):
        if self._fieldnames is None:
            # Initialize self._fieldnames
            # Note: DictReader is an old-style class, so can't use super()
            csv.DictReader.fieldnames.fget(self)
            if self._fieldnames is not None:
                self._fieldnames = [name.strip() for name in self._fieldnames]
        return self._fieldnames

    def __next__(self):
        if self.line_num == 0:
            # Used only for its side effect.
            self.fieldnames
        row = next(self.reader)
        self.line_num = self.reader.line_num

        # unlike the basic reader, we prefer not to return blanks,
        # because we will typically wind up with a dict full of None
        # values
        while row == []:
            row = next(self.reader)
        row = [element.strip() for element in row]
        d = dict(zip(self.fieldnames, row))
        lf = len(self.fieldnames)
        lr = len(row)
        if lf < lr:
            d[self.restkey] = row[lf:].strip()
        elif lf > lr:
            for key in self.fieldnames[lr:]:
                d[key] = self.restval.strip()
        return d


class Metas(query_compile.EvalFunction):
    __intypes__ = []

    def __init__(self, operands):
        super().__init__(operands, object)

    def __call__(self, context):
        args = self.eval_args(context)
        meta = context.entry.meta
        return meta


TargetsEnvironment.functions['metas'] = Metas
