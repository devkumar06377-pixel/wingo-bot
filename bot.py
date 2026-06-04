import os
import json
import asyncio
import logging
from datetime import datetime
from collections import Counter
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN", "8724922311:AAHbErc51Ly8sJN9pYPxyRwy-aZwojC8Cj0")
DATA_FILE = "wingo_data.json"

# ── N-GRAM PATTERNS from real PDF analysis ──
NGRAM4 = {
    'BBB': {'B': 81, 'S': 19},
    'BBS': {'B': 31, 'S': 69},
    'BSB': {'B': 36, 'S': 64},
    'BSS': {'B': 39, 'S': 61},
    'SBB': {'B': 46, 'S': 54},
    'SBS': {'B': 56, 'S': 44},
    'SSB': {'B': 47, 'S': 53},
    'SSS': {'B': 34, 'S': 66},
}
NGRAM3 = {
    'BB': {'B': 70, 'S': 30},
    'BS': {'B': 44, 'S': 56},
    'SB': {'B': 42, 'S': 58},
    'SS': {'B': 36, 'S': 64},
}
NGRAM2 = {
    'B': {'B': 58, 'S': 42},
    'S': {'B': 39, 'S': 61},
}
COLOR_GRAM = {
    'R': {'R': 48, 'G': 32, 'V': 20},
    'G': {'R': 46, 'G': 43, 'V': 11},
    'V': {'R': 58, 'G': 27, 'V': 15},
}

# ── HELPERS ──
def is_big(n): return n >= 5
def get_color(n):
    if n in [0, 5]: return 'violet'
    if n in [1, 3, 7, 9]: return 'green'
    return 'red'
def color_key(n):
    c = get_color(n)
    return 'R' if c == 'red' else 'G' if c == 'green' else 'V'

# ── DATA STORE ──
def load_data():
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r') as f:
                return json.load(f)
    except: pass
    return {}

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f)

def get_user_data(data, uid):
    uid = str(uid)
    if uid not in data:
        data[uid] = {
            'results': [],
            'acc_log': [],
            'last_pred': None,
            'username': ''
        }
    return data[uid]

# ── HISTORICAL DATA (from PDFs) ──
HIST = [
    2,2,2,4,3,7,0,0,0,7,8,3,4,5,1,3,2,6,9,9,6,5,6,4,9,4,6,0,2,5,
    1,3,3,3,4,3,7,8,2,8,2,3,1,3,9,9,1,3,3,3,2,8,9,8,9,7,8,2,7,1,
    8,3,8,9,7,8,2,0,4,6,8,4,6,4,8,4,6,5,6,5,5,7,6,6,6,5,6,9,5,6,
    0,2,2,4,0,5,4,1,1,8,3,3,9,4,9,2,1,4,9,2,6,3,3,8,5,9,1,9,7,0,
    3,4,0,3,4,9,4,0,2,5,3,4,8,1,1,0,4,2,0,2,2,6,0,4,9,2,0,9,5,9,
    5,8,9,3,9,9,5,8,6,5,5,6,8,6,9,8,2,8,9,5,6,6,0,6,6,5,9,6,5,6,
    1,9,9,7,8,4,8,5,9,5,7,5,1,7,5,9,2,7,8,5,9,8,5,9,5,5,9,7,6,9,
    7,5,7,7,6,6,7,9,6,6,6,9,7,5,6,6,7,7,6,9,7,6,6,6,5,7,9,9,5,8,
    0,9,1,4,8,8,8,9,6,8,4,5,6,8,8,9,6,8,9,8,6,8,9,1,6,8,1,9,6,8,
]

# ── PREDICTION ENGINE ──
def compute_prediction(user_results, acc_log):
    all_results = user_results + HIST
    n = len(all_results)
    if n < 5:
        return None

    bs = ['B' if is_big(r['n']) else 'S' for r in all_results]
    cols = [color_key(r['n']) for r in all_results]

    # N-gram lookup
    key4 = bs[0] + bs[1] + bs[2] if len(bs) >= 3 else ''
    key3 = bs[0] + bs[1] if len(bs) >= 2 else ''
    key2 = bs[0]

    if key4 in NGRAM4:
        probs = NGRAM4[key4]
        src = f"4-gram [{key4}→?]"
    elif key3 in NGRAM3:
        probs = NGRAM3[key3]
        src = f"3-gram [{key3}→?]"
    else:
        probs = NGRAM2.get(key2, {'B': 50, 'S': 50})
        src = f"2-gram [{key2}→?]"

    b_prob = probs['B']
    s_prob = probs['S']

    # Error learning
    recent5 = acc_log[:5]
    if len(recent5) >= 3:
        big_wrong = sum(1 for a in recent5 if not a['bs_ok'] and a['pred_bs'] == 'BIG')
        sml_wrong = sum(1 for a in recent5 if not a['bs_ok'] and a['pred_bs'] == 'SMALL')
        if big_wrong >= 3:
            b_prob = max(b_prob - 18, 10)
            s_prob = min(s_prob + 18, 90)
        elif sml_wrong >= 3:
            s_prob = max(s_prob - 18, 10)
            b_prob = min(b_prob + 18, 90)

    confidence = abs(b_prob - s_prob)
    should_wait = confidence < 12

    pred_bs = 'BIG' if b_prob >= s_prob else 'SMALL'
    bs_conf = max(b_prob, s_prob)

    # Color prediction
    last_col = cols[0]
    col_probs = COLOR_GRAM.get(last_col, {'R': 33, 'G': 34, 'V': 33})
    recent_col = Counter(cols[:8])
    min_val = min(recent_col.get(c, 0) for c in ['R', 'G', 'V'])
    col_scores = {}
    for c in ['R', 'G', 'V']:
        overdue = 12 if recent_col.get(c, 0) == min_val else 0
        col_scores[c] = col_probs.get(c, 33) + overdue

    pred_col_key = max(col_scores, key=col_scores.get)
    col_conf = min(80, col_scores[pred_col_key])
    pred_col = {'R': 'red', 'G': 'green', 'V': 'violet'}[pred_col_key]

    # Number prediction
    nc = Counter(r['n'] for r in all_results[:50])
    target_big = pred_bs == 'BIG'
    cands = []
    for i in range(10):
        if is_big(i) == target_big:
            col_match = 2 if color_key(i) == pred_col_key else 0
            cands.append((i, (10 - nc.get(i, 0)) + col_match))
    cands.sort(key=lambda x: -x[1])
    pred_num = cands[0][0]
    alts = [c[0] for c in cands[1:3]]
    n_conf = min(45, max(20, 22 + (10 - nc.get(pred_num, 0)) * 3))

    # Streak
    streak = 1
    for i in range(1, len(bs)):
        if bs[i] == bs[0]: streak += 1
        else: break

    return {
        'bs': pred_bs,
        'bs_conf': round(bs_conf),
        'color': pred_col,
        'col_conf': round(col_conf),
        'number': pred_num,
        'n_conf': round(n_conf),
        'alts': alts,
        'src': src,
        'streak': streak,
        'last_type': bs[0],
        'wait': should_wait,
        'confidence': confidence,
    }

def format_prediction(p, period=None):
    if p['wait']:
        return (
            "⏳ *WAIT THIS ROUND*\n\n"
            "Pattern confidence too low.\n"
            "Skip this round, enter result and wait for next prediction.\n\n"
            "_Enter actual result with /result <number>_"
        )

    col_emoji = {'red': '🔴', 'green': '🟢', 'violet': '🟣'}
    bs_emoji = '🔵' if p['bs'] == 'BIG' else '🔴'

    lines = []
    lines.append("━━━━━━━━━━━━━━━━━")
    lines.append("⚡ *WINGO AI PREDICTION*")
    if period:
        lines.append(f"📍 Period: `{period}`")
    lines.append("━━━━━━━━━━━━━━━━━")
    lines.append(f"\n{bs_emoji} *BIG/SMALL:* `{p['bs']}` — {p['bs_conf']}%")
    lines.append(f"{col_emoji.get(p['color'], '⚪')} *COLOR:* `{p['color'].upper()}` — {p['col_conf']}%")
    lines.append(f"🎯 *NUMBER:* `{p['number']}` — {p['n_conf']}%")
    lines.append(f"🔢 *Alt Numbers:* `{', '.join(map(str, p['alts']))}`")
    lines.append(f"\n📊 *Pattern:* {p['src']}")
    lines.append(f"🔥 *Streak:* {p['streak']}× {p['last_type']}")
    lines.append("\n━━━━━━━━━━━━━━━━━")
    lines.append("_Enter actual result: /result <number>_")
    return '\n'.join(lines)

def format_accuracy(acc_log):
    n = len(acc_log)
    if n == 0:
        return "📊 No verified predictions yet.\nUse /result <number> after each round."
    wins = sum(1 for a in acc_log if a['bs_ok'])
    col_wins = sum(1 for a in acc_log if a['col_ok'])
    pct = round(wins / n * 100)
    col_pct = round(col_wins / n * 100)

    emoji = '🟢' if pct >= 65 else '🟡' if pct >= 50 else '🔴'
    lines = [
        "━━━━━━━━━━━━━━━━━",
        "📊 *ACCURACY REPORT*",
        "━━━━━━━━━━━━━━━━━",
        f"\n{emoji} *BIG/SMALL Accuracy:* {pct}% ({wins}/{n})",
        f"🎨 *Color Accuracy:* {col_pct}% ({col_wins}/{n})",
        f"\n✅ Correct: {wins}",
        f"❌ Wrong: {n - wins}",
        f"📈 Total Verified: {n}",
    ]

    # Strategy
    if n >= 5:
        if pct >= 70: strat = "✨ HIGH CONFIDENCE MODE"
        elif pct >= 58: strat = "📈 MOMENTUM MODE"
        elif pct < 40: strat = "⚡ REVERSAL MODE — adjusting"
        else: strat = "⚖️ BALANCED MODE"
        lines.append(f"\n🧠 *Strategy:* {strat}")

    # Last 5
    if acc_log:
        lines.append("\n*Last 5 results:*")
        for a in acc_log[:5]:
            ok = '✅' if a['bs_ok'] else '❌'
            lines.append(f"{ok} Pred: {a['pred_bs']} {a['pred_col'].upper()} → Got: {a['actual_bs']} {a['actual_col'].upper()} (#{a['actual_n']})")

    return '\n'.join(lines)

# ── BOT HANDLERS ──
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    uid = update.effective_user.id
    ud = get_user_data(data, uid)
    ud['username'] = update.effective_user.first_name or ''
    save_data(data)

    text = (
        "🎮 *WINGO AI PREDICTOR BOT*\n"
        "━━━━━━━━━━━━━━━━━\n\n"
        "Self-learning pattern predictor\n"
        "Based on N-gram analysis from real data\n\n"
        "*COMMANDS:*\n"
        "🎯 /predict — Get next prediction\n"
        "➕ /add <period> <number> — Add result\n"
        "     _Example: /add 10644 7_\n"
        "✅ /result <number> — Verify last prediction\n"
        "     _Example: /result 7_\n"
        "📊 /accuracy — See accuracy report\n"
        "📋 /history — Last 10 results\n"
        "🗑️ /clear — Clear my data\n"
        "❓ /help — Show this menu\n\n"
        "━━━━━━━━━━━━━━━━━\n"
        "_Start by adding results with /add_"
    )
    await update.message.reply_text(text, parse_mode='Markdown')

async def predict_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    uid = update.effective_user.id
    ud = get_user_data(data, uid)

    p = compute_prediction(ud['results'], ud['acc_log'])
    if not p:
        await update.message.reply_text(
            "⚠️ Need at least 5 results.\nAdd with: `/add <period> <number>`",
            parse_mode='Markdown'
        )
        return

    ud['last_pred'] = p
    save_data(data)

    period = ud['results'][0].get('period', '') if ud['results'] else None
    text = format_prediction(p, period)
    await update.message.reply_text(text, parse_mode='Markdown')

async def add_result(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    uid = update.effective_user.id
    ud = get_user_data(data, uid)

    args = ctx.args
    if len(args) < 2:
        await update.message.reply_text(
            "❌ Format: `/add <period> <number>`\nExample: `/add 10644 7`",
            parse_mode='Markdown'
        )
        return

    try:
        period = args[0]
        n = int(args[1])
        if not 0 <= n <= 9:
            raise ValueError
    except:
        await update.message.reply_text("❌ Number must be 0-9\nExample: `/add 10644 7`", parse_mode='Markdown')
        return

    entry = {
        'n': n,
        'period': period,
        'bs': 'BIG' if is_big(n) else 'SMALL',
        'color': get_color(n),
        'time': datetime.now().strftime('%H:%M:%S')
    }
    ud['results'].insert(0, entry)
    if len(ud['results']) > 500:
        ud['results'].pop()

    # Auto predict
    p = compute_prediction(ud['results'], ud['acc_log'])
    ud['last_pred'] = p
    save_data(data)

    col_emoji = {'red': '🔴', 'green': '🟢', 'violet': '🟣'}
    bs_emoji = '🔵' if is_big(n) else '🔴'

    added_text = (
        f"✅ *Added Period {period}*\n"
        f"Number: {bs_emoji} `{n}` — {('BIG' if is_big(n) else 'SMALL')} {col_emoji.get(get_color(n),'⚪')} {get_color(n).upper()}\n"
        f"Total manual results: {len(ud['results'])}\n\n"
    )

    if p:
        pred_text = format_prediction(p, period)
        await update.message.reply_text(added_text + pred_text, parse_mode='Markdown')
    else:
        await update.message.reply_text(added_text + "Add more results for prediction.", parse_mode='Markdown')

async def verify_result(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    uid = update.effective_user.id
    ud = get_user_data(data, uid)

    args = ctx.args
    if not args:
        await update.message.reply_text("❌ Format: `/result <number>`\nExample: `/result 7`", parse_mode='Markdown')
        return

    try:
        actual = int(args[0])
        if not 0 <= actual <= 9:
            raise ValueError
    except:
        await update.message.reply_text("❌ Number must be 0-9", parse_mode='Markdown')
        return

    p = ud.get('last_pred')
    if not p or p.get('wait'):
        # Still add as result
        entry = {
            'n': actual,
            'period': 'verified',
            'bs': 'BIG' if is_big(actual) else 'SMALL',
            'color': get_color(actual),
            'time': datetime.now().strftime('%H:%M:%S')
        }
        ud['results'].insert(0, entry)
        if len(ud['results']) > 500:
            ud['results'].pop()
        new_p = compute_prediction(ud['results'], ud['acc_log'])
        ud['last_pred'] = new_p
        save_data(data)
        txt = f"✅ Result `{actual}` added.\n\n"
        if new_p:
            txt += format_prediction(new_p)
        await update.message.reply_text(txt, parse_mode='Markdown')
        return

    actual_bs = 'BIG' if is_big(actual) else 'SMALL'
    actual_col = get_color(actual)
    bs_ok = actual_bs == p['bs']
    col_ok = actual_col == p['color']

    log_entry = {
        'pred_bs': p['bs'],
        'pred_col': p['color'],
        'pred_num': p['number'],
        'actual_n': actual,
        'actual_bs': actual_bs,
        'actual_col': actual_col,
        'bs_ok': bs_ok,
        'col_ok': col_ok,
        'time': datetime.now().strftime('%H:%M')
    }
    ud['acc_log'].insert(0, log_entry)
    if len(ud['acc_log']) > 200:
        ud['acc_log'].pop()

    # Add as result too
    entry = {
        'n': actual,
        'period': 'verified',
        'bs': actual_bs,
        'color': actual_col,
        'time': datetime.now().strftime('%H:%M:%S')
    }
    ud['results'].insert(0, entry)
    if len(ud['results']) > 500:
        ud['results'].pop()

    # Feedback
    if bs_ok and col_ok:
        fb = "✅ *PERFECT! BIG/SMALL + Color both correct!* 🎉"
        fb_short = "WIN"
    elif bs_ok:
        fb = f"✅ *BIG/SMALL correct!*\nColor wrong: predicted {p['color'].upper()} → got {actual_col.upper()}\nAI learning..."
        fb_short = "HALF WIN"
    else:
        fb = f"❌ *WRONG*\nPredicted: {p['bs']} {p['color'].upper()}\nActual: {actual_bs} {actual_col.upper()}\nAI adjusting strategy..."
        fb_short = "MISS"

    # New prediction
    new_p = compute_prediction(ud['results'], ud['acc_log'])
    ud['last_pred'] = new_p
    save_data(data)

    wins = sum(1 for a in ud['acc_log'] if a['bs_ok'])
    total = len(ud['acc_log'])
    pct = round(wins/total*100) if total else 0

    text = (
        f"{fb}\n\n"
        f"📊 Accuracy: *{pct}%* ({wins}/{total})\n\n"
        "━━━━━━━━━━━━━━━━━\n"
        "*NEXT ROUND PREDICTION:*\n\n"
    )
    if new_p:
        text += format_prediction(new_p)
    else:
        text += "Keep adding results..."

    await update.message.reply_text(text, parse_mode='Markdown')

async def accuracy_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    uid = update.effective_user.id
    ud = get_user_data(data, uid)
    text = format_accuracy(ud['acc_log'])
    await update.message.reply_text(text, parse_mode='Markdown')

async def history_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    uid = update.effective_user.id
    ud = get_user_data(data, uid)

    if not ud['results']:
        await update.message.reply_text("No results yet. Add with `/add <period> <number>`", parse_mode='Markdown')
        return

    col_e = {'red': '🔴', 'green': '🟢', 'violet': '🟣'}
    lines = ["📋 *LAST 10 RESULTS*\n━━━━━━━━━━━━━━━━━"]
    for r in ud['results'][:10]:
        bs_e = '🔵' if r['bs'] == 'BIG' else '🔴'
        lines.append(f"`{r.get('period','–')[-6:]}` → {bs_e} `{r['n']}` {r['bs']} {col_e.get(r['color'],'⚪')} {r['color'].upper()}")
    await update.message.reply_text('\n'.join(lines), parse_mode='Markdown')

async def clear_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    uid = str(update.effective_user.id)
    if uid in data:
        data[uid]['results'] = []
        data[uid]['acc_log'] = []
        data[uid]['last_pred'] = None
        save_data(data)
    await update.message.reply_text("🗑️ All your data cleared.", parse_mode='Markdown')

async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await start(update, ctx)

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle plain number input"""
    text = update.message.text.strip()
    if text.isdigit() and len(text) == 1:
        n = int(text)
        ctx.args = ['auto', text]
        await add_result(update, ctx)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("predict", predict_cmd))
    app.add_handler(CommandHandler("add", add_result))
    app.add_handler(CommandHandler("result", verify_result))
    app.add_handler(CommandHandler("accuracy", accuracy_cmd))
    app.add_handler(CommandHandler("history", history_cmd))
    app.add_handler(CommandHandler("clear", clear_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    logger.info("Bot starting...")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
