# apple-kr-iphone17promax-stock-monitor
(自用)用来查询韩国官方7家Apple store的iPhone 17 Pro Max指定型号的库存
# 🇰🇷 Apple Store iPhone 17 Pro Max 银色库存监控

一个基于 Python 的自动监控脚本，用于检测韩国 Apple Store 中 **iPhone 17 Pro Max 银色 512GB** 的门店自提库存变化，并通过 **Bark 推送** 实时通知。

> **仓库推荐名称**：`apple-kr-iphone17promax-stock-monitor`

---

## ✨ 功能简介

* 自动访问苹果官网的 Pickup 接口，实时查询指定型号的库存情况。
* 支持查询韩国 7 家官方直营店（通过种子门店 + `searchNearby=true` 实现）。
* 每 10~15 秒随机轮询一次，避免触发苹果服务器的防爬屏蔽。
* 检测到库存状态从“无货”变为“有货”时，立即通过 **Bark** 推送通知到手机。
* 自动记录每次检测到“有货”的门店、时间等信息到本地 CSV 文件。

---

## 🧩 环境依赖

* Python ≥ 3.8
* 依赖库：

  ```bash
  pip install requests pandas python-dateutil
  ```

---

## ⚙️ 使用方法

### 1️⃣ 克隆仓库

```bash
git clone https://github.com/yourname/apple-kr-iphone17promax-stock-monitor.git
cd apple-kr-iphone17promax-stock-monitor
```

### 2️⃣ 配置 Bark 推送

#### 推荐方式：使用环境变量

在运行脚本前设置 Bark 的设备 Key：

**macOS / Linux：**

```bash
export BARK_DEVICE_KEY="你的Bark设备Key"
```

**Windows PowerShell：**

```powershell
setx BARK_DEVICE_KEY "你的Bark设备Key"
```

> Bark 官方服务地址默认是 `https://api.day.app`，如使用自建服务器可设置 `BARK_SERVER_BASE`。

---

### 3️⃣ 运行脚本

```bash
python kr_iphone17pm_silver512_monitor.py
```

启动后脚本会持续运行，并在终端输出每次查询结果：

```
[2025-11-02 15:10:12 KST] 홍대:unavailable | 강남:unavailable | 명동:unavailable ...
```

当某家门店有库存时，将自动：

* 推送 Bark 通知到手机；
* 在本地生成 `iphone17pm_silver_512_availability_log.csv` 记录。

---

### 4️⃣ 测试 Bark 是否可用（可选）

可以启用脚本中注释掉的测试片段（`# [BARK TEST SNIPPET]`），让它每轮查询都推送一次“弘大门店状态”，验证通知功能是否正常。

---

## 🔍 配置项说明

| 配置项                     | 说明                     | 默认值                                          |
| ----------------------- | ---------------------- | -------------------------------------------- |
| `TARGET_SKU`            | 要监控的苹果产品型号（SKU）        | `MFYQ4KH/A`                                  |
| `SEED_STORE`            | 起始门店编号（例如 R764 代表弘大）   | `R764`                                       |
| `POLL_MIN` / `POLL_MAX` | 每轮检测的随机间隔（秒）           | 10 / 15                                      |
| `LOG_CSV_PATH`          | 结果日志 CSV 文件名           | `iphone17pm_silver_512_availability_log.csv` |
| `BARK_DEVICE_KEY`       | Bark 推送设备 Key（推荐用环境变量） | —                                            |
| `BARK_SERVER_BASE`      | Bark 服务器地址             | `https://api.day.app`                        |

---

## 🕒 延迟启动

如果你希望在 **7 小时 30 分钟后自动运行脚本**：

**Windows PowerShell：**

```powershell
timeout /t 27000 /nobreak && python kr_iphone17pm_silver512_monitor.py
```

**macOS / Linux：**

```bash
sleep $((7*3600 + 30*60)) && python3 kr_iphone17pm_silver512_monitor.py
```

---

## 🧠 提示

* 如果访问苹果接口时未返回门店列表，请确认 URL 中包含 `store=Rxxx` 参数。
* 若要监控其他型号（例如 iPhone 17 Pro 256GB），请修改 `SKU` 与 URL。
* 若频繁请求，建议适当增大轮询间隔以避免被限流。

---

## 📄 License

MIT License — 欢迎自由使用与二次开发。
