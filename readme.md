my-beancount-scripts
=====================

Beancount 我的个人自用脚本，包含以下功能：

1. 账单导入
   - 支付宝（CSV）
   - 微信（CSV）
   - 余额宝（XLS）（不用于导入，仅用于支付宝账单去重）
   - 中信银行信用卡（EML邮件）
   - 民生银行信用卡（EML邮件）
   - 招商银行信用卡（EML邮件）
   - 工商银行对账单（邮件附件）（仅余额与交易明细部分）
   - 京东订单（仅商品信息与价格）
2. 账单去重
   - 由于个人有手工记账的习惯，因此导入账单时可能出现重复现象。脚本根据金额与时间判断两笔交易是否相同，如果是，则不会导入这笔交易，但有可能添加额外信息（见下）。
   - 如果同一天存在两笔同金额交易，则需要**人工处理**。
   - 由于支付宝的账单**不包含**支付渠道，因此支付宝账单都被统一归结到``Assets:Company:Alipay:StupidAlipay``账户之下。当导入银行卡账单和余额宝账单的时候，如果发现待导入的交易与一笔账户为``StupidAlipay``的交易相同时，会自动将``StupidAlipay``修改为正确的账户。
   - 如果同时导入支付宝、微信和银行账单，必然会重复。如在导入支付宝、微信账单时，发现正在导入的交易已经存在，则会为原先已存在的交易添加支付宝和微信的订单号及时间戳，不会重复导入同一笔交易。
3. 价格抓取（基于bean-price）
   - 10jqka抓取同花顺数据
   - coinmarketcap抓取BTC数据
   - 中国银行（BOC）抓取人民币外汇数据
4. 蚂蚁财富基金定投数据导入

## 使用

**脚本需要自行修改``accounts.py``配置后才可使用**，另外某些导入器可能存在问题，使用前请务必翻阅Issue区。

### 账单导入

```bash
python import.py ~/民生信用卡2019年09月电子对账单.eml
python import.py ./alipay_record_20191007_1634_1.csv
python import.py 微信支付账单\(20190802-20190902\).csv --out out.bean
```
其会自动识别文件类型，自动进行编码转换，不需人工判断。
配置见``accounts.py``.

#### 京东订单
京东订单仅导入商品名和优惠后价格。在浏览器内安装TamperMonkey等UserScript扩展后，[安装此UserScript](https://github.com/zsxsoft/my-beancount-scripts/raw/master/jd.user.js)，刷新京东订单页面，即可在浏览器控制台内看到输出。

### 我的导入顺序

推荐的导入顺序：支付宝、微信、余额宝、银行卡账单。

1. 先导入支付宝和微信账单，因为这两个支付方式留有最多的信息，方便对账。
2. 导入余额宝账单。该导入器**不会**添加任何交易，其唯一的作用是，将已经导入的支付宝账单里时间和金额匹配的交易的支付手段改为余额宝。
3. 导入银行卡账单。由于账单去重的存在，不会重复导入之前通过支付宝和微信已导入的交易，且会自动修复支付方式不正确的支付宝账单。
4. 对于支付宝，检查一下还有多少笔交易在使用``Assets:Company:Alipay:StupidAlipay``这个账户。它有可能是余额支付、花呗支付、网商银行支付等。与支付宝账单对照，手动将所有的``StupidAlipay``改为正确的支付手段。所以**最好不要使用花呗，支付宝余额也尽量调为0**，这样就能免去重新对账的麻烦了。
5. 手动添加``balance``指令，并对照余额是否正确，账单是否全部导入。

### 获得账单

#### 支付宝
支付宝电脑端，「[查看所有交易记录](https://consumeprod.alipay.com/record/standard.htm)」，在其下方找到「下载查询结果」，扫码后可得到zip文件，解压后可得csv。

#### 微信

手机进入微信支付->钱包->（右上角）账单->右上角...->账单下载，之后可在邮箱中得到zip文件，解压后可得csv。

#### 信用卡账单

目前仅测试了Outlook for Mac的邮件导出，可能不适用其他邮件客户端。导出路径为打开邮件后->文件->另存为，可得eml文件。

##### 招商银行信用卡

招商银行默认只发送「电邮盖章」邮件，如需对账则需要「电邮账单」类型。获取方式为：掌上生活->金融->查账单->右上角...->账单服务->账单补寄->(寄送方式改为「电邮账单」)->申请补寄。

#### 余额宝

支付宝电脑端，点击「余额收支明细」下拉菜单，找到「[余额宝收支明细](https://yebprod.alipay.com/yeb/asset.htm)」。在页面下方可找到下载按钮，可得指定日期的xls。

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
  price: "CNY:modules.price_sources.boc/_E6_97_A5_E5_85_83"
  ; 请打开网页 http://www.boc.cn/sourcedb/whpj/
  ; 之后打开浏览器控制台，输入：
  ; $('#pjname option').each((a, b) => console.log(encodeURIComponent(b.value).replace(/%/g,'_') + ' ' + b.innerText))
  ; 按下回车后，即可显示所有对应字符串。例如，_E8_8B_B1_E9_95_91代表英镑等。
```

```bash
export PYTHONPATH=$(pwd)
bean-price main.bean -d 2019-04-01
```

#### 蚂蚁财富基金定投数据导入

支付宝的「基金定投」在账单中不显示具体认购份额和净值，本repo内的``fund.py``可对其进行处理。其基于同花顺抓取的基金数据，将以下交易：
```beancount
2018-07-24 * "蚂蚁财富-蚂蚁（杭州）基金销售有限公司" "蚂蚁财富-XXX基金-买入"
  Assets:Company:Alipay:Fund   200 CNY
  Assets:Company:Alipay:Yuebao
```
改变为
```beancount
2018-07-24 * "蚂蚁财富-蚂蚁（杭州）基金销售有限公司" "蚂蚁财富-XXX基金-买入"
  Assets:Company:Alipay:Fund 99.87 FXXXXXXX { 2.000 CNY }
  Expenses:Finance:TradeFee 0.26 CNY
  Equity:Deviation
  Assets:Company:Alipay:Yuebao -200 CNY
```
具体使用请直接修改``fund.py``。

## 开源协议

The MIT License
