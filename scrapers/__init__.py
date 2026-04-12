from scrapers.tencent_cloud import TencentCloudScraper
from scrapers.aliyun import AliyunScraper
from scrapers.huawei_cloud import HuaweiCloudScraper
from scrapers.aws_lightsail import AWSLightsailScraper
from scrapers.gcp import GCPScraper
from scrapers.azure import AzureScraper
from scrapers.lowendbox import LowEndBoxScraper
from scrapers.racknerd import RackNerdScraper
from scrapers.cloudcone import CloudConeScraper
from scrapers.bandwagon import BandwagonScraper

SCRAPER_REGISTRY: dict[str, type] = {
    "tencent_cloud": TencentCloudScraper,
    "aliyun": AliyunScraper,
    "huawei_cloud": HuaweiCloudScraper,
    "aws_lightsail": AWSLightsailScraper,
    "gcp": GCPScraper,
    "azure": AzureScraper,
    "lowendbox": LowEndBoxScraper,
    "racknerd": RackNerdScraper,
    "cloudcone": CloudConeScraper,
    "bandwagon": BandwagonScraper,
}
