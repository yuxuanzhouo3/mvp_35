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
| 1 Oct 2026 | `yzcmf` → `test` | [#8](https://github.com/yuxuanzhouo3/mvp_35/pull/8) | `1.3` on `test` (`02915cc`). Commit `8d47ec8`. `pro` stays `1.2`. |
| 30 Sep 2026 | `test` → `pro` | [#7](https://github.com/yuxuanzhouo3/mvp_35/pull/7) | `1.2` on `pro` (`32b3707`) |
| 30 Sep 2026 | `yzcmf` → `test` | [#6](https://github.com/yuxuanzhouo3/mvp_35/pull/6) | `1.2` on `test` (`3a23696`) |
| 30 Sep 2026 | `test` → `pro` | [#5](https://github.com/yuxuanzhouo3/mvp_35/pull/5) | `1.1` on `pro` (`22a3f24`) |

## Pace

Add the next day above the previous one. Keep older days. One paragraph: the commit, where it landed, what is true, and what is next.

### 1 October 2026, afternoon

Commit `3ea4e99` is on `yzcmf` only. `test` stays `1.3` (`8d47ec8`) and `pro` stays `1.2`. The running API still writes the JSON document store. Local email and phone register and login now issue access and refresh tokens; `Bearer demo` still works, and CloudBase Auth still answers `503`. Feature flags in `backend/config/flags.json` leave SSO, MFA, OAuth, the mini program, tenant switch, RaaS pay, auto-deal, the extra acquisition channels, the AI agent, fine-tune, the digital human, GEO/SEO, RaaS, and global multi-active off. Analysis also writes `selection_reports`; sends also write `deliveries`; imports, reports, and discoveries emit events. PostgreSQL is the cutover shape in `backend/db/sql/0001_core`, with up and down, and the API does not dual-write it. `rollback/` can pin a tag, migrate, and return to the CloudBase JSON baseline without a git reset. Tests live under `test/` for mvp, svp, and business; `backend/tests/test_flow.py` is gone. `/` and `/workspace` detect phone, iPad, WeChat mini program, Web, Mac, Windows, and Linux, and the phone layout uses a bottom dock. A watch opening the page can pinch-zoom or use the on-page zoom buttons; a watch app itself stays blank. `project.md` and `front.md` hold the 4S contract, the eight rates and five timings, the schema, and the rollback steps. Next after the commit: merge to `test` when agreed. WeChat pay, Hunyuan, and live SES stay unwired.

### 1 October 2026

Commit `8d47ec8` is on `yzcmf` and on `test` as `1.3` ([#8](https://github.com/yuxuanzhouo3/mvp_35/pull/8)). `pro` stays `1.2`. `/` states the two paths. `/workspace` covers products, a report, acquire, and eight rates / five timings. `backend/` is FastAPI: a JSON document store, Docker, a worker, and tenant `202` jobs. The frontend proxies `/api`. Login is `Bearer demo`; CloudBase Auth answers `503` until it is configured. Path A is in: manual and CSV import, a mock catalog, CN→US defaults, rules-only profit (`pg-rules-1.0`), and acquire that carries `seed_analysis_id`. Leads, campaigns, mock SES, cold start, recall, and signed ledgers run on that same demo store. Rates show `—` when the denominator is 0. `/admin` is still a static demo. Next: CloudBase Auth, then compliance, admin APIs, and scale. WeChat pay, Hunyuan, and live SES stay unwired.

### 30 September 2026

`front/` (Next.js 16) is a shell. `/` scrolls or alerts and shows five steps, not two paths: selection reports, then nine-channel acquisition. `/admin` demos overview, ads, users, analytics, invitations, and platform recall, no auth or API. `backend/` is empty. Now: FastAPI, CloudBase Auth, document repository, gateway, Docker, worker, tenant `202` jobs, empty eight rates and five timings. Path A next: manual/CSV, mock catalog, CN→US, rules-only analysis, `seed_analysis_id`. Then: leads, campaigns, SES sandbox, enrichment, cold start, recall, ledgers, compliance, admin APIs, scale. WeChat pay, Hunyuan, and SES wait.
