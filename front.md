# PickGlobal · v0.com 首页生成提示词

将以下提示词粘贴到 [v0.com](https://v0.com)：

```text
Create a polished, production-quality responsive homepage for “PickGlobal”, a B2B SaaS platform for Chinese cross-border sellers.

Product positioning:
- Tagline: “选品分析与出海获客全链路闭环”
- English subtitle: “From Product Discovery to Global Customer Growth”
- Two product paths only:
  1) 选品与分析报告
  2) 帮人获客（九路：线索获客 → 成交 → 召回）
- Path B rule: channels 1–5 acquire customers; 6–8 optimize those channels (and can sell PickGlobal itself); 6–9 can sell PickGlobal
- Initial target markets: United States and China; cross-border mix ~80% CN-US/HK/AU + 20% domestic
- Primary users: Chinese manufacturers, exporters, independent sellers, and cross-border e-commerce teams
- Website domain: pickgrobal.mornscience.top

Build the homepage in Simplified Chinese, with short English labels where they improve the international feel.

Page structure:

1. Sticky navigation
- PickGlobal logo with a simple globe/compass icon
- Links: 选品分析、获客九路、应用场景、常见问题
- Secondary button: 登录
- Primary button: 免费体验
- Responsive mobile navigation

2. Hero section
- Eyebrow: “Oversea Market Selling”
- Headline: “两条路径：先算清货，再帮你把客户找回来”
- Supporting copy: “PickGlobal 把选品分析报告，与电商、社交、展会、代理、大数据等九路获客成交召回，放进同一个工作台。”
- Primary CTA: “开始分析商品”
- Secondary CTA: “查看获客九路”
- Trust note: “首期支持中国与美国市场；数智人 DEMO 为占位演示”
- Add an elegant product dashboard mockup showing:
  - Product opportunity score
  - Estimated profit margin
  - Tax and logistics indicators
  - Risk level
  - Multi-channel lead sources
  - Deal and recall performance
- The mockup should look realistic but clearly be sample/demo data

3. Product path A · 选品与分析报告
Create a connected path:
- 01 导入商品：手动、CSV 或国内货源接口
- 02 规则计算：利润、税务、时效、风险（金额可复核）
- 03 AI 摘要：机会解释与行动建议
- 04 一键进入获客

Use a horizontal stepper on desktop and stacked cards on mobile.

4. Product analysis showcase
Use a split layout:
- Left: persuasive copy and feature checklist for Path A
- Right: an analysis report UI with tabs for:
  - 市场机会
  - 利润测算
  - 税务
  - 物流时效
  - 风险提示
Include charts, score cards, and a concise AI-generated recommendation.

5. Product path B · 获客九路
Create nine concise capability cards grouped as:
- 主获客 1–5：电商平台、社交平台、线上展会、12 代理渠道、智慧大脑大数据
- 优化 6–8：GEO/SEO、AI 内容工厂+数字人+线下客流、跨境元素特色复现
- 本品销售 9：RaaS 官网抽成 + APP 账户销售
Each card must emphasize the shared loop: 线索获客 → 成交 → 召回.
Do not invent a third product line for cold-start/recall; keep it inside Path B.

6. Use cases
Cards for:
- 跨境电商卖家
- 外贸工厂
- 品牌出海团队
- 外贸服务商

7. Multi-platform section
State that users can access the same workspace through:
- Web
- 微信小程序
- Android
- iOS
- macOS
- Windows

Use subtle device icons and emphasize “一个工作台，多端同步”.

8. Security and infrastructure strip
Use concise, non-technical messaging:
- 国内云基础设施
- 数据集中管理
- 操作记录可追溯
- AI 分析与文案生成

Do not mention Vercel, Supabase, OpenAI, Kubernetes, implementation costs, or internal MVP details.

9. FAQ
Include:
- PickGlobal 适合哪些企业？
- 可以分析自有商品吗？
- 首期支持哪些市场？
- 如何获取潜在客户？
- AI 会自动发送邮件吗？
- 是否支持多端使用？

10. Final CTA
- Headline: “让每一个商品，都找到更合适的海外市场”
- Copy: “从第一次分析到客户召回，在一个工作台完成。”
- Buttons: “免费体验” and “预约演示”

11. Footer
- Product name and short positioning
- Navigation groups: 产品、资源、公司
- Contact placeholder
- Domain and copyright
- Add a note that dashboard data shown on the homepage is sample data

Visual direction:
- Modern international B2B SaaS aesthetic
- Clean light theme with deep navy text, cobalt blue primary color, emerald accents, and soft blue gradients
- Generous whitespace, subtle grid/globe background, rounded 16–20px cards
- Refined shadows and borders; avoid excessive glassmorphism
- Strong typography and clear visual hierarchy
- Use world-map, route, analytics, and growth motifs sparingly
- Avoid generic stock photos, flags, cartoon illustrations, and crypto-like styling
- Add restrained scroll animations and hover states
- Meet WCAG contrast expectations

Technical requirements:
- Next.js App Router
- TypeScript
- Tailwind CSS
- shadcn/ui
- Lucide icons
- Recharts for dashboard charts
- Fully responsive and accessible
- Build reusable components
- Homepage only at `/`
- Use local mock data; no backend or external API integration
- Make all navigation and CTA elements visibly interactive
```
