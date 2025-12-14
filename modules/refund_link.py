from beancount.core.data import Transaction

__plugins__ = ['refund_link']

def refund_link(entries, options_map):
    errors = []
    trade_map = {}
    for index, entry in enumerate(entries):
        if isinstance(entry, Transaction):
            trade_no = ''
            if 'alipay_trade_no' in entry.meta:
                trade_no = entry.meta['alipay_trade_no']
            trade_no = trade_no.split('_')[0]
            if trade_no != '':
                if trade_no not in trade_map:
                    trade_map[trade_no] = []
                trade_map[trade_no].append(index)
                if len(trade_map[trade_no]) >= 2:
                    for trade_index in trade_map[trade_no]:
                        link_name = 'L_' + trade_no
                        links = frozenset([link_name]).union(entries[trade_index].links)
                        entries[trade_index] = entries[trade_index]._replace(links=links)

    return entries, errors
