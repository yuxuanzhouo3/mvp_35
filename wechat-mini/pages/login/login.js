const { request, accessToken, enterApp } = require('../../utils/request')
const { accountBody, failMessage } = require('../../utils/format')

Page({
  data: {
    mode: 'password',
    account: '',
    password: '',
    code: '',
    sentCode: '',
    sentNote: '',
    error: '',
    busy: false,
    wxBusy: false,
    sending: false,
    privacy: false,
    privacyName: '《隐私保护指引》',
  },

  onShow() {
    if (accessToken()) wx.switchTab({ url: '/pages/home/home' })
  },

  setMode(event) {
    this.setData({ mode: event.currentTarget.dataset.mode, error: '' })
  },

  onAccount(event) { this.setData({ account: event.detail.value }) },
  onPassword(event) { this.setData({ password: event.detail.value }) },
  onCode(event) { this.setData({ code: event.detail.value }) },

  goForgot() { wx.navigateTo({ url: '/pages/forgot/forgot' }) },
  goRegister() { wx.navigateTo({ url: '/pages/register/register' }) },

  onWechat() {
    if (this.data.busy) return
    if (!wx.getPrivacySetting) {
      this.wechatLogin()
      return
    }
    wx.getPrivacySetting({
      success: (res) => {
        if (res.needAuthorization) {
          this.setData({ privacy: true, privacyName: res.privacyContractName || '《隐私保护指引》' })
          return
        }
        this.wechatLogin()
      },
      fail: () => this.wechatLogin(),
    })
  },

  closePrivacy() {
    this.setData({ privacy: false })
  },

  onAgreePrivacy() {
    this.setData({ privacy: false })
    this.wechatLogin()
  },

  wechatLogin() {
    this.setData({ wxBusy: true, error: '' })
    wx.login({
      success: (res) => {
        if (!res.code) {
          this.setData({ wxBusy: false, error: '微信没有返回登录凭证' })
          return
        }
        request('/auth/miniprogram', { method: 'POST', data: { code: res.code } }, false)
          .then((tokens) => enterApp(tokens))
          .catch((reason) => this.setData({ error: failMessage(reason, '微信登录失败'), wxBusy: false }))
      },
      fail: () => this.setData({ wxBusy: false, error: '微信登录没有完成' }),
    })
  },

  sendCode() {
    this.setData({ error: '', sending: true })
    request('/auth/code/send', {
      method: 'POST',
      data: Object.assign({ purpose: 'login' }, accountBody(this.data.account)),
    }, false)
      .then((result) => {
        const channel = result.channel
        this.setData({
          sentCode: result.code || '',
          sentNote: channel === 'sms' ? '验证码已发到手机，5 分钟内有效。' : channel === 'email' ? '验证码已发到邮箱，10 分钟内有效。' : '若账号存在，验证码已发送。',
        })
      })
      .catch((reason) => this.setData({ error: failMessage(reason) }))
      .then(() => this.setData({ sending: false }))
  },

  onSubmit() {
    const mode = this.data.mode === 'code' ? 'code' : 'password'
    const body = accountBody(this.data.account)
    if (mode === 'password') body.password = this.data.password
    else body.code = this.data.code
    this.setData({ busy: true, error: '', mode })
    const path = mode === 'code' ? '/auth/code/login' : '/auth/login'
    request(path, { method: 'POST', data: body }, false)
      .then((tokens) => enterApp(tokens))
      .catch((reason) => this.setData({ error: failMessage(reason, '登录失败'), busy: false }))
  },
})
