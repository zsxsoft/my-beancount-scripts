my-beancount-scripts
=====================

Beancount 我的个人自用脚本，包含以下功能：

1. 账单导入
   - 支付宝（CSV）
   - 微信（CSV）
   - 中信银行信用卡（EML邮件）
   - 民生银行信用卡（EML邮件）
2. 账单去重
   - 支付宝的账单**不包含**支付渠道，因此如果同时导入支付宝和银行账单，必然会重复。另外由于个人有手工记账的习惯，因此导入账单时也可能出现重复现象。
   - 脚本根据金额与时间判断两笔交易是否相同，如发现正在导入的交易已经存在，则自动为原先已存在的交易添加支付宝和微信的订单号及时间戳，避免重复添加。
   - 如果同一天存在两笔同金额交易，则需要**人工处理**。
3. 价格抓取（基于bean-price）
   - 10jqka抓取同花顺数据
   - coinmarketcap抓取BTC数据
   - 中国银行（BOC）抓取人民币外汇数据

## 使用

### 账单导入

```bash
python import.py ~/民生信用卡2019年09月电子对账单.eml
python import.py ./alipay_record_20191007_1634_1.csv
python import.py 微信支付账单\(20190802-20190902\).csv --out out.bean
```
其会自动识别文件类型，自动进行编码转换，不需人工判断。
配置见``accounts.py``.

因为支付宝的账单非常弱智，因此支付宝余额、余额宝、花呗都被统一归结到``Assets:Company:Alipay:StupidAlipay``，这个账户没有任何价值，建议自行设置余额宝、花呗等的余额，并将该账户pad到0.00余额。

### 价格抓取

示例配置：

```beancount
; 同花顺基金抓取
2010-01-01 commodity F161725
  export: "F161725"
  price: "CNY:modules.price_sources.10jqka/161725"

; CoinMarketCap 加密货币抓取
2010-01-01 commodity BTC
  export: "BTC"
  price: "CNY:modules.price_sources.coinmarketcap/bitcoin--cny"

; 中行人民币外汇抓取
2010-01-01 commodity JPY
  export: "JPY"
  price: "CNY:modules.price_sources.boc/1323"
  ; 请打开网页 http://www.boc.cn/sourcedb/whpj/
  ; 之后打开浏览器控制台，输入：$('#pjname option').each((a, b) => console.log(b.value + ' ' + b.innerText))
  ; 按下回车后，即可显示所有对应数字。例如，1323代表日元，1314代表英镑等。
```

```bash
export PYTHONPATH=$(pwd)
bean-price main.bean -d 2019-04-01
```

## 开源协议

The MIT License
