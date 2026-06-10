import os
import json
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)
from tavily import TavilyClient
import google.generativeai as genai

# ─── CONFIG ───────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
TAVILY_API_KEY = os.environ["TAVILY_API_KEY"]

genai.configure(api_key=GEMINI_API_KEY)
tavily = TavilyClient(api_key=TAVILY_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

# ─── USER STATE ───────────────────────────────────────────
user_sessions = {}  # {user_id: {"topics": [...], "search_results": "..."}}

# ─── SEARCH ───────────────────────────────────────────────
def search_crypto_news():
    queries = [
        "crypto trending projects June 2026",
        "Binance Alpha new listings 2026",
        "DeFi AI RWA crypto narrative 2026",
        "top airdrop projects crypto 2026",
    ]
    all_results = []
    for q in queries:
        try:
            res = tavily.search(query=q, max_results=3, search_depth="basic")
            for r in res.get("results", []):
                all_results.append(f"- {r['title']}: {r['content'][:200]}")
        except Exception:
            pass
    return "\n".join(all_results[:20])

# ─── ANALYZE TOPICS ───────────────────────────────────────
def analyze_topics(search_data: str) -> list[dict]:
    prompt = f"""Sən peşəkar Crypto Content Research Agent-sən.
Aşağıdakı son kripto xəbərlərinə əsasən Binance Square üçün ən yüksək potensiala malik 10 mövzu seç.

XƏBƏRLƏR:
{search_data}

JSON formatında cavab ver, başqa heç nə yazma:
[
  {{
    "id": "A",
    "title": "Mövzu adı",
    "reason": "Niyə trenddir (1-2 cümlə)",
    "risk": "Aşağı/Orta/Yüksək",
    "viral": 8,
    "w2e": 9
  }},
  ...
]
Tam 10 mövzu olsun. Yalnız JSON qaytır."""

    response = model.generate_content(prompt)
    text = response.text.strip()
    # JSON-u təmizlə
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())

# ─── WRITE ARTICLE ────────────────────────────────────────
def write_article(topic: dict) -> str:
    prompt = f"""Sən Binance Square üçün məqalə yazan kripto ekspertisən.

MÖVZU: {topic['title']}
SƏBƏB: {topic['reason']}

Aşağıdakı tələblərə uyğun məqalə yaz:
- 100% orijinal, AI izi minimum
- İnsan tərəfindən yazılmış kimi
- 600-900 söz arası
- Azərbaycan dilində
- Cəlbedici başlıq
- Giriş, əsas hissə (3-4 bölmə), nəticə
- SEO açar sözləri təbii şəkildə istifadə et
- Sonunda 5-7 hashtag əlavə et (#Bitcoin kimi)

Birbaşa məqaləni yaz, izahat vermə."""

    response = model.generate_content(prompt)
    return response.text.strip()

# ─── SOCIAL POSTS ─────────────────────────────────────────
def write_social_posts(topic: dict, article: str) -> str:
    prompt = f"""Bu məqaləyə əsasən 3 paylaşım hazırla:

MƏQALƏ:
{article[:1500]}

Format:
🐦 X/TWITTER POSTU (max 280 simvol):
[mətn]

📊 BINANCE SQUARE POSTU (150-200 söz, emoji ilə):
[mətn]

📱 TELEGRAM PAYLAŞIMI (qısa, cəlbedici):
[mətn]

Azərbaycan dilində yaz."""

    response = model.generate_content(prompt)
    return response.text.strip()

# ─── HANDLERS ─────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Salam! Mən Crypto Content Bot-am.\n\n"
        "📊 /analyze — Bazarı analiz et və top 10 mövzu tap\n"
        "❓ /help — Kömək\n\n"
        "Başlamaq üçün /analyze yaz!"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Necə istifadə etmək:*\n\n"
        "1. /analyze yaz\n"
        "2. Bot bazarı araşdırır (~30 saniyə)\n"
        "3. Sənə 10 mövzu təqdim edir\n"
        "4. Mövzu seç → bot məqalə yazır\n"
        "5. Hazır məqalə + sosial media postları alırsan\n\n"
        "💡 Yeni mövzu üçün yenidən /analyze yaz",
        parse_mode="Markdown"
    )

async def analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = await update.message.reply_text("🔍 Bazar araşdırılır... (20-30 saniyə)")

    try:
        # Search
        await msg.edit_text("🌐 Son xəbərlər yüklənir...")
        search_data = await asyncio.get_event_loop().run_in_executor(
            None, search_crypto_news
        )

        # Analyze
        await msg.edit_text("🧠 Gemini analiz edir...")
        topics = await asyncio.get_event_loop().run_in_executor(
            None, analyze_topics, search_data
        )

        # Save session
        user_sessions[user_id] = {"topics": topics, "search_data": search_data}

        # Format output
        letters = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]
        text = "📊 *İyun 2026 — TOP 10 KRİPTO MÖVZU*\n\n"

        for i, t in enumerate(topics[:10]):
            risk_emoji = {"Aşağı": "🟢", "Orta": "🟡", "Yüksək": "🔴"}.get(t["risk"], "🟡")
            text += (
                f"*{letters[i]}) {t['title']}*\n"
                f"_{t['reason']}_\n"
                f"{risk_emoji} Risk: {t['risk']} | "
                f"🔥 Viral: {t['viral']}/10 | "
                f"✍️ W2E: {t['w2e']}/10\n\n"
            )

        text += "👇 *Hansı mövzunu seçirsiniz?*"

        # Keyboard
        keyboard = []
        row = []
        for i, t in enumerate(topics[:10]):
            row.append(InlineKeyboardButton(letters[i], callback_data=f"topic_{i}"))
            if len(row) == 5:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

        await msg.edit_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except Exception as e:
        await msg.edit_text(f"❌ Xəta baş verdi: {str(e)}\nYenidən cəhd et: /analyze")

async def topic_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id not in user_sessions:
        await query.edit_message_text("⚠️ Sesiya bitib. Yenidən /analyze yaz.")
        return

    topic_idx = int(query.data.split("_")[1])
    topic = user_sessions[user_id]["topics"][topic_idx]

    msg = await query.edit_message_text(
        f"✍️ *{topic['title']}* üzrə məqalə yazılır...\n_(1-2 dəqiqə çəkə bilər)_",
        parse_mode="Markdown"
    )

    try:
        # Write article
        article = await asyncio.get_event_loop().run_in_executor(
            None, write_article, topic
        )

        # Write social posts
        social = await asyncio.get_event_loop().run_in_executor(
            None, write_social_posts, topic, article
        )

        # Send article
        await query.message.reply_text(
            f"📝 *MƏQALƏ*\n\n{article}",
            parse_mode="Markdown"
        )

        # Send social posts
        await query.message.reply_text(
            f"📲 *SOSIAL MEDIA POSTLARI*\n\n{social}",
            parse_mode="Markdown"
        )

        await query.message.reply_text(
            "✅ Hazırdır! Yeni mövzu üçün /analyze yaz."
        )

        await msg.delete()

    except Exception as e:
        await msg.edit_text(f"❌ Məqalə yazılarkən xəta: {str(e)}")

# ─── MAIN ─────────────────────────────────────────────────
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("analyze", analyze))
    app.add_handler(CallbackQueryHandler(topic_selected, pattern="^topic_"))
    print("🤖 Bot işə düşdü!")
    app.run_polling()

if __name__ == "__main__":
    main()
