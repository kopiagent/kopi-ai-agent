# 文档索引

> **AI 助手：动手写代码前先读这里。** 本文件是 `docs/` 的唯一入口目录。
> 「遗留问题」那一栏是活的 —— 它记录了**已知但这次没修**的事，避免下一个人（或下一个
> 会话）把已经查清的东西重查一遍。规则见 `CLAUDE.md`「遗留问题必须落文档」章。
>
> 新增文档后**必须**在本索引加一行，否则等于没写（没人找得到）。

## 遗留问题 / 待决事项（活文档，优先读）

这些文档记录**尚未解决**的事，随工作推进持续更新。改动相关领域前先读对应的一份。

| 文档 | 记录什么 | 状态 |
|---|---|---|
| [pending-product-decisions.md](pending-product-decisions.md) | 产品级待决：第三方 URL 出口、Docker 安全姿态、GHCR 可见性、E2E 主线、品牌单一来源、运维遗留 | 活跃 |
| [brand-rename-audit.md](brand-rename-audit.md) | 品牌改名剩余 ~150 处用户可见串的分类（T1 身份 / T2 商业出口 / T3 需人工判定 / T4 机械） | 活跃 |
| [kopi-gateway-provider-default.md](kopi-gateway-provider-default.md) | KOPI 网关成为默认 provider（`kopi` + `bill.kopiagent.ai/v1`）：两套 provider 解析体系未打通、余额面仍指旧域名、本机 clash 下无法端到端实测 | 活跃 |

## 契约 / 协议

跨进程、跨仓库的接口约定。**改这些等于改协议**，要同步另一端。

| 文档 | 内容 |
|---|---|
| [relay-connector-contract.md](relay-connector-contract.md) | Relay ↔ Connector 线协议（v1，实验性） |
| [chronos-managed-cron-contract.md](chronos-managed-cron-contract.md) | Chronos 托管 cron —— agent ↔ NAS 线协议 |
| [middleware/README.md](middleware/README.md) | Kopi Middleware |

## 运行时子系统

| 文档 | 内容 |
|---|---|
| [session-lifecycle.md](session-lifecycle.md) | 会话生命周期 |
| [billing-lifecycle.md](billing-lifecycle.md) | 计费生命周期：客户端状态、错误与恢复 |
| [micro-compaction.md](micro-compaction.md) | 微压缩 |
| [profile-routing.md](profile-routing.md) | 入站消息的 profile 路由 |
| [streaming-tts.md](streaming-tts.md) | 流式 TTS |

## 部署 / 运维

| 文档 | 内容 |
|---|---|
| [kanban/multi-gateway.md](kanban/multi-gateway.md) | 多网关部署 |
| [security/network-egress-isolation.md](security/network-egress-isolation.md) | Docker 部署的出网隔离 |
| [observability/README.md](observability/README.md) | Kopi Observer Hooks |
| [observability/monitoring.md](observability/monitoring.md) | 网关监控 |
| [observability/relay-shared-metrics.md](observability/relay-shared-metrics.md) | NeMo Relay 共享指标 |

## 设计 / 提案

| 文档 | 内容 |
|---|---|
| [design/profile-builder.md](design/profile-builder.md) | Profile Builder —— dashboard 原生的完整 profile 创建 |
| [design/office-fx-transient-effects.md](design/office-fx-transient-effects.md) | Office FX —— 像素办公室的一次性瞬时特效 |

## 事后复盘（RCA）

| 文档 | 内容 |
|---|---|
| [rca-ssl-cacert-post-git-pull.md](rca-ssl-cacert-post-git-pull.md) | `kopi update` 后 SSL CA 证书包损坏 |
| [plans/2026-06-09-003-fix-telegram-stream-overflow-continuations-plan.md](plans/2026-06-09-003-fix-telegram-stream-overflow-continuations-plan.md) | Telegram 流式回复在首个溢出块后中断 |

---

## 其它入口（不在 docs/ 下，但同样必读）

| 文件 | 内容 |
|---|---|
| `../CLAUDE.md` | **合并门禁（强制）** + 上游同步规则 + 发版流程。任何改动前必读 |
| `../AGENTS.md` | agent 侧约定 |
| `../.upstream-sync.json` | 同步状态的唯一事实来源（`synced_to_commit`）+ 已知噪音名单 |
| `../CONTRIBUTING.md` | 贡献指南 |

## 怎么加一份新文档

1. 放进 `docs/` 下合适的子目录（没有合适的就放顶层）。
2. 第一行写 `# 标题`，紧跟一句「这份文档回答什么问题」。
3. **回到本文件加一行**，归到上面某一栏。
4. 记「遗留问题」的文档：写清**证据指针**（`file:line` / issue / commit），
   以及**为什么这次没做**（缺信息？缺决策？缺依赖？）—— 让下一个人能直接接手，
   而不是从头考古。
