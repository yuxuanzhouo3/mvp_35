function decode(value) {
  try {
    return decodeURIComponent(value || '')
  } catch (error) {
    return value || ''
  }
}

Page({
  data: { pending: true, error: '' },

  onLoad(query) {
    const payload = {
      timeStamp: query.timeStamp || '',
      nonceStr: query.nonceStr || '',
      signType: query.signType || 'RSA',
      paySign: decode(query.paySign),
    }
    payload.package = decode(query.package)
    if (!payload.package || !payload.paySign) {
      this.setData({ pending: false, error: '缺少微信支付参数' })
      return
    }
    wx.requestPayment(Object.assign(payload, {
      success: () => {
        wx.showToast({ title: '已提交支付', icon: 'none' })
        wx.navigateBack({ fail: () => wx.redirectTo({ url: '/pkg/billing/billing' }) })
      },
      fail: (err) => {
        const message = err && err.errMsg && err.errMsg.indexOf('cancel') >= 0 ? '已取消支付' : '支付没有完成'
        this.setData({ pending: false, error: message })
      },
    }))
  },

  back() {
    wx.redirectTo({ url: '/pkg/billing/billing' })
  },
})
