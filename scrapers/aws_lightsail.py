"""AWS Lightsail 爬虫

抓取策略：通过 AWS 公开的定价 JSON 获取 Lightsail 实例价格
所有 Lightsail 区域均为海外，均带公网 IP
"""

import logging
import re

from bs4 import BeautifulSoup

from models import VpsDeal
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

PRICING_URL = "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonLightsail/current/index.json"
PRODUCT_URL = "https://aws.amazon.com/lightsail/pricing/"

REGION_NAMES = {
    "US East (N. Virginia)": "弗吉尼亚",
    "US East (Ohio)": "俄亥俄",
    "US West (Oregon)": "俄勒冈",
    "EU (Ireland)": "爱尔兰",
    "EU (London)": "伦敦",
    "EU (Frankfurt)": "法兰克福",
    "EU (Paris)": "巴黎",
    "EU (Stockholm)": "斯德哥尔摩",
    "Asia Pacific (Mumbai)": "孟买",
    "Asia Pacific (Singapore)": "新加坡",
    "Asia Pacific (Sydney)": "悉尼",
    "Asia Pacific (Tokyo)": "东京",
    "Asia Pacific (Seoul)": "首尔",
    "Asia Pacific (Jakarta)": "雅加达",
    "Canada (Central)": "加拿大",
    "South America (Sao Paulo)": "圣保罗",
}


class AWSLightsailScraper(BaseScraper):
    name = "AWS Lightsail"
    timeout = 60

    def scrape(self) -> list[VpsDeal]:
        try:
            data = self.get_json(PRICING_URL)
        except Exception:
            logger.warning("[%s] 无法获取定价 JSON，尝试备用方式", self.name)
            return self._scrape_pricing_page()

        return self._parse_pricing_json(data)

    def _parse_pricing_json(self, data: dict) -> list[VpsDeal]:
        deals = []
        products = data.get("products", {})
        terms = data.get("terms", {}).get("OnDemand", {})

        product_map = {}
        for sku, prod in products.items():
            pf = prod.get("productFamily", "").lower()
            if "instance" not in pf:
                continue
            attrs = prod.get("attributes", {})
            os_type = attrs.get("operatingSystem", "")
            if "Windows" in os_type:
                continue
            usage = attrs.get("usagetype", "")
            if "IPv6" in usage:
                continue
            product_map[sku] = attrs

        for sku, attrs in product_map.items():
            if sku not in terms:
                continue

            hourly_usd = None
            for offer in terms[sku].values():
                for dim in offer.get("priceDimensions", {}).values():
                    price_str = dim.get("pricePerUnit", {}).get("USD", "0")
                    try:
                        hourly_usd = float(price_str)
                    except ValueError:
                        continue
                    if hourly_usd > 0:
                        break
                if hourly_usd and hourly_usd > 0:
                    break

            if not hourly_usd or hourly_usd <= 0:
                continue

            monthly_usd = hourly_usd * 730
            region = attrs.get("location", "")
            region_label = REGION_NAMES.get(region, region)

            vcpu = attrs.get("vcpu", "")
            memory = attrs.get("memory", "")
            storage = attrs.get("storage", "")
            transfer = attrs.get("dataTransferQuota", "")

            deals.append(VpsDeal(
                provider=self.name,
                name=f"Lightsail {vcpu}vCPU/{memory}",
                monthly_price_cny=self.usd(monthly_usd),
                cpu=f"{vcpu} vCPU",
                ram=memory,
                disk=storage,
                bandwidth=transfer,
                location=region_label,
                url=PRODUCT_URL,
                is_overseas=True,
            ))

        return deals

    def _scrape_pricing_page(self) -> list[VpsDeal]:
        """备用：从定价页面 HTML 抓取"""
        deals = []
        try:
            resp = self.get(PRODUCT_URL)
            soup = BeautifulSoup(resp.text, "lxml")

            price_cols = soup.find_all(string=lambda t: t and "$" in t and "/mo" in t.lower())
            for elem in price_cols:
                text = elem.strip()
                m = re.search(r'\$(\d+\.?\d*)', text)
                if m:
                    price_usd = float(m.group(1))
                    deals.append(VpsDeal(
                        provider=self.name,
                        name=f"Lightsail ${price_usd}/mo",
                        monthly_price_cny=self.usd(price_usd),
                        url=PRODUCT_URL,
                        is_overseas=True,
                    ))
        except Exception:
            logger.debug("[%s] 定价页面抓取失败", self.name, exc_info=True)
        return deals
