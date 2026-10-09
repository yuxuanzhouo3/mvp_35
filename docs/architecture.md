# PickGlobal 代码注记

```text
mvp_35/
├── project.md                 产品两条路径、八率、五时效、4S 目标
├── front.md                   多端呈现；Core Services 对应下面的 modules
├── back.md                    后端边界；目录以当前 backend/ 为准
├── admin.md                   平台后台页面与 /admin/* 接口
├── workflow.md                发布记录
├── docs/
│   ├── architecture.md        本文件
│   ├── pickglobal-placeholders.pdf
│   ├── demo1/
│   │   ├── pickglobal-user-guide.mp4            Eddy，上一版
│   │   ├── pickglobal-user-guide-xiaoxiao.mp4   晓晓，上一版
│   │   ├── pickglobal-user-guide-yunxi.mp4      云希，上一版
│   │   ├── pickglobal-user-guide-yunjian.mp4    云健；与 demo2 相同，站上拷贝在 public/guides
│   │   └── frames/                              上一版截图，不含后台
│   └── demo2/
│       ├── pickglobal-user-guide-yunjian.mp4    云健，当前产品：国内默认、报告弹层、九路分页
│       └── frames/                              官网到看板，不含后台
├── front/                     Next.js 16 · :3000 · pickglobal-web
│   ├── app/
│   │   ├── layout.tsx · globals.css             全站壳与样式
│   │   ├── page.tsx                             官网 /
│   │   ├── login/page.tsx                       租户登录
│   │   ├── register/page.tsx                    注册
│   │   ├── forgot/page.tsx                      忘记密码
│   │   ├── reset/page.tsx                       重置密码
│   │   ├── workspace/
│   │   │   ├── layout.tsx                       无 token 去 /login?next=
│   │   │   ├── page.tsx                         看板，八率
│   │   │   ├── products/page.tsx                选品分析，商品入库
│   │   │   ├── reports/[id]/page.tsx            报告 + 一键获客
│   │   │   ├── acquire/page.tsx                 线索、草稿、批准、发送
│   │   │   └── billing/page.tsx                 账单
│   │   ├── admin/
│   │   │   ├── login/page.tsx                   平台登录，与租户分开
│   │   │   ├── layout.tsx · components.tsx      侧栏与顶栏
│   │   │   ├── page.tsx                         运营总览
│   │   │   ├── ads/page.tsx                     广告
│   │   │   ├── users/page.tsx                   用户
│   │   │   ├── analytics/page.tsx               行为
│   │   │   ├── invitations/page.tsx             邀请
│   │   │   ├── recall/page.tsx                  平台用户召回
│   │   │   ├── search/page.tsx                  全局搜索
│   │   │   ├── audit/page.tsx                   审计
│   │   │   └── settings/page.tsx                平台设置
│   │   └── api/[...path]/route.ts               /api 转到 FastAPI :8000
│   ├── components/
│   │   ├── guide-video.tsx                      顶栏「操作演示」，云健
│   │   ├── auth-shell.tsx                       登录类页面外壳
│   │   ├── product-library.tsx                  官网商品库
│   │   ├── finger-scale.tsx                     双指缩放
│   │   └── ui/button.tsx
│   ├── lib/
│   │   ├── api.ts                               租户请求；401 去登录
│   │   ├── session.ts                           租户 token
│   │   ├── admin-session.ts                     平台 token
│   │   ├── client-adapter.ts                    按端裁剪
│   │   └── utils.ts
│   ├── public/guides/yunjian.mp4                站上播放的教程
│   ├── next.config.mjs                          standalone 输出
│   ├── cloudbaserc.json                         pickglobal-web 部署
│   └── Dockerfile
├── backend/                   Python FastAPI · :8000 · pickglobal-api
│   ├── app/
│   │   ├── main.py                              挂路由，打开 store
│   │   ├── api/
│   │   │   ├── deps.py                          请求绑定租户
│   │   │   └── v1/
│   │   │       ├── router.py                    商品、分析、线索、活动、账单、任务
│   │   │       ├── auth_routes.py               注册、登录、忘记密码、重置
│   │   │       ├── admin_routes.py              /admin/*
│   │   │       ├── pay_routes.py                下单、查单、微信回调
│   │   │       ├── ai_routes.py                 对话，只解释不改数
│   │   │       ├── core_routes.py               健康检查
│   │   │       └── contract.py                  契约路由
│   │   ├── core/
│   │   │   ├── errors.py                        稳定错误码
│   │   │   └── timeutil.py
│   │   ├── modules/
│   │   │   ├── auth.py · tokens.py · passwords.py
│   │   │   ├── selection.py                     路径 A
│   │   │   ├── acquisition.py                   路径 B
│   │   │   ├── payment.py                       订单与分成账本
│   │   │   ├── ai_gateway.py                    混元
│   │   │   ├── providers.py                     九路；DEMO 可 mock
│   │   │   ├── jobs.py · events.py · state.py · scale.py
│   │   │   └── kpi_view.py                      看板读模型
│   │   ├── services/
│   │   │   ├── profit.py                        规则金额
│   │   │   ├── metrics.py                       八率 + 五时效
│   │   │   ├── identity.py                      token → 租户；平台管理员
│   │   │   └── common.py                        渠道、套餐、入库、账本签名
│   │   └── workers/
│   │       ├── loop.py                          python -m app.workers.loop
│   │       └── execute.py                       分析、发现线索、发送
│   ├── db/
│   │   ├── store.py                             默认 JSON
│   │   ├── cloudbase_store.py                   STORAGE_ENGINE=cloudbase
│   │   ├── cloudbase_sql.py                     documents 读写
│   │   ├── sql/ · cloudbase/migrations/         表结构
│   │   └── repository.py · schema.py · money.py · migrate.py
│   ├── config/
│   │   ├── settings.py                          环境变量
│   │   ├── flags.json · flags.py                功能开关
│   │   └── s1|s2|s3|s4-v1.0.0.json              4S 版本
│   ├── data/store.json                          本地库；测试只用这份
│   ├── Dockerfile · cloudbaserc.json · docker-compose.yml
│   └── pyproject.toml
└── test/
    ├── conftest.py · support.py                 测试夹具；强制 JSON
    ├── mvp/                                     冒烟、接口、迁移、回退
    ├── svp/                                     契约、KPI、CloudBase SQL、后台接口
    ├── business/                                安全、兼容、性能、AI
    ├── speedup1/                                金丝雀、混沌、性能
    ├── speedup2/                                观测、合规
    └── speedup3/                                全球与回退
```
