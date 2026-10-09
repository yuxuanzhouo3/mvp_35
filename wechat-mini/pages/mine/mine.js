const { request, accessToken, clearSession } = require('../../utils/request')
const { yuan, failMessage } = require('../../utils/format')

const planLabel = { free: '免费', growth: '成长', scale: '规模' }

Page({
  data: {
    signedIn: false,
    name: '账号',
    contact: '',
    plan: '免费',
    invite: null,
    owed: '',
    discount: '',
    notice: '',
    error: '',
  },

  onShow() {
    const signedIn = Boolean(accessToken())
    this.setData({ signedIn })
    if (signedIn) this.loadProfile()
  },

  onShareAppMessage() {
    const invite = this.data.invite
    const code = invite ? invite.invite_code : ''
    return {
      title: '一起来用 PickGlobal',
      path: '/pages/register/register' + (code ? '?invite=' + encodeURIComponent(code) : ''),
    }
  },

  goLogin() { wx.navigateTo({ url: '/pages/login/login' }) },
  goBilling() { wx.navigateTo({ url: '/pkg/billing/billing' }) },
  goChat() { wx.navigateTo({ url: '/pkg/chat/chat' }) },

  loadProfile() {
    request('/users/me')
      .then((me) => {
        const user = me.user || {}
        const tenant = me.tenant || {}
        this.setData({
          name: user.display_name || user.username || user.email || user.phone || '账号',
          contact: user.email || user.phone || user.username || '',
          plan: planLabel[tenant.plan_id] || tenant.plan_id || '免费',
        })
      })
      .catch((reason) => this.setData({ error: failMessage(reason) }))
  },

  loadInvite() {
    this.setData({ error: '', notice: '' })
    request('/users/me/invite')
      .then((invite) => this.showInvite(invite))
      .catch((reason) => this.setData({ error: failMessage(reason) }))
  },

  showInvite(invite) {
    const events = (invite.events || []).map((item, index) => Object.assign({}, item, { reward: yuan(item.reward_fen), key: String(index) }))
    this.setData({
      invite: Object.assign({}, invite, { events }),
      owed: yuan(invite.owed_fen),
      discount: yuan(invite.discount_fen),
    })
  },

  copyInvite() {
    const invite = this.data.invite
    if (!invite) return
    const path = '/pages/register/register?invite=' + encodeURIComponent(invite.invite_code || '')
    wx.setClipboardData({
      data: path,
      success: () => this.setData({ notice: '邀请路径已复制' }),
    })
  },

  claimCash() {
    request('/users/me/invite/cash', { method: 'POST' })
      .then(() => request('/users/me/invite'))
      .then((invite) => {
        this.showInvite(invite)
        this.setData({ notice: '已申请兑现。现金在 5 个工作日内打出，周末不计入。' })
      })
      .catch((reason) => this.setData({ error: failMessage(reason, '申请失败') }))
  },

  drawOnce() {
    request('/users/me/draw', { method: 'POST' })
      .then((result) => request('/users/me/invite').then((invite) => ({ result, invite })))
      .then(({ result, invite }) => {
        this.showInvite(invite)
        this.setData({ notice: result.amount_fen > 0 ? '抽中 ' + yuan(result.amount_fen) + '，将在 5 个工作日内打款。' : '这次没有抽中现金。' })
      })
      .catch((reason) => this.setData({ error: failMessage(reason, '抽奖失败') }))
  },

  logout() {
    const finish = () => {
      clearSession()
      this.setData({ signedIn: false, invite: null })
      wx.navigateTo({ url: '/pages/login/login' })
    }
    if (!accessToken()) {
      finish()
      return
    }
    request('/auth/logout', { method: 'POST' }).then(finish).catch(finish)
  },
})
