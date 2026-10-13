const { request } = require('../../utils/request')
const { accountBody, failMessage } = require('../../utils/format')

Page({
  data: {
    account: '',
    token: '',
    emailed: false,
    smsSent: false,
    smsCode: '',
    password: '',
    error: '',
    pending: false,
  },

  onAccount(event) { this.setData({ account: event.detail.value }) },
  onSms(event) { this.setData({ smsCode: event.detail.value }) },
  onPassword(event) { this.setData({ password: event.detail.value }) },
  goLogin() { wx.navigateBack({ fail: () => wx.redirectTo({ url: '/pages/login/login' }) }) },

  onSend() {
    const compact = this.data.account.trim().replace(/[\s-]/g, '')
    if (compact.indexOf('@') < 0 && !/^\+?\d{6,}$/.test(compact)) {
      this.setData({ error: '请填写邮箱或手机号' })
      return
    }
    this.setData({ pending: true, error: '' })
    request('/auth/forgot-password', { method: 'POST', data: accountBody(this.data.account) }, false)
      .then((result) => {
        this.setData({
          emailed: result.channel === 'email',
          smsSent: result.channel === 'sms',
          token: result.reset_token || '',
        })
      })
      .catch((reason) => this.setData({ error: failMessage(reason, '发送失败') }))
      .then(() => this.setData({ pending: false }))
  },

  onReset() {
    const data = this.data.smsSent
      ? { phone: accountBody(this.data.account).phone, code: this.data.smsCode, password: this.data.password }
      : { token: this.data.token, password: this.data.password }
    this.setData({ pending: true, error: '' })
    request('/auth/reset-password', { method: 'POST', data }, false)
      .then(() => wx.redirectTo({ url: '/pages/login/login' }))
      .catch((reason) => this.setData({ error: failMessage(reason, '重置失败'), pending: false }))
  },
})
