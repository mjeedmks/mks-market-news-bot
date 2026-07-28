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
    "fed", "federal reserve", "fomc", "powell",
    "inflation", "cpi", "ppi", "pce", "gdp", "nfp",
    "jobs", "unemployment",
    "opec", "opec+",
    "tariff",
    "sanction",
    "iran",
    "israel",
    "hormuz",
    "red sea",
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
        input=f"""أنت محرر أخبار متخصص في السوق الأمريكي.

هدفك هو اختيار الأخبار التي تستحق إرسال إشعار فوري لمتداول في السوق الأمريكي، وليس تلخيص جميع الأخبار.

إذا كان الخبر مكررًا، أو مجرد متابعة لخبر سابق، أو تحديثًا بسيطًا لنفس الحدث، فأرجع فقط:

SKIP

إذا كان الخبر مجرد حركة في النفط أو الذهب أو الدولار أو السندات بدون حدث جديد يفسر الحركة، فأرجع:

SKIP

إذا كان الخبر مجرد تعليق أو توقع أو رأي أو تحليل صحفي، فأرجع:

SKIP

إذا كان الخبر لا يؤثر على قرارات المستثمر أو لا يستحق إشعارًا فوريًا، فأرجع:

SKIP

انشر فقط الأخبار المتعلقة بـ:

- الفيدرالي.
- أسعار الفائدة.
- Powell.
- FOMC.
- CPI.
- PPI.
- PCE.
- GDP.
- NFP.
- البطالة.
- الرسوم الجمركية.
- العقوبات.
- الحروب والتوترات الجيوسياسية المؤثرة.
- قرارات أوبك.
- نتائج الشركات الأمريكية.
- الاندماجات والاستحواذات.
- تقسيم الأسهم.
- إعلانات الشركات الكبرى.
- الأخبار التي قد تحرك السوق بشكل واضح.

إذا قررت نشر الخبر:

- اكتب بالعربية فقط.
- لا تكتب عبارة "عنوان الخبر بالعربية".
- لا تكتب كلمة "الملخص".
- لا تكتب كلمة "التحليل".
- اجعل الخبر مختصرًا.
- إذا كان الخبر عن شركة فاكتب عنوان الخبر فقط.
- إذا كان التأثير واضحًا فأضف سطرًا واحدًا فقط بالشكل التالي:

📊 التأثير: ...

إذا لم تكن متأكدًا بنسبة كبيرة أن الخبر يستحق إشعارًا فوريًا فأرجع فقط:

SKIP

الخبر:

{headline}
"""
    )

    result = response.output_text.strip()

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

            # فلترة الكلمات المهمة
            if not any(word in text for word in KEYWORDS):
                continue

            # تجاهل الأخبار الروتينية أو التحليلات
            if any(x in text for x in [
                "market update",
                "stocks:",
                "forex",
                "fx",
                "currencies",
                "commodity",
                "commodities",
                "rupee",
                "rand",
                "peso",
                "baht",
                "lira",
                "ryanair",
                "airbus",
                "analyst",
                "expects",
                "expected",
                "forecast",
                "opinion",
                "commentary",
                "preview"
            ]):
                continue

            analysis = analyze_news(headline)

            if not analysis:
                continue

            if analysis.strip().upper() == "SKIP":
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
