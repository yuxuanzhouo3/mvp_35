const { channels } = require('../../utils/channels')
const { accessToken } = require('../../utils/request')

Page({
  data: { channels },

  openChannel(event) {
    const id = event.currentTarget.dataset.id
    const url = '/pkg/channel/channel?id=' + id
    if (!accessToken()) {
      wx.setStorageSync('pickglobal.next', url)
      wx.navigateTo({ url: '/pages/login/login' })
      return
    }
    wx.navigateTo({ url })
  },
})
