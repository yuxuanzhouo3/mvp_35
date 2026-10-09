const { request } = require('../../utils/request')
const { failMessage } = require('../../utils/format')

Page({
  data: {
    conversationId: '',
    messages: [],
    draft: '',
    error: '',
    sending: false,
  },

  onShow() {
    request('/chat/conversations')
      .then(async (page) => {
        const current = (page.items || [])[0]
        if (!current) return
        const history = await request('/chat/conversations/' + current.id + '/messages')
        this.setData({
          conversationId: current.id,
          messages: (history.items || []).slice().reverse(),
        })
      })
      .catch((reason) => this.setData({ error: failMessage(reason) }))
  },

  onDraft(event) { this.setData({ draft: event.detail.value }) },

  send() {
    const content = (this.data.draft || '').trim()
    if (!content || this.data.sending) return
    this.setData({ sending: true, error: '', draft: '' })
    const ensure = this.data.conversationId
      ? Promise.resolve(this.data.conversationId)
      : request('/chat/conversations', { method: 'POST', data: { title: '业务助手' } }).then((created) => {
        this.setData({ conversationId: created.id })
        return created.id
      })
    ensure
      .then((id) => request('/chat/conversations/' + id + '/messages', { method: 'POST', data: { content } }))
      .then((turn) => {
        this.setData({ messages: this.data.messages.concat([turn.user, turn.assistant]) })
      })
      .catch((reason) => this.setData({ draft: content, error: failMessage(reason, '发送失败') }))
      .then(() => this.setData({ sending: false }))
  },
})
