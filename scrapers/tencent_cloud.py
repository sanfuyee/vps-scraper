"""腾讯云轻量应用服务器 (Lighthouse) 爬虫

抓取策略：
1. 请求腾讯云轻量服务器国际站定价页，尝试从中提取 JSON 数据
2. 备选：直接请求产品列表 API
海外节点 region 包含：ap-singapore, ap-tokyo, na-siliconvalley, eu-frankfurt 等
"""

import json
import logging
import re

from bs4 import BeautifulSoup

from models import VpsDeal
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

PRICING_URL = "https://cloud.tencent.com/product/lighthouse"
INTL_PRICING_URL = "https://intl.cloud.tencent.com/pricing/lighthouse"
BUY_URL = "https://buy.cloud.tencent.com/lighthouse"

OVERSEAS_REGIONS = {
    "ap-singapore", "ap-bangkok", "ap-mumbai", "ap-jakarta", "ap-tokyo",
    "ap-seoul", "ap-hongkong", "na-siliconvalley", "na-ashburn",
    "eu-frankfurt", "eu-moscow", "sa-saopaulo",
}

REGION_NAMES = {
    "ap-singapore": "新加坡",
    "ap-bangkok": "曼谷",
    "ap-mumbai": "孟买",
    "ap-jakarta": "雅加达",
    "ap-tokyo": "东京",
    "ap-seoul": "首尔",
    "ap-hongkong": "香港",
    "na-siliconvalley": "硅谷",
    "na-ashburn": "弗吉尼亚",
    "eu-frankfurt": "法兰克福",
    "eu-moscow": "莫斯科",
    "sa-saopaulo": "圣保罗",
}


class TencentCloudScraper(BaseScraper):
    name = "腾讯云"

    def scrape(self) -> list[VpsDeal]:
        deals: list[VpsDeal] = []

        deals.extend(self._scrape_intl_page())

        if not deals:
            deals.extend(self._scrape_cn_page())

        return deals

    def _scrape_intl_page(self) -> list[VpsDeal]:
        """从国际站定价页提取价格数据"""
        deals = []
        try:
            resp = self.get(INTL_PRICING_URL)
            soup = BeautifulSoup(resp.text, "lxml")

            for script in soup.find_all("script"):
                text = script.string or ""
                for match in re.finditer(r'(\{[^{}]*"price"[^{}]*\})', text):
                    try:
                        data = json.loads(match.group(1))
                        deal = self._parse_intl_item(data)
                        if deal:
                            deals.append(deal)
                    except (json.JSONDecodeError, KeyError):
                        continue

            tables = soup.find_all("table")
            for table in tables:
                deals.extend(self._parse_pricing_table(table))

        except Exception:
            logger.debug("[%s] 国际站定价页抓取失败", self.name, exc_info=True)
        return deals

    def _scrape_cn_page(self) -> list[VpsDeal]:
        """从中国站产品页提取价格数据"""
        deals = []
        try:
            resp = self.get(PRICING_URL)
            soup = BeautifulSoup(resp.text, "lxml")

            for script in soup.find_all("script"):
                text = script.string or ""
                json_matches = re.findall(r'(?:window\.__INITIAL_STATE__|var\s+\w+\s*=)\s*(\{.+?\});', text, re.DOTALL)
                for raw in json_matches:
                    try:
                        data = json.loads(raw)
                        deals.extend(self._extract_from_state(data))
                    except (json.JSONDecodeError, ValueError):
                        continue

        except Exception:
            logger.debug("[%s] 中国站产品页抓取失败", self.name, exc_info=True)
        return deals

    def _parse_intl_item(self, data: dict) -> VpsDeal | None:
        price = data.get("price")
        region = data.get("region", "")
        if price is None or not any(r in region for r in OVERSEAS_REGIONS):
            return None

        price_usd = float(price)
        return VpsDeal(
            provider=self.name,
            name=data.get("name", "Lighthouse"),
            monthly_price_cny=self.usd(price_usd),
            cpu=data.get("cpu", ""),
            ram=data.get("memory", ""),
            disk=data.get("disk", ""),
            bandwidth=data.get("bandwidth", ""),
            location=REGION_NAMES.get(region, region),
            url=BUY_URL,
            is_overseas=True,
        )

    def _parse_pricing_table(self, table) -> list[VpsDeal]:
        deals = []
        rows = table.find_all("tr")
        if len(rows) < 2:
            return deals

        headers = [th.get_text(strip=True).lower() for th in rows[0].find_all(["th", "td"])]

        for row in rows[1:]:
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cells) < len(headers):
                continue

            cell_map = dict(zip(headers, cells))
            price_str = cell_map.get("price", "") or cell_map.get("月费", "") or cell_map.get("价格", "")
            price_val = self._extract_price(price_str)
            if price_val is None:
                continue

            is_usd = "$" in price_str or "usd" in price_str.lower()
            monthly_cny = self.usd(price_val) if is_usd else price_val

            deals.append(VpsDeal(
                provider=self.name,
                name=cell_map.get("plan", "") or cell_map.get("套餐", "") or "Lighthouse",
                monthly_price_cny=monthly_cny,
                cpu=cell_map.get("vcpu", "") or cell_map.get("cpu", ""),
                ram=cell_map.get("memory", "") or cell_map.get("内存", ""),
                disk=cell_map.get("ssd", "") or cell_map.get("存储", ""),
                bandwidth=cell_map.get("transfer", "") or cell_map.get("流量", ""),
                location=cell_map.get("region", "") or cell_map.get("地域", ""),
                url=BUY_URL,
                is_overseas=True,
            ))
        return deals

    def _extract_from_state(self, data: dict) -> list[VpsDeal]:
        deals = []
        if isinstance(data, dict):
            for key, val in data.items():
                if isinstance(val, list):
                    for item in val:
                        if isinstance(item, dict) and ("price" in item or "unitPrice" in item):
                            region = item.get("region", "") or item.get("zone", "")
                            if any(r in region for r in OVERSEAS_REGIONS):
                                price = float(item.get("price") or item.get("unitPrice", 0))
                                if price > 0:
                                    deals.append(VpsDeal(
                                        provider=self.name,
                                        name=item.get("name", "Lighthouse"),
                                        monthly_price_cny=price,
                                        cpu=str(item.get("cpu", "")),
                                        ram=str(item.get("memory", "")),
                                        disk=str(item.get("disk", "")),
                                        bandwidth=str(item.get("bandwidth", "")),
                                        location=REGION_NAMES.get(region, region),
                                        url=BUY_URL,
                                        is_overseas=True,
                                    ))
                elif isinstance(val, dict):
                    deals.extend(self._extract_from_state(val))
        return deals

    @staticmethod
    def _extract_price(text: str) -> float | None:
        m = re.search(r'[\d,]+\.?\d*', text.replace(",", ""))
        if m:
            try:
                return float(m.group())
            except ValueError:
                pass
        return None
