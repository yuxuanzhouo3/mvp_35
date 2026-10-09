function percent(value) {
  if (value == null || value === '') return '—'
  const number = Number(value)
  if (Number.isNaN(number)) return '—'
  return (number * 100).toFixed(1) + '%'
}

function duration(value) {
  if (value == null) return '—'
  if (value < 90) return value.toFixed(1) + ' 秒'
  if (value < 3600) return Math.round(value / 60) + ' 分钟'
  if (value < 86400) return (value / 3600).toFixed(1) + ' 小时'
  return (value / 86400).toFixed(1) + ' 天'
}

function yuan(fen) {
  return '¥' + (Number(fen || 0) / 100).toFixed(2)
}

function accountBody(account) {
  const value = String(account || '').trim()
  if (value.indexOf('@') >= 0) return { email: value.replace(/\s/g, '').toLowerCase() }
  const compact = value.replace(/[\s-]/g, '')
  if (/^\+?\d{6,}$/.test(compact)) return { phone: compact }
  return { username: value }
}

function failMessage(reason, fallback) {
  return reason && reason.message ? reason.message : (fallback || '操作失败')
}

module.exports = {
  percent,
  duration,
  yuan,
  accountBody,
  failMessage,
}
