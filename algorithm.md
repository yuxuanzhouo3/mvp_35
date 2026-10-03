# 4.3 核心功能 · 算法实现说明

给后端实现用。只覆盖 [project.md](project.md) §4.3：选品、获客、KPI。登录、支付订阅、AI 模型不在这里。

金额、利润率、机会分、线索是否合格、是否入队，只由规则 `pg-rules-1.0` 计算。模型只写解释和文案。改公式必须换 `rules_version`，已落库的报告按旧版本复算。

路径都相对于 `/api/v1`。长任务返回 `202`，正文是 `{job_id, status}`，完成后从 `GET /jobs/{job_id}` 读 `result`。查询都带租户。金额用 `Decimal`，四舍五入到 `0.01`；比率四舍五入到 `0.0001`。分母为 0 的比率写成空，界面显示「—」。

## 索引

| 功能 | 算法 | 代码 | 接口 |
| --- | --- | --- | --- |
| A1 CSV | `product-pricer` | `backend/algorithm/product_pricer.py` | `POST /products/imports` · `POST /algorithms/product-pricer` |
| A1 帮我选品 | `selection-assist` | `backend/algorithm/selection_assist.py` | `GET/POST /catalog/search` · `POST /algorithms/selection-assist` |
| A2 路线市场 | `pg-rules-1.0` 快照 | `app/services/profit.py` · `app/services/common.py` | `PATCH /products/{id}` |
| A3 分析引擎 | `pg-rules-1.0` | `app/services/profit.py` · `app/workers/execute.py` | `POST /selection/analyze` · `POST /products/{id}/analyses` |
| A4 报告与获客 | 四维快照 | `app/modules/selection.py` | `GET /reports/{id}` · `POST /reports/{id}/acquire` |
| B1–B5、B8 发现 | 去重 + `lead-score` | `app/workers/execute.py` · `app/modules/acquisition.py` | `POST /lead-searches` · `POST /acquisition/tasks` |
| B4 分成 | 验签账本 | `app/services/common.py` | `POST /billing/agency/commissions` |
| B6、B7 | 占位，无算法 | `app/api/v1/core_routes.py` | 见各节 |
| B9 RAAS | 验签账本 | `app/services/common.py` | `POST /billing/raas/commissions` |
| 触达 | 批准后发送 | `app/api/v1/router.py` | `POST /campaigns` |
| 冷启 / 召回 | 入队规则 | `app/workers/execute.py` | `POST /lifecycle/scan` · `POST /recall` |
| KPI | `snapshot` | `app/services/metrics.py` | `GET /kpi/dashboard` · `GET /metrics` |

报价匹配在 `backend/algorithm/sources.py`。国内源 `GET /sources/pricer/domestic`，海外源 `GET /sources/pricer/overseas`，货源目录 `GET /sources/catalog`。

---

## 共用：利润内核 `pg-rules-1.0`

实现：`calculate(product, rules_version)`，`app/services/profit.py`。A1、A2、A3、A4 都读它，不要另写一套金额。

默认：货源 `CN`，目标 `US`，路线 `CN-US`，术语 `DDP`，税务 `cn_us`，成本 `CNY`，售价 `USD`，汇率 `7.20`。

| 市场 | 平台费率 | 时效（天） | 税务口径 | 关税 | 增值税 |
| --- | --- | --- | --- | --- | --- |
| US | 0.15 | 12–20 | `cn_us` | 0.075 | 0 |
| HK | 0.08 | 2–4 | `cn_hk` | 0 | 0 |
| AU | 0.12 | 14–22 | `cn_au` | 0.05 | 0.10 |
| CN | 0.05 | 2–5 | `domestic` | 0 | 0.13 |

支付费率一律 `0.029`。未知市场的平台费率用 `0.15`，时效用 7–21 天。

```text
R = target_price_usd
采购USD = cost_cny / fx
包装USD = packaging_cny / fx
国内段USD = domestic_freight_cny / fx
国际段USD = international_freight_usd
C = 采购USD + 包装USD + 国内段USD + 国际段USD
F = R × (平台费率 + 0.029)
T = (采购USD + 国际段USD) × 关税率 + R × 增值税率
N = R − C − F − T
利润率 = N / R
```

风险：利润率 &lt; 0.05，或国际段 / R &gt; 0.35 → `高`；否则利润率 &lt; 0.15 → `中`；否则 `低`。

机会分 = `利润率 × 160`，限制在 0–100 后取整。风险为 `高` 再减 15，最低 0。

拒绝：非数字、负数、`R ≤ 0`、`fx ≤ 0`、未知 `tax_regime`。错误码 `INVALID_AMOUNT` 或 `UNKNOWN_TAX_REGIME`。

落库必带：`net_margin`、`net_profit_usd`、`fx_usd_cny`、`rules_version`。解释里写出版本号，并写明金额只由规则引擎计算。`explanation_model` 为 `rules`。

四维从同一次 `calculate` 切出，禁止再算一遍：

| 维 | 字段 |
| --- | --- |
| 利润 | `net_profit_usd`、`net_margin` |
| 税务 | `tax_usd`、`duty_rate`、`vat_rate`、`tax_regime` |
| 时效 | `transit_days_min`、`transit_days_max` |
| 风险 | `risk_level`、`opportunity_score` |

---

## A1 自有导入 · CSV · `product-pricer`

比价。策略是市面上常见的动态定价：对齐竞争中位价，并且不低于成本加成的 15% 利润线（`competitor-median-with-cost-plus-floor`）。汇率优先用 Frankfurter 发布的欧洲央行 USD/CNY（`FX_API_URL`）。全球商品货架价在配置了 `PRICER_API_URL` 时走第三方动态报价（DxPhi 形态：`product`、`country`、`X-Api-Key`，读 `sellers[].price` 或 `market_price.median`）。第三方没配或调用失败时，汇率退回商品上的数字，货架价退回本地报价本。不要自己再写一套利润公式。

一条 CSV 入口只接受 `algorithm=product-pricer`。其他名字返回 `UNKNOWN_ALGORITHM`。不传算法时只入库，不比价。

### 接口

| 方法 | 作用 |
| --- | --- |
| `POST /algorithms/product-pricer` | 比价，不入库。正文可是 `{csv}` 或单品字段 |
| `POST /products/imports` | `202`。`algorithm=product-pricer` 时，成功行的 `result.quotes` 带比价 |
| `GET /sources/pricer/domestic` | 国内报价。查询 `q`、`sku` |
| `GET /sources/pricer/overseas` | 海外报价。查询 `q`、`sku`、`market`（默认 US） |

单品字段与商品相同：`name`、`sku`、`cost_cny`、`packaging_cny`、`domestic_freight_cny`、`international_freight_usd`、`target_price_usd`，以及可选的市场字段。缺包装和运费时按 `0`。入库前先走 `product_from_body`，名称或 SKU 空则该行失败。

### 匹配

`match_quotes`。国内只留市场 `CN`，海外只留商品的 `target_market`。

1. SKU 全等（忽略大小写）优先。有全等就不用模糊行。
2. 否则：名称互相包含，或关键词出现在名称或类目里。

中位数：奇数取中间；偶数取中间两数平均。国内中位数再除以汇率得到美元。样品最多 8 条。

### 建议售价

```text
fixed_tax = (采购USD + 国际段USD) × 关税率
fee_rate = 平台费率 + 0.029
R ≥ (C + fixed_tax) / (1 − fee_rate − 增值税率 − 0.15)
```

分母 ≤ 0 则 `INVALID_AMOUNT`，表示当前费率下没有 15% 利润线。

| 海外中位价 | `recommended_price_usd` |
| --- | --- |
| 没有 | 标价已不低于利润线则用标价，否则用利润线 |
| ≥ 利润线 | 海外中位价 |
| &lt; 利润线 | 利润线 |

标价低于利润线时，`advice` 先写「当前售价低于 15% 利润线。」再写上表对应的一句。

| `position` | 条件 |
| --- | --- |
| `no_overseas_comp` | 没有海外中位价 |
| `below_market` | 标价 &lt; 中位价 × 0.95 |
| `above_market` | 标价 &gt; 中位价 × 1.05 |
| `in_band` | 其余 |

### 输出

每条报价包含：`algorithm`、`rules_version`、`sku`、`name`、`listed_price_usd`、`floor_price_usd`、`recommended_price_usd`、`position`、`spread_vs_domestic_usd`、`spread_vs_overseas_usd`、`domestic`、`overseas`、`report`（四维）、`advice`。

`domestic` / `overseas` 含 `median`、`usd`、`count`、`samples`、`source` 路径。CSV 接口另有 `items` 和 `errors`（最多 20 条）。某一行失败不让整表失败。

导入任务在重复 SKU 检查通过之后才写入。重复行不产生报价，错误是 `DUPLICATE_SKU`。成功时 `result` 增加 `algorithm`、`sources`、`quotes`，`steps` 增加 `price_compare`。

### 完成标准

样品行 `sku=CUP-1,name=样品杯,cost_cny=72,target_price_usd=40,international_freight_usd=2`：标价 `40.00`，利润线 `19.23`，建议价 `43.49`，`position=below_market`。用建议价再跑 `calculate`，利润率 ≥ 0.15。

---

## A1 帮我选品 · `selection-assist`

按关键词向各大商品平台拉实时在售货，归一成同一行，再用利润内核排序。目录过滤仍是名称、SKU、类目的子串，排序发生在过滤之后。

没有平台钥匙、或该平台超时，这一路记为失败并跳过，不让整次搜索失败。全部平台都不可用时，退回本地演示目录（`cat_cup`、`cat_lamp`、`cat_pet`），并在结果里写 `provider=local-book`。有任一平台返回时 `provider=live`。

不带 `algorithm` 时只返回目录行，不写 `selection`。带了别的算法名则 `UNKNOWN_ALGORITHM`。只有 `selection-assist` 打分。

每一行先变成：

| 字段 | 来源 |
| --- | --- |
| `id` | `{platform}:{external_id}` |
| `name` | 标题 |
| `sku` | 平台商品号；没有则用 `external_id` |
| `category` | 类目，没有则「未分类」 |
| `cost_cny` | 国内供货价，已是人民币。分为单位的先除以 100。海外行没有供货价则留空，不参与利润排序 |
| `target_price_usd` | 海外标价按 Frankfurter 折成美元。国内行用供货价加默认运费后除以同一汇率，得到参考售价 |
| `supplier` | 店铺或供应商名 |
| `platform` | 下表的平台 id |
| `external_id` | 平台侧商品 id |
| `source_url` | 商品页，可空 |

国内平台填成本和供应商。海外平台填目标市场售价。同一关键词两边都查：国内行用来入库，海外行用来给 `product-pricer` 当货架样品。选品排序只对能算出 `cost_cny` 和 `target_price_usd` 的行打分。

### 国内货源平台

钥匙未配置时不调用。调用走各平台官方开放平台，不抓网页。

| 平台 id | 平台 | 官方接口 | 检索 | 取用字段 |
| --- | --- | --- | --- | --- |
| `1688` | 1688 | `https://gw.open.1688.com` | 跨境选品 `POST /openapi/param2/1/com.alibaba.fenxiao.crossborder/product.search.keywordQuery/{APPKEY}`，详情 `product.search.queryProductDetail`；站内关键词 `POST /openapi/param2/1/com.alibaba.product/product.keyword.search/{APPKEY}` | `subject`、价格、起批量、公司名、`offerId`、详情链接 |
| `taobao` | 淘宝联盟 | `https://eco.taobao.com/router/rest` | `taobao.tbk.dg.material.optional` | `title`、`zk_final_price`、`seller_id`、`item_id`、`item_url`、`category_name` |
| `tmall` | 天猫（同一淘宝开放平台） | 同上 | `taobao.tbk.item.info.get`，只要天猫店 | `title`、`zk_final_price`、`num_iid`、`item_url` |
| `pinduoduo` | 拼多多 / 多多进宝 | `https://gw-api.pinduoduo.com/api/router` | `pdd.ddk.goods.search` | `goods_name`、`min_group_price`、`mall_name`、`goods_id`、`goods_sign` |
| `jd` | 京东联盟 | `https://api.jd.com/routerjson` | `jd.union.open.goods.query` | `skuName`、`priceInfo.price`、`shopInfo.shopName`、`skuId`、`materialUrl` |
| `douyin_shop` | 抖店 | `https://openapi-fxg.jinritemai.com` | 联盟商品检索（商品名 + 价格 + 店铺） | `name`、`price`、`shop_name`、`product_id` |
| `kuaishou_shop` | 快手小店 | `https://open.kuaishou.com` | 商品检索 | `title`、`price`、`seller_name`、`item_id` |

价格单位要先看平台：拼多多、京东常见分为单位，入库前除以 100 变成元。1688 的阶梯价取起批量第一档。

### 海外货架平台

按 `target_market` 选择站点。US 用 amazon.com / walmart.com / ebay.com；HK 用亚马逊国际与 eBay；AU 用 amazon.com.au；CN 不再查海外表。

| 平台 id | 平台 | 官方接口 | 检索 | 取用字段 |
| --- | --- | --- | --- | --- |
| `amazon` | 亚马逊商品广告 | `https://webservices.amazon.com` PA-API 5.0 | `SearchItems`、`GetItems` | `ItemInfo.Title`、`Offers.Listings.Price`、`ASIN`、`DetailPageURL` |
| `amazon_catalog` | 亚马逊卖家目录 | `https://sellingpartnerapi-na.amazon.com`（EU、FE 换区域主机） | SP-API `searchCatalogItems` | `summaries`、`asin`、标识符 |
| `walmart` | 沃尔玛 | `https://developer.api.walmart.com` | 联盟检索 `GET /api-proxy/service/affil/product/v2/search`；卖家自己的商品用 Marketplace items | `name`、`salePrice`、`itemId`、`sellerInfo` |
| `ebay` | eBay | `https://api.ebay.com/buy/browse/v1/item_summary/search` | Browse API，查询 `q`，站点用 `X-EBAY-C-MARKETPLACE-ID` | `title`、`price.value`、`seller.username`、`itemId`、`itemWebUrl` |
| `aliexpress` | 速卖通联盟 | `https://api-sg.aliexpress.com/sync` | `aliexpress.affiliate.product.query` | `product_title`、`target_sale_price`、`shop_name`、`product_id` |
| `shopee` | Shopee | `https://partner.shopeemobile.com` | 卖家商品 `GET /api/v2/product/get_item_list`；全站检索只在联盟商品接口开通时调用 | `item_name`、`price`、`item_id`、`shop_id` |
| `lazada` | Lazada | `https://api.lazada.com/rest` | 卖家商品 `/products/get`；全站检索只在联盟商品接口开通时调用 | `name`、`price`、`item_id`、`seller` |
| `google_shopping` | Google 购物 | `https://shoppingcontent.googleapis.com/content/v2.1` | 自有 Merchant Center：`products.list`。没有全网匿名检索，没 Merchant 账号就跳过 | `title`、`price`、`offerId`、`link` |
| `temu` | Temu | 卖家中心合作接口，无公开匿名检索 | 仅在合作方目录钥匙存在时拉 `goodsName`、`price`、`goodsId`、`mallName` | 没钥匙就跳过，不抓页面 |

站点与市场：

| `target_market` | 亚马逊站点 | eBay marketplace id | 其他 |
| --- | --- | --- | --- |
| US | `www.amazon.com` | `EBAY_US` | Walmart US、Google Shopping US |
| HK | 不默认 amazon.com | `EBAY_HK` 若账号开通，否则跳过 | 速卖通 |
| AU | `www.amazon.com.au` | `EBAY_AU` | Google Shopping AU |
| CN | 不查海外表 | 不查 | 只用国内货源表 |

汇率仍用 Frankfurter 的 USD/CNY。平台返回的本地币先换成美元再写入 `target_price_usd`。

采纳 `POST /catalog/adopt` 时，`product_sources` 记下 `provider=平台 id` 和 `external_id`。本地演示目录的 provider 仍是 `mock_catalog`。

### 接口

| 方法 | 作用 |
| --- | --- |
| `GET /catalog/search?q=&algorithm=selection-assist` | 排序 |
| `POST /catalog/search` | 正文 `{q, algorithm}`，同样排序 |
| `POST /algorithms/selection-assist` | 正文 `{q, target_market?}` |
| `GET /sources/catalog?q=` | 原始目录，不打分 |
| `POST /catalog/adopt` | 正文 `{catalog_id}`，写入 `products`，来源 `catalog` |

传了 `target_market` 时，先改每一行再算：`US→cn_us`，`HK→cn_hk`，`AU→cn_au`，`CN→domestic`，路线 `CN-{市场}`。未知市场按 `cn_us`。

### 排序

每一行调用 `calculate`。优先条件同时成立：利润率 ≥ 0.15，且风险不是 `高`。

排序键从高到低：是否优先、机会分、利润率、SKU。`picked` 是优先行个数。`selection.reason` 写明利润率、风险、机会分。`selection.report` 是四维。

### 输出

`algorithm`、`rules_version`、`sources.catalog`、`picked`、`items`。每个 item 保留目录字段（`id`、`name`、`sku`、`cost_cny`、`target_price_usd`、`supplier`），并加上 `selection`。

### 完成标准

`q=杯` 时命中 `CN-CUP-500`，`selection.pick` 为真，利润率约 `0.4215`，风险 `低`。不带算法的 `q=露营` 没有 `selection` 字段。`catalog_id` 不存在则 `CATALOG_NOT_FOUND`。同一租户同一 SKU 再次采纳时返回已有商品，不插第二条。

---

## A2 路线与市场

不单独打分。把市场字段冻结进商品，并让旧报告失效。

可改字段：`origin_country`、`target_market`、`route`、`incoterm`、`tax_regime`、`cost_currency`、`price_currency`、`fx_usd_cny`、`hs_code_hint`，以及成本、运费、售价、名称、类目。

### 接口

`PATCH /products/{id}`。商品不存在则 `PRODUCT_NOT_FOUND`。

这些字段变化时 `context_version` 加 1，并把 `route` 写成 `{origin}-{target_market}`：成本、包装、国内段、国际段、售价、汇率、货源、目标市场、路线、术语、税务口径、两个币种。然后用新字段跑一遍 `calculate`，不合法就拒绝这次修改。

只改名称、类目、HS 编码时不增加 `context_version`。

### 完成标准

把目标市场改成 `AU`、税务改成 `cn_au` 后，旧报告的 `present_report.stale` 为真。过期报告不能一键获客，返回 `ANALYSIS_STALE` / 409。必须重新分析才有新报告。

---

## A3 选品分析引擎

异步。规则算完即成功。混元开关不影响数字，`explanation_model` 仍是 `rules`。

### 接口

| 方法 | 作用 |
| --- | --- |
| `POST /selection/analyze` | 正文 `{product_id}`，`202` |
| `POST /products/{id}/analyses` | 同上 |

商品不存在则 `PRODUCT_NOT_FOUND`。需要 `analysis.write`。同一 `Idempotency-Key` 不重复扣额度、不重复插报告。

### 步骤

1. 读商品。
2. `calculate(product, settings.rules_version)`。
3. 写 `analysis_reports` 与 `selection_reports`，同一 `id`。
4. 快照：`origin_country`、`target_market`、`route`、`incoterm`、`tax_regime`、`fx_usd_cny`，以及当时的 `context_version`。
5. 发出 `selection.completed`、`report.generated`。
6. `result.analysis_id` 为报告 id。`steps` 为 `rules`、`explain`，模型 `rules`。

`selection_reports` 写入：`route`、`market`、`profit_margin`、`tax`、`time_cost`、`risk`、`score`、`status=completed`、`rules_version`、`seed_ready=false`、`net_margin`、`net_profit_usd`、`fx_usd_cny`。

### 完成标准

成本 72、售价 40、国际段 2、汇率 7.2、市场 US：`landed_cost_usd=12.00`，`channel_fee_usd=7.16`，`tax_usd=0.90`，`net_profit_usd=19.94`，`net_margin=0.4985`。关模型仍有这些数。

---

## A4 报告与一键获客

不重新算金额。读 A3 落下的快照。

### 接口

| 方法 | 作用 |
| --- | --- |
| `GET /reports/{id}` | 合同路径 |
| `GET /analyses/{id}` | 同一份报告 |
| `GET /analyses/{id}/export` | `rules_version`、`metrics`、`explanation_model` |
| `POST /reports/{id}/acquire` | 一键获客 |
| `POST /analyses/{id}/acquire` | 同上 |

报告视图必须带：`stale`、`numbers_locked=true`、`market`、`route`、`profit_margin`、`tax`、`time_cost`、`risk`、`score`、`rules_version`、`seed_ready`。已获客时 `seed_analysis_id` 等于报告 id，状态 `acquired`。未获客时 `seed_analysis_id` 为空。

`stale`：商品 `context_version` 与报告不一致。

一键获客：过期则 `ANALYSIS_STALE` / 409，不写 `acquired_at`。首次点击写下 `acquired_at`、`seed_analysis_id`、`seed_ready=true`，发出 `acquisition.started`。再次点击不重复写时间。返回 `{seed_analysis_id, href}`，`href` 指向获客页并带上这个 id。

这个点击是行动率 `ActR` 的分子。获客发现任务要把 `seed_analysis_id` 抄到线索上。

### 完成标准

新报告 `stale` 为假。改市场后为真，获客被 409 挡住。重算后的新报告可以获客，且线索能按 `seed_analysis_id` 滤出来。

---

## 发现管线

B1–B5 和 B8 共用。不要按通道各写一套分数。

### 接口

| 方法 | 作用 |
| --- | --- |
| `POST /lead-searches` | 正文 `{channel, platform?, query, seed_analysis_id?}`，`202` |
| `POST /acquisition/tasks` | 同上，并建 `acquisition_tasks` |
| `GET /leads` | 可按 `channel`、`seed_analysis_id` 过滤 |
| `POST /leads/score` | 正文 `{lead_id}`，按当前分数重判合格 |

未知 `channel` 为 `UNKNOWN_CHANNEL`。`platform` 不在该通道列表里为 `UNKNOWN_PLATFORM`。不传 `platform` 时用该通道第一个平台。

### 去重

```text
dedupe_key = source_channel + ":" + company.小写去空白 + ":" + market
```

已有这个键：不新插入，只回写 `quality_score`、邮箱、平台。没有则插入，`status=new`，`qualified = quality_score ≥ θ`。`θ` 是 `quality_threshold`，默认 60。抄下 `seed_analysis_id`。`exclude_from_ar` 只有通道 `raas` 为真。

### `lead-score`

`qualified = quality_score ≥ θ`。状态仅在 `new` 或 `scored` 时改写：合格 → `qualified`，否则 → `scored`。已经往后走的状态不要拉回。`scored_by=rules`，`model_score` 保持空。模型建议分丢掉。合格时发 `lead.qualified`。

演示数据固定 5 条，分数 `88, 74, 66, 58, 47`。默认阈值下前三条合格。第 5 条没有邮箱。第 4 条邮箱以 `bounce.` 开头，供退信红线使用。公司名带平台后缀，所以不同平台不会撞同一个去重键。

通道与平台 id 见下面 B1–B9 各表。代码里的 `CHANNELS` 必须和那些平台 id 一致，否则 `UNKNOWN_PLATFORM`。

`cross_border` 的五条线索市场依次是 US、HK、AU、US、CN。其他通道依次是 US、US、HK、AU、US。

发出 `lead.discovered`。`result` 含插入数、更新数、`lead_ids`。

### 占位通道接口

`POST /acquisition/ecommerce|social|expo|agency` 由功能开关挡住，默认关，返回未开通。接通前不要在这些路由里另算分数。发现仍走 `POST /lead-searches` 的对应 `channel`。

---

线索统一成：`company`、`contact_name`、`email`、`market`、`quality_score`、`platform`、`source_channel`、`external_id`。买家个人信息只走平台官方接口里已经授权给本应用的字段。没有邮箱的线索可以入库，但不能进发送受众。

没配该平台钥匙时，发现管线仍返回现在的 5 条演示线索，`provider=mock`。配了钥匙就用下表的接口，`provider=live`，演示序列不再混入。

## B1 电商

`channel=ecommerce`。询盘、订单买家、沉默买家都进 `leads`。`POST /acquisition/ecommerce` 在开关 `acquisition.ecommerce` 打开前保持未开通，发现走 `POST /lead-searches`。

| 平台 id | 平台 | 官方接口 | 用来取线索 | 归一化 |
| --- | --- | --- | --- | --- |
| `amazon` | 亚马逊卖家 | SP-API `https://sellingpartnerapi-na.amazon.com`：Orders `getOrders`，Messaging | 订单买家；站内信需要消息权限 | 公司用收货名，邮箱仅在接口返回时抄下，市场按站点 US/EU/FE |
| `temu` | Temu 卖家中心 | 合作方订单与询盘接口（卖家后台开放能力） | 订单买家、询盘 | `mall` 作公司，订单号作 `external_id` |
| `walmart` | 沃尔玛卖家 | `https://marketplace.walmartapis.com` Orders | 订单买家 | 订单 id、站点 US |
| `taobao` | 淘宝 / 天猫 | 淘宝开放平台交易与旺旺客户接口 | 订单买家、询盘 | 买家昵称、订单号；邮箱经常为空 |
| `pinduoduo` | 拼多多 | `pdd.order.list.get` 及买家留言 | 订单买家、留言 | 订单号、店铺名 |

完成标准：没钥匙时 `platform=amazon` 搜一次得到 5 条演示线索；再搜同一次，插入数 0、更新数 5。有钥匙时同一 `external_id` 同样只更新不双插。

## B2 社交

`channel=social`。`POST /acquisition/social` 在开关 `acquisition.social` 打开前保持未开通。

| 平台 id | 平台 | 官方接口 | 用来取线索 | 归一化 |
| --- | --- | --- | --- | --- |
| `linkedin` | LinkedIn | Lead Gen Forms，`https://api.linkedin.com/rest` | 广告表单留下的姓名、公司、邮箱 | 表单响应 id 作 `external_id`，市场默认 US |
| `facebook` | Facebook / Instagram | Graph API `/{page-id}/leadgen_forms` | 主页线索表单 | `leadgen_id`，邮箱字段 |
| `wechat_mini` | 微信小程序 / 企业微信 | 小程序登录；企业微信客户联系 `externalcontact` | 授权用户、客户联系人 | `external_userid`；邮箱可空 |
| `douyin` | 抖音 | 抖音开放平台 `https://open.douyin.com`；企业号线索 | 短视频与直播留资 | 线索 id、昵称 |
| `xiaohongshu` | 小红书 | 聚光 / 蒲公英商业开放接口 | 投放表单留资 | 表单 id；没有公开的匿名用户检索 |
| `kuaishou` | 快手 | `https://open.kuaishou.com` 企业号线索 | 直播与作品留资 | 线索 id、昵称 |

只接表单和已授权客户。不要用搜索接口去扫陌生人的个人主页。

## B3 线上展会

`channel=expo`。会后线索与 B1 同一张 `leads`。`POST /acquisition/expo` 在开关打开前保持未开通。冷启和召回不在发现时发送。

| 平台 id | 平台 | 官方接口 | 用来取线索 | 说明 |
| --- | --- | --- | --- | --- |
| `canton_fair` | 广交会线上 | 展商采购对接导出 / 主办方合作接口 | 展期询盘、名片 | 没有稳定的匿名公开检索；没合作接口就保持未接通 |
| `alibaba_com` | 阿里巴巴国际站 | 国际站开放平台询盘 `alibaba.trade` 询盘列表 | 询盘公司、联系人、国家 | 市场按买家国家映射 US/HK/AU，其余记国家码 |
| `global_sources` | 环球资源 | 展会与询盘合作接口 | 采购商名片 | 同上，没钥匙不调用 |
| `ciie` | 进博会线上 | 主办方展商数据合作 | 采购商登记 | 没有公开 REST 时不抓网站 |
| `online_expo` | 其他线上展 | 仅作演示平台 id | 演示 5 条 | 钥匙未配时的退路，和现在的 mock 相同 |

`online_expo` 必须留在 `CHANNELS` 里，避免现有调用变成 `UNKNOWN_PLATFORM`。

## B4 十二代理

`channel=agency`。发现仍进 `leads`。分成不进线索分。`POST /acquisition/agency` 在开关打开前保持未开通。

十二路是渠道子账户，不是十二个商品搜索站。每一路一个平台 id，线索从该代理自己的系统用合作接口或对方推送进来。

| 平台 id | 代理 | 对方系统 | 对接方式 | 线索里记什么 |
| --- | --- | --- | --- | --- |
| `agent_1` | 亚马逊代运营 | 卖家后台授权后的 SP-API | 拉订单与买家消息 | 代运营客户公司、站点 |
| `agent_2` | 沃尔玛代运营 | Walmart Marketplace | 订单 | 同上 |
| `agent_3` | Temu 代运营 | Temu 卖家合作接口 | 订单与询盘 | 店铺、订单号 |
| `agent_4` | 独立站代运营 | Shopify Admin `https://{shop}.myshopify.com/admin/api` Orders、Customers | 客户 | 店铺域名作公司 |
| `agent_5` | 国际站代运营 | 阿里巴巴国际站询盘 | 询盘 | 买家公司、国家 |
| `agent_6` | 速卖通代运营 | AliExpress 卖家订单接口 | 订单 | 买家、站点 |
| `agent_7` | Shopee / Lazada 代运营 | 对应 Open Platform 订单 | 订单 | 站点国家 |
| `agent_8` | 海外仓 | 仓储合作方出库回传 | 收货公司 | 只取收货公司与国家，不取无关库存 |
| `agent_9` | 物流货代 | 货代运单联系人回传 | 发货联系人 | 公司、邮箱 |
| `agent_10` | 收款服务商 | 到账通知里的付款方名称 | 付款公司 | 只取公司名；金额不写入线索分 |
| `agent_11` | 网红与联盟 | 联盟平台转化回调（如 Impact、ShareASale 的转化 postback） | 推广带来的公司 | 联盟点击 id 作 `external_id` |
| `agent_12` | 本地经销与展团 | 代理商表格或 webhook | 批量公司名单 | 由代理推送，本系统不登录对方后台 |

分成：`POST /billing/agency/commissions`，正文 `{amount_fen, idempotency_key, signature, channel_account_id?, note?}`。

```text
signature = HMAC-SHA256(ledger_hmac_secret, f"{idempotency_key}:{amount_fen}:agency_commission")
```

签名不符则拒绝，不入账。同一 `idempotency_key` 再提交返回已有账，不记第二次。`amount_fen` 为整数分。科目 `agency_commission`，集合 `commission_ledger`。`channel_account_id` 用上表的 `agent_n`。

## B5 智慧大脑

`channel=enrichment`。去重和质量分仍用发现管线。这些接口补公司是否存在、行业、地区，不改已经由规则写下的 `quality_score`。

| 平台 id | 平台 | 官方接口 | 检索 | 取用字段 |
| --- | --- | --- | --- | --- |
| `qichacha` | 企查查 | `https://api.qichacha.com`（开放平台以控制台主机为准） | 企业模糊搜索、工商详情 | 企业名称、法定代表人、省、统一社会信用代码、联系邮箱（若套餐含） |
| `tianyancha` | 天眼查 | 门户 `https://open.tianyancha.com`，接口 `https://open.api.tianyancha.com/services/open/search/2.0` | 搜索、企业基本信息 | 名称、法人、注册地址、邮箱 |
| `qixin` | 启信宝 | `https://api.qixin.com` | 企业搜索、工商照面 | 名称、法人、地区、联系方式 |
| `aiqicha` | 爱企查 | 无稳定对公开放检索 | 不调用 | 不要抓网页；没接口就跳过 |

信用代码写入 `external_id`。市场：注册地在境内记 `CN`，境外主体按注册国映射，映射不上记 `US` 只在演示数据里出现。邮箱缺失时线索仍入库，合格与否只看分数阈值。

## B6 GEO / SEO

不另算利润和线索分。开关 `geo_seo` 默认关，`POST /geo/seo` 未开通。打开后只把落地页带来的留资送进 `leads`，`channel=geo_seo`。

| 平台 id | 平台 | 官方接口 | 用来做什么 |
| --- | --- | --- | --- |
| `gsc` | Google Search Console | `https://searchconsole.googleapis.com` `searchanalytics.query` | 查询词与落地页，不直接产生个人线索 |
| `ga4` | Google Analytics Data API | `https://analyticsdata.googleapis.com` | 落地页会话；线索仍来自表单 |
| `bing` | Bing Webmaster | `https://ssl.bing.com/webmaster/api.svc/json` | 查询与点击 |
| `baidu` | 百度搜索资源平台 | 站长平台数据接口 | 索引与查询；线索来自落地页表单 |
| `landing` | 自有落地页 | `POST /lead-searches`，`platform=landing` | 表单公司、邮箱、市场。这是当前 `CHANNELS` 里的 id |

`landing` 必须保留。Search Console 和百度的数据是页面表现，不能当成一个个买家写进 `leads`。

## B7 内容工厂、数字人、线下客流

不改金额、不改 `quality_score`。`POST /content/generate` 返回 `applied_to_money=false`。`POST /digital-human/generate` 由开关 `digital_human` 挡住。

| 平台 id | 平台 | 官方接口 | 用来做什么 |
| --- | --- | --- | --- |
| `content_factory` | 内容工厂 | 本系统 `POST /content/generate`；模型用已配置的混元 | 草稿文案。文案不能回写利润和分数 |
| `hunyuan` | 腾讯混元 | 混元 OpenAI 兼容对话接口 | 只解释已有报告、起草待批准邮件 |
| `tencent_dh` | 腾讯云数智人 | 数智人视频与播报接口 | 生成视频素材。未购买时线索备注写「数智人 DEMO 占位」 |
| `silicon_dh` | 硅基智能 | 数字人开放接口 | 同上，另一家供应。没钥匙不调用 |
| `digital_human_placeholder` | 占位 | 无外部接口 | 保留在 `CHANNELS` 里，备注占位，分数仍是规则分 |
| `douyin_laike` | 抖音来客 | 来客门店客资 | 线下到店留资，进 `leads`，`channel=content_dh` |
| `wechat_store` | 微信门店 | 门店小程序会员与到店记录 | 到店客户，邮箱可空 |
| `offline_qr` | 线下二维码 | 本系统落地页，无第三方 | 扫码表单。这是当前通道里的平台 id |

## B8 跨境元素

`channel=cross_border`。不新开产品线。四条路线各自用已经列过的商品平台和线索平台，只是市场过滤不同。约八成线索来自中美、中港、中澳，两成来自内陆。

| 平台 id | 路线 | 商品平台（见 A1） | 线索平台（见 B1–B3） | 市场 |
| --- | --- | --- | --- | --- |
| `cn_us` | 中国 → 美国 | 1688、淘宝、拼多多、京东供货；亚马逊、沃尔玛、eBay、Google 购物的 US 站售价 | 亚马逊 US、沃尔玛、LinkedIn、广交会与国际站里国家为 US 的询盘 | `US` |
| `cn_hk` | 中国 → 香港 | 1688 与淘宝供货；eBay HK、速卖通 | 国际站香港买家、微信、展会名片 | `HK` |
| `cn_au` | 中国 → 澳大利亚 | 1688 供货；amazon.com.au、eBay AU | 亚马逊 AU、国际站国家 AU | `AU` |
| `domestic` | 内陆 | 1688、淘宝、拼多多、京东、抖店、快手小店 | 拼多多、淘宝、抖音、快手、企查查 | `CN` |

`cross_border` 的演示数据在没钥匙时仍是 5 条，市场顺序 US、HK、AU、US、CN。有钥匙时按上表过滤，不再使用那 5 条。

## B9 RAAS

卖的是 PickGlobal 自己的结果抽成和账户，不进入普通获客率。`channel=raas` 的每条线索 `exclude_from_ar=true`。

| 平台 id | 卖什么 | 官方接口 | 怎么入账 |
| --- | --- | --- | --- |
| `site_success` | 官网按成交结果抽成 | 本站订单与 `POST /billing/raas/commissions` | 先验签再入账，科目 `raas_commission` |
| `app_account` | App 里按账户销售 | 本系统账户接口；应用商店只对账，不把商店用户列表当线索 | 同上 |
| `app_store` | Apple 销售报表 | App Store Connect Sales and Trends | 只对金额，不把下载用户写进 `leads` |
| `wechat_virtual` | 小程序虚拟支付账户 | 微信支付虚拟支付订单查询 | 只对金额 |

抽成正文与 B4 相同，签名字符串里的科目换成 `raas_commission`，账本集合与代理分开。

`POST /payments/raas` 由 `payment.raas` 挡住。`POST /raas/settle` 由 `raas` 挡住。默认都关。不要在占位路由里记抽成。`site_success` 与 `app_account` 必须留在 `CHANNELS` 里。

---

## 触达

不重新评分。未批准不能发。

### 接口

| 方法 | 作用 |
| --- | --- |
| `POST /campaigns` | 正文 `{name, lead_ids, purpose, seed_analysis_id?, market_pack?}`。`purpose` 只能是 `acquisition`、`activation`、`recall` |
| `POST /campaigns/{id}/drafts` | 规则模板草稿，状态改为 `pending_approval` |
| `POST /campaigns/{id}/approve` | 冻结 `audience_snapshot`，写下 `approved_at` |
| `POST /campaigns/{id}/send` | `202`。仅 `approved` 可发 |

`purpose` 非法则 `INVALID_PURPOSE`。线索不存在则 `LEAD_NOT_FOUND`。没有草稿就批准：`CAMPAIGN_NOT_READY` / 409。已批准再改草稿：`CAMPAIGN_LOCKED` / 409。

受众 A = 批准时的线索，去掉无邮箱、已抑制、退信地址。发送按人写 `outreach_messages`。DEMO 邮件可 mock：地址含 `bounce.` 的记 `bounced`，其余 `delivered`。至少一封 `delivered` 的人计入 D。

草稿文案写明市场包，并写明没有改动金额和评分。`explanation_model` 为 `rules`。

### 完成标准

未批准调用 send 失败。批准后 send 成功，送达人数能被 `TR` 读到。RAAS 线索发出的消息带 `exclude_from_ar`。

---

## 冷启

规则入队，不由模型判断是否流失。

### 日扫 `POST /lifecycle/scan`

跳过正处在 `draft`、`pending_approval`、`approved`、`sending` 活动里的线索。

四条同时成立才入队，原因 `qualified_never_contacted`：

1. 状态 `new`
2. 没有任何 `delivered` 消息
3. `quality_score ≥ θ`
4. 有邮箱，且没有状态为 `queued`、`approved`、`sent` 的冷启任务

写入 `activation_jobs`：`status=queued`，`enqueued_at`，`draft` 为待批准文案。文案不改分数。

### 手动 `POST /recall`

正文 `{lead_id, trigger}`。`trigger=cold_start` 时进 `activation_jobs`，目的 `activation`。同一线索、同一触发已有记录则返回原记录。

触发只允许 `cold_start`、`churn`、`opened_without_reply`。

发送仍要 `POST /activation/jobs/{id}/approve` 然后 `POST /activation/jobs/{id}/send`。未批准不发。

### 完成标准

分数 88 且从未触达的线索入队。分数 47 不入队。已送达的不入队。重复扫描不插第二条进行中的任务。

---

## 召回

与冷启同一日扫，条件不同。原因 `opened_without_reply`：

1. 已有 `opened_at`
2. 没有 `replied_at`，也没有 `won_at`
3. 有邮箱
4. 没有进行中的召回任务

写入 `recall_jobs`，带 `triggered_at`。手动 `POST /recall` 的 `churn` 与 `opened_without_reply` 也进这张表。

发送：`POST /recall/jobs/{id}/approve`，然后 `POST /recall/jobs/{id}/send`。

回暖：线索出现 `warmed_at` 或 `replied_at` 或 `won_at`。这是 `RecR` 的分子，只统计已经 `delivered` 的召回任务。

### 完成标准

打开未回复的线索入队。已赢单的不入队。未批准不能发。

---

## KPI · `snapshot`

实现：`app/services/metrics.py` 的 `snapshot`，看板组装在 `app/modules/kpi_view.py`。不要在接口里手写另一套比率。

### 接口

| 方法 | 作用 |
| --- | --- |
| `GET /kpi/dashboard?window_days=30` | 首屏：四率 + 北星 `AR`；时效默认折叠；红线；生命周期三率 |
| `GET /metrics` | 同一 `snapshot` 原文 |

每次看板读取把当次比率写入 `kpi_metrics`（`metric_code`、`value`、`period`）。空值不要写成 0。

窗口默认 30 天，按记录时间过滤。中位数与 P50：奇数取中，偶数取中间两数平均。P95 下标为 `round((n − 1) × 0.95)`。

### 人数

```text
A = 窗口内已批准、目的为获客的受众人数
D = A 里至少一封 delivered 的人数
W = D 里，首封 delivered 之后 14 天内有 replied_at 或 won_at 的人数
```

目的不是获客的活动不进 A。`exclude_from_ar` 的消息不进获客率。

### 八率

| 代号 | 计算 | 目标字段 |
| --- | --- | --- |
| `N%` | 窗口内报告 `net_margin` 的中位数 | `0.1500` |
| `ActR` | 有 `acquired_at` 的报告 ÷ 完成报告 | `0.5000` |
| `TR` | D ÷ A | `0.9500` |
| `OR` | 独立打开人数 ÷ D | `0.4000` |
| `AR` | W ÷ D | `0.0800`，`north_star=true` |
| `QR` | `quality_score ≥ θ` 的线索 ÷ 窗口内线索 | `0.6000` |
| `ActR_cold` | 冷启任务中，其消息被打开或回复的个数 ÷ 冷启入队 | `0.2500` |
| `RecR` | 已送达且线索已回暖的召回 ÷ 已送达召回 | `0.1000` |

首屏键：`net_margin`、`act_r`、`tr`、`open_r`、`ar`。生命周期键：`qr`、`act_r_cold`、`rec_r`。展示值用 `display`，空则为「—」。

### 五时效

都是秒，取 P50。没有样本则为空。

| 代号 | 计算 | 目标（秒） |
| --- | --- | --- |
| `AnaT` | 报告 `finished_at − requested_at` | 120 |
| `LeadT` | 发现任务成功的 `finished_at − requested_at` | 180 |
| `AcqT` | 仅 W：首次成交标记 − 该人首次 `delivered_at` | 259200 |
| `ActT` | 冷启 `delivered_at − enqueued_at` | 86400 |
| `RecT` | 召回 `delivered_at − triggered_at` | 86400 |

### 红线与告警

按封，状态属于 `delivered`、`bounced`、`complained` 才计入分母。没有发送时不触发。

```text
送达率 = delivered 封数 / 上述封数
退信率 = bounced / 上述封数
投诉率 = complained / 上述封数
tripped = 送达率 < 0.95 或 退信率 ≥ 0.015 或 投诉率 ≥ 0.001
```

`ActT` 或 `RecT` 的 P95 &gt; 72 小时（259200 秒）时 `act_or_rec_p95_over_72h` 为真。

### 完成标准

没有任何报告时 `N%` 为空而不是 0。一键获客一次后，完成报告为 1 时 `ActR` 为 `1.0000`。RAAS 消息不改变 `AR` 的分子分母。
