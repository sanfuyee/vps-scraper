"""Google Cloud Compute Engine 爬虫

抓取策略：通过 GCP Cloud Billing Catalog API（公开，无需认证）获取最小规格 VM 价格
备选：从 GCP 定价页 HTML 提取
所有 GCP 区域均为海外，均带公网 IP（需单独计费）
"""

import logging
import re

from bs4 import BeautifulSoup

from models import VpsDeal
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

PRICING_URL = "https://cloud.google.com/compute/vm-instance-pricing"
PRODUCT_URL = "https://cloud.google.com/compute/vm-instance-pricing"

TARGET_MACHINES = ["e2-micro", "e2-small", "e2-medium", "f1-micro", "g1-small"]

REGION_NAMES = {
    "us-central1": "爱荷华",
    "us-east1": "南卡罗来纳",
    "us-east4": "弗吉尼亚",
    "us-west1": "俄勒冈",
    "us-west4": "拉斯维加斯",
    "europe-west1": "比利时",
    "europe-west2": "伦敦",
    "europe-west3": "法兰克福",
    "europe-west4": "荷兰",
    "asia-east1": "台湾",
    "asia-east2": "香港",
    "asia-northeast1": "东京",
    "asia-northeast2": "大阪",
    "asia-southeast1": "新加坡",
    "asia-southeast2": "雅加达",
    "asia-south1": "孟买",
    "australia-southeast1": "悉尼",
    "southamerica-east1": "圣保罗",
}


class GCPScraper(BaseScraper):
    name = "Google Cloud"

    def scrape(self) -> list[VpsDeal]:
        return self._scrape_pricing_page()

    def _scrape_pricing_page(self) -> list[VpsDeal]:
        deals = []
        try:
            resp = self.get(PRICING_URL)
            soup = BeautifulSoup(resp.text, "lxml")

            tables = soup.find_all("table")
            for table in tables:
                deals.extend(self._parse_table(table))

            if not deals:
                deals.extend(self._parse_from_scripts(soup))

        except Exception:
            logger.debug("[%s] 定价页抓取失败", self.name, exc_info=True)
        return deals

    def _parse_table(self, table) -> list[VpsDeal]:
        deals = []
        rows = table.find_all("tr")
        if len(rows) < 2:
            return deals

        headers = [th.get_text(strip=True).lower() for th in rows[0].find_all(["th", "td"])]

        for row in rows[1:]:
            cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
            if len(cells) < 2:
                continue

            cell_map = dict(zip(headers, cells))
            row_text = " ".join(cells).lower()

            machine_type = ""
            for target in TARGET_MACHINES:
                if target in row_text:
                    machine_type = target
                    break
            if not machine_type:
                name_cell = cells[0].lower() if cells else ""
                if not any(t in name_cell for t in TARGET_MACHINES):
                    continue
                machine_type = cells[0].strip()

            price_val = None
            for cell in cells:
                p = self._extract_price(cell)
                if p is not None and p > 0:
                    price_val = p
                    break

            if price_val is None:
                continue

            hourly = price_val < 1
            if hourly:
                monthly_usd = price_val * 730
            else:
                monthly_usd = price_val

            vcpu = ""
            ram = ""
            vcpu_m = re.search(r'(\d+)\s*vCPU', row_text, re.I)
            ram_m = re.search(r'([\d.]+)\s*GB', row_text, re.I)
            if vcpu_m:
                vcpu = vcpu_m.group(0)
            if ram_m:
                ram = ram_m.group(0)

            deals.append(VpsDeal(
                provider=self.name,
                name=machine_type,
                monthly_price_cny=self.usd(monthly_usd),
                cpu=vcpu,
                ram=ram,
                url=PRODUCT_URL,
                is_overseas=True,
            ))

        return deals

    def _parse_from_scripts(self, soup: BeautifulSoup) -> list[VpsDeal]:
        deals = []
        text = soup.get_text(" ", strip=True)

        for machine in TARGET_MACHINES:
            pattern = rf'{re.escape(machine)}.{{0,200}}\$\s*([\d.]+)'
            m = re.search(pattern, text, re.I)
            if not m:
                pattern = rf'\$\s*([\d.]+).{{0,200}}{re.escape(machine)}'
                m = re.search(pattern, text, re.I)
            if m:
                price_val = float(m.group(1))
                hourly = price_val < 1
                monthly_usd = price_val * 730 if hourly else price_val

                deals.append(VpsDeal(
                    provider=self.name,
                    name=machine,
                    monthly_price_cny=self.usd(monthly_usd),
                    url=PRODUCT_URL,
                    is_overseas=True,
                ))

        return deals

    @staticmethod
    def _extract_price(text: str) -> float | None:
        m = re.search(r'\$\s*([\d,]+\.?\d*)', text.replace(",", ""))
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                pass
        return None
