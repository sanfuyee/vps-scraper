#!/usr/bin/env python3
"""VPS 低价监控 - 主入口

用法：
  python main.py              # 正常运行：抓取 → 过滤 → 去重 → 通知
  python main.py --test       # 发送 Telegram 测试消息
  python main.py --dry-run    # 只抓取和过滤，不发送通知
  python main.py --list-all   # 列出所有抓取到的 deal（不过滤）
"""

import argparse
import logging
import os
import sys

import yaml

from db import get_notified_keys, mark_notified
from models import VpsDeal
from notifier import send_deals, send_test
from scrapers import SCRAPER_REGISTRY

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_config(path: str = "config.yaml") -> dict:
    if not os.path.exists(path):
        path = "config.example.yaml"
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_scrapers(config: dict) -> list[VpsDeal]:
    enabled = config.get("scrapers", [])
    usd_to_cny = config.get("usd_to_cny", 7.2)
    all_deals: list[VpsDeal] = []

    for name in enabled:
        cls = SCRAPER_REGISTRY.get(name)
        if cls is None:
            logger.warning("未知爬虫: %s，跳过", name)
            continue

        scraper = cls(usd_to_cny=usd_to_cny)
        deals = scraper.safe_scrape()
        all_deals.extend(deals)

    logger.info("共抓取 %d 条 deal", len(all_deals))
    return all_deals


def filter_deals(deals: list[VpsDeal], config: dict) -> list[VpsDeal]:
    f = config.get("filter", {})
    max_yearly = f.get("max_yearly_price_cny", 200)
    max_monthly = f.get("max_monthly_price_cny", 20)
    require_overseas = f.get("require_overseas", True)
    require_public_ip = f.get("require_public_ip", True)

    matched = [d for d in deals if d.matches_filter(max_yearly, max_monthly, require_overseas, require_public_ip)]
    logger.info("过滤后 %d 条符合条件", len(matched))
    return matched


def deduplicate(deals: list[VpsDeal], data_dir: str = ".") -> list[VpsDeal]:
    notified = get_notified_keys(data_dir)
    new_deals = [d for d in deals if d.unique_key not in notified]
    logger.info("去重后 %d 条新 deal（历史已通知 %d 条）", len(new_deals), len(notified))
    return new_deals


def main():
    parser = argparse.ArgumentParser(description="VPS 低价监控")
    parser.add_argument("--test", action="store_true", help="发送 Telegram 测试消息")
    parser.add_argument("--dry-run", action="store_true", help="只抓取和过滤，不发送通知")
    parser.add_argument("--list-all", action="store_true", help="列出所有 deal 不过滤")
    parser.add_argument("--config", default="config.yaml", help="配置文件路径")
    args = parser.parse_args()

    config = load_config(args.config)

    if args.test:
        ok = send_test()
        sys.exit(0 if ok else 1)

    deals = run_scrapers(config)

    if args.list_all:
        print(f"\n===== 共 {len(deals)} 条 deal =====\n")
        for d in deals:
            print(d.format_telegram())
            print("─" * 40)
        return

    matched = filter_deals(deals, config)

    if not matched:
        logger.info("没有符合条件的 deal")
        return

    new_deals = deduplicate(matched)

    if not new_deals:
        logger.info("没有新的 deal 需要推送")
        return

    if args.dry_run:
        print(f"\n===== [Dry Run] {len(new_deals)} 条新 deal =====\n")
        for d in new_deals:
            print(d.format_telegram())
            print("─" * 40)
        return

    ok = send_deals(new_deals)

    if ok:
        mark_notified([d.unique_key for d in new_deals])
        logger.info("推送成功，已记录 %d 条 deal", len(new_deals))
    else:
        logger.error("推送失败，未记录 deal（下次将重试）")
        sys.exit(1)


if __name__ == "__main__":
    main()
