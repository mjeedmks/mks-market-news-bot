import os
import time
import requests
from cache import get, set as cache_set
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
    cached = get(headline)

    if cached:
        return cached

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

اكتب الملخص مباشرة باللغة العربية.
لا تكتب كلمة "ترجمة" أو "ملخص" داخل المحتوى.
ابدأ بالخبر مباشرة.

🏷️ التصنيف:
اختر تصنيفاً واحداً فقط.

⭐ الأهمية:
اختر درجة واحدة فقط حسب أهمية الخبر وتأثيره المتوقع على الأسواق الأمريكية.

اكتب النتيجة بهذا الشكل فقط:

🟢 1/3 = منخفضة
🟡 2/3 = متوسطة
🔴 3/3 = عالية

لا تشرح سبب التقييم.
اكتب الدرجة فقط.

📊 التأثير:

إذا كان التأثير إيجابياً فاكتب:
🟢 إيجابي

إذا كان التأثير سلبياً فاكتب:
🔴 سلبي

إذا كان التأثير محدوداً فاكتب:
🟡 محدود

إذا كان التأثير محايداً فاكتب:
⚪ محايد

📝 السبب:
اشرح باختصار سبب التأثير في سطر واحد.
لا تتجاوز 20 كلمة.
اعتمد فقط على المعلومات الموجودة في الخبر، ولا تضف استنتاجات أو معلومات غير مذكورة.

🏢 الشركة:🏢 الشركة:
اذكر اسم الشركة المختصر ورمزها فقط.
مثال:
American Airlines (AAL)

ولا تكتب Inc أو Corp أو Group أو Holdings إلا إذا كانت جزءًا من الاسم الرسمي المتداول.
إذا لم يذكر الخبر شركة أمريكية مدرجة بشكل صريح فلا تخمن ولا تستنتج أي شركة، ولا تكتب سطر الشركة إطلاقًا.

🏭 القطاع:
إذا كان الخبر يتعلق بقطاع معين فاذكر اسم القطاع فقط.
مثال:
الطيران
الطاقة
التقنية
اذكر القطاع الرسمي فقط.
إذا لم يتعلق الخبر بقطاع معين فلا تكتب سطر القطاع إطلاقًا.
📈 المؤشر:
اذكر S&P500 أو Nasdaq فقط إذا كان هناك تأثير مباشر.
إذا لم يوجد تأثير فلا تذكر هذا السطر إطلاقًا.
ولا تذكر أن الشركة ضمن مكونات المؤشر.

📈 احتمالية الصعود:

اذكر حتى 3 أسهم أمريكية فقط قد ترتفع بسبب الخبر إذا كان هناك ارتباط مباشر وواضح.

اكتب رمز السهم (Ticker) فقط.

إذا لم توجد أسهم واضحة فلا تكتب هذا القسم إطلاقًا.

📉 احتمالية الهبوط:

اذكر حتى 3 أسهم أمريكية فقط قد تنخفض بسبب الخبر إذا كان هناك ارتباط مباشر وواضح.

اكتب رمز السهم (Ticker) فقط.

إذا لم توجد أسهم واضحة فلا تكتب هذا القسم إطلاقًا.

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
        import traceback
        traceback.print_exc()
        time.sleep(60)
