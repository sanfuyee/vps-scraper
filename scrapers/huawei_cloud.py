"""华为云云耀云服务器 (HECS) 爬虫

抓取策略：从华为云产品定价页和活动页提取海外节点价格
海外节点: ap-southeast-1(新加坡/曼谷), af-south-1(约翰内斯堡), la-south-2(圣地亚哥) 等
"""

import json
import logging
import re

from bs4 import BeautifulSoup

from models import VpsDeal
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

PRICING_URL = "https://www.huaweicloud.com/pricing/calculator.html#/hecs"
PRODUCT_URL = "https://www.huaweicloud.com/product/hecs.html"
INTL_URL = "https://www.huaweicloud.com/intl/en-us/product/hecs.html"
BUY_URL = "https://www.huaweicloud.com/product/hecs.html"

CN_REGION_KEYS = ["cn-north", "cn-south", "cn-east", "cn-southwest", "北京", "上海", "广州", "深圳", "贵阳"]

OVERSEAS_REGION_KEYS = [
    "ap-southeast", "af-south", "la-south", "la-north", "na-mexico",
    "sa-brazil", "eu-west", "tr-west",
    "新加坡", "曼谷", "雅加达", "香港", "约翰内斯堡", "圣地亚哥",
    "墨西哥城", "圣保罗", "巴黎", "阿姆斯特丹", "都柏林", "伊斯坦布尔",
    "singapore", "bangkok", "jakarta", "hong kong",
]


def _is_overseas(text: str) -> bool:
    t = text.lower()
    if any(k in t for k in CN_REGION_KEYS):
        return False
    return any(k in t for k in OVERSEAS_REGION_KEYS)


class HuaweiCloudScraper(BaseScraper):
    name = "华为云"

    def scrape(self) -> list[VpsDeal]:
        deals: list[VpsDeal] = []

        deals.extend(self._scrape_product_page())

        if not deals:
            deals.extend(self._scrape_intl_page())

        return deals

    def _scrape_product_page(self) -> list[VpsDeal]:
        deals = []
        try:
            resp = self.get(PRODUCT_URL)
            soup = BeautifulSoup(resp.text, "lxml")

            for script in soup.find_all("script"):
                text = script.string or ""
                for raw in re.findall(r'(\{.+?\})', text, re.DOTALL):
                    if len(raw) > 5000:
                        continue
                    try:
                        data = json.loads(raw)
                        if "price" in data or "unitPrice" in data:
                            deal = self._parse_item(data, is_cny=True)
                            if deal:
                                deals.append(deal)
                    except (json.JSONDecodeError, TypeError):
                        continue

            price_sections = soup.find_all(class_=re.compile(r"price|spec|config|plan", re.I))
            for section in price_sections:
                text = section.get_text(" ", strip=True)
                if _is_overseas(text):
                    price = self._extract_price(text)
                    if price and price > 0:
                        deals.append(VpsDeal(
                            provider=self.name,
                            name="云耀云服务器 HECS",
                            monthly_price_cny=price,
                            location=text[:60],
                            url=BUY_URL,
                            is_overseas=True,
                        ))

        except Exception:
            logger.debug("[%s] 产品页抓取失败", self.name, exc_info=True)
        return deals

    def _scrape_intl_page(self) -> list[VpsDeal]:
        deals = []
        try:
            resp = self.get(INTL_URL)
            soup = BeautifulSoup(resp.text, "lxml")

            tables = soup.find_all("table")
            for table in tables:
                rows = table.find_all("tr")
                if len(rows) < 2:
                    continue
                headers = [th.get_text(strip=True).lower() for th in rows[0].find_all(["th", "td"])]
                for row in rows[1:]:
                    cells = [td.get_text(strip=True) for td in row.find_all("td")]
                    if len(cells) < 2:
                        continue
                    cell_map = dict(zip(headers, cells))
                    price_str = cell_map.get("price", "") or cell_map.get("pricing", "")
                    price_val = self._extract_price(price_str)
                    if price_val is None:
                        continue

                    is_usd = "$" in price_str
                    monthly_cny = self.usd(price_val) if is_usd else price_val

                    deals.append(VpsDeal(
                        provider=self.name,
                        name=cell_map.get("flavor", "") or "HECS",
                        monthly_price_cny=monthly_cny,
                        cpu=cell_map.get("vcpus", ""),
                        ram=cell_map.get("memory", ""),
                        disk=cell_map.get("storage", ""),
                        url=BUY_URL,
                        is_overseas=True,
                    ))

        except Exception:
            logger.debug("[%s] 国际站抓取失败", self.name, exc_info=True)
        return deals

    def _parse_item(self, data: dict, is_cny: bool) -> VpsDeal | None:
        price = data.get("price") or data.get("unitPrice")
        if price is None:
            return None
        try:
            price_val = float(price)
        except (ValueError, TypeError):
            return None

        region = str(data.get("region", "") or data.get("regionId", ""))
        if not _is_overseas(region):
            return None

        monthly_cny = price_val if is_cny else self.usd(price_val)
        return VpsDeal(
            provider=self.name,
            name=data.get("name", "") or "HECS",
            monthly_price_cny=monthly_cny,
            cpu=str(data.get("cpu", "")),
            ram=str(data.get("memory", "")),
            disk=str(data.get("disk", "")),
            location=region,
            url=BUY_URL,
            is_overseas=True,
        )

    @staticmethod
    def _extract_price(text: str) -> float | None:
        m = re.search(r'[\d,]+\.?\d*', text.replace(",", ""))
        if m:
            try:
                return float(m.group())
            except ValueError:
                pass
        return None
