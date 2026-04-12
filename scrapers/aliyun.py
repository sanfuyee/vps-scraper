"""阿里云轻量应用服务器 (SWAS) 爬虫

抓取策略：
1. 从阿里云国际站 SWAS 定价页提取价格
2. 从中国站活动/产品页提取
海外节点: ap-southeast-1(新加坡), ap-northeast-1(东京), us-west-1(硅谷), eu-central-1(法兰克福) 等
"""

import json
import logging
import re

from bs4 import BeautifulSoup

from models import VpsDeal
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

INTL_URL = "https://www.alibabacloud.com/product/swas/pricing"
CN_URL = "https://www.aliyun.com/product/swas"
BUY_URL = "https://www.aliyun.com/product/swas"

OVERSEAS_KEYWORDS = [
    "singapore", "新加坡", "tokyo", "东京", "hongkong", "香港",
    "silicon", "硅谷", "virginia", "弗吉尼亚", "frankfurt", "法兰克福",
    "london", "伦敦", "mumbai", "孟买", "jakarta", "雅加达",
    "seoul", "首尔", "sydney", "悉尼", "dubai", "迪拜",
    "ap-southeast", "ap-northeast", "us-west", "us-east",
    "eu-central", "eu-west", "me-east",
]

CN_REGIONS = [
    "beijing", "北京", "shanghai", "上海", "guangzhou", "广州",
    "shenzhen", "深圳", "hangzhou", "杭州", "chengdu", "成都",
    "cn-", "华北", "华东", "华南",
]


def _is_overseas(text: str) -> bool:
    t = text.lower()
    if any(kw in t for kw in CN_REGIONS):
        return False
    return any(kw in t for kw in OVERSEAS_KEYWORDS)


class AliyunScraper(BaseScraper):
    name = "阿里云"

    def scrape(self) -> list[VpsDeal]:
        deals: list[VpsDeal] = []
        deals.extend(self._scrape_intl())
        if not deals:
            deals.extend(self._scrape_cn())
        return deals

    def _scrape_intl(self) -> list[VpsDeal]:
        deals = []
        try:
            resp = self.get(INTL_URL)
            soup = BeautifulSoup(resp.text, "lxml")

            for script in soup.find_all("script"):
                text = script.string or ""
                for raw in re.findall(r'(\[{.+?}\])', text, re.DOTALL):
                    try:
                        arr = json.loads(raw)
                        if isinstance(arr, list):
                            for item in arr:
                                deal = self._try_parse(item, is_usd=True)
                                if deal:
                                    deals.append(deal)
                    except (json.JSONDecodeError, TypeError):
                        continue

            tables = soup.find_all("table")
            for table in tables:
                deals.extend(self._parse_table(table, is_usd=True))

        except Exception:
            logger.debug("[%s] 国际站抓取失败", self.name, exc_info=True)
        return deals

    def _scrape_cn(self) -> list[VpsDeal]:
        deals = []
        try:
            resp = self.get(CN_URL)
            soup = BeautifulSoup(resp.text, "lxml")

            for script in soup.find_all("script"):
                text = script.string or ""
                for raw in re.findall(r'(\{["\'].+?["\']:.+?\})', text, re.DOTALL):
                    try:
                        data = json.loads(raw)
                        deal = self._try_parse(data, is_usd=False)
                        if deal:
                            deals.append(deal)
                    except (json.JSONDecodeError, TypeError):
                        continue

            price_cards = soup.find_all(class_=re.compile(r"price|card|plan|product", re.I))
            for card in price_cards:
                deal = self._parse_card(card)
                if deal:
                    deals.append(deal)

        except Exception:
            logger.debug("[%s] 中国站抓取失败", self.name, exc_info=True)
        return deals

    def _try_parse(self, item: dict, is_usd: bool) -> VpsDeal | None:
        if not isinstance(item, dict):
            return None
        price = item.get("price") or item.get("originalPrice") or item.get("discountPrice")
        if price is None:
            return None
        try:
            price_val = float(price)
        except (ValueError, TypeError):
            return None
        if price_val <= 0:
            return None

        region = str(item.get("region", "") or item.get("regionId", "") or item.get("location", ""))
        if region and not _is_overseas(region):
            return None

        monthly_cny = self.usd(price_val) if is_usd else price_val

        return VpsDeal(
            provider=self.name,
            name=item.get("name", "") or item.get("specName", "") or "轻量服务器",
            monthly_price_cny=monthly_cny,
            cpu=str(item.get("cpu", "") or item.get("core", "")),
            ram=str(item.get("memory", "") or item.get("ram", "")),
            disk=str(item.get("disk", "") or item.get("storage", "")),
            bandwidth=str(item.get("bandwidth", "") or item.get("dataDisk", "")),
            location=region,
            url=BUY_URL,
            is_overseas=True if not region else _is_overseas(region),
        )

    def _parse_table(self, table, is_usd: bool) -> list[VpsDeal]:
        deals = []
        rows = table.find_all("tr")
        if len(rows) < 2:
            return deals

        headers = [th.get_text(strip=True).lower() for th in rows[0].find_all(["th", "td"])]
        for row in rows[1:]:
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cells) < 2:
                continue
            cell_map = dict(zip(headers, cells))

            price_str = ""
            for key in ("price", "月费", "价格", "monthly"):
                if key in cell_map:
                    price_str = cell_map[key]
                    break

            price_val = self._extract_num(price_str)
            if price_val is None or price_val <= 0:
                continue

            location = ""
            for key in ("region", "地域", "location"):
                if key in cell_map:
                    location = cell_map[key]
                    break

            if location and not _is_overseas(location):
                continue

            monthly_cny = self.usd(price_val) if is_usd else price_val
            deals.append(VpsDeal(
                provider=self.name,
                name=cell_map.get("plan", "") or cell_map.get("套餐", "") or "轻量服务器",
                monthly_price_cny=monthly_cny,
                cpu=cell_map.get("vcpu", "") or cell_map.get("cpu", ""),
                ram=cell_map.get("memory", "") or cell_map.get("内存", ""),
                disk=cell_map.get("storage", "") or cell_map.get("存储", ""),
                bandwidth=cell_map.get("transfer", "") or cell_map.get("流量", ""),
                location=location,
                url=BUY_URL,
                is_overseas=True,
            ))
        return deals

    def _parse_card(self, card) -> VpsDeal | None:
        text = card.get_text(" ", strip=True)
        price_val = self._extract_num(text)
        if price_val is None or price_val <= 0:
            return None
        if not _is_overseas(text):
            return None

        return VpsDeal(
            provider=self.name,
            name="轻量服务器",
            monthly_price_cny=price_val,
            location=text[:50],
            url=BUY_URL,
            is_overseas=True,
        )

    @staticmethod
    def _extract_num(text: str) -> float | None:
        m = re.search(r'[\d,]+\.?\d*', text.replace(",", ""))
        if m:
            try:
                return float(m.group())
            except ValueError:
                pass
        return None
