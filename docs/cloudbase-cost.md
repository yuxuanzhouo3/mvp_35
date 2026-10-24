# 云开发费用：检查与安全关停

上海云开发按天结算扣费，来自环境 `mvp35-d6g2zp4539a542ebc`（别名 mvp35）的云托管空转，不是短信、微信支付或混元。

本页只允许**读状态**、**把最小副本改成 0**、以及**删除失败的部署版本**。禁止销毁环境、冻结服务、删库、关超量按量。域名、数据和当前线上服务都保留。

对照：[费用中心](https://console.cloud.tencent.com/expense/transactions) · [mvp35 控制台](https://tcb.cloud.tencent.com/dev?envId=mvp35-d6g2zp4539a542ebc)

## 账号里的环境

| 环境 ID | 别名 | 套餐 | 超量按量 | 和这笔流水的关系 |
| --- | --- | --- | --- | --- |
| `mvp35-d6g2zp4539a542ebc` | mvp35 | 个人版，资源点，到期 2026-12-31 | 开 | **就是这笔扣费** |
| `cloud1-3gn61ziydcfe6a57` | mornfront | 个人版预付，到期 2027-02-18，自动续费开 | 关 | 不进按天扣余额；不用就关自动续费 |

mvp35 线上版本目标：

| 服务 | 规格 | 安全目标 | 2026-10-22 状态 |
| --- | --- | --- | --- |
| `pickglobal-web` | 1 核 2GB，最大副本 2 | 最小副本 **0** | **已完成**：`pickglobal-web-114`，min=0，流量 100% |
| `pickglobal-api` | 1 核 2GB，最大副本 2 | 最小副本 **0** | **已完成**：`pickglobal-api-070`，min=0，流量 100% |

`pickglobal.mornscience.top` 仍指向这两套云托管。站点已验证返回 200。最小副本为 0 时域名仍在；连续约半小时没访问才会缩到 0，下次打开可能冷启动几十秒。

不该动：共享 PostgreSQL `postgres-hn5po6jy`、静态托管、云存储、云函数命名空间、mornfront 环境。

单价（上海云托管）：CPU 0.055 元/核时，内存 0.032 元/GB 时。一套 1C2G 常驻约 0.119 元/时。个人版每月先抵 4 万资源点，超出部分因超量按量已开，从余额扣。

## 每周检查

和 `test → pro` 同一天（周一）跑一次。本机需已 `tcb login`，或环境变量里有腾讯云临时密钥。脚本不打印密钥。

```bash
python3 scripts/cloudbase_cost_check.py --write-log
```

看这几项：

1. mvp35 是否还在，状态是否 `NORMAL`。
2. `pickglobal-web` / `pickglobal-api` 当前流量版本的**最小副本是否为 0**。
3. 有没有新版本又被设成最小副本 1（重新部署常会带回来）。
4. [pickglobal.mornscience.top](https://pickglobal.mornscience.top) 是否还返回 200。
5. 费用中心是否还有「云开发-上海-按天结算」。最小副本改 0 后，空闲约半小时才停表；当天仍可能有已产生的用量。

若最小副本又变成 ≥ 1：

```bash
python3 scripts/cloudbase_cost_check.py --scale-to-zero --write-log
```

脚本会对 mvp35 的 web/api 用**当前镜像**提交一次 `MinNum=0` 的更新，并清理本次产生的失败版本。不改 mornfront，不冻结，不删环境。

`pickglobal-api` 若再次 `deploy_failed`，改用手改（不伤环境）：

1. 打开 [pickglobal-api 版本页](https://tcb.cloud.tencent.com/dev?envId=mvp35-d6g2zp4539a542ebc#/platform-run/service/detail?serverName=pickglobal-api&tab=version)
2. 点当前流量 100% 的版本 → 扩缩容 / 副本模式改成 **低成本**
3. 最小副本改成 **0**，最大仍可留 2 → 保存

控制台等价路径同样适用于 web。

## 禁止

- 销毁环境、冻结云托管、删除当前流量版本、删除 PostgreSQL。
- 关掉超量按量（配额用尽会直接停服）。
- 把流量切到旧版本，或把最大副本改成 0。

下次部署若默认最小副本 1，部署后再跑一遍检查；web 可用 `--scale-to-zero`，api 若热更新失败就用手改上面三步。

## 检查记录

| 日期 | 操作 | mvp35 web 最小/当前 | mvp35 api 最小/当前 | 站点 | 备注 |
| --- | --- | --- | --- | --- | --- |
| 2026-10-22 | 初查 | 1 / 1（web-111） | 1 / 1（api-063） | 200 | 两套常驻，对应按天扣费 |
| 2026-10-22 | 最小副本改 0 | 0 / 1（web-112） | 1 / 1（api-063） | 200 | web 已低成本；api 热更新失败，待控制台改 min=0；失败版本已删 |
| 2026-10-22 | 复查 | 0 / 1 (pickglobal-web-112) | 1 / 1 (pickglobal-api-063) | 200 | 脚本检查 |
| 2026-10-24 | 复查 | 0 / 1 (pickglobal-web-114) | 0 / 1 (pickglobal-api-070) | 200 | 脚本检查 |
