export type ChannelLaunch = 'live' | 'pending'

export const channels = [
  { id: 'ecommerce', code: 'B1', name: '电商平台', launch: 'pending' as ChannelLaunch, priority: false, copy: '待上线。店铺登录与订单获客尚未开放。', platforms: ['amazon', 'temu', 'walmart', 'taobao', 'pinduoduo'] },
  { id: 'social', code: 'B2', name: '社交种草', launch: 'live' as ChannelLaunch, priority: true, copy: '优先开通。登录后 AI 种草或复刻热点，落到表单，收中高意向并加微信或授权邮箱/手机。', platforms: ['wechat_mini', 'wechat_channels', 'douyin', 'xiaohongshu', 'kuaishou', 'weibo', 'bilibili', 'zhihu', 'tiktok', 'instagram', 'youtube', 'facebook', 'x', 'linkedin', 'pinterest'] },
  { id: 'expo', code: 'B3', name: '线上展会', launch: 'live' as ChannelLaunch, priority: false, copy: '登录后入驻线上展会，收中高意向并加微信或授权邮箱/手机。', platforms: ['online_expo', 'alibaba_com', 'canton_fair', 'global_sources', 'ciie'] },
  { id: 'agency', code: 'B4', name: '代理渠道', launch: 'live' as ChannelLaunch, priority: false, copy: '搜集代理商平台；登录后自行联系一二级代理谈分销与合约。', platforms: ['agent_1', 'agent_2', 'agent_3'] },
  { id: 'enrichment', code: 'B5', name: '智慧大脑', launch: 'live' as ChannelLaunch, priority: false, copy: '登录后检索全国公司法人通信信息，自行联系。', platforms: ['qichacha', 'tianyancha', 'qixin'] },
  { id: 'geo_seo', code: 'B6', name: 'GEO / SEO', launch: 'live' as ChannelLaunch, priority: false, copy: '落地页归因，不另开线索主表', platforms: ['landing'] },
  { id: 'content_dh', code: 'B7', name: '内容与数智人', launch: 'live' as ChannelLaunch, priority: false, copy: '内容任务和扫码获客', platforms: ['content_factory', 'digital_human_placeholder', 'offline_qr'] },
  { id: 'cross_border', code: 'B8', name: '跨境元素', launch: 'live' as ChannelLaunch, priority: false, copy: '中美、中港、中澳与内陆', platforms: ['cn_us', 'cn_hk', 'cn_au', 'domestic'] },
  { id: 'raas', code: 'B9', name: 'RaaS', launch: 'live' as ChannelLaunch, priority: false, copy: '只按送达和支付成功分佣，手点赢单不计', platforms: ['site_success', 'app_account'] },
]

export const socialGroups = [
  { id: 'cn', name: '国内种草', platforms: ['wechat_mini', 'wechat_channels', 'douyin', 'xiaohongshu', 'kuaishou', 'weibo', 'bilibili', 'zhihu'] },
  { id: 'intl', name: '海外种草', platforms: ['tiktok', 'instagram', 'youtube', 'facebook', 'x', 'linkedin', 'pinterest'] },
]

export const sameButton = 'inline-flex h-12 w-full items-center justify-center rounded-xl px-3 text-center text-sm font-medium leading-none disabled:opacity-50'
