const channels = [
  { id: 'ecommerce', code: 'B1', name: '电商平台', copy: 'Amazon、Temu、Walmart、淘宝、拼多多', platforms: ['amazon', 'temu', 'walmart', 'taobao', 'pinduoduo'] },
  { id: 'social', code: 'B2', name: '社交平台', copy: 'LinkedIn、Facebook、微信、抖音、小红书、快手', platforms: ['linkedin', 'facebook', 'wechat_mini', 'douyin', 'xiaohongshu', 'kuaishou'] },
  { id: 'expo', code: 'B3', name: '线上展会', copy: '会期集中发现，会后冷启或召回', platforms: ['online_expo'] },
  { id: 'agency', code: 'B4', name: '代理渠道', copy: '渠道子账户获客，分成与线索账分开', platforms: ['agent_1', 'agent_2', 'agent_3'] },
  { id: 'enrichment', code: 'B5', name: '智慧大脑', copy: '企查查、天眼查去重、打分并留痕', platforms: ['qichacha', 'tianyancha'] },
  { id: 'geo_seo', code: 'B6', name: 'GEO / SEO', copy: '落地页归因，不另开线索主表', platforms: ['landing'] },
  { id: 'content_dh', code: 'B7', name: '内容与数智人', copy: '内容任务和扫码获客', platforms: ['content_factory', 'digital_human_placeholder', 'offline_qr'] },
  { id: 'cross_border', code: 'B8', name: '跨境元素', copy: '中美、中港、中澳与内陆', platforms: ['cn_us', 'cn_hk', 'cn_au', 'domestic'] },
  { id: 'raas', code: 'B9', name: 'RaaS', copy: '只按送达和支付成功分佣，手点赢单不计', platforms: ['site_success', 'app_account'] },
]

module.exports = { channels }
