const { request } = require('../../utils/request')
const { percent, failMessage } = require('../../utils/format')

const tabs = [
  { id: 'market', name: '市场机会' },
  { id: 'profit', name: '利润测算' },
  { id: 'tax', name: '税务' },
  { id: 'logistics', name: '物流时效' },
  { id: 'risk', name: '风险提示' },
]

Page({
  data: {
    id: '',
    rules: '—',
    model: '—',
    stale: false,
    ready: false,
    busy: false,
    error: '',
    cards: [],
    tabs,
    tab: 'market',
    panels: {},
    panel: '',
    explanation: '',
  },

  onLoad(options) {
    this.setData({ id: options.id || '' })
    request('/analyses/' + options.id)
      .then((report) => {
        const metrics = report.metrics || {}
        const panels = {
          market: '路线 ' + (metrics.route || '—') + ' · 货源 ' + (metrics.origin_country || '—') + ' · 市场 ' + (metrics.target_market || '—') + ' · 术语 ' + (metrics.incoterm || '—') + '。机会分 ' + (metrics.opportunity_score || '—') + '，由利润率规则折算。',
          profit: 'R $' + metrics.target_price_usd + ' − C $' + metrics.landed_cost_usd + ' − F $' + metrics.channel_fee_usd + ' − T $' + metrics.tax_usd + ' = N $' + metrics.net_profit_usd + '。汇率 ' + metrics.fx_usd_cny + '。',
          tax: '税务口径 ' + metrics.tax_regime + '。关税率 ' + metrics.duty_rate + '，增值税率 ' + metrics.vat_rate + '，税费合计 $' + metrics.tax_usd + '。',
          logistics: '预计时效 ' + metrics.transit_days_min + '–' + metrics.transit_days_max + ' 天。国际段 $' + metrics.international_usd + '。',
          risk: '风险等级 ' + metrics.risk_level + '。推荐线是利润率 15%。低于该线时先复核成本或售价。',
        }
        this.setData({
          ready: true,
          stale: Boolean(report.stale),
          rules: report.rules_version || '—',
          model: report.explanation_model || '—',
          explanation: report.explanation || '',
          panels,
          panel: panels.market,
          cards: [
            { label: '利润率 N%', value: percent(metrics.net_margin) },
            { label: '净利润', value: metrics.net_profit_usd != null ? '$' + metrics.net_profit_usd : '—' },
            { label: '机会分', value: metrics.opportunity_score != null ? String(metrics.opportunity_score) : '—' },
            { label: '风险', value: metrics.risk_level ? String(metrics.risk_level) : '—' },
          ],
        })
      })
      .catch((reason) => this.setData({ error: failMessage(reason) }))
  },

  setTab(event) {
    const tab = event.currentTarget.dataset.id
    this.setData({ tab, panel: this.data.panels[tab] || '' })
  },

  acquire() {
    if (!this.data.ready || this.data.stale) return
    this.setData({ busy: true, error: '' })
    request('/analyses/' + this.data.id + '/acquire', { method: 'POST' })
      .then((data) => {
        const href = (data && data.href) || ''
        const matched = href.match(/seed_analysis_id=([^&]+)/)
        const seed = matched ? decodeURIComponent(matched[1]) : this.data.id
        wx.navigateTo({ url: '/pkg/channel/channel?id=ecommerce&seed=' + encodeURIComponent(seed) })
      })
      .catch((reason) => this.setData({ error: failMessage(reason) }))
      .then(() => this.setData({ busy: false }))
  },
})
