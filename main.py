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

client = OpenAI(api_key=OPENAI_API_KEY)

sent = load()


# ==========================================
# الأخبار التي نريد وصولها إلى GPT
# ==========================================

KEYWORDS = [
    # الاقتصاد الأمريكي
    "fed",
    "federal reserve",
    "fomc",
    "powell",
    "interest rate",
    "rate cut",
    "rate hike",
    "inflation",
    "cpi",
    "ppi",
    "pce",
    "gdp",
    "nfp",
    "payroll",
    "jobs",
    "unemployment",

    # سياسات اقتصادية
    "tariff",
    "tariffs",
    "sanction",
    "sanctions",

    # أحداث نفطية كبيرة فقط
    "opec",
    "opec+",
    "hormuz",

    # السوق الأمريكي
    "nasdaq",
    "nyse",
    "cboe",
    "occ",

    # الشركات
    "earnings",
    "revenue",
    "guidance",
    "dividend",
    "split",
    "merger",
    "acquisition",
    "takeover",

    # التقنية والذكاء الاصطناعي
    "artificial intelligence",
    "openai",
    "nvidia",
    "microsoft",
    "apple",
    "amazon",
    "meta",
    "tesla",
    "amd",
    "broadcom",
    "google",
    "alphabet",
    "netflix"
]


# ==========================================
# أخبار نرفضها قبل إرسالها إلى GPT
# ==========================================

BLOCKED_PHRASES = [
    "market update",
    "morning news",
    "morning bid",
    "stocks:",
    "forex",
    "currencies",
    "commodity",
    "commodities",

    # توقعات وآراء
    "analyst says",
    "analysts say",
    "analyst expects",
    "forecast",
    "opinion",
    "commentary",
    "preview",

    # عملات أجنبية
    "rupee",
    "rand",
    "peso",
    "baht",
    "lira"
]


# ==========================================
# إرسال الرسالة إلى تيليجرام
# ==========================================

def send(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    response = requests.post(
        url,
        data={
            "chat_id": CHAT_ID,
            "text": msg,
            "disable_web_page_preview": True
        },
        timeout=15
    )

    response.raise_for_status()


# ==========================================
# تحليل الخبر
# ==========================================

def analyze_news(headline):
    cached = get(headline)

    if cached:
        return cached

    response = client.responses.create(
        model="gpt-5-nano",

        input=f"""أنت محرر أخبار لقناة متخصصة فقط في السوق الأمريكي.

مهمتك شديدة الصرامة.

أمامك عنوان خبر واحد.

يجب عليك اتخاذ أحد قرارين فقط:

1- SKIP
2- كتابة الخبر بالعربية جاهزًا للنشر.


========================
أولاً: متى تكتب SKIP؟
========================

اكتب SKIP لأي خبر لا يهم متداول الأسهم الأمريكية بشكل مباشر وواضح.

اكتب SKIP للأخبار التالية:

- الأخبار السياسية العامة.
- التصريحات السياسية العادية.
- التهديدات السياسية المتكررة.
- أخبار الحروب اليومية.
- القصف والهجمات المحدودة.
- أخبار السفن والناقلات.
- أخبار البحر الأحمر اليومية.
- أخبار الحوثيين اليومية.
- أخبار إيران وإسرائيل اليومية إذا لم يحدث تطور استثنائي كبير.
- أخبار سوريا واليمن وغزة المحلية.
- الأخبار المحلية لدول أجنبية.
- مجرد ارتفاع أو انخفاض النفط.
- مجرد ارتفاع أو انخفاض الذهب.
- مجرد ارتفاع أو انخفاض الدولار.
- مجرد ارتفاع أو انخفاض السندات.
- تحركات الأسواق اليومية.
- توقعات المحللين.
- الآراء.
- المقالات التحليلية.
- الأخبار المكررة أو التي لا تضيف تطورًا جوهريًا.
- أي خبر تأثيره على السوق الأمريكي غير مباشر أو ضعيف.

لا تفترض أن الخبر مهم فقط لأنه يتعلق بالنفط أو الحرب.

إذا احتجت إلى شرح طويل لإثبات أن الخبر يؤثر على السوق الأمريكي:
اكتب SKIP.


========================
ثانياً: الأخبار المطلوبة
========================

انشر الأخبار المهمة مباشرة عن:

- الاحتياطي الفيدرالي.
- FOMC.
- تصريحات Powell المهمة المتعلقة بالسياسة النقدية.
- قرارات أسعار الفائدة الأمريكية.
- CPI الأمريكي.
- PPI الأمريكي.
- PCE الأمريكي.
- GDP الأمريكي.
- NFP.
- البطالة الأمريكية.
- بيانات وظائف أمريكية مهمة.
- الرسوم الجمركية الأمريكية المهمة.
- العقوبات الاقتصادية الأمريكية المهمة.
- نتائج الشركات الأمريكية المهمة.
- رفع أو خفض التوجيهات المستقبلية للشركات.
- الاندماجات والاستحواذات المهمة.
- تقسيم الأسهم.
- إعلانات الشركات الأمريكية الكبرى.
- القرارات التنظيمية الكبيرة التي تؤثر على الشركات أو السوق الأمريكي.
- قرارات أوبك الجوهرية المتعلقة بالإنتاج.

الأحداث الجيوسياسية لا تنشرها إلا إذا كانت استثنائية وقد تؤثر مباشرة وبشكل كبير على الأسواق، مثل:

- إغلاق مضيق هرمز.
- تعطيل واسع ومؤكد لإمدادات النفط العالمية.
- إعلان حرب رسمي كبير.
- دخول الولايات المتحدة رسميًا في حرب.
- وقف إطلاق نار كبير يغير وضع الأسواق بشكل واضح.

أما التطورات الصغيرة والمتكررة:
SKIP.


========================
ثالثاً: صيغة الخبر
========================

إذا قررت نشر الخبر:

- اكتب بالعربية.
- لا تكتب YES.
- لا تكتب NO.
- لا تكتب كلمة "الملخص".
- لا تكتب كلمة "التحليل".
- لا تذكر المصدر، لأن البرنامج سيضيفه.
- اجعل الخبر مختصرًا وواضحًا.

إذا كان الخبر عن شركة:
اكتب الخبر فقط، بدون توقع تأثير من عندك.

إذا كان خبرًا اقتصاديًا وكان تأثيره واضحًا جدًا:
يمكن إضافة سطر واحد فقط:

📊 التأثير: ...

لا تخترع تأثيرًا إذا لم يكن واضحًا.

إذا كنت مترددًا هل الخبر يستحق إشعارًا أم لا:
SKIP.


العنوان الأصلي:

{headline}
"""
    )

    result = response.output_text.strip()

    cache_set(headline, result)

    return result


# ==========================================
# تشغيل البوت
# ==========================================

while True:

    try:

        url = (
            "https://finnhub.io/api/v1/news"
            f"?category=general&token={FINNHUB_API_KEY}"
        )

        response = requests.get(url, timeout=15)
        response.raise_for_status()

        news = response.json()

        for item in news:

            item_id = item.get("id")

            if item_id in sent:
                continue

            headline = item.get("headline", "").strip()

            if not headline:
                continue

            text = headline.lower()


            # ==================================
            # فلتر أولي
            # ==================================

            if not any(word in text for word in KEYWORDS):
                continue


            # ==================================
            # منع الأخبار الروتينية
            # ==================================

            if any(word in text for word in BLOCKED_PHRASES):
                continue


            # ==================================
            # تحليل GPT
            # ==================================

            analysis = analyze_news(headline)

            if not analysis:
                continue

            if analysis.strip().upper() == "SKIP":
                continue


            # حماية إضافية من YES / NO
            if analysis.strip().upper() in ["YES", "NO"]:
                continue


            # ==================================
            # تسجيل الخبر
            # ==================================

            sent.add(item_id)
            save(sent)


            # ==================================
            # الرسالة النهائية
            # ==================================

            message = f"""{analysis}

📰 المصدر: {item.get('source', 'غير معروف')}

━━━━━━━━━━━━━━
📊 Chart News US | أخبار السوق الامريكي
https://t.me/ChartMaster_News
"""

            send(message)

        time.sleep(60)


    except Exception:
        import traceback
        traceback.print_exc()
        time.sleep(60)
