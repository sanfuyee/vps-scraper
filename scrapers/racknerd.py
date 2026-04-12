"""RackNerd 爬虫

抓取策略：从 RackNerd 官网和已知促销页面提取 VPS 套餐价格
RackNerd 常年有 $10-23/年 的超低价套餐，是最稳定的低价来源之一
"""

import logging
import re

from bs4 import BeautifulSoup

from models import VpsDeal
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

PROMO_URLS = [
    "https://www.racknerd.com/NewYear/",
    "https://www.racknerd.com/BlackFriday/",
]

MAIN_URL = "https://www.racknerd.com/"
KVM_URL = "https://www.racknerd.com/kvm-vps"
BUY_URL = "https://www.racknerd.com/"

LOCATIONS = "Los Angeles, San Jose, Seattle, Dallas, Chicago, New York, Ashburn, Amsterdam"


class RackNerdScraper(BaseScraper):
    name = "RackNerd"

    def scrape(self) -> list[VpsDeal]:
        deals: list[VpsDeal] = []

        for url in PROMO_URLS:
            deals.extend(self._scrape_page(url))

        deals.extend(self._scrape_page(KVM_URL))

        if not deals:
            deals.extend(self._scrape_page(MAIN_URL))

        return deals

    def _scrape_page(self, url: str) -> list[VpsDeal]:
        deals = []
        try:
            resp = self.get(url)
            soup = BeautifulSoup(resp.text, "lxml")

            for section in soup.find_all(class_=re.compile(r"pricing|plan|package|product", re.I)):
                deal = self._parse_section(section, url)
                if deal:
                    deals.append(deal)

            if not deals:
                deals.extend(self._parse_freeform(soup, url))

        except Exception:
            logger.debug("[%s] 页面抓取失败: %s", self.name, url, exc_info=True)
        return deals

    def _parse_section(self, section, page_url: str) -> VpsDeal | None:
        text = section.get_text(" ", strip=True)

        price_yearly = None
        price_monthly = None

        ym = re.search(r'\$\s*(\d+\.?\d*)\s*/?\s*(?:year|yr|ann)', text, re.I)
        if ym:
            price_yearly = float(ym.group(1))

        mm = re.search(r'\$\s*(\d+\.?\d*)\s*/?\s*(?:month|mo)\b', text, re.I)
        if mm:
            price_monthly = float(mm.group(1))

        if price_yearly is None and price_monthly is None:
            return None

        cpu_m = re.search(r'(\d+)\s*(?:v?CPU|Core)', text, re.I)
        ram_m = re.search(r'(\d+\.?\d*)\s*(?:GB|MB)\s*(?:RAM|DDR|Memory)', text, re.I)
        disk_m = re.search(r'(\d+)\s*(?:GB|TB)\s*(?:SSD|NVMe|Pure|Raid|HDD)', text, re.I)
        bw_m = re.search(r'(\d+\.?\d*)\s*(?:TB|GB)\s*(?:BW|Bandwidth|Transfer)', text, re.I)

        order_link = section.find("a", href=re.compile(r"order|cart|buy", re.I))
        link = order_link["href"] if order_link else page_url

        return VpsDeal(
            provider=self.name,
            name=self._extract_plan_name(text),
            monthly_price_cny=self.usd(price_monthly) if price_monthly else None,
            yearly_price_cny=self.usd(price_yearly) if price_yearly else None,
            cpu=cpu_m.group(0).strip() if cpu_m else "",
            ram=ram_m.group(0).strip() if ram_m else "",
            disk=disk_m.group(0).strip() if disk_m else "",
            bandwidth=bw_m.group(0).strip() if bw_m else "",
            location=LOCATIONS,
            url=link,
            is_overseas=True,
        )

    def _parse_freeform(self, soup: BeautifulSoup, page_url: str) -> list[VpsDeal]:
        deals = []
        text = soup.get_text(" ", strip=True)

        for m in re.finditer(
            r'\$\s*(\d+\.?\d*)\s*/?\s*(year|yr|month|mo)\b',
            text, re.I,
        ):
            price_val = float(m.group(1))
            period = m.group(2).lower()

            start = max(0, m.start() - 300)
            end = min(len(text), m.end() + 100)
            context = text[start:end]

            cpu_m = re.search(r'(\d+)\s*v?CPU', context, re.I)
            ram_m = re.search(r'(\d+\.?\d*)\s*GB\s*(?:RAM|DDR)', context, re.I)
            disk_m = re.search(r'(\d+)\s*GB\s*(?:SSD|NVMe)', context, re.I)

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
                cpu=cpu_m.group(0).strip() if cpu_m else "",
                ram=ram_m.group(0).strip() if ram_m else "",
                disk=disk_m.group(0).strip() if disk_m else "",
                location=LOCATIONS,
                url=page_url,
                is_overseas=True,
            ))

        return deals

    @staticmethod
    def _extract_plan_name(text: str) -> str:
        m = re.search(r'((?:KVM|VPS|Plan)\s*\S*)', text, re.I)
        if m:
            return m.group(1).strip()[:40]
        return "KVM VPS"
