const { request, waitJob } = require('../../utils/request')
const { channels } = require('../../utils/channels')
const { failMessage } = require('../../utils/format')

const reachForms = [
  { id: 'email', name: '邮箱' },
  { id: 'sms', name: '短信' },
  { id: 'wechat', name: '微信' },
  { id: 'phone', name: '电话' },
]

const baseViews = [
  { id: 'discover', name: '发现线索' },
  { id: 'leads', name: '线索池' },
  { id: 'outreach', name: '触达' },
  { id: 'activation', name: '冷客启动' },
  { id: 'recall', name: '流失召回' },
  { id: 'ledger', name: '分成入账' },
]

Page({
  data: {
    missing: false,
    channel: { code: '', name: '', copy: '', platforms: [''], id: '' },
    views: baseViews,
    view: 'discover',
    platformIndex: 0,
    leads: [],
    pickedCount: 0,
    campaigns: [],
    activation: [],
    message: '',
    error: '',
    busy: false,
    reach: 'email',
    reachForms,
    seed: '',
  },

  picked: {},

  onLoad(options) {
    const channel = channels.find((item) => item.id === options.id)
    if (!channel) {
      this.setData({ missing: true })
      return
    }
    const views = channel.id === 'raas'
      ? [{ id: 'ledger', name: '结果分佣' }].concat(baseViews.slice(0, 5))
      : baseViews
    this.picked = {}
    wx.setNavigationBarTitle({ title: channel.code + ' ' + channel.name })
    this.setData({
      channel,
      views,
      view: channel.id === 'raas' ? 'ledger' : 'discover',
      seed: options.seed || '',
    })
    this.reload()
  },

  back() {
    wx.navigateBack({ fail: () => wx.switchTab({ url: '/pages/acquire/acquire' }) })
  },

  setView(event) { this.setData({ view: event.currentTarget.dataset.id }) },
  onPlatform(event) { this.setData({ platformIndex: Number(event.detail.value) }) },
  setReach(event) { this.setData({ reach: event.currentTarget.dataset.id }) },

  async run(action) {
    this.setData({ busy: true, error: '' })
    try {
      await action()
      await this.reload()
    } catch (reason) {
      const message = failMessage(reason)
      if (message === '需要登录') wx.navigateTo({ url: '/pages/login/login' })
      else this.setData({ error: message })
    } finally {
      this.setData({ busy: false })
    }
  },

  async reload() {
    const seed = this.data.seed
    const channelId = this.data.channel.id
    const [leadData, campaignData, activationData] = await Promise.all([
      request('/leads' + (seed ? '?seed_analysis_id=' + encodeURIComponent(seed) : '')),
      request('/campaigns'),
      request('/activation/jobs'),
    ])
    const leads = (leadData.items || [])
      .filter((lead) => lead.source_channel === channelId)
      .map((lead) => ({
        id: lead.id,
        company: lead.company,
        checked: Boolean(this.picked[lead.id]),
        meta: [lead.email || '无邮箱', lead.market, lead.platform, String(lead.quality_score), lead.qualified ? '' : '未达标', lead.status].filter(Boolean).join(' · '),
      }))
    this.setData({
      leads,
      campaigns: (campaignData.items || []).map((item) => ({
        id: item.id,
        name: item.name,
        status: item.status,
        draft: item.draft || '',
      })),
      activation: (activationData.items || []).map((item) => ({
        id: item.id,
        reason: item.reason,
        status: item.status,
        draft: item.draft || '',
      })),
      pickedCount: Object.keys(this.picked).filter((id) => this.picked[id]).length,
    })
  },

  toggleLead(event) {
    const id = event.currentTarget.dataset.id
    this.picked[id] = !this.picked[id]
    const leads = this.data.leads.map((lead) => (lead.id === id ? Object.assign({}, lead, { checked: this.picked[id] }) : lead))
    this.setData({
      leads,
      pickedCount: Object.keys(this.picked).filter((key) => this.picked[key]).length,
    })
  },

  discover() {
    const platform = this.data.channel.platforms[this.data.platformIndex]
    this.run(async () => {
      const created = await request('/lead-searches', {
        method: 'POST',
        data: {
          channel: this.data.channel.id,
          platform,
          query: platform,
          seed_analysis_id: this.data.seed || null,
        },
      })
      const job = await waitJob(created.job_id)
      if (job.status === 'failed') throw new Error((job.error && job.error.message) || '发现失败')
      this.setData({
        message: this.data.channel.id === 'content_dh' ? '已发现线索。数智人仍是 DEMO 占位。' : '线索已写入统一线索池。',
        view: 'leads',
      })
    })
  },

  signal(event) {
    const id = event.currentTarget.dataset.id
    this.run(() => request('/leads/' + id + '/signals', { method: 'POST', data: { type: 'open' } }))
  },

  won(event) {
    const id = event.currentTarget.dataset.id
    const company = event.currentTarget.dataset.company
    const raas = this.data.channel.id === 'raas'
    wx.showModal({
      title: '赢单 · ' + company,
      content: raas ? '这只改线索状态。结果分佣不认手点赢单。' : '标记赢单后，若发生在送达后 14 天内，计入获客率。',
      success: (res) => {
        if (!res.confirm) return
        this.run(async () => {
          await request('/leads/' + id + '/signals', { method: 'POST', data: { type: 'won' } })
          this.setData({ message: raas ? '已标记赢单。这一下不产生抽成。' : '已标记赢单。若发生在送达后 14 天内，计入获客率。' })
        })
      },
    })
  },

  pickedIds() {
    return Object.keys(this.picked).filter((id) => this.picked[id])
  },

  createCampaign() {
    const ids = this.pickedIds()
    this.run(async () => {
      await request('/campaigns', {
        method: 'POST',
        data: {
          name: this.data.channel.code + ' ' + new Date().toLocaleString('zh-CN'),
          lead_ids: ids,
          seed_analysis_id: this.data.seed || null,
          market_pack: 'cn_us',
        },
      })
      this.setData({ message: '活动已创建。未批准不能发送。' })
    })
  },

  draft(event) {
    this.run(async () => {
      await request('/campaigns/' + event.currentTarget.dataset.id + '/drafts', { method: 'POST' })
      this.setData({ message: '草稿已生成，等待批准。' })
    })
  },

  approve(event) {
    this.run(async () => {
      await request('/campaigns/' + event.currentTarget.dataset.id + '/approve', { method: 'POST' })
      this.setData({ message: '已批准，并冻结受众快照。' })
    })
  },

  confirmSend(title, emailRun) {
    if (this.data.reach !== 'email') {
      const form = reachForms.find((item) => item.id === this.data.reach)
      wx.showModal({
        title: (form ? form.name : '') + ' · 占位',
        content: (form ? form.name : '该方式') + '触达还没有接通。这里只保留入口，不会发出内容。',
        showCancel: false,
      })
      this.setData({ message: (form ? form.name : '该方式') + '仍是占位，没有发送。' })
      return
    }
    wx.showModal({
      title,
      content: '邮箱走演示发送，不会真实发信。未批准时服务端会拒绝。',
      success: (res) => {
        if (res.confirm) this.run(emailRun)
      },
    })
  },

  sendCampaign(event) {
    const id = event.currentTarget.dataset.id
    this.confirmSend('发送 · ' + event.currentTarget.dataset.name, async () => {
      const created = await request('/campaigns/' + id + '/send', { method: 'POST' })
      const job = await waitJob(created.job_id)
      if (job.status === 'failed') throw new Error((job.error && job.error.message) || '发送失败')
      this.setData({ message: '邮箱发送任务完成。演示环境不会真实发信。' })
    })
  },

  scan() {
    this.run(async () => {
      const created = await request('/lifecycle/scan', { method: 'POST' })
      const job = await waitJob(created.job_id)
      if (job.status === 'failed') throw new Error((job.error && job.error.message) || '扫描失败')
      this.setData({ message: '规则扫描完成。合格且从未触达的线索进入冷启。' })
    })
  },

  approveLife(event) {
    this.run(() => request('/activation/jobs/' + event.currentTarget.dataset.id + '/approve', { method: 'POST' }))
  },

  sendLife(event) {
    const id = event.currentTarget.dataset.id
    this.confirmSend('发送冷启', async () => {
      const created = await request('/activation/jobs/' + id + '/send', { method: 'POST' })
      const job = await waitJob(created.job_id)
      if (job.status === 'failed') throw new Error((job.error && job.error.message) || '发送失败')
      this.setData({ message: '邮箱冷启已提交。演示环境不会真实发信。' })
    })
  },
})
