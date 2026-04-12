import logging
import time
from abc import ABC, abstractmethod

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from models import VpsDeal

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]


class BaseScraper(ABC):
    name: str = "base"
    timeout: int = 30

    def __init__(self, usd_to_cny: float = 7.2):
        self.usd_to_cny = usd_to_cny
        self.session = self._build_session()

    def _build_session(self) -> requests.Session:
        s = requests.Session()
        retry = Retry(total=2, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry)
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        s.headers.update({
            "User-Agent": USER_AGENTS[0],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
        })
        return s

    def get(self, url: str, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        logger.debug("[%s] GET %s", self.name, url)
        resp = self.session.get(url, **kwargs)
        resp.raise_for_status()
        return resp

    def get_json(self, url: str, **kwargs) -> dict:
        resp = self.get(url, **kwargs)
        return resp.json()

    def usd(self, amount: float) -> float:
        return round(amount * self.usd_to_cny, 2)

    @abstractmethod
    def scrape(self) -> list[VpsDeal]:
        ...

    def safe_scrape(self) -> list[VpsDeal]:
        try:
            start = time.time()
            deals = self.scrape()
            elapsed = time.time() - start
            logger.info("[%s] 抓取到 %d 条信息 (%.1fs)", self.name, len(deals), elapsed)
            return deals
        except Exception:
            logger.exception("[%s] 抓取失败", self.name)
            return []
