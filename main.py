import os
import time
import re
import hashlib
import datetime
import requests
from cache import get, set as cache_set
from sent import load, save
from openai import OpenAI

# ==========================================
# المفاتيح والمتغيرات
# ==========================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
FRED_API_KEY = os.getenv("FRED_API_KEY")

print("OPENAI =", OPENAI_API_KEY[:12] if OPENAI_API_KEY else "None")
print("FINNHUB =", FINNHUB_API_KEY[:8] if FINNHUB_API_KEY else "None")
print("FRED =", FRED_API_KEY[:8] if FRED_API_KEY else "None")

client = OpenAI(api_key=OPENAI_API_KEY)

sent = load()


# ==========================================
# الأخبار التي نريد وصولها إلى GPT
# ==========================================

KEYWORDS = [
    "fed", "federal reserve", "fomc", "powell",
    "interest rate", "rate cut", "rate hike",
    "inflation", "cpi", "ppi", "pce", "gdp", "nfp",
    "payroll", "jobs report", "unemployment rate",

    "dollar", "gold", "treasury", "treasuries",
    "bond", "bonds", "yield", "yields",

    "tariff", "tariffs", "sanction", "sanctions",

    "opec", "opec+", "strait of hormuz", "crude oil",
    "oil price", "oil prices", "lng",

    "nasdaq", "nyse", "cboe", "s&p 500", "dow jones",

    "earnings", "quarterly revenue", "guidance",
    "dividend", "stock split", "merger", "acquisition",
    "takeover", "ipo",

    "artificial intelligence", "openai", "nvidia",
    "microsoft", "apple", "amazon", "meta platforms",
    "tesla", "amd", "broadcom", "alphabet", "netflix"
]


# ==========================================
# أخبار نرفضها قبل إرسالها إلى GPT
# ==========================================

BLOCKED_PHRASES = [
    # روتين إعلامي
    "market update", "morning news", "morning bid",
    "stocks:", "forex", "currencies",
    "commodity", "commodities",

    # آراء وتحليلات
    "analyst says", "analysts say", "analyst expects",
    "opinion", "commentary", "preview",
    "jim cramer", "cramer says", "cramer's",

    # عملات أجنبية غير مهمة
    "rupee", "rand", "peso", "baht", "lira",

    # سياسة وحروب ومصطلحات عسكرية
    "election", "elections", "president of", "prime minister",
    "parliament", "congress hearing", "senate vote",
    "military", "missile", "missiles", "airstrike",
    "air strike", "troops", "soldiers", "ceasefire",
    "gaza", "hamas", "houthi", "houthis", "yemen",
    "syria", "hezbollah", "west bank", "protest",
    "protests", "riot", "coup", "assassination",
    "royal family", "king of",
    "diplomat", "embassy", "united nations",
    "human rights", "refugee", "refugees",
    "immigration policy", "border wall",
    "climate summit", "extreme weather", "wildfire",
    "earthquake", "hurricane", "flood", "flooding"
]


# ==========================================
# مطابقة الكلمات المفتاحية بدقة (Whole Word)
# ==========================================

def build_pattern(words):
    escaped = [re.escape(w) for w in words]
    pattern = r"(?:{})".format("|".join(escaped))
    return re.compile(pattern, flags=re.IGNORECASE)


KEYWORDS_PATTERN = build_pattern(KEYWORDS)
BLOCKED_PATTERN = build_pattern(BLOCKED_PHRASES)


# ==========================================
# ذاكرة مؤقتة لمنع تكرار نفس الحدث
# ==========================================

recent_topics = []

TOPIC_MEMORY_SECONDS = 6 * 60 * 60
MAX_RECENT_TOPICS = 300


def normalize_headline(text):
    text = text.lower()
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)

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
        similarity = len(common) / min(len(current_words), len(old_words))

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
# تحليل الخبر عبر GPT
# ==========================================

def analyze_news(headline):
    cached = get(headline)
    if cached:
        return cached

    try:
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

- أي خبر سياسي أو عسكري أو حربي، بأي شكل، إلا إذا كان له تأثير اقتصادي مباشر وواضح على السوق الأمريكي (مثل إغلاق مضيق هرمز أو عقوبات نفطية كبيرة).
- عقوبات فردية على شركات صغيرة، شبكات دعم، أفراد، أو كيانات محدودة (مثل عقوبات على شركة طيران أو شخص أو شبكة تهريب): SKIP، لأنها لا تؤثر على السوق الأمريكي.
- انشر العقوبات فقط إذا كانت واسعة النطاق وتؤثر على قطاع كامل، مثل: عقوبات نفطية شاملة على دولة، عقوبات تجارية كبيرة، أو عقوبات تشمل بنوك مركزية أو صادرات رئيسية.
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
- أي خبر تأثيره على السوق الأمريكي ضعيف جدًا أو غير مباشر.

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
- CPI. PPI. PCE. GDP. NFP.
- البطالة.
- بيانات الوظائف الأمريكية المهمة.
- التضخم الأمريكي.
- الرسوم الجمركية الأمريكية المهمة.
- العقوبات الاقتصادية الأمريكية الكبيرة (وليس الفردية).

أخبار الدولار والذهب والسندات مهمة فقط إذا كانت الحركة ملحوظة
ومرتبطة بسبب اقتصادي مهم (وليس حدث سياسي أو حرب).


========================
ثالثاً: أخبار الشركات
========================

انشر أخبار الشركات الأمريكية إذا
