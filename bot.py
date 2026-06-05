import os
import json
import random
import logging
from datetime import datetime, timedelta
from collections import Counter
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN", "8724922311:AAHbErc51Ly8sJN9pYPxyRwy-aZwojC8Cj0")
DATA_FILE = "data.json"

# ── OWNER CONFIG ──────────────────────────────────────────────
OWNER_ID = 5125916435
UPI_ID = "unknown7387@axl"
PREMIUM_DAYS = 5  # default 5 days

REFERRAL_LINKS = {
    "1": {"name": "BDG WIN", "url": "https://bdgwin1.vip//#/register?invitationCode=8438396488"},
    "2": {"name": "Lottery 7", "url": "https://www.lottery7g.com/#/register?invitationCode=186118943973"},
    "3": {"name": "Big Mumbai", "url": "https://www.jabalpurhills.com/#/register?invitationCode=5224471352"},
    "4": {"name": "Jai Club", "url": "https://www.jaiclub43.com/#/register?invitationCode=484122804377"},
}

FREE_LIMIT = 5

# ── N-GRAM PATTERNS ───────────────────────────────────────────
NGRAM4 = {
    'BBB': {'B': 81, 'S': 19}, 'BBS': {'B': 31, 'S': 69},
    'BSB': {'B': 36, 'S': 64}, 'BSS': {'B': 39, 'S': 61},
    'SBB': {'B': 46, 'S': 54}, 'SBS': {'B': 56, 'S': 44},
    'SSB': {'B': 47, 'S': 53}, 'SSS': {'B': 34, 'S': 66},
}
NGRAM3 = {
    'BB': {'B': 70, 'S': 30}, 'BS': {'B': 44, 'S': 56},
    'SB': {'B': 42, 'S': 58}, 'SS': {'B': 36, 'S': 64},
}
NGRAM2 = {
    'B': {'B': 58, 'S': 42}, 'S': {'B': 39, 'S': 61},
}
COLOR_GRAM = {
    'R': {'R': 48, 'G': 32, 'V': 20},
    'G': {'R': 46, 'G': 43, 'V': 11},
    'V': {'R': 58, 'G': 27, 'V': 15},
}
HIST = [2,2,2,4,3,7,0,0,0,7,8,3,4,5,1,3,2,6,9,9,6,5,6,4,9,4,6,0,2,5,
        1,3,3,3,4,3,7,8,2,8,2,3,1,3,9,9,1,3,3,3,2,8,9,8,9,7,8,2,7,1,
        8,3,8,9,7,8,2,0,4,6,8,4,6,4,8,4,6,5,6,5,5,7,6,6,6,5,6,9,5,6,
        0,2,2,4,0,5,4,1,1,8,3,3,9,4,9,2,1,4,9,2,6,3,3,8,5,9,1,9,7,0,
        3,4,0,3,4,9,4,0,2,5,3,4,8,1,1,0,4,2,0,2,2,6,0,4,9,2,0,9,5,9,
        1,9,9,7,8,4,8,5,9,5,7,5,1,7,5,9,2,7,8,5,9,8,5,9,5,5,9,7,6,9]

# ── HELPERS ───────────────────────────────────────────────────
def is_big(n): return n >= 5
def get_col(n):
    if n in [0,5]: return 'violet'
    if n in [1,3,7,9]: return 'green'
    return 'red'
def col_key(n):
    c = get_col(n)
    return 'R' if c=='red' else 'G' if c=='green' else 'V'

def load():
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE,'r') as f:
                return json.load(f)
    except: pass
    return {}

def save(data):
    try:
        with open(DATA_FILE,'w') as f:
            json.dump(data, f)
    except Exception as e:
        logger.error(f"Save error: {e}")

def get_ud(data, uid):
    uid = str(uid)
    if uid not in data:
        data[uid] = {
            'results': [], 'acc': [], 'last_pred': None,
            'premium': False, 'premium_expiry': None,
            'free_used': 0, 'free_date': None,
            'pending_payment': None
        }
        save(data)
    # migrate old users
    ud = data[uid]
    for k,v in [('premium',False),('premium_expiry',None),
                ('free_used',0),('free_date',None),('pending_payment',None)]:
        if k not in ud: ud[k] = v
    return ud

def is_premium(ud, uid):
    if str(uid) == str(OWNER_ID):
        return True
    if not ud.get('premium'):
        return False
    exp = ud.get('premium_expiry')
    if exp and datetime.now() > datetime.fromisoformat(exp):
        ud['premium'] = False
        ud['premium_expiry'] = None
        return False
    return True

def check_free_limit(ud):
    today = datetime.now().strftime('%Y-%m-%d')
    if ud.get('free_date') != today:
        ud['free_date'] = today
        ud['free_used'] = 0
    return ud['free_used'] < FREE_LIMIT

def use_free(ud):
    ud['free_used'] = ud.get('free_used', 0) + 1

def free_remaining(ud):
    today = datetime.now().strftime('%Y-%m-%d')
    if ud.get('free_date') != today:
        return FREE_LIMIT
    return max(0, FREE_LIMIT - ud.get('free_used', 0))

# ── PREDICTION ENGINE ─────────────────────────────────────────
def predict(results, acc):
    all_r = results + [{'n':n} for n in HIST]
    if len(all_r) < 5:
        return None
    bs = ['B' if is_big(r['n']) else 'S' for r in all_r]
    cols = [col_key(r['n']) for r in all_r]
    k4 = ''.join(bs[:3]) if len(bs)>=3 else ''
    k3 = ''.join(bs[:2]) if len(bs)>=2 else ''
    k2 = bs[0]
    if k4 in NGRAM4:
        p = NGRAM4[k4]; src = f"4-gram[{k4}]"
    elif k3 in NGRAM3:
        p = NGRAM3[k3]; src = f"3-gram[{k3}]"
    else:
        p = NGRAM2.get(k2, {'B':50,'S':50}); src = f"2-gram[{k2}]"
    bp, sp = p['B'], p['S']
    r5 = acc[:5]
    if len(r5) >= 3:
        bw = sum(1 for a in r5 if not a['bs_ok'] and a['pb']=='BIG')
        sw = sum(1 for a in r5 if not a['bs_ok'] and a['pb']=='SMALL')
        if bw >= 3: bp=max(bp-18,10); sp=min(sp+18,90)
        elif sw >= 3: sp=max(sp-18,10); bp=min(bp+18,90)
    conf = abs(bp-sp)
    wait = conf < 12
    pred_bs = 'BIG' if bp>=sp else 'SMALL'
    bs_conf = max(bp,sp)
    lc = cols[0]
    cp = COLOR_GRAM.get(lc, {'R':33,'G':34,'V':33})
    rc = Counter(cols[:8])
    mv = min(rc.get(c,0) for c in ['R','G','V'])
    cs = {}
    for c in ['R','G','V']:
        od = 12 if rc.get(c,0)==mv else 0
        cs[c] = cp.get(c,33)+od
    pc = max(cs, key=cs.get)
    cc = min(80, cs[pc])
    pcol = {'R':'red','G':'green','V':'violet'}[pc]
    nc = Counter(r['n'] for r in all_r[:50])
    tb = pred_bs=='BIG'
    cands = []
    for i in range(10):
        if is_big(i)==tb:
            cm = 2 if col_key(i)==pc else 0
            cands.append((i,(10-nc.get(i,0))+cm))
    cands.sort(key=lambda x:-x[1])
    pn = cands[0][0]
    alts = [c[0] for c in cands[1:3]]
    nc2 = min(45,max(20,22+(10-nc.get(pn,0))*3))
    sk=1
    for i in range(1,len(bs)):
        if bs[i]==bs[0]: sk+=1
        else: break
    return {
        'bs':pred_bs,'bsc':round(bs_conf),
        'col':pcol,'cc':round(cc),
        'num':pn,'nc':round(nc2),
        'alts':alts,'src':src,'sk':sk,
        'lt':bs[0],'wait':wait
    }

def fmt_pred(p, period=None, premium=False):
    if not p: return "❌ Need more results. Use /add <period> <number>"
    if p['wait']:
        return "⏳ *WAIT THIS ROUND*\n\nPattern unclear — confidence low.\nEnter result and wait for next round."
    ce = {'red':'🔴','green':'🟢','violet':'🟣'}
    be = '🔵' if p['bs']=='BIG' else '🔴'
    t = "━━━━━━━━━━━━━━━━━\n"
    t += "⚡ *WINGO AI PREDICTION*\n"
    if period: t += f"📍 Period: `{period}`\n"
    t += "━━━━━━━━━━━━━━━━━\n\n"
    t += f"{be} *BIG/SMALL:* `{p['bs']}` — {p['bsc']}%\n"
    if premium:
        t += f"{ce.get(p['col'],'⚪')} *COLOR:* `{p['col'].upper()}` — {p['cc']}%\n"
        t += f"🎯 *NUMBER:* `{p['num']}` — {p['nc']}%\n"
        t += f"🔢 *Alternates:* `{', '.join(map(str,p['alts']))}`\n"
        t += f"\n📊 Pattern: `{p['src']}`\n"
        t += f"🔥 Streak: `{p['sk']}× {p['lt']}`\n"
    else:
        t += f"🔒 *COLOR, NUMBER & more* → Premium only\n"
    t += "\n━━━━━━━━━━━━━━━━━\n"
    t += "_Verify with: /result <number>_"
    return t

def premium_msg():
    return (
        "━━━━━━━━━━━━━━━━━\n"
        "🚀 *PREMIUM UPGRADE*\n"
        "━━━━━━━━━━━━━━━━━\n\n"
        "Aapki *5 free predictions* khatam ho gayi!\n\n"
        "💎 *PREMIUM FEATURES:*\n"
        "✅ Unlimited predictions\n"
        "✅ Color prediction (🔴🟢🟣)\n"
        "✅ Exact number prediction\n"
        "✅ Alternate numbers\n"
        "✅ Pattern analysis\n"
        "✅ Accuracy report /accuracy\n"
        "✅ Full history /history\n\n"
        "💰 *PREMIUM LENE KE 2 TARIKE:*\n\n"
        "1️⃣ *Game Deposit (FREE Premium):*\n"
        "   Neeche se kisi ek game mein register karke ₹500+ deposit karo → Screenshot bhejo → *Lifetime Premium*\n\n"
        "2️⃣ *Direct Payment (UPI):*\n"
        f"   UPI: `{UPI_ID}`\n"
        "   💰 *₹49* → 5 Days\n"
        "   💰 *₹99* → 15 Days\n"
        "   💰 *₹149* → Lifetime\n"
        "   Payment screenshot bhejo\n\n"
        "👇 *Apna option choose karo:*"
    )

def get_premium_keyboard():
    keyboard = [
        [InlineKeyboardButton("🎮 Game Register (FREE Premium)", callback_data="premium_game")],
        [InlineKeyboardButton("💳 UPI ₹49 Pay Karo", callback_data="premium_upi")],
        [InlineKeyboardButton("❓ Already paid? Screenshot bhejo", callback_data="premium_sent")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_game_keyboard():
    keyboard = []
    for k, v in REFERRAL_LINKS.items():
        keyboard.append([InlineKeyboardButton(f"🎯 {v['name']}", url=v['url'])])
    keyboard.append([InlineKeyboardButton("✅ Register ho gaya, Screenshot bhejo", callback_data="premium_sent")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="premium_back")])
    return InlineKeyboardMarkup(keyboard)

# ── COMMANDS ──────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    uid = update.effective_user.id
    ud = get_ud(data, uid)
    prem = is_premium(ud, uid)
    rem = free_remaining(ud)
    status = "👑 *PREMIUM*" if prem else f"🆓 *FREE* ({rem}/{FREE_LIMIT} predictions left today)"
    t = (
        "🎮 *WINGO AI PREDICTOR*\n"
        "━━━━━━━━━━━━━━━━━\n\n"
        f"Status: {status}\n\n"
        "*COMMANDS:*\n"
        "➕ /add `<period> <number>`\n"
        "    _e.g. /add 10644 7_\n\n"
        "✅ /result `<number>`\n"
        "    _e.g. /result 7_\n\n"
        "🎯 /predict — Get prediction\n"
        "📊 /accuracy — Accuracy report _(Premium)_\n"
        "📋 /history — Last 10 results _(Premium)_\n"
        "💎 /premium — Upgrade to Premium\n"
        "🗑 /clear — Clear my data\n\n"
        "━━━━━━━━━━━━━━━━━\n"
        "_Start: /add <period> <number>_"
    )
    await update.message.reply_text(t, parse_mode='Markdown')

async def cmd_premium(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    uid = update.effective_user.id
    ud = get_ud(data, uid)
    if is_premium(ud, uid):
        exp = ud.get('premium_expiry')
        if exp:
            exp_str = datetime.fromisoformat(exp).strftime('%d %b %Y')
            msg = f"👑 *Aap already PREMIUM hain!*\n\nExpiry: {exp_str}\n\n/predict se prediction lo!"
        else:
            msg = "👑 *Aap PREMIUM hain! (Lifetime)*\n\n/predict se prediction lo!"
        await update.message.reply_text(msg, parse_mode='Markdown')
        return
    await update.message.reply_text(
        premium_msg(), parse_mode='Markdown',
        reply_markup=get_premium_keyboard()
    )

async def callback_premium(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "premium_game":
        txt = (
            "🎮 *GAME REGISTER KARKE FREE PREMIUM PAO!*\n\n"
            "Steps:\n"
            "1️⃣ Neeche se kisi ek game choose karo\n"
            "2️⃣ Link pe register karo\n"
            "3️⃣ Minimum ₹500 deposit karo\n"
            "4️⃣ Deposit screenshot bhejo is bot mein\n"
            "5️⃣ Verify hone pe *Lifetime Premium* milega! 🎉\n\n"
            "👇 *Game choose karo:*"
        )
        await query.edit_message_text(txt, parse_mode='Markdown', reply_markup=get_game_keyboard())

    elif data == "premium_upi":
        txt = (
            "💳 *UPI PAYMENT - PLANS*\n\n"
            f"UPI ID: `{UPI_ID}`\n\n"
            "📦 *PLANS:*\n"
            "🔹 *₹49* → 5 Days\n"
            "🔹 *₹99* → 15 Days\n"
            "🔹 *₹149* → Lifetime (Unlimited)\n\n"
            "Steps:\n"
            "1️⃣ UPI ID copy karo\n"
            "2️⃣ Apna plan choose karke pay karo\n"
            "3️⃣ Payment screenshot is bot mein bhejo\n"
            "4️⃣ Message mein likho kitne din ka plan liya\n"
            "5️⃣ Thoda wait karo — verify hote hi access milega!\n\n"
            "⚠️ _Screenshot mein amount clearly dikhni chahiye_"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="premium_back")]])
        await query.edit_message_text(txt, parse_mode='Markdown', reply_markup=kb)

    elif data == "premium_sent":
        txt = (
            "✅ *Screenshot bhejo!*\n\n"
            "Is bot mein directly screenshot bhejo.\n"
            "Hamari team verify karegi aur aapko message aayega.\n\n"
            "⏱ _Verification mein thoda time lag sakta hai_"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="premium_back")]])
        await query.edit_message_text(txt, parse_mode='Markdown', reply_markup=kb)

    elif data == "premium_back":
        await query.edit_message_text(
            premium_msg(), parse_mode='Markdown',
            reply_markup=get_premium_keyboard()
        )

async def handle_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """User screenshot bheje toh owner ko forward karo"""
    data = load()
    uid = update.effective_user.id
    user = update.effective_user
    ud = get_ud(data, uid)

    if is_premium(ud, uid):
        await update.message.reply_text("👑 Aap already Premium hain!", parse_mode='Markdown')
        return

    # User ko message bhejo
    await update.message.reply_text(
        "📸 *Screenshot mil gaya!*\n\n"
        "⏳ Aapka UID verify ho raha hai, thoda time lag sakta hai.\n"
        "✅ Verify hone ke baad aapko access mil jayega!",
        parse_mode='Markdown'
    )

    # Owner ko screenshot aur message bhejo
    try:
        msg = (
            f"🔔 *NEW PAYMENT REQUEST*\n\n"
            f"👤 Name: {user.full_name}\n"
            f"🆔 User ID: `{uid}`\n"
            f"📛 Username: @{user.username or 'N/A'}\n\n"
            f"✅ Approve: `/approve {uid}`\n"
            f"❌ Reject: `/reject {uid}`"
        )
        await ctx.bot.forward_message(
            chat_id=5125916435,
            from_chat_id=update.message.chat_id,
            message_id=update.message.message_id
        )
        await ctx.bot.send_message(
            chat_id=5125916435,
            text=msg,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Forward error: {e}")

async def cmd_approve(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Owner: /approve <user_id> [days]"""
    if update.effective_user.id != OWNER_ID:
        return
    args = ctx.args
    if not args:
        await update.message.reply_text("Usage: /approve <user_id> [days]\nDefault 14 days (game deposit = 0 for lifetime)")
        return
    target_id = str(args[0])
    days = int(args[1]) if len(args) > 1 else PREMIUM_DAYS
    data = load()
    ud = get_ud(data, target_id)
    ud['premium'] = True
    if days == 0:
        ud['premium_expiry'] = None
        exp_txt = "Lifetime"
    else:
        exp = datetime.now() + timedelta(days=days)
        ud['premium_expiry'] = exp.isoformat()
        exp_txt = exp.strftime('%d %b %Y')
    save(data)
    # Notify user
    try:
        await ctx.bot.send_message(
            chat_id=int(target_id),
            text=(
                "🎉 *Congratulations! PREMIUM ACTIVATED!*\n\n"
                f"✅ Aapka payment verify ho gaya!\n"
                f"📅 Expiry: *{exp_txt}*\n\n"
                "Ab aap unlimited predictions le sakte hain!\n"
                "/predict se shuru karo 🚀"
            ),
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Notify error: {e}")
    await update.message.reply_text(f"✅ User {target_id} ko Premium diya! ({exp_txt})")

async def cmd_reject(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Owner: /reject <user_id>"""
    if update.effective_user.id != OWNER_ID:
        return
    args = ctx.args
    if not args:
        await update.message.reply_text("Usage: /reject <user_id>")
        return
    target_id = str(args[0])
    try:
        await ctx.bot.send_message(
            chat_id=int(target_id),
            text=(
                "❌ *Payment Verify Nahi Hua*\n\n"
                "Aapka screenshot verify nahi ho saka.\n\n"
                "Possible reasons:\n"
                "• Amount kam tha\n"
                "• Screenshot clear nahi tha\n"
                "• Wrong UPI ID pe payment\n\n"
                "Dobara try karo ya /premium pe contact karo."
            ),
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Reject notify error: {e}")
    await update.message.reply_text(f"❌ User {target_id} reject kiya.")

async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Owner: /stats"""
    if update.effective_user.id != OWNER_ID:
        return
    data = load()
    total = len(data)
    prem = sum(1 for uid, ud in data.items() if ud.get('premium'))
    active_today = 0
    today = datetime.now().strftime('%Y-%m-%d')
    for uid, ud in data.items():
        if ud.get('free_date') == today and ud.get('free_used', 0) > 0:
            active_today += 1
    await update.message.reply_text(
        f"📊 *BOT STATS*\n\n"
        f"👥 Total Users: {total}\n"
        f"👑 Premium Users: {prem}\n"
        f"🆓 Free Users: {total - prem}\n"
        f"⚡ Active Today: {active_today}",
        parse_mode='Markdown'
    )

async def cmd_add(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    uid = update.effective_user.id
    ud = get_ud(data, uid)
    prem = is_premium(ud, uid)

    args = ctx.args
    if not args or len(args) < 2:
        await update.message.reply_text(
            "❌ Format: `/add <period> <number>`\nExample: `/add 10644 7`",
            parse_mode='Markdown')
        return
    try:
        period = args[0]
        n = int(args[1])
        if not 0 <= n <= 9: raise ValueError
    except:
        await update.message.reply_text(
            "❌ Number must be 0-9\nExample: `/add 10644 7`",
            parse_mode='Markdown')
        return

    # Free limit check
    if not prem:
        if not check_free_limit(ud):
            save(data)
            await update.message.reply_text(
                premium_msg(), parse_mode='Markdown',
                reply_markup=get_premium_keyboard()
            )
            return
        use_free(ud)

    entry = {'n':n,'period':period,'bs':'BIG' if is_big(n) else 'SMALL','col':get_col(n)}
    ud['results'].insert(0, entry)
    if len(ud['results'])>500: ud['results'].pop()
    p = predict(ud['results'], ud['acc'])
    ud['last_pred'] = p
    save(data)

    ce = {'red':'🔴','green':'🟢','violet':'🟣'}
    be = '🔵' if is_big(n) else '🔴'
    rem_txt = "" if prem else f"\n🆓 Free predictions left today: *{free_remaining(ud)}*"
    added = (f"✅ *Added!*\n"
             f"Period: `{period}` | {be} `{n}` {('BIG' if is_big(n) else 'SMALL')} "
             f"{ce.get(get_col(n),'⚪')} {get_col(n).upper()}\n"
             f"Total: {len(ud['results'])} results{rem_txt}\n\n")
    await update.message.reply_text(added + fmt_pred(p, period, prem), parse_mode='Markdown')

    # Show upgrade prompt after last free prediction
    if not prem and free_remaining(ud) == 0:
        await update.message.reply_text(
            "⚠️ *Aaj ki free predictions khatam!*\nKal dobara aao ya Premium lo 👇",
            parse_mode='Markdown',
            reply_markup=get_premium_keyboard()
        )

async def cmd_result(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    uid = update.effective_user.id
    ud = get_ud(data, uid)
    prem = is_premium(ud, uid)

    args = ctx.args
    if not args:
        await update.message.reply_text(
            "❌ Format: `/result <number>`\nExample: `/result 7`",
            parse_mode='Markdown')
        return
    try:
        actual = int(args[0])
        if not 0 <= actual <= 9: raise ValueError
    except:
        await update.message.reply_text("❌ Number must be 0-9", parse_mode='Markdown')
        return

    p = ud.get('last_pred')
    abs_bs = 'BIG' if is_big(actual) else 'SMALL'
    abs_col = get_col(actual)
    entry = {'n':actual,'period':'v','bs':abs_bs,'col':abs_col}
    ud['results'].insert(0,entry)
    if len(ud['results'])>500: ud['results'].pop()

    txt = ""
    if p and not p.get('wait'):
        bs_ok = abs_bs == p['bs']
        col_ok = abs_col == p['col']
        log = {'pb':p['bs'],'pc':p['col'],'pn':p['num'],
               'an':actual,'abs':abs_bs,'ac':abs_col,
               'bs_ok':bs_ok,'col_ok':col_ok}
        ud['acc'].insert(0,log)
        if len(ud['acc'])>200: ud['acc'].pop()
        wins = sum(1 for a in ud['acc'] if a['bs_ok'])
        tot = len(ud['acc'])
        pct = round(wins/tot*100) if tot else 0
        if bs_ok and col_ok:
            fb = "✅ *PERFECT! BIG/SMALL + Color correct!* 🎉"
        elif bs_ok:
            fb = f"✅ *BIG/SMALL correct!*\nColor: pred {p['col'].upper()} → got {abs_col.upper()}"
        else:
            fb = f"❌ *WRONG*\nPred: {p['bs']} {p['col'].upper()} → Got: {abs_bs} {abs_col.upper()}\nAI learning..."
        txt = f"{fb}\n📊 Accuracy: *{pct}%* ({wins}/{tot})\n\n"

    new_p = predict(ud['results'], ud['acc'])
    ud['last_pred'] = new_p
    save(data)
    txt += "━━━━━━━━━━━━━━━━━\n*NEXT PREDICTION:*\n\n"
    txt += fmt_pred(new_p, None, prem)
    await update.message.reply_text(txt, parse_mode='Markdown')

async def cmd_predict(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    uid = update.effective_user.id
    ud = get_ud(data, uid)
    prem = is_premium(ud, uid)

    if not prem and not check_free_limit(ud):
        save(data)
        await update.message.reply_text(
            premium_msg(), parse_mode='Markdown',
            reply_markup=get_premium_keyboard()
        )
        return

    if not prem:
        use_free(ud)

    p = predict(ud['results'], ud['acc'])
    ud['last_pred'] = p
    save(data)
    period = ud['results'][0].get('period','') if ud['results'] else None
    await update.message.reply_text(fmt_pred(p, period, prem), parse_mode='Markdown')

async def cmd_accuracy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    uid = update.effective_user.id
    ud = get_ud(data, uid)
    if not is_premium(ud, uid):
        await update.message.reply_text(
            "🔒 *Accuracy report Premium feature hai!*\n\n/premium se upgrade karo.",
            parse_mode='Markdown', reply_markup=get_premium_keyboard()
        )
        return
    acc = ud['acc']
    if not acc:
        await update.message.reply_text(
            "📊 No verified predictions yet.\nUse /result after each round.",
            parse_mode='Markdown')
        return
    wins = sum(1 for a in acc if a['bs_ok'])
    cw = sum(1 for a in acc if a['col_ok'])
    n = len(acc)
    pct = round(wins/n*100)
    cpct = round(cw/n*100)
    em = '🟢' if pct>=65 else '🟡' if pct>=50 else '🔴'
    t = (f"━━━━━━━━━━━━━━━━━\n📊 *ACCURACY REPORT*\n━━━━━━━━━━━━━━━━━\n\n"
         f"{em} *BIG/SMALL:* {pct}% ({wins}/{n})\n"
         f"🎨 *Color:* {cpct}% ({cw}/{n})\n"
         f"✅ Hit: {wins} | ❌ Miss: {n-wins} | 📈 Total: {n}\n\n")
    if n>=5:
        if pct>=70: s="✨ HIGH CONFIDENCE"
        elif pct>=58: s="📈 MOMENTUM MODE"
        elif pct<40: s="⚡ REVERSAL MODE"
        else: s="⚖️ BALANCED MODE"
        t += f"🧠 Strategy: *{s}*\n\n"
    t += "*Last 5:*\n"
    for a in acc[:5]:
        ok = '✅' if a['bs_ok'] else '❌'
        t += f"{ok} Pred:{a['pb'][:3]} {a['pc'][:3].upper()} → Got:{a['abs'][:3]} {a['ac'][:3].upper()} (#{a['an']})\n"
    await update.message.reply_text(t, parse_mode='Markdown')

async def cmd_history(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    uid = update.effective_user.id
    ud = get_ud(data, uid)
    if not is_premium(ud, uid):
        await update.message.reply_text(
            "🔒 *History Premium feature hai!*\n\n/premium se upgrade karo.",
            parse_mode='Markdown', reply_markup=get_premium_keyboard()
        )
        return
    if not ud['results']:
        await update.message.reply_text(
            "No results yet.\nAdd with: `/add <period> <number>`",
            parse_mode='Markdown')
        return
    ce = {'red':'🔴','green':'🟢','violet':'🟣'}
    t = "📋 *LAST 10 RESULTS*\n━━━━━━━━━━━━━━━━━\n"
    for r in ud['results'][:10]:
        be = '🔵' if r['bs']=='BIG' else '🔴'
        per = str(r.get('period','–'))[-6:]
        t += f"`{per}` {be}`{r['n']}` {r['bs']} {ce.get(r['col'],'⚪')}{r['col'].upper()}\n"
    await update.message.reply_text(t, parse_mode='Markdown')

async def cmd_clear(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    uid = str(update.effective_user.id)
    if uid in data:
        prem = data[uid].get('premium', False)
        exp = data[uid].get('premium_expiry', None)
        data[uid] = {'results':[],'acc':[],'last_pred':None,
                     'premium':prem,'premium_expiry':exp,
                     'free_used':0,'free_date':None,'pending_payment':None}
        save(data)
    await update.message.reply_text("🗑 Data cleared!", parse_mode='Markdown')

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    if txt.isdigit() and len(txt)==1:
        ctx.args = ['auto', txt]
        await cmd_add(update, ctx)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("add", cmd_add))
    app.add_handler(CommandHandler("result", cmd_result))
    app.add_handler(CommandHandler("predict", cmd_predict))
    app.add_handler(CommandHandler("accuracy", cmd_accuracy))
    app.add_handler(CommandHandler("history", cmd_history))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("premium", cmd_premium))
    app.add_handler(CommandHandler("approve", cmd_approve))
    app.add_handler(CommandHandler("reject", cmd_reject))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("help", cmd_start))
    app.add_handler(CallbackQueryHandler(callback_premium, pattern="^premium_"))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    logger.info("Bot started!")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
