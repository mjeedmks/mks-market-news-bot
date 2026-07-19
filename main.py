import os
import time
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

sent = set()

# الكلمات التي نهتم بها
KEYWORDS = [
    "fed", "federal reserve", "fomc",
    "inflation", "cpi", "ppi", "gdp",
    "jobs", "unemployment",
    "treasury", "bond", "yield",
    "oil", "crude", "gold", "dollar",
    "nasdaq", "nyse", "cboe", "occ",
    "earnings", "revenue", "guidance",
    "dividend", "split",
    "merger", "acquisition",
    "ai", "artificial intelligence",
    "nvidia", "microsoft", "apple",
    "amazon", "meta", "tesla",
    "amd", "broadcom", "google",
    "alphabet", "netflix"
]


def send(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(
        url,
        data={
            "chat_id": CHAT_ID,
            "text": msg,
            "disable_web_page_preview": True
        }
    )


while True:
    try:
        url = f"https://finnhub.io/api/v1/news?category=general&token={FINNHUB_API_KEY}"
        news = requests.get(url).json()

        for item in news[:10]:

            if item["id"] in sent:
                continue

            headline = item["headline"].lower()

            # تجاهل الأخبار غير المهمة
            if not any(word in headline for word in KEYWORDS):
                continue

            sent.add(item["id"])

            message = f"""🚨 خبر عاجل

{item['headline']}

📰 المصدر: {item['source']}

━━━━━━━━━━━━━━
📊 Chart Master US | الأسواق الأمريكية
"""

            send(message)

        time.sleep(60)

    except Exception as e:
        print(e)
        time.sleep(60)
