"""LowEndBox 聚合站爬虫

抓取策略：从 LowEndBox 博客首页和 RSS 提取最新 VPS deal 文章，
从文章内容中正则提取价格和配置信息
"""

import logging
import re

from bs4 import BeautifulSoup

from models import VpsDeal
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

SITE_URL = "https://lowendbox.com/"
RSS_URL = "https://lowendbox.com/feed/"


class LowEndBoxScraper(BaseScraper):
    name = "LowEndBox"

    def scrape(self) -> list[VpsDeal]:
        deals = self._scrape_rss()
        if not deals:
            deals = self._scrape_homepage()
        return deals

    def _scrape_rss(self) -> list[VpsDeal]:
        deals = []
        try:
            resp = self.get(RSS_URL)
            soup = BeautifulSoup(resp.text, "lxml-xml")

            for item in soup.find_all("item")[:15]:
                title = item.find("title")
                link = item.find("link")
                desc = item.find("description") or item.find("content:encoded")

                if not title or not desc:
                    continue

                title_text = title.get_text(strip=True)
                link_text = link.get_text(strip=True) if link else ""
                desc_text = desc.get_text(strip=True)

                parsed = self._parse_deal(title_text, desc_text, link_text)
                deals.extend(parsed)

        except Exception:
            logger.debug("[%s] RSS 抓取失败", self.name, exc_info=True)
        return deals

    def _scrape_homepage(self) -> list[VpsDeal]:
        deals = []
        try:
            resp = self.get(SITE_URL)
            soup = BeautifulSoup(resp.text, "lxml")

            articles = soup.find_all("article")[:15]
            for article in articles:
                title_el = article.find(["h2", "h3"])
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                link_el = title_el.find("a")
                link = link_el["href"] if link_el and link_el.get("href") else ""

                content = article.get_text(" ", strip=True)
                parsed = self._parse_deal(title, content, link)
                deals.extend(parsed)

        except Exception:
            logger.debug("[%s] 首页抓取失败", self.name, exc_info=True)
        return deals

    def _parse_deal(self, title: str, content: str, url: str) -> list[VpsDeal]:
        deals = []
        prices = re.findall(
            r'\$\s*(\d+\.?\d*)\s*/?\s*(year|yr|annual|month|mo)\b',
            content, re.IGNORECASE,
        )
        if not prices:
            prices = re.findall(
                r'\$\s*(\d+\.?\d*)\s*/?\s*(year|yr|annual|month|mo)\b',
                title, re.IGNORECASE,
            )
        if not prices:
            return deals

        cpu_m = re.search(r'(\d+)\s*(?:v?cpu|core)', content, re.I)
        ram_m = re.search(r'(\d+\.?\d*)\s*(?:GB|MB)\s*(?:RAM|DDR|memory)', content, re.I)
        disk_m = re.search(r'(\d+)\s*(?:GB|TB)\s*(?:SSD|NVMe|HDD|disk|storage)', content, re.I)
        bw_m = re.search(r'(\d+\.?\d*)\s*(?:TB|GB)\s*(?:BW|bandwidth|transfer|traffic)', content, re.I)
        loc_m = re.search(r'(?:location|datacenter|DC)s?[:\s]+([A-Za-z\s,/]+)', content, re.I)

        provider = self._extract_provider(title)
        cpu = cpu_m.group(0).strip() if cpu_m else ""
        ram = ram_m.group(0).strip() if ram_m else ""
        disk = disk_m.group(0).strip() if disk_m else ""
        bw = bw_m.group(0).strip() if bw_m else ""
        location = loc_m.group(1).strip()[:80] if loc_m else ""

        for price_str, period in prices:
            price_val = float(price_str)
            if price_val <= 0:
                continue

            yearly_cny = None
            monthly_cny = None
            if period.lower() in ("year", "yr", "annual"):
                yearly_cny = self.usd(price_val)
            else:
                monthly_cny = self.usd(price_val)

            deals.append(VpsDeal(
                provider=f"LEB/{provider}" if provider else self.name,
                name=title[:80],
                monthly_price_cny=monthly_cny,
                yearly_price_cny=yearly_cny,
                cpu=cpu,
                ram=ram,
                disk=disk,
                bandwidth=bw,
                location=location,
                url=url,
                is_overseas=True,
            ))

        return deals

    @staticmethod
    def _extract_provider(title: str) -> str:
        parts = re.split(r'[:\-–—|]', title, maxsplit=1)
        if len(parts) >= 2:
            return parts[0].strip()
        return ""
