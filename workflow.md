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

## Current pace

On 30 September 2026, `front/` (Next.js 16) is a shell. `/` scrolls or alerts and shows five steps, not two paths: selection reports, then nine-channel acquisition. `/admin` demos overview, ads, users, analytics, invitations, and platform recall, no auth or API. `backend/` is empty. Now: FastAPI, CloudBase Auth, document repository, gateway, Docker, worker, tenant `202` jobs, empty eight rates and five timings. Path A next: manual/CSV, mock catalog, CN→US, rules-only analysis, `seed_analysis_id`. Then: leads, campaigns, SES sandbox, enrichment, cold start, recall, ledgers, compliance, admin APIs, scale. WeChat pay, Hunyuan, and SES wait.

Step	          Pull request	 Result
test → pro      #5             1.1 on pro (22a3f24)
yzcmf → test    #6             1.2 on test (3a23696)
test → pro      #7             1.2 on pro (32b3707)
