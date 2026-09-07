# Flow

Work and push on `yzcmf` → updates `origin/yzcmf` only.

1. Open a PR: `yzcmf` → `test`, merge when you agree.
2. Open a PR: `test` → `pro`, merge when you agree.

Direct pushes to `test` and `pro` are blocked.

Compare links:

- Test: https://github.com/yuxuanzhouo3/mvp_35/compare/test...yzcmf
- Pro: https://github.com/yuxuanzhouo3/mvp_35/compare/pro...test

## Version on each merge

Each time you merge, commit a version on that branch.

`test` and `pro` use the same `x.y`.

Version numbers always contain exactly two numeric components:
`1.0`, `1.1`, `1.2`, `2.0`, and so on. Do not use patch versions such as `1.0.0`.

Private npm app manifests omit the npm `version` field because npm requires
three-component semantic versions; the project release version remains `x.y`.

| `test` | → `pro` |
| --- | --- |
| `1.0` | `1.0` |
| `1.1` | `1.1` |

## Weekly production promotion

`.github/workflows/promote-test-to-pro.yml` runs every Monday at 13:30 UTC+8.

- If `test` has no changes beyond `pro`, it does nothing.
- If a `test` → `pro` PR is already open, it does not create a duplicate.
- Otherwise it opens the next two-component release PR for manual approval:
  `1.1` → `1.2` → `1.3` and so on.
- Major releases such as `2.0` are selected through the workflow's manual
  version input; a scheduled run only increments the minor component.
- The workflow never pushes directly to protected branches and never merges
  production without review.
