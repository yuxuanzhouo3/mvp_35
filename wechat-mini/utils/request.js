const { apiBase } = require('../config')

const KEY = 'pickglobal.session'

function readSession() {
  try {
    const parsed = wx.getStorageSync(KEY)
    if (!parsed || !parsed.access_token || !parsed.refresh_token) return null
    return parsed
  } catch (error) {
    return null
  }
}

function writeSession(tokens) {
  wx.setStorageSync(KEY, {
    access_token: tokens.access_token,
    refresh_token: tokens.refresh_token,
  })
}

function clearSession() {
  wx.removeStorageSync(KEY)
}

function accessToken() {
  const session = readSession()
  return session ? session.access_token : ''
}

function requestRaw(path, options, token) {
  const header = { 'Content-Type': 'application/json' }
  if (token) header.Authorization = 'Bearer ' + token
  return new Promise((resolve, reject) => {
    wx.request({
      url: apiBase + path,
      method: (options && options.method) || 'GET',
      data: options && options.data,
      header,
      success: resolve,
      fail(err) {
        reject(new Error((err && err.errMsg) || '网络请求失败'))
      },
    })
  })
}

async function refreshSession() {
  const current = readSession()
  if (!current) return false
  const res = await requestRaw('/auth/refresh', {
    method: 'POST',
    data: { refresh_token: current.refresh_token },
  }, '')
  const tokens = res.data && res.data.data
  if (res.statusCode !== 200 || !tokens || !tokens.access_token) return false
  writeSession(tokens)
  return true
}

function errorMessage(body, status) {
  if (body && body.error && body.error.message) return body.error.message
  if (status === 401) return '需要登录'
  return '请求失败'
}

async function request(path, options, allowRefresh) {
  if (allowRefresh === undefined) allowRefresh = true
  const token = accessToken()
  const res = await requestRaw(path, options, token)
  const authPath = path.indexOf('/auth/') === 0
  if (res.statusCode === 401 && allowRefresh && token && !authPath) {
    const refreshed = await refreshSession()
    if (refreshed) return request(path, options, false)
    clearSession()
    throw new Error('需要登录')
  }
  if (res.statusCode === 401 && !authPath) {
    clearSession()
    throw new Error('需要登录')
  }
  if (res.statusCode < 200 || res.statusCode >= 300) {
    throw new Error(errorMessage(res.data, res.statusCode))
  }
  return res.data ? res.data.data : null
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function waitJob(jobId) {
  for (let attempt = 0; attempt < 40; attempt += 1) {
    const job = await request('/jobs/' + jobId)
    if (job.status === 'succeeded' || job.status === 'failed') return job
    await sleep(400)
  }
  throw new Error('任务仍在排队，请稍后刷新')
}

function enterApp(tokens) {
  writeSession(tokens)
  const next = wx.getStorageSync('pickglobal.next') || ''
  wx.removeStorageSync('pickglobal.next')
  if (next.indexOf('/pkg/') === 0 || next.indexOf('/pages/pay/') === 0) {
    wx.redirectTo({ url: next })
    return
  }
  wx.switchTab({ url: '/pages/home/home' })
}

module.exports = {
  request,
  waitJob,
  readSession,
  writeSession,
  clearSession,
  accessToken,
  enterApp,
}
