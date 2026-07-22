import os
import time
import requests
from cache import get, set as cache_set
from sent import load, save
from openai import OpenAI

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
print("OPENAI =", OPENAI_API_KEY[:12] if OPENAI_API_KEY else "None")
print("FINNHUB =", FINNHUB_API_KEY[:8] if FINNHUB_API_KEY else "None")
print("KEY START:", repr(OPENAI_API_KEY[:15]))
client = OpenAI(api_key=OPENAI_API_KEY)

sent = load()

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
    },
    timeout=15
)
    
def analyze_news(headline):
    cached = get(headline)

    if cached:
        return cached

    response = client.responses.create(
        model="gpt-5-nano",
        input=f"""
أنت محلل محترف للأسواق المالية الأمريكية.

مهم جداً:

إذا كان الخبر لا يؤثر على الأسواق المالية أو المستثمرين فأرجع فقط:

SKIP

ويشمل ذلك:
- الرياضة
- الجرائم
- المشاهير
- الأخبار المحلية غير الاقتصادية
- أي خبر لا يحرك الأسواق.

ولا تتجاهل أبداً الأخبار المتعلقة بـ:
- الفيدرالي
- أسعار الفائدة
- التضخم
- CPI
- PPI
- PCE
- GDP
- الوظائف
- البطالة
- السندات
- الدولار
- الذهب
- النفط
- أوبك
- الرسوم الجمركية
- العقوبات
- الحروب
- الهجمات العسكرية
- التوترات الجيوسياسية
- شركات السوق الأمريكي
- الأرباح
- الاندماجات
- الاستحواذات
- تقسيم الأسهم
- الذكاء الاصطناعي
- أشباه الموصلات.
إذا كان الخبر مهماً فاتبع القواعد التالية:

- اكتب باللغة العربية فقط.
- يمنع استخدام أي كلمة أو عنوان باللغة الإنجليزية إلا أسماء الشركات أو رموز الأسهم إذا وردت في الخبر.
- لا تترجم اسم الشركة أو رمز السهم.
- لا تكتب كلمة Summary أو Impact أو أي عنوان إنجليزي.

إذا كان الخبر اقتصادياً أو جيوسياسياً فاكتب فقط:

🚨 عنوان الخبر بالعربية.

📊 التأثير: (سطر واحد فقط إذا كان التأثير واضحاً)

مثال:
📊 التأثير: إيجابي للدولار | سلبي للمؤشرات

إذا كان الخبر يتعلق بشركة فاكتب فقط:

🚨 عنوان الخبر بالعربية.

ولا تكتب:
- ملخص.
- التأثير.
- تحليل.
- قطاعات.
- أسهم.
- أي تفاصيل إضافية.

إذا لم يكن الخبر مؤثراً على الأسواق فأرجع فقط:

SKIP

الخبر:

{headline}
"""
    )
    result = response.output_text

    cache_set(headline, result)

    return result
while True:
    try:
        url = f"https://finnhub.io/api/v1/news?category=general&token={FINNHUB_API_KEY}"
        response = requests.get(url, timeout=15)
        print(response.text)
        news = response.json()
        for item in news:
            if item["id"] in sent:
                continue

            headline = item["headline"]
            text = headline.lower()

            # تجاهل الأخبار غير المهمة
            if not any(word in text for word in KEYWORDS):
                continue

            analysis = analyze_news(headline)

            if analysis.strip() == "SKIP":
                continue

            sent.add(item["id"])
            save(sent)

            message = f"""{analysis}

📰 المصدر: {item['source']}

━━━━━━━━━━━━━━
📊 Chart News US | أخبار السوق الامريكي
https://t.me/ChartMaster_News
"""

            send(message)


        time.sleep(60)
    except Exception as e:
        import traceback
        traceback.print_exc()
        time.sleep(60)
