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
        input=f"""أنت محرر أخبار متخصص في السوق الأمريكي.

هدفك ليس تلخيص جميع الأخبار، بل اختيار الأخبار التي تستحق إرسال إشعار فوري لمتداول في السوق الأمريكي.

إذا كان الخبر لا يستحق إشعارًا فوريًا فأرجع فقط:

SKIP

اعتبر الأخبار التالية غير مهمة وأرجع SKIP:

- تحديثات أسعار النفط أو الذهب أو الدولار أو السندات بدون سبب جديد.
- التعليق على حركة السوق اليومية.
- تغيرات بسيطة في أسعار السلع أو العملات.
- أخبار شركات أجنبية لا تؤثر على السوق الأمريكي.
- أخبار مكررة أو منخفضة الأهمية.
- أخبار محلية أو سياسية لا تؤثر على الأسواق.
- أي خبر لا يغير قرارات المستثمر.

أما إذا كان الخبر يتعلق بأحد الأمور التالية فقم بنشره:

- الفيدرالي.
- أسعار الفائدة.
- FOMC.
- Powell.
- CPI.
- PPI.
- PCE.
- GDP.
- NFP.
- البطالة.
- الرسوم الجمركية.
- العقوبات.
- الحروب والتوترات الجيوسياسية المؤثرة.
- قرارات أوبك أو تغيرات الإنتاج.
- نتائج الشركات الأمريكية.
- الاندماجات والاستحواذات.
- تقسيم الأسهم.
- إعلانات الشركات الكبرى.
- الأخبار التي قد تحرك السوق بشكل واضح.

إذا كان الخبر عن النفط أو الذهب أو الدولار أو السندات:

لا تنشره إلا إذا كان سبب الحركة خبرًا جديدًا ومؤثرًا مثل:

- قرار أوبك.
- عقوبات.
- حرب.
- هجوم.
- اضطراب بالإمدادات.
- قرار حكومي.

أما مجرد ارتفاع أو انخفاض الأسعار فلا تنشره.

إذا قررت نشر الخبر:

- اكتب بالعربية فقط.
- اجعل الرسالة قصيرة.
- اكتب عنوانًا واضحًا.
- إذا كان التأثير واضحًا أضف سطرًا واحدًا فقط:

📊 التأثير: ...

إذا كان الخبر عن شركة:

اكتب عنوان الخبر فقط بدون أي تحليل.

إذا ترددت في أهمية الخبر فأرجع:

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

            # تجاهل الأخبار الروتينية قبل إرسالها إلى GPT
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
                "airbus"
            ]):
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
