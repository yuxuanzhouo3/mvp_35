const { request, enterApp } = require('../../utils/request')
const { accountBody, failMessage } = require('../../utils/format')

Page({
  data: {
    displayName: '',
    account: '',
    password: '',
    code: '',
    inviteCode: '',
    sentCode: '',
    sentNote: '',
    error: '',
    pending: false,
  },

  onLoad(options) {
    if (options.invite) this.setData({ inviteCode: options.invite })
  },

  onName(event) { this.setData({ displayName: event.detail.value }) },
  onAccount(event) { this.setData({ account: event.detail.value }) },
  onPassword(event) { this.setData({ password: event.detail.value }) },
  onCode(event) { this.setData({ code: event.detail.value }) },
  onInvite(event) { this.setData({ inviteCode: event.detail.value }) },
  goLogin() { wx.navigateTo({ url: '/pages/login/login' }) },

  sendCode() {
    this.setData({ error: '' })
    request('/auth/code/send', {
      method: 'POST',
      data: Object.assign({ purpose: 'register' }, accountBody(this.data.account)),
    }, false)
      .then((result) => {
        this.setData({
          sentCode: result.code || '',
          sentNote: result.channel === 'sms' ? '验证码已发到手机，5 分钟内有效。' : '验证码已发送，请查收后填写。',
        })
      })
      .catch((reason) => this.setData({ error: failMessage(reason) }))
  },

  onSubmit() {
    const compact = this.data.account.trim().replace(/[\s-]/g, '')
    if (compact.indexOf('@') < 0 && !/^\+?\d{6,}$/.test(compact)) {
      this.setData({ error: '请填写邮箱或手机号' })
      return
    }
    if ((this.data.password || '').length < 6) {
      this.setData({ error: '密码至少 6 位' })
      return
    }
    this.setData({ pending: true, error: '' })
    const body = Object.assign({
      password: this.data.password,
      display_name: this.data.displayName || null,
      code: this.data.code || null,
      invite_code: this.data.inviteCode || null,
    }, accountBody(this.data.account))
    request('/auth/register', { method: 'POST', data: body }, false)
      .then(() => request('/auth/login', {
        method: 'POST',
        data: Object.assign({ password: this.data.password }, accountBody(this.data.account)),
      }, false))
      .then((tokens) => enterApp(tokens))
      .catch((reason) => this.setData({ error: failMessage(reason, '注册失败'), pending: false }))
  },
})
