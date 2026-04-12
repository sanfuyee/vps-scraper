# VPS 低价监控

定时抓取各大云厂商 VPS 价格，发现符合条件的低价机器后通过 Telegram 推送通知。完全免费运行。

## 监控范围

| 梯队 | 厂商 | 说明 |
|------|------|------|
| 国内大厂 | 腾讯云、阿里云、华为云 | 海外轻量服务器活动价 |
| 国际大厂 | AWS Lightsail、Google Cloud、Azure | 公开 Pricing API |
| 小厂/聚合 | LowEndBox、RackNerd、CloudCone、搬瓦工 | 常年低价 |

## 筛选条件（默认）

- 年付 ≤ 200 CNY **或** 月付 ≤ 20 CNY
- 海外机房
- 带公网 IPv4

## 部署（GitHub Actions，免费）

### 1. Fork 本仓库

### 2. 创建 Telegram Bot

1. 在 Telegram 搜索 [@BotFather](https://t.me/BotFather)，发送 `/newbot`
2. 按提示设置名称，获得 **Bot Token**（格式 `123456:ABC-DEF...`）
3. 搜索你刚创建的 Bot，发送任意消息
4. 访问 `https://api.telegram.org/bot<TOKEN>/getUpdates`，从返回的 JSON 中找到 `chat.id`

### 3. 配置 GitHub Secrets

进入仓库 Settings → Secrets and variables → Actions → New repository secret：

| Name | Value |
|------|-------|
| `TELEGRAM_BOT_TOKEN` | Bot Token |
| `TELEGRAM_CHAT_ID` | Chat ID |

### 4. 启用 Workflow

进入 Actions 标签页，启用 workflow，也可以点 "Run workflow" 手动触发测试。

每天东八区中午 12:00 自动运行一次。

## 本地运行

```bash
# 安装依赖
pip install -r requirements.txt

# 复制并编辑配置
cp config.example.yaml config.yaml

# 设置环境变量
export TELEGRAM_BOT_TOKEN="your-bot-token"
export TELEGRAM_CHAT_ID="your-chat-id"

# 运行
python main.py

# 仅抓取不通知
python main.py --dry-run

# 列出所有 deal（不过滤）
python main.py --list-all

# 测试 Telegram 连通性
python main.py --test
```

## 配置说明

编辑 `config.yaml`（本地）或使用默认 `config.example.yaml`：

```yaml
filter:
  max_yearly_price_cny: 200   # 年付上限 (CNY)
  max_monthly_price_cny: 20   # 月付上限 (CNY)
  require_overseas: true       # 仅海外
  require_public_ip: true      # 需要公网 IP

usd_to_cny: 7.2               # 汇率

scrapers:                      # 注释掉可禁用某个爬虫
  - tencent_cloud
  - aliyun
  - huawei_cloud
  - aws_lightsail
  - gcp
  - azure
  - lowendbox
  - racknerd
  - cloudcone
  - bandwagon
```

## 添加新爬虫

1. 在 `scrapers/` 下创建新文件，继承 `BaseScraper`
2. 实现 `scrape()` 方法，返回 `list[VpsDeal]`
3. 在 `scrapers/__init__.py` 的 `SCRAPER_REGISTRY` 中注册
4. 在 `config.yaml` 的 `scrapers` 列表中启用

## 费用

| 组件 | 费用 |
|------|------|
| GitHub Actions | 免费 |
| Telegram Bot | 免费 |
| 数据存储 | 免费（Git） |

**总费用：$0**
