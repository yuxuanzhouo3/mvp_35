export type SharePlan = {
  id: string
  name: string
  monthYuan: number
  take: number
  leadFen: number
  recallFen: number
}

/** 月费越高，成交抽成和计件单价越低。计件单位是分。 */
export const sharePlans: SharePlan[] = [
  { id: 'free', name: '免费', monthYuan: 0, take: 0.9, leadFen: 100, recallFen: 50 },
  { id: 'op_100', name: '会员 100', monthYuan: 100, take: 0.7, leadFen: 50, recallFen: 25 },
  { id: 'op_1000', name: '会员 1000', monthYuan: 1000, take: 0.5, leadFen: 20, recallFen: 10 },
  { id: 'op_10000', name: '会员 10000', monthYuan: 10000, take: 0.3, leadFen: 10, recallFen: 5 },
  { id: 'op_100000', name: '会员 100000', monthYuan: 100000, take: 0.1, leadFen: 0, recallFen: 0 },
  { id: 'op_1000000', name: '会员 1000000', monthYuan: 1000000, take: 0, leadFen: 0, recallFen: 0 },
]

export function sharePlan(id: string | null | undefined) {
  return sharePlans.find((item) => item.id === id) || null
}
