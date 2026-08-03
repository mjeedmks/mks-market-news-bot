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

    prompt_lines = [
        "أنت محرر أخبار لقناة متخصصة في السوق الأمريكي.",
        "",
        "أمامك عنوان خبر واحد.",
        "",
        "مهمتك اختيار الأخبار المفيدة لمتداول ومستثمر في السوق الأمريكي، مع تجنب الأخبار الضعيفة والمتكررة.",
        "",
        "اتخذ أحد قرارين فقط:",
        "",
        "1- SKIP",
        "2- كتابة الخبر بالعربية جاهزًا للنشر.",
        "",
        "",
        "========================",
        "أولاً: متى تكتب SKIP؟",
        "========================",
        "",
        "اكتب SKIP للأخبار التالية:",
        "",
        "- أي خبر سياسي أو عسكري أو حربي، بأي شكل، إلا إذا كان له تأثير اقتصادي مباشر وواضح على السوق الأمريكي (مثل إغلاق مضيق هرمز أو عقوبات نفطية كبيرة).",
        "- عقوبات فردية على شركات صغيرة، شبكات دعم، أفراد، أو كيانات محدودة (مثل عقوبات على شركة طيران أو شخص أو شبكة تهريب): SKIP، لأنها لا تؤثر على السوق الأمريكي.",
        "- انشر العقوبات فقط إذا كانت واسعة النطاق وتؤثر على قطاع كامل، مثل: عقوبات نفطية شاملة على دولة، عقوبات تجارية كبيرة، أو عقوبات تشمل بنوك مركزية أو صادرات رئيسية.",
        "- التصريحات السياسية العادية.",
        "- التهديدات السياسية المتكررة.",
        "- أخبار الحروب اليومية الصغيرة.",
        "- القصف والهجمات المحدودة.",
        "- أخبار السفن والناقلات الفردية التي لا تؤثر على الإمدادات العالمية.",
        "- أخبار البحر الأحمر اليومية الصغيرة.",
        "- أخبار الحوثيين اليومية الصغيرة.",
        "- أخبار إيران وإسرائيل اليومية إذا لم يوجد تطور اقتصادي أو سوقي مهم.",
        "- أخبار سوريا واليمن وغزة المحلية.",
        "- الأخبار المحلية لدول أجنبية التي لا تؤثر على السوق الأمريكي.",
        "- تحركات الأسواق اليومية التي لا يوجد خلفها سبب مهم.",
        "- الآراء الشخصية للمحللين أو المعلقين التلفزيونيين.",
        "- توصيات الشراء والبيع ورفع وخفض السعر المستهدف.",
        "- المقالات التحليلية العامة.",
        "- الأخبار المكررة التي لا تضيف معلومة جوهرية جديدة.",
        "- أي خبر تأثيره على السوق الأمريكي ضعيف جدًا أو غير مباشر.",
        "",
        "لا تجعل مجرد ذكر شركة كبيرة سببًا كافيًا للنشر.",
        "",
        "إذا كان الخبر مجرد رأي عن Apple أو Microsoft أو Nvidia أو Amazon",
        "أو أي شركة أخرى بدون إعلان أو معلومة جديدة من الشركة:",
        "SKIP.",
        "",
        "",
        "========================",
        "ثانياً: أخبار الاقتصاد والأسواق",
        "========================",
        "",
        "انشر الأخبار المهمة المتعلقة بـ:",
        "",
        "- الاحتياطي الفيدرالي.",
        "- FOMC.",
        "- تصريحات Powell المهمة.",
        "- أسعار الفائدة الأمريكية.",
        "- CPI. PPI. PCE. GDP. NFP.",
        "- البطالة.",
        "- بيانات الوظائف الأمريكية المهمة.",
        "- التضخم الأمريكي.",
        "- الرسوم الجمركية الأمريكية المهمة.",
        "- العقوبات الاقتصادية الأمريكية الكبيرة (وليس الفردية).",
        "",
        "أخبار الدولار والذهب والسندات مهمة فقط إذا كانت الحركة ملحوظة",
        "ومرتبطة بسبب اقتصادي مهم (وليس حدث سياسي أو حرب).",
        "",
        "",
        "========================",
        "ثالثاً: أخبار الشركات",
        "========================",
        "",
        "انشر أخبار الشركات الأمريكية إذا تضمنت معلومة مهمة فعلية مثل:",
        "نتائج أرباح، إيرادات، تجاوز/إخفاق التوقعات، رفع/خفض التوجيهات،",
        "صفقة كبيرة، اندماج، استحواذ، تقسيم سهم، منتج جديد رئيسي،",
        "قرار تنظيمي مهم، مشكلة تشغيلية كبيرة.",
        "",
        "لا تنشر لمجرد وجود اسم شركة كبيرة. SKIP لآراء Jim Cramer أو أي محلل.",
        "",
        "",
        "========================",
        "رابعاً: الطاقة (فقط الأحداث الجوهرية جدًا)",
        "========================",
        "",
        "انشر فقط: قرار جوهري من أوبك، إغلاق مضيق هرمز، تعطيل واسع للإمدادات،",
        "عقوبات كبيرة تؤثر على صادرات الطاقة، حدث يغيّر تدفقات الطاقة العالمية بشكل جوهري.",
        "",
        'أي حدث حربي أو سياسي آخر مهما بدا "مرتبطًا بالنفط": SKIP، إلا إذا تحقق أعلاه بوضوح.',
        "",
        "",
        "========================",
        "خامساً: صيغة الخبر",
        "========================",
        "",
        "- اكتب بالعربية فقط.",
        "- لا تكتب YES/NO.",
        "- لا تذكر المصدر.",
        "- اجعل الخبر مختصرًا وواضحًا.",
        "- لا تضف معلومات غير موجودة في العنوان.",
        "- لا تضف أي تحليل أو تعليق أو استنتاج من عندك، فقط الخبر كما هو.",
        "",
        "إذا كنت مترددًا: SKIP.",
        "",
        "العنوان الأصلي:",
        "",
        headline,
    ]

    prompt = "\n".join(prompt_lines)

    try:
        response = client.responses.create(
            model="gpt-5-nano",
            input=prompt
        )
        result = response.output_text.strip()
    except Exception as e:
        print("GPT ERROR:", e)
        return None

    cache_set(headline, result)
    return result


# ==========================================
# مساعد: توليد ID بديل لو الخبر بلا id
# ==========================================

def get_safe_id(item, headline):
    item_id = item.get("id")
    if item_id:
        return item_id
    return hashlib.md5(headline.encode("utf-8")).hexdigest()


# ==========================================
# التقويم الاقتصادي الأسبوعي (FRED API)
# ==========================================

FOMC_MEETINGS_2025 = [
    "2025-01-29",
    "2025-03-19",
    "2025-05-07",
    "2025-06-18",
    "2025-07-30",
    "2025-09-17",
    "2025-10-29",
    "2025-12-10",
]

US_MARKET_HOLIDAYS_2025 = {
    "2025-01-01": "رأس السنة الميلادية",
    "2025-01-20": "يوم مارتن لوثر كينغ",
    "2025-02-17": "عيد الرؤساء (واشنطن)",
    "2025-04-18": "الجمعة العظيمة",
    "2025-05-26": "يوم الذكرى (Memorial Day)",
    "2025-06-19": "يوم الحرية (Juneteenth)",
    "2025-07-04": "عيد الاستقلال",
    "2025-09-01": "عيد العمال (Labor Day)",
    "2025-11-27": "عيد الشكر",
    "2025-12-25": "عيد الميلاد",
}

ARABIC_DAYS = {
    "Monday": "الإثنين",
    "Tuesday": "الثلاثاء",
    "Wednesday": "الأربعاء",
    "Thursday": "الخميس",
    "Friday": "الجمعة",
    "Saturday": "السبت",
    "Sunday": "الأحد",
}

TARGET_RELEASES_NAMES = {
    "Employment Situation": "تقرير الوظائف الأمريكي (NFP)",
    "Consumer Price Index": "مؤشر التضخم (CPI)",
    "Producer Price Index": "مؤشر أسعار المنتجين (PPI)",
    "Gross Domestic Product": "الناتج المحلي الإجمالي (GDP)",
    "Personal Income and Outlays": "مؤشر PCE (المفضل للفيدرالي)",
}

RELEASE_ID_CACHE = {}


def find_release_id(name):
    url = "https://api.stlouisfed.org/fred/releases"
    params = {
        "api_key": FRED_API_KEY,
        "file_type": "json"
    }

    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()

    for release in data.get("releases", []):
        if name.lower() == release.get("name", "").lower():
            return release["id"]

    return None


def resolve_release_ids():
    for eng_name in TARGET_RELEASES_NAMES:
        if eng_name in RELEASE_ID_CACHE:
            continue

        try:
            release_id = find_release_id(eng_name)
        except Exception as e:
            print(f"FRED resolve error for {eng_name}:", e)
            continue

        if release_id:
            RELEASE_ID_CACHE[eng_name] = release_id
            print(f"✅ تم ربط: {eng_name} -> ID {release_id}")
        else:
            print(f"⚠️ لم يتم العثور على Release ID لـ: {eng_name}")


def get_release_dates(release_id, start_date, end_date):
    url = "https://api.stlouisfed.org/fred/release/dates"
    params = {
        "release_id": release_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "include_release_dates_with_no_data": "true",
        "realtime_start": start_date,
        "realtime_end": end_date
    }

    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()

    return [d["date"] for d in data.get("release_dates", [])]


def get_weekly_economic_calendar_fred(week_start, week_end):
    results = []

    if not RELEASE_ID_CACHE:
        resolve_release_ids()

    start_str = week_start.strftime("%Y-%m-%d")
    end_str = week_end.strftime("%Y-%m-%d")

    for eng_name, release_id in RELEASE_ID_CACHE.items():
        try:
            dates = get_release_dates(release_id, start_str, end_str)
            for date_str in dates:
                results.append({
                    "date": date_str,
                    "event": TARGET_RELEASES_NAMES[eng_name]
                })
        except Exception as e:
            print(f"FRED error for {eng_name}:", e)

    for date_str in FOMC_MEETINGS_2025:
        if start_str <= date_str <= end_str:
            results.append({
                "date": date_str,
                "event": "قرار الفيدرالي بشأن الفائدة (FOMC)"
            })

    results.sort(key=lambda x: x["date"])
    return results


def get_holidays_this_week(monday_date):
    holidays_found = []

    for i in range(7):
        d = monday_date + datetime.timedelta(days=i)
        date_str = d.strftime("%Y-%m-%d")

        if date_str in US_MARKET_HOLIDAYS_2025:
            holidays_found.append((d, US_MARKET_HOLIDAYS_2025[date_str]))

    return holidays_found


def format_weekly_message(events, holidays, week_start, week_end):
    lines = []

    lines.append("📅 التقويم الاقتصادي الأمريكي")
    lines.append(
        f"الأسبوع من {week_start.strftime('%Y-%m-%d')} "
        f"إلى {week_end.strftime('%Y-%m-%d')}"
    )
    lines.append("")

    if holidays:
        lines.append("🔴 تنبيه: عطلة رسمية في السوق الأمريكي")
        for date, reason in holidays:
            day_name = ARABIC_DAYS.get(date.strftime("%A"), date.strftime("%A"))
            lines.append(
                f"- يوم {day_name} ({date.strftime('%Y-%m-%d')}): "
                f"{reason} — السوق مغلق 🚫"
            )
        lines.append("")

    if events:
        lines.append("📊 أهم الأحداث الاقتصادية:")
        for e in events:
            date_obj = datetime.datetime.strptime(e["date"], "%Y-%m-%d")
            day_name = ARABIC_DAYS.get(date_obj.strftime("%A"), "")
            lines.append(f"- {day_name} {e['date']} | {e['event']}")
    else:
        lines.append("لا توجد بيانات اقتصادية مسجلة لهذا الأسبوع.")

    lines.append("")
    lines.append("━━━━━━━━━━━━━━")
    lines.append("📊 Chart News US | أخبار السوق الامريكي")
    lines.append("https://t.me/ChartMaster_News")

    return "\n".join(lines)


def get_last_weekly_sent():
    try:
        with open("weekly_sent.txt", "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return None


def set_last_weekly_sent(date_str):
    with open("weekly_sent.txt", "w") as f:
        f.write(date_str)


# ==========================================
# تشغيل البوت
# ==========================================

while True:
    try:
        # ==================================
        # جلب الأخبار من Finnhub
        # ==================================

        url = (
            "https://finnhub.io/api/v1/news"
            f"?category=general&token={FINNHUB_API_KEY}"
        )

        response = requests.get(url, timeout=15)
        response.raise_for_status()

        news = response.json()

        if not isinstance(news, list):
            print("Unexpected API response:", news)
            news = []

        for item in news:

            headline = item.get("headline", "").strip()
            if not headline:
                continue

            item_id = get_safe_id(item, headline)

            if item_id in sent:
                continue

            text = headline.lower()

            # فلتر: منع السياسة والحروب أولاً
            if BLOCKED_PATTERN.search(text):
                continue

            # فلتر: يجب أن يحتوي على كلمة مفتاحية
            if not KEYWORDS_PATTERN.search(text):
                continue

            # تحليل الخبر بواسطة GPT
            analysis = analyze_news(headline)

            if not analysis:
                continue

            if analysis.strip().upper() in ["SKIP", "YES", "NO"]:
                continue

            # منع تكرار نفس الحدث
            if is_duplicate_topic(headline):
                print("DUPLICATE SKIPPED:", headline)
                continue

            # إرسال الخبر
            message = f"""-


{analysis}

📰 المصدر: {item.get('source', 'غير معروف')}

━━━━━━━━━━━━━━
📊 Chart News US | أخبار السوق الامريكي
https://t.me/ChartMaster_News
"""

            send(message)

            sent.add(item_id)
            save(sent)

            remember_topic(headline)

        # ==================================
        # التقويم الاقتصادي الأسبوعي (كل أحد)
        # ==================================

               today = datetime.date.today()
        today_str = today.strftime("%Y-%m-%d")

        force_test = os.getenv("FORCE_WEEKLY_TEST") == "1"

        if (today.weekday() == 6 or force_test) and (force_test or get_last_weekly_sent() != today_str):
            week_start = today + datetime.timedelta(days=1)
            week_end = week_start + datetime.timedelta(days=6)

            events = get_weekly_economic_calendar_fred(week_start, week_end)
            holidays = get_holidays_this_week(week_start)

            weekly_message = format_weekly_message(
                events, holidays, week_start, week_end
            )

            send(weekly_message)
            set_last_weekly_sent(today_str)
                print("Weekly calendar sent successfully.")

            except Exception as e:
                print("Weekly summary error:", e)

        time.sleep(60)

    except Exception:
        import traceback
        traceback.print_exc()
        time.sleep(60)
