'use client'

export type MetricBasis = {
  method: string
  included: number
  excluded: number
  note: string
}

export type MetricInputs = {
  analyses?: number
  acquired?: number
  qualified?: number
  leads?: number
  audience?: number
  delivered_people?: number
  opened_people?: number
  wins?: number
  activations?: number
  cold_hit?: number
  recall_delivered?: number
  warm_hit?: number
}

type Term = {
  title: string
  code: string
  formula: string
  meaning: string
  words: Array<[string, string]>
}

export const metricTerms: Record<string, Term> = {
  net_margin: {
    title: '利润率',
    code: 'N%',
    formula: '中位数(净利润 N ÷ 目标售价 R)',
    meaning: '每一份完成报告里，扣掉采购、物流、平台费、支付费和税之后，还剩多少比例。看板不把各份报告相加，取中位数。',
    words: [
      ['N', '净利润。售价减去成本、费用和税。'],
      ['R', '目标售价。'],
      ['中位数', '把报告利润率从小到大排列，取正中间。不受特别高或特别低的一单拉动。'],
    ],
  },
  act_r: {
    title: '行动率',
    code: 'ActR',
    formula: '点了「一键获客」或被采纳的报告 ÷ 完成报告',
    meaning: '报告做完之后，有多少真的进入获客，而不是只停在看报告。',
    words: [['完成报告', '分析已经跑完的报告。'], ['一键获客', '从报告进入获客经营。']],
  },
  tr: {
    title: '触达率',
    code: 'TR',
    formula: '送达人数 D ÷ 计划受众 A',
    meaning: '批准发送的人里，至少有一封信真正送达的比例。',
    words: [
      ['A', '批准时的受众，去掉退订、退信和没有邮箱的人。'],
      ['D', '受众里至少收到一封已送达邮件的人。'],
    ],
  },
  open_r: {
    title: '打开率',
    code: 'OR',
    formula: '打开过的人数 ÷ 送达人数 D',
    meaning: '送达之后有没有被打开。同一个人打开多次只算一个人。',
    words: [['unique 打开', '按人去重，不按打开次数。'], ['D', '至少一封送达的人。']],
  },
  ar: {
    title: '获客率',
    code: 'AR',
    formula: '有效获客 W ÷ 送达人数 D',
    meaning: '送达之后 14 天内回复、赢单或约见的人，占送达人数的比例。这是北星指标。',
    words: [
      ['W', '送达后 14 天内回复、赢单或约见。'],
      ['D', '至少一封送达的人。手点赢单若没有对应送达，不进这个分子。'],
      ['北星', '全站最看重的获客结果，目标不低于 8%。'],
    ],
  },
  qr: {
    title: '线索合格率',
    code: 'QR',
    formula: '质量分达到阈值的线索 ÷ 入库线索',
    meaning: '找回来的线索里，有多少达到可以继续联系的质量。',
    words: [['θ', '质量分阈值，由服务端规则设定。'], ['入库', '写进线索库的人，不含被规则丢掉的。']],
  },
  act_r_cold: {
    title: '冷客激活率',
    code: 'ActR_cold',
    formula: '序列内打开或回复 ÷ 进入冷启队列的人数',
    meaning: '原来没有互动的人，被冷启序列触达后有没有打开或回复。',
    words: [['冷启', '对还没回复过的线索按顺序发信。'], ['入队', '被放进冷启任务的人。']],
  },
  rec_r: {
    title: '召回成功率',
    code: 'RecR',
    formula: '回暖人数 ÷ 召回已送达人数',
    meaning: '曾经开过口、后来沉默的人，召回送达之后又回复、回暖或赢单的比例。不和普通获客率混在一起。',
    words: [['回暖', '召回送达后再次回复、标记回暖或赢单。'], ['召回触达', '召回信状态是已送达。']],
  },
  ana_t: {
    title: '分析时效',
    code: 'AnaT',
    formula: 'P50(报告完成时间 − 请求时间)',
    meaning: '从发起分析到报告完成，一半的请求在这个时间内做完。目标不超过 2 分钟。',
    words: [['P50', '把耗时从小到大排列，取正中间。超过目标记为未达标。']],
  },
  lead_t: {
    title: '线索时效',
    code: 'LeadT',
    formula: 'P50(发现任务成功 − 发起)',
    meaning: '从开始找线索到任务成功的中位时间。目标不超过 3 分钟。',
    words: [['discovery', '线索发现任务。只统计成功结束的任务。']],
  },
  acq_t: {
    title: '获客时效',
    code: 'AcqT',
    formula: 'P50(首次成为 W − 首次送达)',
    meaning: '信送达之后，多久产生回复、赢单或约见。只统计已经成为 W 的人。目标不超过 3 天。',
    words: [['first_W', '这个人第一次被记为有效获客的时间。'], ['first_delivered', '这个人第一封送达的时间。']],
  },
  act_t: {
    title: '激活时效',
    code: 'ActT',
    formula: 'P50(首封送达 − 进入冷启队列)',
    meaning: '冷启任务从入队到第一封送达的中位时间。目标不超过 24 小时。',
    words: [['P95', '最慢的那一小段。激活或召回的 P95 超过 72 小时会告警。']],
  },
  rec_t: {
    title: '召回时效',
    code: 'RecT',
    formula: 'P50(首封送达 − 召回触发)',
    meaning: '召回从触发到第一封送达的中位时间。目标不超过 24 小时。',
    words: [['触发', '召回任务开始的时间，不是批准草稿的时间。']],
  },
  delivery_rate: {
    title: '送达率',
    code: '按封',
    formula: '已送达封数 ÷（送达 + 退信 + 投诉）',
    meaning: '按邮件封数，不是按人。低于 95% 触发红线，应当限流。',
    words: [['红线', '送达率、退信率、投诉率三条一起看。触发后先停发，不继续加量。']],
  },
  bounce_rate: {
    title: '退信率',
    code: '按封',
    formula: '退信封数 ÷（送达 + 退信 + 投诉）',
    meaning: '邮箱拒收或地址无效的比例。达到 1.5% 触发红线。',
    words: [['退信', '对端邮件服务器没有收下。']],
  },
  complaint_rate: {
    title: '投诉率',
    code: '按封',
    formula: '投诉封数 ÷（送达 + 退信 + 投诉）',
    meaning: '收件人标记投诉的比例。达到 0.1% 触发红线。',
    words: [['投诉', '收件人向邮件服务标记这封信不受欢迎。']],
  },
}

export function MetricDetail({
  termKey,
  value,
  averaged,
  basis,
  inputs,
  onClose,
}: {
  termKey: string
  value: string
  averaged: boolean
  basis?: MetricBasis | null
  inputs?: MetricInputs | null
  onClose: () => void
}) {
  const term = metricTerms[termKey]
  if (!term) return null
  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/45 p-4 sm:p-10" onClick={onClose}>
      <div className="max-h-[86vh] w-[min(880px,94vw)] overflow-y-auto rounded-3xl border border-border bg-card p-8 shadow-2xl sm:p-10" role="dialog" onClick={(event) => event.stopPropagation()}>
        <p className="text-sm text-muted-foreground">{term.code}</p>
        <h2 className="mt-2 text-3xl font-semibold">{term.title}</h2>
        <p className="mt-4 text-4xl font-semibold tracking-tight">{value}</p>
        <p className="mt-6 text-base leading-7">{term.meaning}</p>
        <p className="mt-4 rounded-2xl bg-muted px-4 py-3 text-base leading-7">公式：{term.formula}</p>
        {averaged ? (
          <p className="mt-4 text-base leading-7 text-muted-foreground">
            这个账号还没有获客，所以这里用管理后台的全站平均，不用样例数。纳入 {basis?.included ?? 0} 个有效用户，排除 {basis?.excluded ?? 0} 个无效用户。{basis?.note}
          </p>
        ) : (
          <p className="mt-4 text-base leading-7 text-muted-foreground">
            这是本账号最近 30 天的数。完成报告 {inputs?.analyses ?? 0}，一键获客 {inputs?.acquired ?? 0}，入库线索 {inputs?.leads ?? 0}，合格 {inputs?.qualified ?? 0}，受众 {inputs?.audience ?? 0}，送达人数 {inputs?.delivered_people ?? 0}，打开人数 {inputs?.opened_people ?? 0}，有效获客 {inputs?.wins ?? 0}，冷启入队 {inputs?.activations ?? 0}，冷启打开或回复 {inputs?.cold_hit ?? 0}，召回送达 {inputs?.recall_delivered ?? 0}，回暖 {inputs?.warm_hit ?? 0}。分母为 0 时显示「—」。
          </p>
        )}
        <dl className="mt-6 space-y-3">
          {term.words.map(([word, text]) => (
            <div key={word}>
              <dt className="text-sm font-semibold">{word}</dt>
              <dd className="mt-1 text-base leading-7 text-muted-foreground">{text}</dd>
            </div>
          ))}
        </dl>
        <button type="button" className="mt-8 rounded-xl border border-border px-5 py-3 text-base" onClick={onClose}>关闭</button>
      </div>
    </div>
  )
}
