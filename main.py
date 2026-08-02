import os
import time
import re
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

    # الدولار والذهب والسندات
    "dollar",
    "gold",
    "treasury",
    "treasuries",
    "bond",
    "bonds",
    "yield",
    "yields",

    # سياسات اقتصادية
    "tariff",
    "tariffs",
    "sanction",
    "sanctions",

    # الطاقة والأحداث الكبيرة
    "opec",
    "opec+",
    "hormuz",
    "oil",
    "lng",

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

    # آراء وتحليلات
    "analyst says",
    "analysts say",
    "analyst expects",
    "opinion",
    "commentary",
    "preview",

    # آراء إعلامية لا نحتاج إشعارًا لها
    "jim cramer",
    "cramer says",
    "cramer's",

    # عملات أجنبية
    "rupee",
    "rand",
    "peso",
    "baht",
    "lira"
]


# ==========================================
# ذاكرة مؤقتة لمنع تكرار نفس الحدث
# ==========================================

recent_topics = []

TOPIC_MEMORY_SECONDS = 6 * 60 * 60
MAX_RECENT_TOPICS = 300


def normalize_headline(text):
    text = text.lower()

    # إزالة الروابط
    text = re.sub(r"https?://\S+", " ", text)

    # إزالة علامات الترقيم
    text = re.sub(r"[^a-z0-9\s]", " ", text)

    # كلمات شائعة لا تساعد في تحديد موضوع الخبر
    stop_words = {
        "the", "a", "an", "and", "or", "of", "to", "in",
        "on", "for", "with", "as", "at", "by", "from",
        "after", "amid", "says", "say", "said", "new",
        "update", "report", "reports"
    }

    words = [
        word for word in text.split()
        if word not in stop_words and len(word) > 2
    ]

    return set(words)


def is_duplicate_topic(headline):
    global recent_topics

    now = time.time()

    # حذف المواضيع القديمة
    recent_topics = [
        item for item in recent_topics
        if now - item["time"] < TOPIC_MEMORY_SECONDS
    ]

    current_words = normalize_headline(headline)

    if len(current_words) < 3:
        return False

    for item in recent_topics:
        old_words = item["words"]

        if not old_words:
            continue

        common = current_words & old_words

        similarity = len(common) / min(
            len(current_words),
            len(old_words)
        )

        # إذا كان التشابه مرتفعًا نعتبره نفس الحدث
        if similarity >= 0.65:
            return True

    return False


def remember_topic(headline):
    global recent_topics

    recent_topics.append({
        "time": time.time(),
        "words": normalize_headline(headline)
    })

    if len(recent_topics) > MAX_RECENT_TOPICS:
        recent_topics = recent_topics[-MAX_RECENT_TOPICS:]

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

        input=f"""أنت محرر أخبار لقناة متخصصة في السوق الأمريكي.

أمامك عنوان خبر واحد.

مهمتك اختيار الأخبار المفيدة لمتداول ومستثمر في السوق الأمريكي، مع تجنب الأخبار الضعيفة والمتكررة.

اتخذ أحد قرارين فقط:

1- SKIP
2- كتابة الخبر بالعربية جاهزًا للنشر.


========================
أولاً: متى تكتب SKIP؟
========================

اكتب SKIP للأخبار التالية:

- الأخبار السياسية العامة التي لا تؤثر على الأسواق.
- التصريحات السياسية العادية.
- التهديدات السياسية المتكررة.
- أخبار الحروب اليومية الصغيرة.
- القصف والهجمات المحدودة.
- أخبار السفن والناقلات الفردية التي لا تؤثر على الإمدادات العالمية.
- أخبار البحر الأحمر اليومية الصغيرة.
- أخبار الحوثيين اليومية الصغيرة.
- أخبار إيران وإسرائيل اليومية إذا لم يوجد تطور اقتصادي أو سوقي مهم.
- أخبار سوريا واليمن وغزة المحلية.
- الأخبار المحلية لدول أجنبية التي لا تؤثر على السوق الأمريكي.
- تحركات الأسواق اليومية التي لا يوجد خلفها سبب مهم.
- الآراء الشخصية للمحللين أو المعلقين التلفزيونيين.
- توصيات الشراء والبيع ورفع وخفض السعر المستهدف.
- المقالات التحليلية العامة.
- الأخبار المكررة التي لا تضيف معلومة جوهرية جديدة.
- أي خبر تأثيره على السوق الأمريكي ضعيف جدًا.

لا تجعل مجرد ذكر شركة كبيرة سببًا كافيًا للنشر.

إذا كان الخبر مجرد رأي عن Apple أو Microsoft أو Nvidia أو Amazon
أو أي شركة أخرى بدون إعلان أو معلومة جديدة من الشركة:
SKIP.


========================
ثانياً: أخبار الاقتصاد والأسواق
========================

انشر الأخبار المهمة المتعلقة بـ:

- الاحتياطي الفيدرالي.
- FOMC.
- تصريحات Powell المهمة.
- أسعار الفائدة الأمريكية.
- CPI.
- PPI.
- PCE.
- GDP.
- NFP.
- البطالة.
- بيانات الوظائف الأمريكية المهمة.
- التضخم الأمريكي.
- الرسوم الجمركية الأمريكية المهمة.
- العقوبات الاقتصادية الأمريكية المهمة.

أخبار الدولار والذهب والسندات مهمة إذا كانت الحركة ملحوظة
ومرتبطة بسبب اقتصادي مهم، مثل:

- تغير توقعات الفائدة.
- قرار أو تصريح من الفيدرالي.
- بيانات تضخم أو وظائف مهمة.
- تغير واضح في توقعات السياسة النقدية.
- حدث اقتصادي أو جيوسياسي كبير.

مثال:

الدولار يسجل أسوأ أسبوع منذ عدة أشهر بسبب تغير توقعات الفيدرالي:
انشره.

الذهب يتحرك بشكل واضح بسبب توقعات خفض الفائدة:
انشره.

أما حركة صغيرة وروتينية بدون سبب مهم:
SKIP.


========================
ثالثاً: أخبار الشركات
========================

انشر أخبار الشركات الأمريكية إذا تضمنت معلومة مهمة فعلية مثل:

- نتائج الأرباح.
- الإيرادات المهمة.
- تجاوز أو إخفاق واضح في التوقعات.
- رفع التوجيهات المستقبلية.
- خفض التوجيهات المستقبلية.
- نمو قوي أو تراجع كبير في نشاط رئيسي للشركة.
- إعلان استثمار أو إنفاق رأسمالي ضخم.
- صفقة كبيرة.
- اندماج.
- استحواذ.
- تقسيم سهم.
- منتج أو خدمة رئيسية جديدة.
- قرار تنظيمي مهم.
- مشكلة تشغيلية كبيرة قد تؤثر على أعمال الشركة.
- إعلان جوهري من إدارة الشركة.

لا تنشر الخبر لمجرد وجود اسم شركة كبيرة فيه.

إذا كان الخبر مجرد رأي Jim Cramer أو محلل أو مستثمر:
SKIP.


========================
رابعاً: الطاقة والجيوسياسة
========================

انشر الأحداث المهمة التي قد تؤثر فعليًا على النفط أو الطاقة
أو السوق الأمريكي، مثل:

- قرار جوهري من أوبك بشأن الإنتاج.
- إغلاق مضيق هرمز.
- تعطيل واسع لإمدادات النفط أو الغاز.
- عقوبات اقتصادية كبيرة تؤثر على صادرات النفط أو الطاقة.
- حدث يسبب تغيرًا مهمًا في تدفقات الطاقة العالمية.
- إعلان حرب رسمي كبير.
- دخول الولايات المتحدة رسميًا في حرب.
- وقف إطلاق نار كبير يغير توقعات الأسواق.

يمكن نشر خبر مهم عن LNG أو النفط إذا كان يكشف
تغيرًا كبيرًا في الإمدادات أو الطلب أو طرق الشحن.

أما الحوادث الصغيرة والمتكررة:
SKIP.


========================
خامساً: صيغة الخبر
========================

إذا قررت نشر الخبر:

- اكتب بالعربية فقط.
- لا تكتب YES.
- لا تكتب NO.
- لا تكتب SKIP إلا إذا قررت رفض الخبر.
- لا تكتب كلمة "الملخص".
- لا تكتب كلمة "التحليل".
- لا تذكر المصدر، لأن البرنامج سيضيفه.
- اجعل الخبر مختصرًا وواضحًا.
- لا تضف معلومات غير موجودة في العنوان.

إذا كان الخبر عن شركة:
اكتب الخبر فقط بدون توقع تأثير من عندك.

إذا كان خبرًا اقتصاديًا وكان تأثيره واضحًا جدًا:
يمكن إضافة سطر واحد فقط:

📊 التأثير: ...

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
            # فلتر أولي للكلمات المهمة
            # ==================================

            if not any(word in text for word in KEYWORDS):
                continue


            # ==================================
            # منع الأخبار الروتينية والآراء
            # ==================================

            if any(word in text for word in BLOCKED_PHRASES):
                continue


            # ==================================
            # تحليل الخبر بواسطة GPT
            # ==================================

            analysis = analyze_news(headline)

            if not analysis:
                continue

            if analysis.strip().upper() == "SKIP":
                continue

            # حماية من ظهور YES / NO في القناة
            if analysis.strip().upper() in ["YES", "NO"]:
                continue


            # ==================================
            # منع تكرار نفس الحدث
            # يتم الفحص بعد قبول GPT للخبر
            # وقبل إرساله إلى القناة
            # ==================================

            if is_duplicate_topic(headline):
                print("DUPLICATE SKIPPED:", headline)
                continue


            # ==================================
            # إرسال الخبر
            # ==================================

            message = f"""-


{analysis}

📰 المصدر: {item.get('source', 'غير معروف')}

━━━━━━━━━━━━━━
📊 Chart News US | أخبار السوق الامريكي
https://t.me/ChartMaster_News
"""

            send(message)


            # ==================================
            # لا نسجل الخبر إلا بعد نجاح الإرسال
            # ==================================

            sent.add(item_id)
            save(sent)

            remember_topic(headline)
                    # ننتظر دقيقة قبل فحص الأخبار من جديد
        time.sleep(60)


    except Exception:
        import traceback
        traceback.print_exc()

        # في حال حدوث خطأ ننتظر دقيقة ثم نحاول من جديد
        time.sleep(60)
