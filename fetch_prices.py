#!/usr/bin/env python3
"""
价格获取脚本 - 替代 bean-price

功能：
1. 在指定日期范围内，按间隔查找使用了哪些货币单位且没有设置 price
2. 周六向前推一天，周日向后推一天
3. 批量查询 API
"""

import argparse
from datetime import datetime, timedelta
from collections import defaultdict
import importlib

from beancount import loader
from beancount.core import data
from beancount.parser import printer


def adjust_weekend(d):
    """周六向前推一天，周日向后推一天（但如果周一是未来则跳过）"""
    today = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
    w = d.weekday()
    if w == 5:  # 周六
        return d - timedelta(days=1)
    if w == 6:  # 周日
        monday = d + timedelta(days=1)
        if monday > today:
            return None  # 跳过这天
        return monday
    return d


def get_commodities_config(entries):
    """获取配置了 price 的货币: {commodity: (quote_currency, module_path, ticker)}"""
    result = {}
    for entry in entries:
        if isinstance(entry, data.Commodity) and 'price' in entry.meta:
            spec = entry.meta['price']
            quote, source_spec = spec.split(':', 1)
            module, ticker = source_spec.rsplit('/', 1)
            result[entry.currency] = (quote, module, ticker)
    return result


def get_existing_prices(entries):
    """获取已存在的价格: {(commodity, date_str)}"""
    return {(e.currency, e.date.strftime('%Y-%m-%d')) for e in entries if isinstance(e, data.Price)}


def get_latest_price_dates(entries, commodities):
    """
    获取指定货币的最新价格日期
    返回: {commodity: date}
    """
    result = {}
    for entry in entries:
        if isinstance(entry, data.Price) and entry.currency in commodities:
            if entry.currency not in result or entry.date > result[entry.currency]:
                result[entry.currency] = entry.date
    return result


def get_active_commodities(entries, config, end_date):
    """
    获取在 end_date 当天余额不为0的货币（配置了价格源的）
    返回: set of commodity
    """
    from beancount.core import inventory
    
    # 计算截止 end_date 的余额
    balances = defaultdict(inventory.Inventory)
    
    for entry in entries:
        if isinstance(entry, data.Transaction) and entry.date <= end_date.date():
            for posting in entry.postings:
                if posting.units:
                    balances[posting.units.currency].add_position(posting)
    
    # 筛选余额不为0且配置了价格源的货币
    active = set()
    for currency, inv in balances.items():
        if currency in config and not inv.is_empty():
            active.add(currency)
    
    return active


def get_default_start(entries, config, end_date):
    """
    默认开始日期：在 end_date 活跃的货币中，各自最新价格日期里最老的那个
    """
    active = get_active_commodities(entries, config, end_date)
    if not active:
        return None
    
    latest_dates = get_latest_price_dates(entries, active)
    if not latest_dates:
        return None
    
    oldest = min(latest_dates.values())
    return datetime.combine(oldest, datetime.min.time())


def get_sample_dates(start, end, interval):
    """生成采样日期列表"""
    samples = []
    cur = start
    while cur <= end:
        samples.append(cur)
        cur += timedelta(days=interval)
    return samples


def main():
    parser = argparse.ArgumentParser(description="价格获取脚本")
    parser.add_argument("--entry", default="main.bean")
    parser.add_argument("--start", help="开始日期 YYYY-MM-DD (默认: 各货币最新价格日期中最老的)")
    parser.add_argument("--end", help="结束日期 YYYY-MM-DD (默认: 今天)")
    parser.add_argument("--interval", type=int, default=3, help="采样间隔天数")
    parser.add_argument("--out", default="prices.bean")
    parser.add_argument("--dry-run", action="store_true", help="仅显示需要获取的价格")
    parser.add_argument("--commodities", help="仅获取指定货币，逗号分隔")
    args = parser.parse_args()
    
    print(f"加载账本: {args.entry}")
    entries, errors, _ = loader.load_file(args.entry)
    
    config = get_commodities_config(entries)
    
    if args.end:
        end = datetime.strptime(args.end, '%Y-%m-%d')
    else:
        end = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
    
    if args.start:
        start = datetime.strptime(args.start, '%Y-%m-%d')
    else:
        start = get_default_start(entries, config, end)
        if start is None:
            print("没有找到活跃货币的价格记录，请使用 --start 指定开始日期")
            return
    
    active_commodities = get_active_commodities(entries, config, end)
    print(f"活跃货币: {', '.join(sorted(active_commodities))}")
    print(f"日期范围: {start.strftime('%Y-%m-%d')} ~ {end.strftime('%Y-%m-%d')}")
    
    existing = get_existing_prices(entries)
    sample_dates = get_sample_dates(start, end, args.interval)
    
    filter_set = set(args.commodities.split(',')) if args.commodities else None
    
    # 按数据源分组: {module: {(commodity, ticker): [dates]}}
    by_source = defaultdict(lambda: defaultdict(list))
    
    print(f"\n=== 需要获取的价格 ===")
    for sample_date in sample_dates:
        for commodity in sorted(active_commodities):
            if commodity not in config:
                continue
            if filter_set and commodity not in filter_set:
                continue
            
            adjusted = adjust_weekend(sample_date)
            
            if adjusted is None:
                continue  # 跳过周日且周一是未来的情况
            
            adjusted_str = adjusted.strftime('%Y-%m-%d')
            
            # 检查调整后的日期是否已存在价格
            if (commodity, adjusted_str) in existing:
                continue
            
            quote, module, ticker = config[commodity]
            
            print(f"  {commodity} @ {adjusted_str} ({module.split('.')[-1]})")
            by_source[module][(commodity, ticker)].append(adjusted)
    
    total = sum(len(d) for items in by_source.values() for d in items.values())
    if total == 0:
        print("\n没有需要获取的价格")
        return
    
    print(f"\n共需获取 {total} 条价格")
    
    if args.dry_run:
        return
    
    # 获取价格
    all_prices = []
    for module_path, items in by_source.items():
        print(f"\n=== {module_path.split('.')[-1]} ===")
        
        try:
            module = importlib.import_module(module_path)
            source = module.Source()
        except Exception as e:
            print(f"  无法加载: {e}")
            continue
        
        tickers = list(items.keys())
        dates = sorted(set(d for ds in items.values() for d in ds))
        
        try:
            results = source.get_batch_prices(tickers, dates)
            for commodity, result_date, price, quote in results:
                all_prices.append(data.Price(
                    meta={}, date=result_date, currency=commodity,
                    amount=data.Amount(price, quote)
                ))
                print(f"  {commodity}: {price} {quote} @ {result_date}")
        except Exception as e:
            print(f"  获取失败: {e}")
    
    # 去重排序输出
    unique = {(p.currency, p.date): p for p in all_prices}
    sorted_prices = sorted(unique.values(), key=lambda p: (p.date, p.currency))
    
    if sorted_prices:
        with open(args.out, 'w') as f:
            for p in sorted_prices:
                f.write(printer.format_entry(p))
        print(f"\n已输出 {len(sorted_prices)} 条价格到 {args.out}")


if __name__ == '__main__':
    main()
