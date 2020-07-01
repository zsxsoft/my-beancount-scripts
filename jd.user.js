// ==UserScript==
// @name         JD to Beancount
// @version      0.1
// @description  JD to Beancount
// @author       zsx
// @match        https://order.jd.com/*
// @match        https://details.jd.com/*
// @grant        none
// ==/UserScript==

(function() {
    'use strict'
    const $ = document.querySelectorAll.bind(document)
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
    if ($('.goods-total').length > 0) {
        const fp = a => a.replace(/￥|¥/, '').trim()
        const p = fp($('.txt.count')[0].innerText)
        const t = fp($('.goods-total .txt')[0].innerText)
        const pe = p / t
        const f = Array.from($('tr[class*="product"]')).map(a => {
            const q = a.querySelector.bind(a)
            const t = d => q(d).innerText.trim()
            return `
${document.querySelector('[id*="datesubmit"]').value.split(' ')[0]} * "京东" "${t('.p-name')}"
  Expenses:Unknown                             ${(fp(t('.f-price')) * a.querySelectorAll('td')[4].innerText.trim() * pe).toFixed(2)} CNY
  Assets:Unknown
`
        }).join('')
        console.log(f)
    }
    // Your code here...
})();
