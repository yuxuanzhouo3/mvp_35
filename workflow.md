# Flow

Work and push on `yzcmf`. That updates `origin/yzcmf` only.

1. Open a PR: `yzcmf` → `test`, merge when you agree.
2. Open a PR: `test` → `pro`, merge when you agree.

Direct pushes to `test` and `pro` are blocked.

Compare:

- Test: https://github.com/yuxuanzhouo3/mvp_35/compare/test...yzcmf
- Pro: https://github.com/yuxuanzhouo3/mvp_35/compare/pro...test

## Version on each merge

Each merge commits a version on that branch. `test` and `pro` use the same `x.y`, always exactly two numeric components: `1.0`, `1.1`, `1.2`, `2.0`. Do not use patch versions such as `1.0.0`. Private npm app manifests omit the npm `version` field because npm requires three-component semantic versions. The project release version remains `x.y`.

| `test` | → `pro` |
| --- | --- |
| `1.0` | `1.0` |
| `1.1` | `1.1` |

## Weekly production promotion

`.github/workflows/promote-test-to-pro.yml` runs every Monday at 13:30 UTC+8. If `test` has no changes beyond `pro`, it does nothing. An open `test` → `pro` PR is not duplicated. Otherwise it opens the next two-component release PR for manual approval: `1.1` → `1.2` → `1.3` and so on. Major releases such as `2.0` use the manual version input. A scheduled run only increments the minor component. No direct push to protected branches, and no production merge without review.

## Releases

Add a row when a merge lands. Newest row first.

| Day | Step | Pull request | Result |
| --- | --- | --- | --- |
| 13 Oct 2026 | `yzcmf` → `test` | [#15](https://github.com/yuxuanzhouo3/mvp_35/pull/15) | `1.9` on `test` (`4b1a6bc`). Tip `d936f75`. `pro` stays `1.2`. |
| 12 Oct 2026 | `yzcmf` → `test` | [#14](https://github.com/yuxuanzhouo3/mvp_35/pull/14) | `1.8` on `test` (`f94dd3e`). Tip `3bbec32`. `pro` stays `1.2`. |
| 9 Oct 2026 | `yzcmf` → `test` | [#13](https://github.com/yuxuanzhouo3/mvp_35/pull/13) | `1.7` on `test` (`378fe20`). Tip `1faa275`. `pro` stays `1.2`. |
| 4 Oct 2026 | `yzcmf` → `test` | [#11](https://github.com/yuxuanzhouo3/mvp_35/pull/11) | `1.6` on `test` (`433cabe`). Tip `e9faa82`. `pro` stays `1.2`. |
| 3 Oct 2026 | `yzcmf` → `test` | [#10](https://github.com/yuxuanzhouo3/mvp_35/pull/10) | `1.5` on `test` (`1698cc7`). Tip `6704ca4`. `pro` stays `1.2`. |
| 2 Oct 2026 | `yzcmf` → `test` | [#9](https://github.com/yuxuanzhouo3/mvp_35/pull/9) | `1.4` on `test` (`951b554`). Tip `e31c5d7`. `pro` stays `1.2`. |
| 1 Oct 2026 | `yzcmf` → `test` | [#8](https://github.com/yuxuanzhouo3/mvp_35/pull/8) | `1.3` on `test` (`02915cc`). Commit `8d47ec8`. `pro` stays `1.2`. |
| 30 Sep 2026 | `test` → `pro` | [#7](https://github.com/yuxuanzhouo3/mvp_35/pull/7) | `1.2` on `pro` (`32b3707`) |
| 30 Sep 2026 | `yzcmf` → `test` | [#6](https://github.com/yuxuanzhouo3/mvp_35/pull/6) | `1.2` on `test` (`3a23696`) |
| 30 Sep 2026 | `test` → `pro` | [#5](https://github.com/yuxuanzhouo3/mvp_35/pull/5) | `1.1` on `pro` (`22a3f24`) |

## Pace

Add the next day above the previous one. Keep older days. One paragraph: the commit, where it landed, what is true, and what is next.

### 24 October 2026

Tip `2cbbb6a` is on `origin/yzcmf` only. `test` stays `1.9` ([#15](https://github.com/yuxuanzhouo3/mvp_35/pull/15), `4b1a6bc`, tip `d936f75`). `pro` stays `1.2`. CloudBase cost notes and `scripts/cloudbase_cost_check.py` track mvp35 CloudRun idle spend; `scripts/tcb-deploy.sh` and both `cloudbaserc.json` files keep min replicas at 0 and max at 2. Safe scale-to-zero only—no env destroy. Web is already min=0; api may still need a console fix after hot-update failures. Next: merge to `test` when you agree. Weekly pull request [#12](https://github.com/yuxuanzhouo3/mvp_35/pull/12) stays open from `test` to `pro`, titled `1.3`. Live SES stays unwired.

### 22 October 2026

Tip `549f20f` is on `origin/yzcmf` only. `test` stays `1.9` ([#15](https://github.com/yuxuanzhouo3/mvp_35/pull/15), `4b1a6bc`, tip `d936f75`). `pro` stays `1.2`. B2–B5 now require a login mode: social invent/remix, expo settle/follow, agency directory/outreach, enrichment search/merge. `POST /content/seed-drafts` writes pending copy; approve does not publish. Discovery enriches WeChat, email, or phone and marks mid/high intent. Domestic webmail links on the price compare dialog open the inbox home instead of compose deep-links. Next: merge to `test` when you agree. CloudBase `tcb` with git still waits. Weekly pull request [#12](https://github.com/yuxuanzhouo3/mvp_35/pull/12) stays open from `test` to `pro`, titled `1.3`. Live SES stays unwired.

### 17 October 2026

Tip `fd19d81` is on `origin/yzcmf` only. `test` stays `1.9` ([#15](https://github.com/yuxuanzhouo3/mvp_35/pull/15), `4b1a6bc`, tip `d936f75`). `pro` stays `1.2`. Selection adds TikTok Shop and Temu to the US shelf beside eBay and AliExpress, with budget and used-item parsing for English queries. Channel login stores per-tenant OAuth or pasted keys; lead feeds read those tokens. Phone checkout uses WeChat H5 and Alipay WAP. The products desk gets camera capture, prompt chips, and offline-platform mail drafts in the price compare dialog. Next: merge to `test` when you agree. CloudBase `tcb` with git still waits. Weekly pull request [#12](https://github.com/yuxuanzhouo3/mvp_35/pull/12) stays open from `test` to `pro`, titled `1.3`. Live SES stays unwired.

### 13 October 2026

`yzcmf` through `d936f75` is on `test` as `1.9` ([#15](https://github.com/yuxuanzhouo3/mvp_35/pull/15), `4b1a6bc`). `pro` stays `1.2`. This merge carries the 1.8 Releases and pace note onto test; product tip remains the 1.8 stack through `3bbec32`. Next: CloudBase `tcb` with git. Weekly pull request [#12](https://github.com/yuxuanzhouo3/mvp_35/pull/12) stays open from `test` to `pro`, titled `1.3`, and now includes this test update. Live SES stays unwired.

### 12 October 2026

`yzcmf` through `3bbec32` is on `test` as `1.8` ([#14](https://github.com/yuxuanzhouo3/mvp_35/pull/14), `f94dd3e`). `pro` stays `1.2`. Test now has four-shelf selection, B1–B5 channel login with yearly plans and overseas shelf caps, the PostgreSQL `cache_entries` hot cache, and Hunyuan-compatible AI for 客服 and AI 选品 (off until keys), plus voice and image input and branded acquire/pay marks. Next: CloudBase `tcb` with git. Weekly pull request [#12](https://github.com/yuxuanzhouo3/mvp_35/pull/12) stays open from `test` to `pro`, titled `1.3`, and now includes this test update. Live SES stays unwired.

### 11 October 2026

`b6c9b04` through tip `b49bde2` are on `origin/yzcmf` only. `test` stays `1.7` ([#13](https://github.com/yuxuanzhouo3/mvp_35/pull/13), `378fe20`, tip `1faa275`). `pro` stays `1.2`. Selection asks four shelves: 1688 and Pinduoduo for the CNY cost, eBay and AliExpress for the USD median (`price_basis=us_shelf`). With no China price, an eBay or AliExpress row still shows as a US shelf item. eBay account deletion answers the challenge and accepts the notice. Commit `2b7c144` adds B1–B5 channel login (B1 must pick analyze, half, or full before OAuth), a connected callback page, yearly `growth_year` and `scale_year` at 0.7 × 12 months, overseas shelf caps (free 5, growth 10, scale 30) with daily AI limits, and a PostgreSQL `cache_entries` table for the shared hot cache. Billing shows month and year for each tier. Commit `b49bde2` wires OpenAI-compatible Hunyuan/Tongyi/OpenAI for 客服 and AI 选品 (`backend/AI/`, off until keys), adds voice and image input on the products desk, and tints the acquire cards and WeChat/Alipay pay marks. Next: merge to `test` when you agree. CloudBase `tcb` with git still waits. Weekly pull request [#12](https://github.com/yuxuanzhouo3/mvp_35/pull/12) stays open from `test` to `pro`, titled `1.3`. Live SES stays unwired.

### 9 October 2026

`yzcmf` through `1faa275` is on `test` as `1.7` ([#13](https://github.com/yuxuanzhouo3/mvp_35/pull/13), `378fe20`). `pro` stays `1.2`. Test now has the WeChat mini program, route-aware shelf and lead feeds, legal consent before sign-in, the shared legal pages, and the 1688 price cache: hourly on the free plan, every 15 minutes on a paid plan, with 10 manual pulls. Next: CloudBase `tcb` with git. Weekly pull request [#12](https://github.com/yuxuanzhouo3/mvp_35/pull/12) is already open from `test` to `pro`, titled `1.3`, and now includes this test update. It waits until you agree. Hunyuan and live SES stay unwired.

### 4 October 2026

`yzcmf` through `e9faa82` is on `test` as `1.6` ([#11](https://github.com/yuxuanzhouo3/mvp_35/pull/11), `433cabe`). `pro` stays `1.2`. Test now has ad slots, the pricer and selection algorithms, profit-share plans, one acquire step at a time, invite rewards, and recall links. Alipay and WeChat pay succeeded. Next: CloudBase `tcb` with git. A `test` → `pro` merge waits until you agree. Hunyuan and live SES stay unwired.

### 3 October 2026

`yzcmf` through `6704ca4` is on `test` as `1.5` ([#10](https://github.com/yuxuanzhouo3/mvp_35/pull/10), `1698cc7`). `pro` stays `1.2`. Test now has tenant sign-in, billing, email and SMS codes, WeChat and Alipay checkout, a WeChat QR on the web, and JSAPI pay in the mini program. Alipay and WeChat pay succeeded. Commit `85653b0` is on `yzcmf` only. It adds ad slots on the homepage, workspace, and reports; an admin user list with masked email and phone; ads that require an external customer URL before they go live; a 10-fen payment test amount when configured; Alipay AES page pay; and a 30-second CloudBase document cache. Dashboard rates fall back to sample numbers when the tenant has no deals. Commit `50968b3` is on `yzcmf` only. It adds `product-pricer` and `selection-assist`, optional FX and shelf-price feeds, spreadsheet import, a report dialog, and one acquire desk per channel. `algorithm.md` records those rules. Commit `e885cd3` is on `yzcmf` only. It records the `pg-share-1.0` profit-share plans, two-level agents, a domestic CN→CN default, and one acquire page per channel. Commit `51fa3eb` shows one acquire step at a time. The homepage states China to the US as the first market. Next: CloudBase `tcb` with git. A `test` → `pro` merge waits until you agree. Hunyuan and live SES stay unwired.

### 2 October 2026

`yzcmf` through `e31c5d7` is on `test` as `1.4` ([#9](https://github.com/yuxuanzhouo3/mvp_35/pull/9), `951b554`). `pro` stays `1.2`. Test now has the 4S contract, the optional CloudBase document store, the signed-in admin, and the voice guides. Next: CloudBase `tcb` with git. A `test` → `pro` merge waits until you agree. WeChat pay, Hunyuan, and live SES stay unwired.

### 1 October 2026

Commit `8d47ec8` is on `yzcmf` and on `test` as `1.3` ([#8](https://github.com/yuxuanzhouo3/mvp_35/pull/8)). `pro` stays `1.2`. Commits `3ea4e99`, `ecea5ad`, `7787ae4`, `a774185`, `e76e521`, and `80cee57` are on `origin/yzcmf` only. `80cee57` is the tip. `/` states the two paths. `/workspace` covers products, a report, acquire, and eight rates / five timings, and detects phone, iPad, WeChat mini program, Web, Mac, Windows, and Linux. The phone layout uses a bottom dock. A watch opening the page can pinch-zoom or use the on-page zoom buttons; a watch app itself stays blank. The frontend proxies `/api`. `backend/` is FastAPI with Docker, a worker, and tenant `202` jobs. The default store is still the local JSON file. `STORAGE_ENGINE=cloudbase` opens `CloudBaseStore` and writes the same documents into the remote CloudBase PostgreSQL `documents` table. The core migration is the existing `0001_core` up script; the documents table is a second migration. The API does not dual-write. Tests force `STORAGE_ENGINE=json`. `backend/.env` is ignored. Login is `Bearer demo`, and local email and phone register and login issue access and refresh tokens. CloudBase Auth still answers `503`. Feature flags in `backend/config/flags.json` leave SSO, MFA, OAuth, the mini program, tenant switch, RaaS pay, auto-deal, the extra acquisition channels, the AI agent, fine-tune, the digital human, GEO/SEO, RaaS, and global multi-active off. Path A is in: manual and CSV import, a mock catalog, CN→US defaults, rules-only profit (`pg-rules-1.0`), and acquire that carries `seed_analysis_id`. Analysis also writes `selection_reports`; sends also write `deliveries`; imports, reports, and discoveries emit events. Leads, campaigns, mock SES, cold start, recall, and signed ledgers run on that store. Rates show `—` when the denominator is 0. PostgreSQL is the cutover shape in `backend/db/sql/0001_core`, with up and down. `rollback/` can pin a tag, migrate, and return to the CloudBase JSON baseline without a git reset. Tests live under `test/` for mvp, svp, and business. `/admin` requires a signed-in session at `/admin/login`. Overview, ads, users, invitations, analytics, recall, search, settings, and audit read the admin API. A starter platform user is created on startup. Product search is one shared library on `/` and in the workspace. CloudBase migrations and the Postgres shape live under `backend/db`. `project.md` and `front.md` hold the 4S contract, the eight rates and five timings, the schema, and the rollback steps. Demo voice guides are `demo/pickglobal-user-guide.mp4` plus xiaoxiao, yunjian, and yunxi. Next: merge `yzcmf` to `test` when agreed. CloudBase `tcb` with git waits until after that. WeChat pay, Hunyuan, and live SES stay unwired.

### 30 September 2026

`front/` (Next.js 16) is a shell. `/` scrolls or alerts and shows five steps, not two paths: selection reports, then nine-channel acquisition. `/admin` demos overview, ads, users, analytics, invitations, and platform recall, no auth or API. `backend/` is empty. Now: FastAPI, CloudBase Auth, document repository, gateway, Docker, worker, tenant `202` jobs, empty eight rates and five timings. Path A next: manual/CSV, mock catalog, CN→US, rules-only analysis, `seed_analysis_id`. Then: leads, campaigns, SES sandbox, enrichment, cold start, recall, ledgers, compliance, admin APIs, scale. WeChat pay, Hunyuan, and SES wait.
