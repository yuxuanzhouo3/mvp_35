# Flow

Work and push on `yzcmf`. That updates `origin/yzcmf` only. Open a PR from `yzcmf` to `test` and merge when you agree. Then open a PR from `test` to `pro` and merge when you agree. Direct pushes to `test` and `pro` are blocked.

Compare links:

- Test: https://github.com/yuxuanzhouo3/mvp_35/compare/test...yzcmf
- Pro: https://github.com/yuxuanzhouo3/mvp_35/compare/pro...test

## Version on each merge

Each merge commits a version on that branch. `test` and `pro` use the same `x.y`. Versions always contain exactly two numeric components: `1.0`, `1.1`, `1.2`, `2.0`. Do not use patch versions such as `1.0.0`. Private npm app manifests omit the npm `version` field because npm requires three-component semantic versions. The project release version remains `x.y`.

| `test` | → `pro` |
| --- | --- |
| `1.0` | `1.0` |
| `1.1` | `1.1` |

## Weekly production promotion

`.github/workflows/promote-test-to-pro.yml` runs every Monday at 13:30 UTC+8. If `test` has no changes beyond `pro`, it does nothing. If a `test` → `pro` PR is already open, it does not create a duplicate. Otherwise it opens the next two-component release PR for manual approval: `1.1` → `1.2` → `1.3`. Major releases such as `2.0` are selected through the workflow's manual version input. A scheduled run only increments the minor component. The workflow never pushes directly to protected branches and never merges production without review.

## Current pace

On 30 September 2026 the product is a shell. `front/` is Next.js 16. `/` is a marketing page whose buttons scroll or alert. Its copy is still a five-step path. `project.md` locks two paths: selection reports, then nine-channel acquisition. `/admin` demos overview, ads, users, analytics, invitations, and platform recall, with no auth and no API. `backend/` is empty.

Do the skeleton now: FastAPI, CloudBase Auth, document repository, gateway, Docker, worker, tenant-scoped `202` jobs, and an empty eight-rate / five-timing snapshot. Path A is next: manual and CSV import, a mock catalog, a CN→US snapshot, rules-only analysis, and a report action that carries `seed_analysis_id`. After that, in order: leads, campaigns, SES sandbox, enrichment, cold start, recall, ledgers, compliance, admin APIs, and scale. WeChat pay, Hunyuan, and SES stay unwired until their step.
