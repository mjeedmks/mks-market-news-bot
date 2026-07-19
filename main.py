import os
import time
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

sent = set()


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
            if item["id"] not in sent:
                sent.add(item["id"])

                message = f"""🚨 خبر عاجل

{item['headline']}

📰 المصدر: {item['source']}"""

                send(message)

        time.sleep(60)

    except Exception as e:
        print(e)
        time.sleep(60)
