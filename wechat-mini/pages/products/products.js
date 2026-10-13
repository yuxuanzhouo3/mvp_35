const { request, waitJob, accessToken } = require('../../utils/request')
const { percent, failMessage } = require('../../utils/format')

const routes = [
  { origin_country: 'CN', target_market: 'CN', tax_regime: 'domestic', route: 'CN-CN', label: '国内' },
  { origin_country: 'CN', target_market: 'US', tax_regime: 'cn_us', route: 'CN-US', label: '中国 → 美国' },
  { origin_country: 'CN', target_market: 'HK', tax_regime: 'cn_hk', route: 'CN-HK', label: '中国 → 香港' },
  { origin_country: 'CN', target_market: 'AU', tax_regime: 'cn_au', route: 'CN-AU', label: '中国 → 澳大利亚' },
  { origin_country: 'US', target_market: 'CN', tax_regime: 'domestic', route: 'US-CN', label: '美国 → 中国' },
]

const emptyForm = {
  name: '',
  sku: '',
  category: '家居',
  cost_cny: '72',
  packaging_cny: '4',
  domestic_freight_cny: '6',
  international_freight_usd: '3.2',
  target_price_usd: '39',
  origin_country: 'CN',
  target_market: 'CN',
  route: 'CN-CN',
  incoterm: 'DDP',
  tax_regime: 'domestic',
  cost_currency: 'CNY',
  price_currency: 'USD',
  fx_usd_cny: '7.20',
  hs_code_hint: '',
}

function quoteView(item) {
  const report = item.report || {}
  const profit = report.profit || {}
  const risk = report.risk || {}
  return {
    sku: item.sku,
    name: item.name,
    price: item.recommended_price_usd,
    margin: percent(profit.net_margin),
    risk: risk.risk_level || '—',
    advice: item.advice || '',
  }
}

Page({
  data: {
    signedIn: false,
    tab: 'manual',
    tabs: [
      { id: 'manual', name: '手动录入' },
      { id: 'sheet', name: '表格导入' },
      { id: 'catalog', name: '帮我选品' },
      { id: 'library', name: '已入库' },
    ],
    form: emptyForm,
    routeLabels: routes.map((item) => item.label),
    routeIndex: 0,
    csv: 'sku,name,cost_cny,target_price_usd,international_freight_usd\nCUP-1,样品杯,72,40,2\n',
    csvFile: '',
    q: '',
    catalog: [],
    library: [],
    quotes: [],
    message: '',
    error: '',
    busy: false,
  },

  onShow() {
    const signedIn = Boolean(accessToken())
    this.setData({ signedIn })
    if (signedIn && this.data.tab === 'library') this.loadLibrary()
  },

  goLogin() {
    wx.setStorageSync('pickglobal.next', '')
    wx.navigateTo({ url: '/pages/login/login' })
  },

  setTab(event) {
    const tab = event.currentTarget.dataset.id
    this.setData({ tab, error: '', message: '' })
    if (tab === 'library') this.loadLibrary()
  },

  onField(event) {
    this.setData({ ['form.' + event.currentTarget.dataset.key]: event.detail.value })
  },

  onRoute(event) {
    const route = routes[Number(event.detail.value)] || routes[0]
    this.setData({
      routeIndex: Number(event.detail.value),
      'form.origin_country': route.origin_country,
      'form.target_market': route.target_market,
      'form.tax_regime': route.tax_regime,
      'form.route': route.route,
    })
  },

  onCsv(event) { this.setData({ csv: event.detail.value }) },
  onQuery(event) { this.setData({ q: event.detail.value }) },

  async run(action) {
    this.setData({ busy: true, error: '', message: '' })
    try {
      await action()
    } catch (reason) {
      const message = failMessage(reason)
      if (message === '需要登录') wx.navigateTo({ url: '/pages/login/login' })
      else this.setData({ error: message })
    } finally {
      this.setData({ busy: false })
    }
  },

  saveProduct() {
    this.run(async () => {
      await request('/products', { method: 'POST', data: this.data.form })
      this.setData({ message: '商品已入库，可以开始分析。', tab: 'library' })
      await this.fetchLibrary('')
    })
  },

  chooseFile() {
    wx.chooseMessageFile({
      count: 1,
      type: 'file',
      extension: ['csv', 'tsv', 'txt'],
      success: (res) => {
        const file = res.tempFiles && res.tempFiles[0]
        if (!file) return
        wx.getFileSystemManager().readFile({
          filePath: file.path,
          encoding: 'utf8',
          success: (read) => {
            let text = String(read.data || '')
            if (file.name.toLowerCase().endsWith('.tsv') || (text.indexOf('\t') >= 0 && text.slice(0, 400).indexOf(',') < 0)) {
              text = text.split(/\r?\n/).map((line) => line.split('\t').join(',')).join('\n')
            }
            this.setData({ csv: text, csvFile: file.name })
          },
          fail: () => this.setData({ error: '无法读取这个文件' }),
        })
      },
    })
  },

  importCsv() {
    this.run(async () => {
      const created = await request('/products/imports', { method: 'POST', data: { csv: this.data.csv, algorithm: 'product-pricer' } })
      const job = await waitJob(created.job_id)
      if (job.status === 'failed') throw new Error((job.error && job.error.message) || '导入失败')
      const priced = job.result || {}
      this.setData({
        quotes: (priced.quotes || []).map(quoteView),
        message: '表格导入完成：成功 ' + (priced.imported || 0) + '，失败 ' + (priced.failed || 0) + '。',
      })
    })
  },

  priceOnly() {
    this.run(async () => {
      const priced = await request('/algorithms/product-pricer', { method: 'POST', data: { csv: this.data.csv } })
      const items = priced.items || []
      this.setData({
        quotes: items.map(quoteView),
        message: items.length ? '已比对 ' + items.length + ' 条售价。' : '没有可比对的商品行。',
      })
    })
  },

  searchCatalog() {
    this.run(async () => {
      const data = await request('/catalog/search?q=' + encodeURIComponent(this.data.q || '') + '&algorithm=selection-assist')
      this.setData({
        catalog: (data.items || []).map((item) => {
          const selection = item.selection || {}
          return {
            id: item.id,
            name: item.name,
            meta: [item.supplier, item.sku, '¥' + item.cost_cny, '$' + item.target_price_usd, selection.pick ? '优先' : '暂缓', '机会分 ' + (selection.score || '—'), '利润率 ' + percent(selection.net_margin)].filter(Boolean).join(' · '),
          }
        }),
      })
    })
  },

  adopt(event) {
    const id = event.currentTarget.dataset.id
    const name = event.currentTarget.dataset.name
    this.run(async () => {
      await request('/catalog/adopt', { method: 'POST', data: { catalog_id: id } })
      this.setData({ message: name + ' 已进入商品库。' })
    })
  },

  async fetchLibrary(q) {
    const data = await request('/products?q=' + encodeURIComponent(q || ''))
    this.setData({
      library: (data.items || []).map((item) => ({
        id: item.id,
        name: item.name,
        meta: [item.sku, item.origin_country && item.target_market ? item.origin_country + ' → ' + item.target_market : '', item.target_price_usd ? '$' + item.target_price_usd : ''].filter(Boolean).join(' · '),
      })),
    })
  },

  loadLibrary() {
    this.run(() => this.fetchLibrary(this.data.q))
  },

  analyze(event) {
    const id = event.currentTarget.dataset.id
    this.run(async () => {
      const created = await request('/products/' + id + '/analyses', { method: 'POST' })
      const job = await waitJob(created.job_id)
      if (job.status === 'failed' || !job.result || !job.result.analysis_id) {
        throw new Error((job.error && job.error.message) || '分析失败')
      }
      wx.navigateTo({ url: '/pkg/report/report?id=' + job.result.analysis_id })
    })
  },

  remove(event) {
    const id = event.currentTarget.dataset.id
    const name = event.currentTarget.dataset.name
    wx.showModal({
      title: '删除商品',
      content: '确认删除 ' + name + '？',
      success: (res) => {
        if (!res.confirm) return
        this.run(async () => {
          await request('/products/' + id, { method: 'DELETE' })
          this.setData({ message: '已删除 ' + name })
          await this.fetchLibrary(this.data.q)
        })
      },
    })
  },
})
