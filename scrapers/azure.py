"""Azure VM 爬虫

抓取策略：通过 Azure Retail Prices REST API 获取最便宜的 Linux VM 价格
API 完全公开，无需认证
文档: https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices
"""

import logging

from models import VpsDeal
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

API_URL = "https://prices.azure.com/api/retail/prices"
PRODUCT_URL = "https://azure.microsoft.com/en-us/pricing/details/virtual-machines/linux/"

TARGET_SERIES = ["B1s", "B1ls", "B1ms", "B2ts", "B2ats", "A0", "A1"]


class AzureScraper(BaseScraper):
    name = "Azure"

    def scrape(self) -> list[VpsDeal]:
        deals = []
        for sku in TARGET_SERIES:
            deals.extend(self._fetch_sku(sku))
        return deals

    def _fetch_sku(self, sku: str) -> list[VpsDeal]:
        deals = []
        try:
            params = {
                "$filter": (
                    f"serviceName eq 'Virtual Machines' "
                    f"and priceType eq 'Consumption' "
                    f"and armSkuName eq 'Standard_{sku}' "
                    f"and currencyCode eq 'USD'"
                ),
            }
            data = self.get_json(API_URL, params=params)
            seen = set()

            for item in data.get("Items", []):
                meter = item.get("meterName", "")
                if "Windows" in meter or "Spot" in meter or "Low Priority" in meter:
                    continue

                region = item.get("armRegionName", "")
                if not region or region.startswith("usgov") or region.startswith("china"):
                    continue

                price_usd = item.get("retailPrice", 0) or item.get("unitPrice", 0)
                if price_usd <= 0:
                    continue

                monthly_usd = price_usd * 730
                dedup_key = f"{sku}|{region}"
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)

                deals.append(VpsDeal(
                    provider=self.name,
                    name=f"Standard_{sku}",
                    monthly_price_cny=self.usd(monthly_usd),
                    cpu=str(item.get("vcpus", "")),
                    ram=str(item.get("memoryInMb", "")),
                    location=region,
                    url=PRODUCT_URL,
                    is_overseas=True,
                ))

        except Exception:
            logger.debug("[%s] SKU %s 抓取失败", self.name, sku, exc_info=True)
        return deals
