from dataclasses import dataclass, field
from typing import Optional


@dataclass
class VpsDeal:
    provider: str
    name: str
    monthly_price_cny: Optional[float] = None
    yearly_price_cny: Optional[float] = None
    currency: str = "CNY"
    cpu: str = ""
    ram: str = ""
    disk: str = ""
    bandwidth: str = ""
    location: str = ""
    has_public_ip: bool = True
    is_overseas: bool = True
    url: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def effective_monthly_cny(self) -> Optional[float]:
        if self.monthly_price_cny is not None:
            return self.monthly_price_cny
        if self.yearly_price_cny is not None:
            return round(self.yearly_price_cny / 12, 2)
        return None

    @property
    def unique_key(self) -> str:
        price = self.yearly_price_cny or self.monthly_price_cny or 0
        return f"{self.provider}|{self.name}|{price:.2f}"

    def matches_filter(
        self,
        max_yearly_cny: float,
        max_monthly_cny: float,
        require_overseas: bool,
        require_public_ip: bool,
    ) -> bool:
        if require_overseas and not self.is_overseas:
            return False
        if require_public_ip and not self.has_public_ip:
            return False

        price_ok = False
        if self.yearly_price_cny is not None and self.yearly_price_cny <= max_yearly_cny:
            price_ok = True
        if self.monthly_price_cny is not None and self.monthly_price_cny <= max_monthly_cny:
            price_ok = True
        if self.yearly_price_cny is None and self.monthly_price_cny is None:
            return False

        return price_ok

    def format_telegram(self) -> str:
        lines = [f"*{self.provider}* — {self.name}"]
        if self.monthly_price_cny is not None:
            lines.append(f"月付: ¥{self.monthly_price_cny:.1f}")
        if self.yearly_price_cny is not None:
            lines.append(f"年付: ¥{self.yearly_price_cny:.1f}")
        specs = []
        if self.cpu:
            specs.append(f"CPU {self.cpu}")
        if self.ram:
            specs.append(f"RAM {self.ram}")
        if self.disk:
            specs.append(f"Disk {self.disk}")
        if self.bandwidth:
            specs.append(f"BW {self.bandwidth}")
        if specs:
            lines.append("配置: " + " / ".join(specs))
        if self.location:
            lines.append(f"机房: {self.location}")
        if self.url:
            lines.append(f"[购买链接]({self.url})")
        return "\n".join(lines)
