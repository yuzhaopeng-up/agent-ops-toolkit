#!/usr/bin/env python3
"""
live_e2e.py — cross_channel_router 真实 token 端到端测试脚本

⚠️  会真实发送消息，请用 sandbox 应用 + 测试用户。

用法:
  # 1. 设置环境变量 (建议从 .env 读取，不要硬编码)
  export FEISHU_APP_ID='cli_xxx'
  export FEISHU_APP_SECRET='xxxx'
  export FEISHU_TEST_OPEN_ID='ou_xxxxx'    # 接收方 open_id

  export WECOM_CORP_ID='wwxxx'
  export WECOM_CORP_SECRET='xxxx'
  export WECOM_AGENT_ID='1000001'
  export WECOM_TEST_USER='YuZhaoPeng'      # 接收方 userid

  # 2. 跑 dry-run（不发送，只验证连通性 + token 获取）
  python3 live_e2e.py --dry-run

  # 3. 跑真实发送
  python3 live_e2e.py --live --channel feishu
  python3 live_e2e.py --live --channel wecom
  python3 live_e2e.py --live --channel both

测试矩阵 (每个 channel):
  S1. text 简单文本
  S2. card 富文本卡片
  S3. card + buttons (飞书支持，企微降级为 textcard 单按钮)
  S4. 故意触发错误：发送给不存在的 user → 验证 INVALID_RECIPIENT
  S5. 长文本 → 触发降级矩阵的分片
"""
import argparse
import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from src.adapter import FeishuAdapter, WeComAdapter
from src.errors import INVALID_RECIPIENT, AUTH_EXPIRED
from src.message import OutboundMessage, Recipients, Recipient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("live_e2e")


def _msg(message_id, msg_type, content, recipient):
    return OutboundMessage(
        message_id=message_id,
        trace_id=f"trace_{message_id}",
        message_type=msg_type,
        content=content,
        recipients=Recipients(targets=[recipient]),
    )


def test_feishu(adapter, test_open_id, dry_run):
    log.info("=" * 60)
    log.info("FEISHU live e2e — receiver=%s", test_open_id)
    log.info("=" * 60)

    if dry_run:
        log.info("[dry-run] 仅验证 client 创建与 token 获取")
        c = adapter.client
        if c is None:
            log.error("FEISHU adapter has no client — check env vars")
            return 1
        try:
            tok = c._get_token()
            log.info("✅ tenant_access_token OK (len=%d, ends=%s)",
                     len(tok), tok[-6:])
            return 0
        except Exception as e:
            log.error("❌ token failed: %s", e)
            return 1

    rc = 0

    # S1: text
    log.info("\n--- S1: 简单文本 ---")
    r = adapter.send(_msg("e2e_s1_text", "text",
                          {"text": f"[live e2e] hello {time.strftime('%H:%M:%S')}"},
                          Recipient(type="user", id=test_open_id)))
    log.info("S1 result: status=%s code=%s id=%s",
             r.status, r.error_code, r.channel_message_id)
    if r.status != "sent":
        log.error("S1 FAIL: %s", r.error_message)
        rc = 1

    time.sleep(1)
    # S2: card
    log.info("\n--- S2: 富文本卡片 ---")
    r = adapter.send(_msg("e2e_s2_card", "card",
                          {"title": "Live E2E Test",
                           "body": "**Status**: ✅ all systems go\n\n_via cross_channel_router_"},
                          Recipient(type="user", id=test_open_id)))
    log.info("S2 result: status=%s code=%s", r.status, r.error_code)
    if r.status != "sent":
        log.error("S2 FAIL: %s", r.error_message)
        rc = 1

    time.sleep(1)
    # S3: card + buttons
    log.info("\n--- S3: card + buttons ---")
    r = adapter.send(_msg("e2e_s3_btn", "card",
                          {"title": "Card with Action",
                           "body": "Click below for docs:",
                           "buttons": [
                               {"label": "Open docs",
                                "url": "https://beta-agent-agent.nousresearch.com/docs"},
                           ]},
                          Recipient(type="user", id=test_open_id)))
    log.info("S3 result: status=%s code=%s", r.status, r.error_code)
    if r.status != "sent":
        log.error("S3 FAIL: %s", r.error_message)
        rc = 1

    time.sleep(1)
    # S4: 故意发给不存在的 user，验证 INVALID_RECIPIENT
    log.info("\n--- S4: 故意 invalid_recipient ---")
    r = adapter.send(_msg("e2e_s4_bad", "text",
                          {"text": "this should fail"},
                          Recipient(type="user", id="ou_DOES_NOT_EXIST_FAKE")))
    log.info("S4 result: status=%s code=%s msg=%s",
             r.status, r.error_code, r.error_message)
    if r.status == "failed" and r.error_code == INVALID_RECIPIENT:
        log.info("✅ S4 invalid_recipient mapping verified")
    elif r.status == "failed":
        log.warning("⚠️  S4 returned %s instead of INVALID_RECIPIENT — "
                    "需要更新 FEISHU_ERROR_MAP", r.error_code)
    else:
        log.error("❌ S4 should have failed but got status=%s", r.status)
        rc = 1

    return rc


def test_wecom(adapter, test_userid, dry_run):
    log.info("=" * 60)
    log.info("WECOM live e2e — receiver=%s", test_userid)
    log.info("=" * 60)

    if dry_run:
        c = adapter.client
        if c is None:
            log.error("WECOM adapter has no client — check env vars")
            return 1
        try:
            tok = c._get_token()
            log.info("✅ access_token OK (len=%d, ends=%s)",
                     len(tok), tok[-6:])
            return 0
        except Exception as e:
            log.error("❌ token failed: %s", e)
            return 1

    rc = 0

    log.info("\n--- S1: 简单文本 ---")
    r = adapter.send(_msg("e2e_s1_text", "text",
                          {"text": f"[live e2e] hello {time.strftime('%H:%M:%S')}"},
                          Recipient(type="user", id=test_userid)))
    log.info("S1: status=%s code=%s msgid=%s",
             r.status, r.error_code, r.channel_message_id)
    if r.status != "sent":
        log.error("S1 FAIL: %s", r.error_message)
        rc = 1

    time.sleep(1)
    log.info("\n--- S2: 卡片 ---")
    r = adapter.send(_msg("e2e_s2_card", "card",
                          {"title": "Live E2E Test",
                           "body": "Status: all systems go",
                           "url": "https://beta-agent-agent.nousresearch.com/docs"},
                          Recipient(type="user", id=test_userid)))
    log.info("S2: status=%s code=%s", r.status, r.error_code)
    if r.status != "sent":
        log.error("S2 FAIL: %s", r.error_message)
        rc = 1

    time.sleep(1)
    log.info("\n--- S3: invalid_recipient ---")
    r = adapter.send(_msg("e2e_s3_bad", "text",
                          {"text": "should fail"},
                          Recipient(type="user", id="DOES_NOT_EXIST_USER")))
    log.info("S3: status=%s code=%s msg=%s",
             r.status, r.error_code, r.error_message)
    if r.status == "failed":
        log.info("✅ S3 失败如预期 (code=%s)", r.error_code)
    else:
        log.error("❌ S3 应失败但成功了")
        rc = 1

    return rc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true",
                        help="真实发送 (默认 dry-run)")
    parser.add_argument("--dry-run", action="store_true",
                        help="仅验证 token (默认行为)")
    parser.add_argument("--channel", choices=["feishu", "wecom", "both"],
                        default="both")
    args = parser.parse_args()

    dry = not args.live  # 默认 dry-run

    rc = 0
    if args.channel in ("feishu", "both"):
        adapter = FeishuAdapter()  # 从环境变量读 token
        if adapter.client is None:
            log.warning("FEISHU 跳过：未设置 FEISHU_APP_ID / FEISHU_APP_SECRET")
        else:
            target = os.getenv("FEISHU_TEST_OPEN_ID")
            if not target and not dry:
                log.error("FEISHU live: 缺 FEISHU_TEST_OPEN_ID")
                return 2
            rc |= test_feishu(adapter, target, dry)

    if args.channel in ("wecom", "both"):
        adapter = WeComAdapter()
        if adapter.client is None:
            log.warning("WECOM 跳过：未设置 WECOM_CORP_ID / WECOM_CORP_SECRET")
        else:
            target = os.getenv("WECOM_TEST_USER")
            if not target and not dry:
                log.error("WECOM live: 缺 WECOM_TEST_USER")
                return 2
            rc |= test_wecom(adapter, target, dry)

    log.info("\nFinal exit code: %d", rc)
    return rc


if __name__ == "__main__":
    sys.exit(main())
