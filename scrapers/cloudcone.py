"""CloudCone 爬虫

抓取策略：从 CloudCone 官网和促销页面提取 VPS 价格
CloudCone 经常有闪购活动，价格可以非常低
机房位于 Los Angeles
"""

import logging
import re

from bs4 import BeautifulSoup

from models import VpsDeal
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

MAIN_URL = "https://cloudcone.com/"
VPS_URL = "https://cloudcone.com/cloud-servers/"
DEALS_URL = "https://cloudcone.com/offers/"
BUY_URL = "https://cloudcone.com/"


class CloudConeScraper(BaseScraper):
    name = "CloudCone"

    def scrape(self) -> list[VpsDeal]:
        deals: list[VpsDeal] = []

        deals.extend(self._scrape_page(DEALS_URL))
        deals.extend(self._scrape_page(VPS_URL))

        return deals

    def _scrape_page(self, url: str) -> list[VpsDeal]:
        deals = []
        try:
            resp = self.get(url)
            soup = BeautifulSoup(resp.text, "lxml")

            for card in soup.find_all(class_=re.compile(r"price|plan|package|product|offer", re.I)):
                deal = self._parse_card(card, url)
                if deal:
                    deals.append(deal)

            if not deals:
                deals.extend(self._parse_freeform(soup, url))

        except Exception:
            logger.debug("[%s] 页面抓取失败: %s", self.name, url, exc_info=True)
        return deals

    def _parse_card(self, card, page_url: str) -> VpsDeal | None:
        text = card.get_text(" ", strip=True)

        yearly_cny = None
        monthly_cny = None

        ym = re.search(r'\$\s*(\d+\.?\d*)\s*/?\s*(?:year|yr|ann)', text, re.I)
        if ym:
            yearly_cny = self.usd(float(ym.group(1)))

        mm = re.search(r'\$\s*(\d+\.?\d*)\s*/?\s*(?:month|mo)\b', text, re.I)
        if mm:
            monthly_cny = self.usd(float(mm.group(1)))

        if yearly_cny is None and monthly_cny is None:
            return None

        cpu_m = re.search(r'(\d+)\s*(?:v?CPU|Core)', text, re.I)
        ram_m = re.search(r'(\d+\.?\d*)\s*(?:GB|MB)\s*(?:RAM|DDR|Memory)', text, re.I)
        disk_m = re.search(r'(\d+)\s*(?:GB|TB)\s*(?:SSD|NVMe|Disk|Storage)', text, re.I)
        bw_m = re.search(r'(\d+\.?\d*)\s*(?:TB|GB)\s*(?:BW|Bandwidth|Transfer)', text, re.I)

        link_el = card.find("a", href=re.compile(r"order|cart|buy|app", re.I))
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
            location="Los Angeles",
            url=link,
            is_overseas=True,
        )

    def _parse_freeform(self, soup: BeautifulSoup, page_url: str) -> list[VpsDeal]:
        deals = []
        text = soup.get_text(" ", strip=True)

        for m in re.finditer(r'\$\s*(\d+\.?\d*)\s*/?\s*(year|yr|month|mo)\b', text, re.I):
            price_val = float(m.group(1))
            period = m.group(2).lower()
            if price_val <= 0:
                continue

            start = max(0, m.start() - 200)
            end = min(len(text), m.end() + 100)
            ctx = text[start:end]

            cpu_m = re.search(r'(\d+)\s*v?CPU', ctx, re.I)
            ram_m = re.search(r'(\d+\.?\d*)\s*GB\s*(?:RAM|DDR)', ctx, re.I)

            yearly_cny = None
            monthly_cny = None
            if period in ("year", "yr"):
                yearly_cny = self.usd(price_val)
            else:
                monthly_cny = self.usd(price_val)

            deals.append(VpsDeal(
                provider=self.name,
                name=f"VPS ${price_val}/{period}",
                monthly_price_cny=monthly_cny,
                yearly_price_cny=yearly_cny,
                cpu=cpu_m.group(0) if cpu_m else "",
                ram=ram_m.group(0) if ram_m else "",
                location="Los Angeles",
                url=page_url,
                is_overseas=True,
            ))

        return deals

    @staticmethod
    def _plan_name(text: str) -> str:
        m = re.search(r'((?:SC|VPS|SSD|Cloud)\s*\d*)', text, re.I)
        return m.group(1).strip()[:40] if m else "Cloud VPS"
