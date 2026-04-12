"""BandwagonHost (搬瓦工) 爬虫

抓取策略：从搬瓦工产品页面提取 VPS 套餐和价格
搬瓦工以优质中美线路闻名，偶尔有低价限量套餐补货
"""

import logging
import re

from bs4 import BeautifulSoup

from models import VpsDeal
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

MAIN_URL = "https://bandwagonhost.com/cart.php"
VPS_URL = "https://bwh81.net/cart.php?gid=1"
BUY_URL = "https://bandwagonhost.com/"


class BandwagonScraper(BaseScraper):
    name = "搬瓦工"

    def scrape(self) -> list[VpsDeal]:
        deals: list[VpsDeal] = []

        deals.extend(self._scrape_page(VPS_URL))

        if not deals:
            deals.extend(self._scrape_page(MAIN_URL))

        return deals

    def _scrape_page(self, url: str) -> list[VpsDeal]:
        deals = []
        try:
            resp = self.get(url)
            soup = BeautifulSoup(resp.text, "lxml")

            products = soup.find_all(class_=re.compile(r"product|package|plan", re.I))
            if not products:
                products = soup.find_all("div", class_=re.compile(r"box|item", re.I))

            for prod in products:
                deal = self._parse_product(prod, url)
                if deal:
                    deals.append(deal)

            if not deals:
                tables = soup.find_all("table")
                for table in tables:
                    deals.extend(self._parse_table(table, url))

        except Exception:
            logger.debug("[%s] 页面抓取失败: %s", self.name, url, exc_info=True)
        return deals

    def _parse_product(self, prod, page_url: str) -> VpsDeal | None:
        text = prod.get_text(" ", strip=True)

        if "out of stock" in text.lower() or "sold out" in text.lower():
            return None

        yearly_cny = None
        monthly_cny = None

        ym = re.search(r'\$\s*(\d+\.?\d*)\s*/?\s*(?:year|yr|ann|per year)', text, re.I)
        if ym:
            yearly_cny = self.usd(float(ym.group(1)))

        mm = re.search(r'\$\s*(\d+\.?\d*)\s*/?\s*(?:month|mo|per month)\b', text, re.I)
        if mm:
            monthly_cny = self.usd(float(mm.group(1)))

        qm = re.search(r'\$\s*(\d+\.?\d*)\s*/?\s*(?:quarter|qtr|3 month)', text, re.I)
        if qm and monthly_cny is None:
            monthly_cny = self.usd(float(qm.group(1)) / 3)

        if yearly_cny is None and monthly_cny is None:
            return None

        cpu_m = re.search(r'(\d+)\s*x?\s*(?:v?CPU|Core)', text, re.I)
        ram_m = re.search(r'(\d+\.?\d*)\s*(?:GB|MB)\s*(?:RAM|DDR)', text, re.I)
        disk_m = re.search(r'(\d+)\s*(?:GB|TB)\s*(?:SSD|NVMe|RAID|KiwiVM)', text, re.I)
        bw_m = re.search(r'(\d+\.?\d*)\s*(?:TB|GB)\s*(?:BW|Bandwidth|Transfer)', text, re.I)
        loc_m = re.search(r'(?:DC|Location)s?[:\s]+([^\n]+)', text, re.I)

        link_el = prod.find("a", href=re.compile(r"order|cart|buy|configure", re.I))
        link = link_el["href"] if link_el else page_url

        return VpsDeal(
            provider=self.name,
            name=self._plan_name(text),
            monthly_price_cny=monthly_cny,
            yearly_price_cny=yearly_cny,
            cpu=cpu_m.group(0).strip() if cpu_m else "",
            ram=ram_m.group(0).strip() if ram_m else "",
            disk=disk_m.group(0).strip() if disk_m else "",
            bandwidth=bw_m.group(0).strip() if bw_m else "",
            location=loc_m.group(1).strip()[:80] if loc_m else "US/HK/JP",
            url=link,
            is_overseas=True,
        )

    def _parse_table(self, table, page_url: str) -> list[VpsDeal]:
        deals = []
        rows = table.find_all("tr")
        for row in rows:
            text = row.get_text(" ", strip=True)
            pm = re.search(r'\$\s*(\d+\.?\d*)\s*/?\s*(year|yr|month|mo|quarter)', text, re.I)
            if not pm:
                continue
            if "out of stock" in text.lower():
                continue

            price_val = float(pm.group(1))
            period = pm.group(2).lower()

            yearly_cny = None
            monthly_cny = None
            if period in ("year", "yr"):
                yearly_cny = self.usd(price_val)
            elif period == "quarter":
                monthly_cny = self.usd(price_val / 3)
            else:
                monthly_cny = self.usd(price_val)

            deals.append(VpsDeal(
                provider=self.name,
                name="KVM VPS",
                monthly_price_cny=monthly_cny,
                yearly_price_cny=yearly_cny,
                location="US/HK/JP",
                url=page_url,
                is_overseas=True,
            ))
        return deals

    @staticmethod
    def _plan_name(text: str) -> str:
        for pattern in [r'((?:\d+\s*GB?\s*KVM|SPECIAL|THE\s+\w+)\s*\S*)', r'(Plan\s*\S*)']:
            m = re.search(pattern, text, re.I)
            if m:
                return m.group(1).strip()[:40]
        return "KVM VPS"
