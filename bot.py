import os
import json
import random
import logging
import io
from datetime import datetime, timedelta
from collections import Counter
from PIL import Image

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)
import google.generativeai as genai

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "8724922311":AAHbErc51Ly8sJN9pYPxyRwy-aZwojC8Cj0
GEMINI_API_KEY = "AQ.Ab8RN6JY7SD4Vg0Zcm3zEfQq9qxp1di-wv3XvKACZNYl81MKrw"
DATA_FILE = "data.json"

OWNER_ID = 5125916435
UPI_ID = "unknown7387@axl"
PREMIUM_DAYS = 5
FREE_LIMIT = 5

REFERRAL_LINKS = {
    "1": {"name": "BDG WIN", "url": "https://bdgwin1.vip//#/register?invitationCode=8438396488"},
    "2": {"name": "Lottery 7", "url": "https://www.lottery7g.com/#/register?invitationCode=186118943973"},
    "3": {"name": "Big Mumbai", "url": "https://www.jabalpurhills.com/#/register?invitationCode=5224471352"},
    "4": {"name": "Jai Club", "url": "https://www.jaiclub43.com/#/register?invitationCode=484122804377"},
}

LEVELS = [
    (0, "🌱 Beginner"), (10, "⚡ Rising Star"), (25, "🔥 Pro Player"),
    (50, "💎 Expert"), (100, "👑 Legend"), (200, "🚀 Master")
]

BADGES = {
    'first_pred': '🎯 First Prediction', 'streak_5': '🔥 5 Win Streak',
    'streak_10': '💥 10 Win Streak', 'accuracy_70': '🎖️ 70% Accuracy',
    'accuracy_80': '🏆 80% Accuracy', 'predictions_50': '⭐ 50 Predictions',
    'predictions_100': '🌟 100 Predictions', 'referral_1': '👥 First Referral',
    'referral_5': '👑 5 Referrals', 'premium_user': '💎 Premium Member',
}

NGRAM4 = {'BBB': {'B': 81, 'S': 19}, 'BBS': {'B': 31, 'S': 69}, 'BSB': {'B': 36, 'S': 64}, 'BSS': {'B': 39, 'S': 61}, 'SBB': {'B': 46, 'S': 54}, 'SBS': {'B': 56, 'S': 44}, 'SSB': {'B': 47, 'S': 53}, 'SSS': {'B': 34, 'S': 66}}
NGRAM3 = {'BB': {'B': 70, 'S': 30}, 'BS': {'B': 44, 'S': 56}, 'SB': {'B': 42, 'S': 58}, 'SS': {'B': 36, 'S': 64}}
NGRAM2 = {'B': {'B': 58, 'S': 42}, 'S': {'B': 39, 'S': 61}}
COLOR_GRAM = {'R': {'R': 48, 'G': 32, 'V': 20}, 'G': {'R': 46, 'G': 43, 'V': 11}, 'V': {'R': 58, 'G': 27, 'V': 15}}
HIST = [2,2,2,4,3,7,0,0,0,7,8,3,4,5,1,3,2,6,9,9,6,5,6,4,9,4,6,0,2,5]

WELCOME_MESSAGES = [
    "🔥 Kya baat hai {name} bhai! Tu aa gaya — ab game ka scene badlega! 🎯",
    "💥 Aye {name}! Sahi jagah aaya hai — yahan AI teri madad karega jeetne mein! 🤖",
    "🚀 Welcome {name}! Teri kismat badalne wali hai aaj! AI prediction ready hai! ⚡",
]

# ── GEMINI AI SETUP ───────────────────────────────────────────
genai.configure(api_key=GEMINI_API_KEY)

analyst_prompt = """
Aap ek expert Wingo/Color Prediction Data Analyst aur friendly AI assistant hain.
Aap user se Hinglish mein baat karenge. 
Jab pucha jaye toh game history ka pattern samjhayenge.
Agar image aati hai toh numbers (0-9) extract karke agla trend batayenge.
Hamesha professional rahein, aur yaad rakhein ki game mein risk hota hai.
"""

model = genai.GenerativeModel('gemini-1.5-flash', system_instruction=analyst_prompt)
user_chat_sessions = {}

def get_chat_session(uid):
    if uid not in user_chat_sessions:
        user_chat_sessions[uid] = model.start_chat(history=[])
    return user_chat_sessions[uid]

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
            with open(DATA_FILE,'r') as f: return json.load(f)
    except: pass
    return {}

def save(data):
    try:
        with open(DATA_FILE,'w') as f: json.dump(data, f)
    except Exception as e: logger.error(f"Save error: {e}")

def get_ud(data, uid):
    uid = str(uid)
    if uid not in data:
        data[uid] = {
            'results': [], 'acc': [], 'last_pred': None,
            'premium': False, 'premium_expiry': None, 'free_used': 0, 'free_date': None,
            'points': 0, 'badges': [], 'level': 0, 'referral_code': f"REF{uid[-6:]}",
            'referred_by': None, 'referrals': 0, 'win_streak': 0, 'max_streak': 0, 
            'total_preds': 0, 'banned': False, 'joined': datetime.now().isoformat()
        }
        save(data)
    ud = data[uid]
    if 'premium' not in ud: ud['premium'] = False
    return ud

def is_premium(ud, uid):
    if str(uid) == str(OWNER_ID): return True
    if ud.get('banned'): return False
    if not ud.get('premium'): return False
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

def use_free(ud): ud['free_used'] = ud.get('free_used', 0) + 1
def free_remaining(ud):
    today = datetime.now().strftime('%Y-%m-%d')
    if ud.get('free_date') != today: return FREE_LIMIT
    return max(0, FREE_LIMIT - ud.get('free_used', 0))

def get_level(points):
    level_name = LEVELS[0][1]
    for pts, name in LEVELS:
        if points >= pts: level_name = name
    return level_name

def add_points(ud, pts): ud['points'] = ud.get('points', 0) + pts

def check_badges(ud):
    new_badges = []
    badges = ud.get('badges', [])
    total = ud.get('total_preds', 0)
    acc = ud.get('acc', [])
    wins = sum(1 for a in acc if a.get('bs_ok'))
    n = len(acc)
    pct = round(wins/n*100) if n else 0
    checks = [
        ('first_pred', total >= 1), ('streak_5', ud.get('win_streak', 0) >= 5),
        ('streak_10', ud.get('win_streak', 0) >= 10), ('accuracy_70', pct >= 70 and n >= 10),
        ('accuracy_80', pct >= 80 and n >= 10), ('predictions_50', total >= 50),
        ('predictions_100', total >= 100), ('referral_1', ud.get('referrals', 0) >= 1),
        ('referral_5', ud.get('referrals', 0) >= 5), ('premium_user', ud.get('premium', False)),
    ]
    for badge, condition in checks:
        if condition and badge not in badges:
            badges.append(badge)
            new_badges.append(badge)
    ud['badges'] = badges
    return new_badges

def predict(results, acc):
    all_r = results + [{'n':n} for n in HIST]
    if len(all_r) < 5: return None
    bs = ['B' if is_big(r['n']) else 'S' for r in all_r]
    cols = [col_key(r['n']) for r in all_r]
    k4 = ''.join(bs[:3]) if len(bs)>=3 else ''
    k3 = ''.join(bs[:2]) if len(bs)>=2 else ''
    k2 = bs[0]
    if k4 in NGRAM4: p = NGRAM4[k4]; src = f"4-gram[{k4}]"
    elif k3 in NGRAM3: p = NGRAM3[k3]; src = f"3-gram[{k3}]"
    else: p = NGRAM2.get(k2, {'B':50,'S':50}); src = f"2-gram[{k2}]"
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
    num_counts = Counter(r['n'] for r in all_r[:30])
    hot = [str(x[0]) for x in num_counts.most_common(3)]
    cold = [str(x[0]) for x in num_counts.most_common()[:-4:-1]]
    risk = 'LOW 🟢' if conf >= 30 else 'MEDIUM 🟡' if conf >= 15 else 'HIGH 🔴'
    if wait: suggest = "⏳ WAIT — Pattern unclear"
    elif conf >= 30: suggest = "✅ STRONG — Khel sakte ho!"
    elif conf >= 15: suggest = "⚠️ MEDIUM — Careful khelo"
    else: suggest = "🛑 SKIP — Risky hai!"
    return {
        'bs':pred_bs,'bsc':round(bs_conf), 'col':pcol,'cc':round(cc),
        'num':pn,'nc':round(nc2), 'alts':alts,'src':src,'sk':sk,
        'lt':bs[0],'wait':wait, 'hot':hot,'cold':cold,
        'risk':risk,'suggest':suggest,'conf':conf
    }

def fmt_pred(p, period=None, premium=False):
    if not p: return "❌ Need more results. Use /add <period> <number>"
    if p['wait']:
        return "⏳ *WAIT THIS ROUND*\n\nPattern unclear — confidence low.\nAdd result aur wait karo."
    ce = {'red':'🔴','green':'🟢','violet':'🟣'}
    be = '🔵' if p['bs']=='BIG' else '🔴'
    t = "━━━━━━━━━━━━━━━━━\n⚡ *WINGO AI PREDICTION*\n"
    if period: t += f"📍 Period: `{period}`\n"
    t += "━━━━━━━━━━━━━━━━━\n\n"
    t += f"{be} *BIG/SMALL:* `{p['bs']}` — {p['bsc']}%\n"
    if premium:
        t += f"{ce.get(p['col'],'⚪')} *COLOR:* `{p['col'].upper()}` — {p['cc']}%\n"
        t += f"🎯 *NUMBER:* `{p['num']}` — {p['nc']}%\n"
        t += f"🔢 *Alternates:* `{', '.join(map(str,p['alts']))}`\n\n"
        t += f"📊 Pattern: `{p['src']}`\n🔥 Streak: `{p['sk']}× {p['lt']}`\n"
        t += f"⚠️ Risk: {p['risk']}\n💡 {p['suggest']}\n"
        t += f"🔴 Hot: `{', '.join(p['hot'])}` | 🔵 Cold: `{', '.join(p['cold'])}`\n"
    else:
        t += f"🔒 COLOR, NUMBER & more → Premium only\n⚠️ Risk: {p['risk']}\n"
    t += "\n━━━━━━━━━━━━━━━━━\n_Verify: /result <number>_"
    return t

def premium_msg():
    return (
        "━━━━━━━━━━━━━━━━━\n🚀 *PREMIUM UPGRADE*\n━━━━━━━━━━━━━━━━━\n\n"
        "Aapki *5 free predictions* khatam!\n\n"
        "💎 *PREMIUM FEATURES:*\n✅ Unlimited predictions\n✅ Color + Number prediction\n"
        "✅ Risk meter & Smart suggestion\n✅ Chat with AI & Auto Screenshot Prediction!\n\n"
        "💰 *PLANS:*\n🔹 *₹49* → 5 Days\n🔹 *₹99* → 15 Days\n🔹 *₹149* → Lifetime\n\n"
        f"💳 UPI: `{UPI_ID}`\n\n👇 *Choose karo:*"
    )

def get_premium_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎮 Game Register (FREE Premium)", callback_data="premium_game")],
        [InlineKeyboardButton("💳 ₹49 - 5 Days", callback_data="premium_upi49"),
         InlineKeyboardButton("💳 ₹99 - 15 Days", callback_data="premium_upi99")],
        [InlineKeyboardButton("💳 ₹149 - Lifetime", callback_data="premium_upi149")],
        [InlineKeyboardButton("❓ Already paid? Screenshot bhejo", callback_data="premium_sent")],
    ])

def get_game_keyboard():
    keyboard = [[InlineKeyboardButton(f"🎯 {v['name']}", url=v['url'])] for v in REFERRAL_LINKS.values()]
    keyboard.append([InlineKeyboardButton("✅ Done, Screenshot bhejo", callback_data="premium_sent")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="premium_back")])
    return InlineKeyboardMarkup(keyboard)

# ── COMMANDS ──────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    uid = update.effective_user.id
    ud = get_ud(data, uid)
    name = update.effective_user.first_name or "Bhai"
    prem = is_premium(ud, uid)
    rem = free_remaining(ud)
    level = get_level(ud.get('points', 0))
    status = "👑 *PREMIUM*" if prem else f"🆓 *FREE* ({rem}/{FREE_LIMIT} left today)"
    welcome = random.choice(WELCOME_MESSAGES).format(name=name)
    t = (
        f"{welcome}\n\n━━━━━━━━━━━━━━━━━\n⚡ *WINGO AI PREDICTOR*\n━━━━━━━━━━━━━━━━━\n\n"
        f"Status: {status}\nLevel: {level}\n\n*COMMANDS:*\n"
        "➕ /add `<period> <number>`\n✅ /result `<number>`\n"
        "🎯 /predict\n📸 /scan — Screenshot se predict\n🤖 /analysis — AI analysis\n"
        "📊 /accuracy\n📋 /history\n👤 /profile\n🏆 /leaderboard\n"
        "🎁 /refer\n🎟️ /coupon\n💎 /premium\n❓ /faq\n🗑 /clear\n\n"
        "💬 *Tips:* Aap seedhe numbers (e.g. `7`) ya koi sawal bhi type kar sakte hain!"
    )
    await update.message.reply_text(t, parse_mode='Markdown')

async def cmd_scan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    uid = update.effective_user.id
    if not is_premium(get_ud(data, uid), uid):
        await update.message.reply_text("🔒 *Screenshot scan Premium feature hai!*\n/premium se upgrade karo.", parse_mode='Markdown', reply_markup=get_premium_keyboard())
        return
    await update.message.reply_text("📸 *Game history ka screenshot bhejo!*\nAI automatically numbers read karega.", parse_mode='Markdown')

async def cmd_analysis(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    uid = update.effective_user.id
    ud = get_ud(data, uid)
    if not is_premium(ud, uid):
        await update.message.reply_text("🔒 *AI Analysis Premium feature hai!*", parse_mode='Markdown')
        return
    if len(ud.get('results', [])) < 5:
        await update.message.reply_text("❌ Kam se kam 5 results chahiye! /add se add karo.", parse_mode='Markdown')
        return
    
    await ctx.bot.send_chat_action(chat_id=uid, action='typing')
    recent = [r['n'] for r in ud['results'][:20]]
    prompt = f"Last 20 results hain: {recent}. Is sequence mein trend dhundho aur batao agla number/color kya hone ke zyada chances hain, Hindi/Hinglish me short me batao."
    try:
        session = get_chat_session(uid)
        resp = await session.send_message_async(prompt)
        await update.message.reply_text(f"🧠 *AI ANALYSIS*\n\n{resp.text}", parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ Analysis failed: {str(e)}", parse_mode='Markdown')

# ── HANDLERS (WITH ERROR DEBUGGING) ───────────────────────────
async def handle_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    uid = update.effective_user.id
    ud = get_ud(data, uid)
    if is_premium(ud, uid):
        await ctx.bot.send_chat_action(chat_id=uid, action='typing')
        try:
            photo = update.message.photo[-1]
            file = await ctx.bot.get_file(photo.file_id)
            image_bytes = await file.download_as_bytearray()
            image = Image.open(io.BytesIO(image_bytes))

            session = get_chat_session(uid)
            prompt = "Extract only the result numbers (0-9) from this Wingo history image list from top to bottom. Then analyze the pattern and predict the next color/number."
            response = await session.send_message_async([prompt, image])
            await update.message.reply_text(f"📸 *Vision Analysis:*\n\n{response.text}", parse_mode='Markdown')
        except Exception as e:
            await update.message.reply_text(f"❌ Image processing error:\n`{str(e)}`", parse_mode='Markdown')
    else:
        await update.message.reply_text("📸 *Screenshot mil gaya!*\nPayment validation ke liye owner ke paas bhej diya gaya hai.", parse_mode='Markdown')
        await ctx.bot.forward_message(chat_id=OWNER_ID, from_chat_id=uid, message_id=update.message.message_id)

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    uid = update.effective_user.id
    data = load()
    ud = get_ud(data, uid)
    
    if txt.isdigit() and len(txt)==1:
        ctx.args = ['auto', txt]
        await cmd_add(update, ctx)
        return

    if is_premium(ud, uid):
        await ctx.bot.send_chat_action(chat_id=uid, action='typing')
        try:
            session = get_chat_session(uid)
            context = f"[Internal Data: User's last 5 results: {[r['n'] for r in ud.get('results', [])[:5]]}]\n"
            response = await session.send_message_async(context + txt)
            await update.message.reply_text(response.text, parse_mode='Markdown')
        except Exception as e:
            await update.message.reply_text(f"❌ AI connection error:\n`{str(e)}`", parse_mode='Markdown')
    else:
        await update.message.reply_text("💬 Live AI Chat premium feature hai. Aap manually number (0-9) enter kar sakte hain.", parse_mode='Markdown')

# ── CORE COMMANDS ─────────────────────────────────────────────
async def cmd_add(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    uid = update.effective_user.id
    ud = get_ud(data, uid)
    if ud.get('banned'): return
    prem = is_premium(ud, uid)
    args = ctx.args
    if not args or len(args) < 2:
        await update.message.reply_text("❌ Format: `/add <period> <number>`", parse_mode='Markdown'); return
    try:
        period = args[0]; n = int(args[1])
        if not 0 <= n <= 9: raise ValueError
    except:
        await update.message.reply_text("❌ Number must be 0-9", parse_mode='Markdown'); return
    if not prem:
        if not check_free_limit(ud):
            await update.message.reply_text(premium_msg(), parse_mode='Markdown', reply_markup=get_premium_keyboard()); return
        use_free(ud)
    ud['results'].insert(0, {'n':n,'period':period,'bs':'BIG' if is_big(n) else 'SMALL','col':get_col(n)})
    if len(ud['results'])>500: ud['results'].pop()
    ud['total_preds'] = ud.get('total_preds',0)+1
    add_points(ud, 2)
    p = predict(ud['results'], ud['acc'])
    ud['last_pred'] = p
    save(data)
    ce = {'red':'🔴','green':'🟢','violet':'🟣'}
    rem_txt = "" if prem else f"\n🆓 Free left: *{free_remaining(ud)}*"
    added = f"✅ *Added!* {n} {'BIG' if is_big(n) else 'SMALL'} {ce.get(get_col(n),'⚪')}{rem_txt}\n\n"
    await update.message.reply_text(added + fmt_pred(p, period, prem), parse_mode='Markdown')

async def cmd_result(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    uid = update.effective_user.id
    ud = get_ud(data, uid)
    prem = is_premium(ud, uid)
    args = ctx.args
    if not args: await update.message.reply_text("❌ Format: `/result <number>`", parse_mode='Markdown'); return
    try:
        actual = int(args[0])
        if not 0 <= actual <= 9: raise ValueError
    except: return
    p = ud.get('last_pred')
    abs_bs = 'BIG' if is_big(actual) else 'SMALL'
    abs_col = get_col(actual)
    ud['results'].insert(0, {'n':actual,'period':'v','bs':abs_bs,'col':abs_col})
    txt = ""
    if p and not p.get('wait'):
        bs_ok = abs_bs == p['bs']
        col_ok = abs_col == p['col']
        ud['acc'].insert(0, {'pb':p['bs'],'pc':p['col'],'pn':p['num'],'an':actual,'abs':abs_bs,'ac':abs_col,'bs_ok':bs_ok,'col_ok':col_ok})
        if bs_ok: ud['win_streak']=ud.get('win_streak',0)+1; ud['max_streak']=max(ud.get('max_streak',0),ud['win_streak']); add_points(ud,5)
        else: ud['win_streak']=0
        wins = sum(1 for a in ud['acc'] if a['bs_ok'])
        tot = len(ud['acc'])
        pct = round(wins/tot*100) if tot else 0
        txt = f"{'✅ PERFECT' if bs_ok else '❌ WRONG'}\n📊 Accuracy: *{pct}%* ({wins}/{tot})\n\n"
    new_p = predict(ud['results'], ud['acc'])
    ud['last_pred'] = new_p
    save(data)
    await update.message.reply_text(txt + "━━━━━━━━━━━━━━━━━\n*NEXT PREDICTION:*\n\n" + fmt_pred(new_p, None, prem), parse_mode='Markdown')

async def cmd_predict(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    uid = update.effective_user.id
    ud = get_ud(data, uid)
    prem = is_premium(ud, uid)
    if not prem and not check_free_limit(ud):
        await update.message.reply_text(premium_msg(), parse_mode='Markdown', reply_markup=get_premium_keyboard()); return
    if not prem: use_free(ud)
    p = predict(ud['results'], ud['acc'])
    ud['last_pred'] = p
    save(data)
    await update.message.reply_text(fmt_pred(p, None, prem), parse_mode='Markdown')

async def cmd_profile(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    uid = update.effective_user.id
    ud = get_ud(data, uid)
    name = update.effective_user.first_name or "User"
    level = get_level(ud.get('points', 0))
    plan_txt = "Premium 👑" if is_premium(ud, uid) else f"Free ({free_remaining(ud)} left)"
    t = f"👤 *{name}'s PROFILE*\n\n🏅 Level: {level}\n⭐ Points: {ud.get('points',0)}\n📊 Plan: {plan_txt}\n🎯 Total Preds: {ud.get('total_preds',0)}"
    await update.message.reply_text(t, parse_mode='Markdown')

async def cmd_accuracy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    uid = update.effective_user.id
    ud = get_ud(data, uid)
    if not is_premium(ud, uid): await update.message.reply_text("🔒 Premium feature!"); return
    acc = ud.get('acc', [])
    if not acc: await update.message.reply_text("📊 No data yet."); return
    wins = sum(1 for a in acc if a['bs_ok'])
    pct = round(wins/len(acc)*100)
    await update.message.reply_text(f"📊 *ACCURACY:* {pct}% ({wins}/{len(acc)})", parse_mode='Markdown')

async def cmd_history(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    uid = update.effective_user.id
    ud = get_ud(data, uid)
    if not is_premium(ud, uid): await update.message.reply_text("🔒 Premium feature!"); return
    t = "📋 *LAST 10 RESULTS*\n"
    for r in ud.get('results', [])[:10]: t += f"`{r['n']}` - {r['bs']} {r['col'].upper()}\n"
    await update.message.reply_text(t, parse_mode='Markdown')

async def cmd_premium(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    uid = update.effective_user.id
    if is_premium(get_ud(data, uid), uid):
        await update.message.reply_text("👑 *Aap PREMIUM hain!*", parse_mode='Markdown'); return
    await update.message.reply_text(premium_msg(), parse_mode='Markdown', reply_markup=get_premium_keyboard())

async def callback_premium(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    d = query.data
    if d == "premium_game":
        await query.edit_message_text("🎮 *REGISTER & GET FREE PREMIUM*\nDeposit & send screenshot.", parse_mode='Markdown', reply_markup=get_game_keyboard())
    elif d in ["premium_upi49","premium_upi99","premium_upi149"]:
        await query.edit_message_text(f"💳 *UPI ID:* `{UPI_ID}`\nPay & send screenshot.", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="premium_back")]]))
    elif d == "premium_sent":
        await query.edit_message_text("✅ Screenshot bhejo! Verify hote hi access milega.", parse_mode='Markdown')
    elif d == "premium_back":
        await query.edit_message_text(premium_msg(), parse_mode='Markdown', reply_markup=get_premium_keyboard())

# --- Basic commands directly ---
async def cmd_refer(update: Update, ctx: ContextTypes.DEFAULT_TYPE): await update.message.reply_text(f"🎁 *REFERRAL LINK:*\n`https://t.me/{(await ctx.bot.get_me()).username}?start={get_ud(load(), update.effective_user.id).get('referral_code')}`", parse_mode='Markdown')
async def cmd_faq(update: Update, ctx: ContextTypes.DEFAULT_TYPE): await update.message.reply_text("❓ /add se result dalo, /predict se prediction lo.", parse_mode='Markdown')
async def cmd_clear(update: Update, ctx: ContextTypes.DEFAULT_TYPE): 
    data = load()
    uid = str(update.effective_user.id)
    if uid in data: data[uid]['results'] = []; data[uid]['acc'] = []; save(data)
    await update.message.reply_text("🗑 Data cleared!")
async def cmd_leaderboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE): await update.message.reply_text("🏆 Leaderboard is updating...", parse_mode='Markdown')
async def cmd_coupon(update: Update, ctx: ContextTypes.DEFAULT_TYPE): await update.message.reply_text("🎟️ Invalid or expired coupon.")

# --- Admin commands ---
async def cmd_approve(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    try:
        tid = str(ctx.args[0])
        data = load()
        data[tid]['premium'] = True
        save(data)
        await ctx.bot.send_message(chat_id=int(tid), text="🎉 *PREMIUM ACTIVATED!*", parse_mode='Markdown')
        await update.message.reply_text(f"✅ User {tid} Premium!")
    except: pass

async def cmd_reject(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    try: await ctx.bot.send_message(chat_id=int(ctx.args[0]), text="❌ *Payment verify nahi hua!*")
    except: pass

async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    data = load()
    await update.message.reply_text(f"📊 Users: {len([k for k in data if not k.startswith('__')])}")

def main():
    app = Application.builder().token(TOKEN).build()
    
    commands = {
        "start": cmd_start, "add": cmd_add, "result": cmd_result, "predict": cmd_predict,
        "profile": cmd_profile, "accuracy": cmd_accuracy, "history": cmd_history,
        "premium": cmd_premium, "scan": cmd_scan, "analysis": cmd_analysis,
        "refer": cmd_refer, "faq": cmd_faq, "clear": cmd_clear, "leaderboard": cmd_leaderboard,
        "coupon": cmd_coupon, "approve": cmd_approve, "reject": cmd_reject, "stats": cmd_stats
    }
    for cmd, func in commands.items():
        app.add_handler(CommandHandler(cmd, func))
        
    app.add_handler(CallbackQueryHandler(callback_premium, pattern="^premium_"))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    logger.info("Bot started successfully!")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
