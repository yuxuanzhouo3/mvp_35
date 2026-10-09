const { request } = require('../../utils/request')
const { yuan, failMessage } = require('../../utils/format')

const statusLabel = {
  pending: '待支付',
  succeeded: '已入账',
  failed: '失败',
  refunded: '已退款',
  active: '生效中',
  issued: '已开票',
  created: '已创建',
}

function pay(jsapi) {
  const payload = {
    timeStamp: jsapi.timeStamp,
    nonceStr: jsapi.nonceStr,
    signType: jsapi.signType || 'RSA',
    paySign: jsapi.paySign,
  }
  payload.package = jsapi.package
  return new Promise((resolve, reject) => {
    wx.requestPayment(Object.assign(payload, {
      success: resolve,
      fail: reject,
    }))
  })
}

Page({
  data: {
    plans: [],
    payments: [],
    invoices: [],
    active: '',
    testing: false,
    error: '',
    notice: '',
    busy: false,
  },

  onShow() { this.load() },

  load() {
    request('/billing/summary')
      .then((summary) => {
        const active = (summary.subscription.items || []).find((item) => item.status === 'active')
        this.setData({
          testing: Boolean(summary.payment_testing),
          active: active ? (active.plan_id || active.plan || '生效中') : '',
          plans: (summary.plans || []).map((plan) => ({
            id: plan.id,
            name: plan.name,
            price: yuan(plan.amount_fen),
            period: plan.period === 'year' ? '年' : '月',
            payable: Number(plan.amount_fen) > 0,
          })),
          payments: (summary.payments.items || []).map((item) => ({
            id: item.id,
            amount: yuan(item.amount),
            pending: item.status === 'pending',
            statusLabel: statusLabel[item.status] || item.status,
          })),
          invoices: ((summary.invoices && summary.invoices.items) || []).map((item) => ({
            id: item.id,
            amount: yuan(item.amount),
            statusLabel: statusLabel[item.status] || item.status,
          })),
          error: '',
        })
      })
      .catch((reason) => this.setData({ error: failMessage(reason) }))
  },

  checkout(event) {
    const planId = event.currentTarget.dataset.id
    this.setData({ busy: true, error: '', notice: '' })
    request('/payments/checkout', {
      method: 'POST',
      data: {
        plan_id: planId,
        kind: 'subscription',
        provider: 'wechat',
        scene: 'miniprogram',
        idempotency_key: 'plan-' + planId + '-wechat-' + Date.now(),
      },
    })
      .then(async (payment) => {
        if (payment.jsapi) {
          await pay(payment.jsapi)
          this.setData({ notice: '订单 ' + payment.id + ' 已提交微信支付。入账以后台签名回调为准。' })
        } else {
          this.setData({ notice: payment.message || ('订单 ' + payment.id + ' 保持待支付，尚未入账。') })
        }
        this.load()
      })
      .catch((reason) => {
        const message = reason && reason.errMsg && reason.errMsg.indexOf('cancel') >= 0
          ? '已取消支付'
          : failMessage(reason, '下单失败')
        this.setData({ error: message })
      })
      .then(() => this.setData({ busy: false }))
  },

  query(event) {
    const id = event.currentTarget.dataset.id
    this.setData({ busy: true, error: '' })
    request('/payments/' + id + '/query', { method: 'POST' })
      .then((payment) => {
        this.setData({
          notice: payment.granted ? '这笔支付已入账。' : '查询结果仍是' + (statusLabel[payment.status] || payment.status) + '，尚未入账。',
        })
        this.load()
      })
      .catch((reason) => this.setData({ error: failMessage(reason, '查询失败') }))
      .then(() => this.setData({ busy: false }))
  },
})
