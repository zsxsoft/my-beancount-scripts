// ==UserScript==
// @name         JD to Beancount
// @version      0.1
// @description  JD to Beancount
// @author       zsx
// @match        https://order.jd.com/*
// @match        https://details.yiyaojd.com/*
// @match        https://details.jd.com/*
// @grant        none
// ==/UserScript==

(function () {
  'use strict'
  const $ = document.querySelectorAll.bind(document)
  const getByGoodsTotal = ($) => {
    if ($('.goods-total').length > 0) {
      const fp = a => a.replace(/￥|¥/, '').trim()
      let p = parseFloat(fp($('.txt.count')[0].innerText))
      const t = parseFloat(fp($('.goods-total .txt')[0].innerText))
      let asset = '  Assets:Unknown\n'
      let ecard = ''
      // 礼品卡处理
      const z = $('.txt.count')[0].parentNode.parentNode.children
      let kk = null
      for (let i = z.length - 1; i >= 0; i--) {
        if (/礼品卡/.test(z[i].innerText)) {
          kk = z[i]
          break
        }
      }
      if (kk !== null) {
        const giftCardPaid = -(fp(kk.querySelector('.txt').innerText).replace(/ /, ''))
        if (parseInt(p) === 0) {
          asset = ''
          p = giftCardPaid
        } else {
          p += giftCardPaid
        }
        ecard = '  Assets:Company:JD:Ecard -' + giftCardPaid.toFixed(2) + ' CNY\n'
      }
      // 计算
      const pe = p / t
      const f = Array.from($('tr[class*="product"]')).map(a => {
        const q = a.querySelector.bind(a)
        const t = d => q(d).innerText.trim()
        return (`
${document.querySelector('[id*="datesubmit"]').value.split(' ')[0]} * "京东" "${t('.p-name')}"
  Expenses:Unknown                             ${(fp(t('.f-price')) * a.querySelectorAll('td')[4].innerText.trim() * pe).toFixed(2)} CNY
${asset}${ecard}
`).trim()
      }).join('')
      console.log(f)
    }
  }
  if ($('.td-void.order-tb').length > 0) {
    setTimeout(() => {
      const f = Array.from($('.order-tb tbody[id*="tb-"]')).map(a => {
        const q = a.querySelector.bind(a)
        const t = d => q(d).innerText
        if (a.querySelectorAll('[id*="track"]').length === 1) {
          return `
${t('.dealtime').split(' ')[0]} * "京东" "${t('.p-name')}"
  Expenses:Unknown   ${t('.amount').match(/([0-9.]+)/)[1]} CNY
  Assets:Unknown
`.trim()
        } else {
          return `
${t('.dealtime').split(' ')[0]} * "京东" "请点击详情"
  Expenses:Unknown   ${t('.amount').match(/([0-9.]+)/)[1]} CNY
  Assets:Unknown
`.trim()
        }
      }).join('\n\n')
      console.log(f)
    }, 5000)
  }
  getByGoodsTotal($)

  // Your code here...
})()
