const { request, accessToken } = require('../../utils/request')
const { percent, duration, failMessage } = require('../../utils/format')

const rateOrder = [
  ['net_margin', '利润率', false],
  ['act_r', '行动率', false],
  ['tr', '触达率', false],
  ['open_r', '打开率', false],
  ['ar', '获客率', true],
  ['qr', '线索合格率', false],
  ['act_r_cold', '冷客激活率', false],
  ['rec_r', '召回成功率', false],
]

const timingOrder = [
  ['ana_t', '分析时效 AnaT', '≤ 2 分钟', 48],
  ['lead_t', '线索时效 LeadT', '≤ 3 分钟', 96],
  ['acq_t', '获客时效 AcqT', '≤ 3 天', 103680],
  ['act_t', '激活时效 ActT', '≤ 24 小时', 21600],
  ['rec_t', '召回时效 RecT', '≤ 24 小时', 28800],
]

const sampleRates = {
  net_margin: '0.499', act_r: '0.62', tr: '0.96', open_r: '0.42',
  ar: '0.092', qr: '0.64', act_r_cold: '0.28', rec_r: '0.12',
}
const sampleTargets = {
  net_margin: '0.15', act_r: '0.5', tr: '0.95', open_r: '0.4',
  ar: '0.08', qr: '0.6', act_r_cold: '0.25', rec_r: '0.1',
}

Page({
  data: {
    signedIn: false,
    samples: [
      { label: '机会分', value: '80' },
      { label: '利润率', value: '49.9%' },
      { label: '税费', value: '可复核' },
      { label: '风险', value: '低' },
    ],
    rates: [],
    timings: [],
    footer: '',
    redline: '',
    alert: false,
    error: '',
  },

  onShow() {
    const signedIn = Boolean(accessToken())
    this.setData({ signedIn })
    if (signedIn) this.load()
  },

  onShareAppMessage() {
    return { title: 'PickGlobal 选品与获客', path: '/pages/home/home' }
  },

  goLogin() { wx.navigateTo({ url: '/pages/login/login' }) },
  goProducts() { wx.switchTab({ url: '/pages/products/products' }) },
  goAcquire() { wx.switchTab({ url: '/pages/acquire/acquire' }) },

  load() {
    request('/metrics')
      .then((metrics) => {
        const rates = rateOrder.map(([key, label, star]) => {
          const rate = metrics.rates && metrics.rates[key]
          const sampled = !rate || rate.value == null
          return {
            label,
            star,
            sampled,
            value: percent(sampled ? sampleRates[key] : rate.value),
            target: percent((rate && rate.target) || sampleTargets[key]),
          }
        })
        const timings = timingOrder.map(([key, label, target, sample]) => ({
          label,
          target,
          value: duration(metrics.timings_p50_seconds && metrics.timings_p50_seconds[key] != null ? metrics.timings_p50_seconds[key] : sample),
        }))
        const counts = metrics.counts || {}
        const red = metrics.redlines || {}
        this.setData({
          rates,
          timings,
          alert: Boolean(metrics.alerts && metrics.alerts.act_or_rec_p95_over_72h),
          footer: '导入成功率 ' + percent(metrics.import_success_rate) + ' · 完成报告 ' + (counts.analyses || 0) + ' · 一键获客 ' + (counts.acquired || 0) + ' · 线索 ' + (counts.leads || 0),
          redline: red.tripped ? '送达红线已触发。按封送达率 ' + percent(red.delivery_rate) + '，退信 ' + percent(red.bounce_rate) + '，投诉 ' + percent(red.complaint_rate) + '。' : '',
          error: '',
        })
      })
      .catch((reason) => this.setData({ error: failMessage(reason) }))
  },
})
