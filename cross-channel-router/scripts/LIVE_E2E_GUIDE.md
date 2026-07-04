# Live E2E 验证指南（cross_channel_router）

P2-3 任务 — 在拥有 sandbox 凭据的环境下，对真实 Feishu/WeCom endpoint 进行端到端验证。

## 目标

验证 `src/http_clients.py` 的：
1. token 获取与缓存
2. 消息发送（text / card / card+buttons）
3. 错误码归一映射的真实性

## 已离线完成 ✅

- ✅ 41 个单元测试通过（mock urllib），含 7 个错误码覆盖测试
- ✅ 错误码映射表完整性自检（FEISHU_ERROR_MAP 10 条 + WECOM_ERROR_MAP 9 条 + 标准码全用）
- ✅ 用 fake credentials 实测打到飞书 endpoint，发现新错误码 `10003 invalid param` 已加入映射表
- ✅ 脚本 `scripts/live_e2e.py` 已就绪

## 需要 sandbox 才能完成的步骤 ⏳

需要的凭据（用户提供）：

### 飞书 sandbox

到 https://open.feishu.cn 创建一个测试自建应用：
- `FEISHU_APP_ID`：cli_xxx
- `FEISHU_APP_SECRET`：***
- `FEISHU_TEST_OPEN_ID`：测试接收方 open_id（自己测试机器人 → 自己）
- 应用权限要勾上 `im:message:send_as_bot`

### 企微 sandbox

到 https://work.weixin.qq.com 创建一个测试自建应用：
- `WECOM_CORP_ID`：wwxxx
- `WECOM_CORP_SECRET`：***
- `WECOM_AGENT_ID`：1000xxx
- `WECOM_TEST_USER`：测试接收方 userid（自己的企微账号 ID）
- 把测试用户加入应用可见范围

## 运行步骤

```bash
cd skills/cross_channel_router

# 1. 设置环境变量（建议放 .env，不要 commit）
export FEISHU_APP_ID='cli_xxx'
export FEISHU_APP_SECRET='***'
export FEISHU_TEST_OPEN_ID='ou_xxxxx'

export WECOM_CORP_ID='wwxxx'
export WECOM_CORP_SECRET='***'
export WECOM_AGENT_ID='1000001'
export WECOM_TEST_USER='YuZhaoPeng'

# 2. dry-run（仅验证 token 获取，不发消息）
python3 scripts/live_e2e.py --dry-run --channel both

#   预期: ✅ tenant_access_token OK / ✅ access_token OK
#   失败时打印具体错误码与 msg，可对照映射表

# 3. live 真实发送（会发 4 条飞书 + 3 条企微到测试用户）
python3 scripts/live_e2e.py --live --channel feishu
python3 scripts/live_e2e.py --live --channel wecom

#   预期: 测试用户收到 6~7 条消息
#   S1 文本 / S2 卡片 / S3 卡片+按钮 / S4 故意失败（INVALID_RECIPIENT）
```

## 预期产出与验收标准

| 测试 | 预期结果 |
|---|---|
| dry-run | exit_code=0；token 长度 > 30；尾 6 位被打印 |
| S1 text | `status=sent`，接收方收到时间戳文本 |
| S2 card | `status=sent`，接收方看到带标题的卡片 |
| S3 card+buttons | 飞书：卡片下方有可点按钮；企微：textcard 单按钮 |
| S4 invalid_recipient | `status=failed`, `error_code=INVALID_RECIPIENT` |

## 后续：把发现的新错误码沉淀回映射表

每次跑完 live e2e，把意外出现的错误码补到：

- `src/http_clients.py` 的 `FEISHU_ERROR_MAP` / `WECOM_ERROR_MAP`
- `tests/test_error_code_coverage.py` 的 `EXPECTED_MAP`

这是 cross_channel_router 长期维护的核心机制：**真实运行 → 沉淀错误码 → 单元测试固化**。

## 安全注意事项

- ❌ 不要把 sandbox 凭据 commit 到 git
- ❌ 不要在生产应用里跑 e2e（会真发消息）
- ✅ 用 sandbox 应用 + 仅自己 vs 自己测试
- ✅ 完成验证后立即 unset 环境变量或 rotate sandbox secret
