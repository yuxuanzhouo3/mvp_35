'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Button, buttonVariants } from '@/components/ui/button'
import {
  ArrowRight, BarChart3, Check, ChevronDown, ChevronRight, Globe2, Laptop, Menu, MapPin,
  Monitor, PackageSearch, Radar, RefreshCw, ShieldCheck, Smartphone, Sparkles, Store,
  Tablet, Target, Terminal, Users, X,
} from 'lucide-react'
import { Bar, BarChart, ResponsiveContainer, XAxis, YAxis } from 'recharts'
import { readClient, type ClientInfo } from '@/lib/client-adapter'
import { ProductLibrary } from '@/components/product-library'
import { GuideVideo } from '@/components/guide-video'
import { AdSlot } from '@/components/ad-slot'
import { api } from '@/lib/api'
import { accessToken, logoutSession } from '@/lib/session'

const marketData = [
  { name: '利润', value: 50 }, { name: '税费', value: 18 }, { name: '物流', value: 32 }, { name: '风险', value: 24 },
]
const faqs = [
  ['PickGlobal 适合哪些企业？', '适合中国制造商、出口商、独立卖家和跨境电商团队。工作台只做两件事：选品分析报告，以及九路获客成交召回。'],
  ['可以分析自有商品吗？', '可以。手动录入、CSV 或国内货源目录会进入同一个商品库，不绑定外部电商选品主库。'],
  ['首期支持哪些市场？', '默认货源中国、目标美国，税务按中美口径。路线可以扩展到香港、澳大利亚和一部分内陆市场。'],
  ['如何获取潜在客户？', '电商、社交、展会、代理和大数据是主获客；GEO/SEO、内容与跨境元素用于优化；RaaS 用来销售 PickGlobal 本身。冷启和召回属于获客路径，不是第三条产品线。'],
  ['AI 会自动发送邮件吗？', '不会。文案生成后必须人工批准才发送。利润、税费和评分由规则引擎计算，模型不能改这些数字。'],
  ['是否支持多端使用？', '手机、iPad、微信小程序、Web、Mac、Windows 和 Linux 共用同一套选品与获客。手机上直接开始分析，不必先装客户端。'],
]
const pathA = [
  ['01', '双向入口', '手动、CSV，或从国内货源目录选入同一商品库', PackageSearch],
  ['02', '路线与市场', '货源地、目标市场、物流路线、税务口径和售价币种', Globe2],
  ['03', '规则引擎', '利润、税务、时效和风险可复核，模型只解释不改数', BarChart3],
  ['04', '报告并获客', '四维报告上的一键获客，会带上这份分析', Target],
]
const channelGroups = [
  {
    title: '主获客 1–5',
    items: [
      ['B1', 'ecommerce', '电商平台', 'Amazon、Temu、Walmart、淘宝、拼多多。访客、询盘和买家进入同一线索池。'],
      ['B2', 'social', '社交平台', 'LinkedIn、Facebook、微信小程序、抖音、小红书、快手。'],
      ['B3', 'expo', '线上展会', '会期集中发现，会后进入冷启或召回。'],
      ['B4', 'agency', '12 代理渠道', '渠道子账户获客，分成与线索账分开。'],
      ['B5', 'enrichment', '智慧大脑大数据', '企查查、天眼查等来源去重、打分并留痕。'],
    ],
  },
  {
    title: '优化 6–8，也可用于销售本品',
    items: [
      ['B6', 'geo_seo', 'GEO / SEO', '给前五路补充落地页归因，不另开线索主表。'],
      ['B7', 'content_dh', '内容、数智人、线下', '内容任务和扫码获客。数智人 DEMO 为占位演示。'],
      ['B8', 'cross_border', '跨境元素复现', '约 80% 覆盖中美、中港、中澳，20% 覆盖内陆。'],
    ],
  },
  {
    title: '本品销售',
    items: [
      ['B9', 'raas', 'RaaS', '官网成功抽成和 APP 账户销售。抽成账本与普通获客率分开。'],
    ],
  },
]

function SectionTitle({ eyebrow, title, copy }: { eyebrow: string; title: string; copy?: string }) {
  return (
    <div className="mx-auto flex max-w-2xl flex-col items-center gap-4 text-center">
      <span className="eyebrow">{eyebrow}</span>
      <h2 className="text-balance text-3xl font-semibold tracking-tight text-foreground md:text-5xl">{title}</h2>
      {copy && <p className="text-pretty text-base leading-7 text-muted-foreground md:text-lg">{copy}</p>}
    </div>
  )
}

export default function Page() {
  const router = useRouter()
  const [menuOpen, setMenuOpen] = useState(false)
  const [activeTab, setActiveTab] = useState('市场机会')
  const [openFaq, setOpenFaq] = useState<number | null>(0)
  const [chartReady, setChartReady] = useState(false)
  const [client, setClient] = useState<ClientInfo | null>(null)
  const [signedIn, setSignedIn] = useState(false)
  const [accountName, setAccountName] = useState('')
  const [loginHint, setLoginHint] = useState('')
  const [loginNext, setLoginNext] = useState('/workspace/acquire')
  useEffect(() => {
    setChartReady(true)
    setClient(readClient())
    if (!accessToken()) return
    setSignedIn(true)
    api<{ user: { display_name?: string; username?: string; email?: string } }>('/users/me')
      .then((me) => setAccountName(me.user.display_name || me.user.username || me.user.email || '已登录'))
      .catch(() => {
        setSignedIn(Boolean(accessToken()))
        setAccountName((current) => current || '已登录')
      })
  }, [])
  function openChannel(code: string, id: string) {
    const next = `/workspace/acquire?channel=${id}`
    if (accessToken()) {
      router.push(next)
      return
    }
    setLoginNext(next)
    setLoginHint(`请先登录。登录后会进入 ${code}。`)
    document.getElementById('path-b')?.scrollIntoView({ behavior: 'smooth' })
  }
  function signOut() {
    void logoutSession().then(() => {
      setSignedIn(false)
      setAccountName('')
    })
  }
  const scrollTo = (id: string) => {
    setMenuOpen(false)
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' })
  }

  return (
    <main className="min-h-screen overflow-hidden pb-24 md:pb-0">
      <header className="site-header sticky top-0 z-50 border-b border-border/70 bg-background/90 backdrop-blur-md">
        <div className="container flex h-14 items-center justify-between md:h-16">
          <a href="#top" className="flex items-center gap-2" aria-label="PickGlobal 首页">
            <span className="flex size-8 items-center justify-center rounded-xl bg-primary text-primary-foreground"><Globe2 className="size-[18px]" /></span>
            <span className="text-lg font-semibold tracking-tight">Pick<span className="text-primary">Global</span></span>
          </a>
          <nav className="hidden items-center gap-7 text-sm text-muted-foreground md:flex">
            <button onClick={() => scrollTo('path-a')}>选品分析</button>
            <button onClick={() => scrollTo('path-b')}>获客九路</button>
            <button onClick={() => scrollTo('scenes')}>应用场景</button>
            <button onClick={() => scrollTo('faq')}>常见问题</button>
          </nav>
          <div className="hidden items-center gap-3 md:flex">
            {signedIn ? (
              <>
                <Link href="/workspace" className={buttonVariants({ variant: 'ghost' })}>工作台</Link>
                {accountName && <span className="max-w-28 truncate text-sm text-muted-foreground">{accountName}</span>}
                <button type="button" className="text-sm text-muted-foreground hover:text-foreground" onClick={signOut}>退出</button>
              </>
            ) : (
              <>
                <Link href="/login" className={buttonVariants({ variant: 'ghost' })}>登录</Link>
                <Link href="/register" className={buttonVariants()}>免费体验 <ArrowRight data-icon="inline-end" /></Link>
              </>
            )}
            <GuideVideo />
          </div>
          <div className="flex items-center gap-2 md:hidden">
            <GuideVideo />
            <Button variant="ghost" size="icon" className="size-11" onClick={() => setMenuOpen(!menuOpen)} aria-label={menuOpen ? '关闭菜单' : '打开菜单'}>{menuOpen ? <X /> : <Menu />}</Button>
          </div>
        </div>
        {menuOpen && (
          <div className="border-t border-border bg-background px-5 py-5 md:hidden">
            <nav className="flex flex-col gap-1 text-base">
              <button className="min-h-11 text-left" onClick={() => scrollTo('path-a')}>选品分析</button>
              <button className="min-h-11 text-left" onClick={() => scrollTo('path-b')}>获客九路</button>
              <button className="min-h-11 text-left" onClick={() => scrollTo('scenes')}>应用场景</button>
              <button className="min-h-11 text-left" onClick={() => scrollTo('faq')}>常见问题</button>
              {signedIn ? (
                <>
                  {accountName && <p className="min-h-11 text-left text-muted-foreground">{accountName}</p>}
                  <Link href="/workspace" className="min-h-11 text-left">工作台</Link>
                  <button type="button" className="min-h-11 text-left" onClick={signOut}>退出</button>
                </>
              ) : (
                <>
                  <Link href="/login" className="min-h-11 text-left">登录</Link>
                  <Link href="/register" className={buttonVariants({ className: 'mt-2 min-h-12' })}>免费体验</Link>
                </>
              )}
            </nav>
          </div>
        )}
      </header>

      <section id="top" className="hero-grid relative">
        <div className="container grid items-center gap-6 py-8 md:grid-cols-[.95fr_1.05fr] md:gap-12 md:py-28">
          <div className="relative z-10 flex flex-col items-start gap-4 md:gap-6">
            <span className="eyebrow"><Sparkles className="size-3.5" /> Oversea Market Selling</span>
            <h1 className="max-w-xl text-balance text-[1.7rem] font-semibold leading-[1.15] tracking-[-.03em] md:text-6xl md:leading-[1.1] md:tracking-[-.04em]">两条路径：先算清货，再帮你把客户找回来</h1>
            <p className="max-w-lg text-pretty text-[15px] leading-6 text-muted-foreground md:text-lg md:leading-7">
              <span className="md:hidden">先看清利润和风险，再把客户找回来。</span>
              <span className="hidden md:inline">PickGlobal 把选品分析报告，与电商、社交、展会、代理、大数据等九路获客成交召回，放进同一个工作台。</span>
            </p>
            <div className="flex w-full flex-col gap-3 sm:w-auto sm:flex-row">
              <Link href="/workspace/products" className={buttonVariants({ size: 'lg', className: 'min-h-12 w-full text-base sm:w-auto' })}>开始分析商品 <ArrowRight data-icon="inline-end" /></Link>
              <Button size="lg" variant="outline" className="min-h-12 w-full text-base sm:w-auto" onClick={() => scrollTo('path-b')}>查看获客九路</Button>
            </div>
            <div className="grid w-full grid-cols-2 gap-2 md:hidden" aria-label="样例指标">
              {[['机会分', '80'], ['利润率', '49.9%'], ['税费', '可复核'], ['风险', '低']].map(([label, value]) => (
                <div key={label} className="rounded-xl border border-border bg-card px-2 py-2.5"><p className="text-[10px] text-muted-foreground">{label}</p><p className="mt-1 text-sm font-semibold">{value}</p></div>
              ))}
            </div>
            <div className="flex items-center gap-2 text-xs text-muted-foreground"><MapPin className="size-3.5 shrink-0 text-emerald-600" /> 首期支持中国与美国市场</div>
          </div>
          <div className="dashboard-shell animate-float hidden md:block" aria-label="PickGlobal 工作台演示">
            <div className="flex items-center justify-between border-b border-border/70 px-4 py-3 md:px-5">
              <div className="flex items-center gap-2"><div className="flex size-7 items-center justify-center rounded-lg bg-primary text-primary-foreground"><Globe2 className="size-4" /></div><span className="text-xs font-semibold">选品与获客工作台</span></div>
              <span className="rounded-full bg-emerald-50 px-2 py-1 text-[10px] font-medium text-emerald-700">演示数据</span>
            </div>
            <div className="grid gap-3 p-4 md:grid-cols-2 md:p-5">
              {[['机会分', '80'], ['利润率', '49.9%'], ['税费', '可复核'], ['风险', '低']].map(([label, value]) => (
                <div key={label} className="rounded-xl border border-border bg-card p-3"><p className="text-[10px] text-muted-foreground">{label}</p><p className="mt-2 text-xl font-semibold">{value}</p></div>
              ))}
              <div className="rounded-xl border border-border bg-card p-3 md:col-span-2">
                <p className="text-xs font-semibold">九路线索与成交</p>
                <p className="mt-2 text-[11px] leading-5 text-muted-foreground">电商 · 社交 · 展会 · 代理 · 大数据 · GEO · 内容 · 跨境 · RaaS。成交和召回都回到同一条获客路径。</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <AdSlot placement="home_mid_banner" className="container my-4 max-md:my-3" />

      <section id="library" className="section-padding border-t border-border bg-muted/30">
        <div className="container max-w-3xl">
          <SectionTitle eyebrow="Product library" title="商品库" copy="搜索已入库的商品，使用它生成分析报告，或删除这条记录。" />
          <div className="mt-8">
            <ProductLibrary />
          </div>
        </div>
      </section>

      <section id="path-a" className="section-padding">
        <div className="container">
          <SectionTitle eyebrow="Path A" title="选品与分析报告" copy="双向入口汇入同一商品库，算清利润和风险之后，再进入获客。" />
          <div className="mt-14 grid gap-4 md:grid-cols-4">
            {pathA.map(([num, title, copy, Icon], index) => (
              <div key={num as string} className="step-card relative">
                <div className="mb-5 flex items-center justify-between"><span className="text-xs font-semibold text-primary">{num as string}</span><span className="flex size-9 items-center justify-center rounded-xl bg-primary/10 text-primary"><Icon className="size-4" /></span></div>
                <h3 className="font-semibold">{title as string}</h3>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">{copy as string}</p>
                {index < 3 && <ChevronRight className="step-arrow" />}
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="analysis" className="section-padding bg-muted/35">
        <div className="container grid items-center gap-12 md:grid-cols-[.82fr_1.18fr]">
          <div>
            <span className="eyebrow">Auditable report</span>
            <h2 className="mt-4 text-balance text-3xl font-semibold tracking-tight md:text-5xl">报告能复核，也能接着获客</h2>
            <ul className="mt-7 flex flex-col gap-4">
              {['金额用小数规则计算，并保存规则版本', '改了市场或成本，必须重算才出新报告', '一键获客会带上这份分析编号'].map((item) => (
                <li key={item} className="flex items-start gap-3 text-sm"><span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-emerald-700"><Check className="size-3" /></span>{item}</li>
              ))}
            </ul>
            <Link href="/workspace/products" className={`${buttonVariants()} mt-7`}>打开选品分析</Link>
          </div>
          <div className="report-card">
            <div className="flex gap-1 overflow-x-auto border-b border-border px-3 pt-3 md:px-5">
              {['市场机会', '利润测算', '税务', '物流时效', '风险提示'].map((tab) => (
                <button key={tab} onClick={() => setActiveTab(tab)} className={`report-tab ${activeTab === tab ? 'report-tab-active' : ''}`}>{tab}</button>
              ))}
            </div>
            <div className="p-4 md:p-6">
              <p className="text-xs text-muted-foreground">{activeTab} · 规则摘要</p>
              <h3 className="mt-2 text-xl font-semibold">美国市场样本：利润率约 49.9%</h3>
              <div className="mt-6 h-36">
                {chartReady && (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={marketData} layout="vertical" margin={{ left: 10, right: 8 }}>
                      <XAxis type="number" hide />
                      <YAxis dataKey="name" type="category" axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }} width={40} />
                      <Bar dataKey="value" fill="var(--primary)" radius={[0, 5, 5, 0]} barSize={10} />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </div>
              <p className="mt-3 text-xs text-muted-foreground">首页图表是样例。工作台里的金额以规则引擎结果为准。</p>
            </div>
          </div>
        </div>
      </section>

      <section id="path-b" className="section-padding">
        <div className="container">
          <SectionTitle eyebrow="Path B" title="九路获客，同一条成交与召回闭环" copy="1–5 负责把客户找来，6–8 用来优化这些通道，也可以销售 PickGlobal，9 是结果抽成。登录后点开一路，进入对应获客页。" />
          {loginHint && (
            <div className="mx-auto mt-8 flex max-w-2xl flex-wrap items-center justify-center gap-3 rounded-2xl border border-primary/30 bg-primary/5 px-5 py-4 text-sm">
              <p>{loginHint}</p>
              <Link href={`/login?next=${encodeURIComponent(loginNext)}`} className={buttonVariants()}>去登录</Link>
            </div>
          )}
          <div className="mt-14 flex flex-col gap-10">
            {channelGroups.map((group) => (
              <div key={group.title}>
                <h3 className="text-sm font-semibold text-primary">{group.title}</h3>
                <div className="mt-4 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                  {group.items.map(([code, id, title, copy]) => (
                    <button key={code} type="button" className="feature-card !min-h-56 !w-full cursor-pointer !p-7 text-left" onClick={() => openChannel(code, id)}>
                      <span className="text-sm font-semibold text-primary">{code}</span>
                      <h3 className="mt-4 text-xl font-semibold">{title}</h3>
                      <p className="mt-3 text-sm leading-7 text-muted-foreground">{copy}</p>
                      <p className="mt-5 text-sm font-medium text-primary">{signedIn ? '进入这一路' : '登录后进入'}</p>
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
          <div className="mt-8"><Link href="/workspace/acquire" className={buttonVariants()}>打开获客经营</Link></div>
        </div>
      </section>

      <section id="scenes" className="section-padding bg-navy text-white">
        <div className="container">
          <div className="max-w-xl"><span className="eyebrow eyebrow-dark">Built for growth teams</span><h2 className="mt-4 text-balance text-3xl font-semibold tracking-tight md:text-5xl">不论你从哪里出发，都能找到增长下一步</h2></div>
          <div className="mt-12 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {[['跨境电商卖家', '先算清一款货，再按渠道找买家', Store], ['外贸工厂', '把产能和目标市场放进同一份报告', PackageSearch], ['品牌出海团队', '统一线索、批准和召回', Sparkles], ['外贸服务商', '用可复核的利润和获客率交付方案', Users]].map(([title, copy, Icon]) => (
              <div key={title as string} className="dark-feature"><Icon className="size-5 text-cyan-300" /><h3 className="mt-8 font-semibold">{title as string}</h3><p className="mt-2 text-sm leading-6 text-slate-300">{copy as string}</p></div>
            ))}
          </div>
        </div>
      </section>

      <section className="section-padding">
        <div className="container">
          <div className="platform-panel">
            <div className="max-w-xl">
              <span className="eyebrow">One workspace, everywhere</span>
              <h2 className="mt-4 text-balance text-3xl font-semibold tracking-tight md:text-5xl">一个工作台，多端同步</h2>
              <p className="mt-5 leading-7 text-muted-foreground">手机看任务，iPad 读报告，小程序做分享。Web、Mac、Windows 和 Linux 打开同一份工作台。</p>
              {client && <p className="mt-3 text-sm font-medium text-foreground">{client.surface === 'phone' || client.surface === 'miniprogram' ? `已按${client.label}排版，从底部开始分析。` : client.surface === 'ipad' ? '已按 iPad 排版，报告和列表可以并排看。' : '安装包稍后开放，现在直接用网页。'}</p>}
            </div>
            <div className="mt-8 grid grid-cols-3 gap-4 text-center sm:grid-cols-4 lg:mt-0 lg:grid-cols-7">
              {[['Web', Monitor], ['手机', Smartphone], ['iPad', Tablet], ['微信小程序', Globe2], ['Mac', Laptop], ['Windows', Monitor], ['Linux', Terminal]].map(([name, Icon]) => (
                <div key={name as string} className={`flex flex-col items-center gap-2 text-xs ${client?.label === name ? 'font-semibold text-foreground' : 'text-muted-foreground'}`}><span className={`flex size-12 items-center justify-center rounded-2xl border bg-background text-primary ${client?.label === name ? 'border-primary ring-2 ring-primary/30' : 'border-border'}`}><Icon className="size-5" /></span>{name as string}</div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="border-y border-border bg-muted/30">
        <div className="container grid gap-4 py-8 sm:grid-cols-2 lg:grid-cols-4">
          {[['国内云基础设施', ShieldCheck], ['数据集中管理', Radar], ['操作记录可追溯', RefreshCw], ['AI 分析与文案生成', Sparkles]].map(([text, Icon]) => (
            <div key={text as string} className="flex items-center gap-3 text-sm font-medium"><Icon className="size-4 text-primary" />{text as string}</div>
          ))}
        </div>
      </section>

      <section id="faq" className="section-padding">
        <div className="container grid gap-12 md:grid-cols-[.7fr_1.3fr]">
          <div>
            <span className="eyebrow">Questions, answered</span>
            <h2 className="mt-4 text-balance text-3xl font-semibold tracking-tight md:text-5xl">还有问题？<br />我们来回答。</h2>
            <Button className="mt-7" variant="outline" onClick={() => scrollTo('contact')}>预约演示 <ArrowRight data-icon="inline-end" /></Button>
          </div>
          <div className="flex flex-col border-t border-border">
            {faqs.map(([question, answer], index) => (
              <div key={question} className="border-b border-border">
                <button className="flex w-full items-center justify-between gap-4 py-5 text-left text-sm font-medium" onClick={() => setOpenFaq(openFaq === index ? null : index)} aria-expanded={openFaq === index}>
                  <span>{question}</span>
                  <ChevronDown className={`size-4 shrink-0 text-muted-foreground transition-transform ${openFaq === index ? 'rotate-180' : ''}`} />
                </button>
                {openFaq === index && <p className="pb-5 pr-8 text-sm leading-6 text-muted-foreground">{answer}</p>}
              </div>
            ))}
          </div>
        </div>
      </section>

      <AdSlot placement="pricing_banner" className="container mb-2 max-md:mb-4" />

      <section id="contact" className="section-padding">
        <div className="container">
          <div className="cta-panel">
            <div className="relative z-10 mx-auto flex max-w-2xl flex-col items-center gap-5 text-center">
              <span className="eyebrow eyebrow-dark">Start your next market</span>
              <h2 className="text-balance text-3xl font-semibold tracking-tight text-white md:text-5xl">让每一个商品，都找到更合适的海外市场</h2>
              <p className="text-slate-300">从第一次分析到客户召回，在一个工作台完成。</p>
              <div className="flex flex-wrap justify-center gap-3">
                <Link href={signedIn ? '/workspace' : '/register'} className={buttonVariants({ size: 'lg', className: '!h-11 !border-transparent !bg-white !px-5 !text-slate-950 hover:!bg-slate-100' })}>{signedIn ? '进入工作台' : '免费体验'} <ArrowRight data-icon="inline-end" /></Link>
                <Link href="/workspace/acquire" className={buttonVariants({ size: 'lg', variant: 'outline', className: '!h-11 !border-cyan-200 !bg-cyan-400/15 !px-5 !text-cyan-50 hover:!bg-cyan-300/25 hover:!text-white' })}>预约演示</Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      <footer className="border-t border-border">
        <div className="container grid gap-10 py-12 md:grid-cols-[1.5fr_1fr_1fr_1fr]">
          <div>
            <div className="flex items-center gap-2"><span className="flex size-8 items-center justify-center rounded-xl bg-primary text-primary-foreground"><Globe2 className="size-4" /></span><span className="font-semibold">Pick<span className="text-primary">Global</span></span></div>
            <p className="mt-4 max-w-xs text-sm leading-6 text-muted-foreground">选品分析与出海获客全链路闭环。</p>
          </div>
          <div><h3 className="text-sm font-semibold">产品</h3><div className="mt-4 flex flex-col gap-3 text-sm text-muted-foreground"><button className="text-left hover:text-foreground" onClick={() => scrollTo('path-a')}>选品分析</button><button className="text-left hover:text-foreground" onClick={() => scrollTo('path-b')}>获客九路</button><Link href="/workspace" className="text-left hover:text-foreground">工作台</Link></div></div>
          <div><h3 className="text-sm font-semibold">资源</h3><div className="mt-4 flex flex-col gap-3 text-sm text-muted-foreground"><button className="text-left hover:text-foreground" onClick={() => scrollTo('faq')}>常见问题</button><button className="text-left hover:text-foreground" onClick={() => scrollTo('scenes')}>应用场景</button><button className="text-left hover:text-foreground" onClick={() => scrollTo('contact')}>预约演示</button></div></div>
          <div><h3 className="text-sm font-semibold">公司</h3><div className="mt-4 flex flex-col gap-3 text-sm text-muted-foreground"><a href="https://pickglobal.mornscience.top" className="hover:text-foreground">pickglobal.mornscience.top</a><a href="mailto:pickglobal@yeah.net" className="hover:text-foreground">pickglobal@yeah.net</a><a href="mailto:mornscience@sina.cn" className="hover:text-foreground">mornscience@sina.cn</a><span>中国 · 美国</span></div></div>
        </div>
        <div className="container flex flex-col gap-2 border-t border-border py-6 text-xs text-muted-foreground md:flex-row md:items-center md:justify-between"><span>© 2026 PickGlobal. 保留所有权利。</span><span>首页展示数据均为样例数据</span></div>
      </footer>
      <div className="phone-dock md:hidden">
        <Link href="/workspace/products" className={buttonVariants({ className: 'min-h-12 flex-1 text-base' })}>开始分析</Link>
        <Link href="/workspace/acquire" className={buttonVariants({ variant: 'outline', className: 'min-h-12 px-4 text-base' })}>获客</Link>
      </div>
    </main>
  )
}
