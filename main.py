import os
import time
import requests
from openai import OpenAI

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

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
    
def analyze_news(headline):
    response = client.responses.create(
        model="gpt-5-nano",
        input=f"""
        أنت محلل محترف للأسواق المالية الأمريكية.

مهم جداً:

إذا كان الخبر لا يؤثر على:
- الأسهم الأمريكية
- المؤشرات
- الاقتصاد الأمريكي
- الفيدرالي
- السندات
- الدولار
- النفط
- الذهب
- الشركات المدرجة
- الأرباح
- الاندماجات
- الذكاء الاصطناعي
- أشباه الموصلات

فأرجع فقط الكلمة التالية:

SKIP

ولا تكتب أي شيء آخر.

أما إذا كان الخبر مهماً فأعده بهذا الشكل:

🚨 خبر عاجل

📝 الملخص:
ترجم الخبر للعربية مع اختصار احترافي.

🏷️ التصنيف:
اختر تصنيفاً واحداً فقط.

📊 التأثير:
- إيجابي أو سلبي.
- على أي شركة؟
- على أي قطاع؟
- على S&P500 أو Nasdaq إذا كان لذلك علاقة.

الخبر:

{headline}
"""
    )

    return response.output_text

while True:
    try:
        url = f"https://finnhub.io/api/v1/news?category=general&token={FINNHUB_API_KEY}"
        news = requests.get(url).json()

        for item in news[:10]:

            if item["id"] in sent:
                continue

            headline = item["headline"]
            text = headline.lower()

            # تجاهل الأخبار غير المهمة
            if not any(word in text for word in KEYWORDS):
                continue

            sent.add(item["id"])

            # تصنيف الخبر
            category = "📰 عام"

            if any(x in text for x in ["earnings", "revenue", "guidance"]):
                category = "💰 أرباح"

            elif any(x in text for x in ["fed", "fomc", "interest rate", "powell"]):
                category = "🏦 الفيدرالي"

            elif any(x in text for x in ["oil", "crude"]):
                category = "🛢 النفط"

            elif any(x in text for x in ["gold"]):
                category = "🥇 الذهب"

            elif any(x in text for x in ["cpi", "inflation", "ppi"]):
                category = "📈 التضخم"

            elif any(x in text for x in ["jobs", "employment", "unemployment"]):
                category = "👷 الوظائف"
                        analysis = analyze_news(headline)

            if analysis.strip() == "SKIP":
                continue

            message = f"""{analysis}

📰 المصدر: {item['source']}

━━━━━━━━━━━━━━
📊 Chart Master US  
قناة الأسواق الأمريكية | كل ما يخص التداول
"""

            send(message)


        time.sleep(60)

    except Exception as e:
        print(e)
        time.sleep(60)
