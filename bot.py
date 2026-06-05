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
    'first_pred': '🎯 First Prediction',
    'streak_5': '🔥 5 Win Streak',
    'streak_10': '💥 10 Win Streak',
    'accuracy_70': '🎖️ 70% Accuracy',
    'accuracy_80': '🏆 80% Accuracy',
    'predictions_50': '⭐ 50 Predictions',
    'predictions_100': '🌟 100 Predictions',
    'referral_1': '👥 First Referral',
    'referral_5': '👑 5 Referrals',
    'premium_user': '💎 Premium Member',
}

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

WELCOME_MESSAGES = [
    "🔥 Kya baat hai {name} bhai! Tu aa gaya — ab game ka scene badlega! 🎯",
    "💥 Aye {name}! Sahi jagah aaya hai — yahan AI teri madad karega jeetne mein! 🤖",
    "🚀 Welcome {name}! Teri kismat badalne wali hai aaj! AI prediction ready hai! ⚡",
    "🎮 Arrey {name} bhai! Tu bhi smart player hai — AI ke saath khelo aur jeeto! 💰",
    "⚡ Hey {name}! Wingo ka asli secret formula yahan hai — prediction lo aur khelo! 🎯",
    "🌟 {name} bhai aa gaye! Ab prediction bhi hogi aur jeet bhi — guaranteed AI power! 🔥",
    "💎 Welcome {name}! Yeh bot sirf winners ke liye hai — aur tu winner lag raha hai! 🏆",
    "🎯 Aye {name}! Sahi time pe aaya — AI abhi best form mein hai! Chalo khelein! 🚀",
]

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
            'pending_payment': None,
            'points': 0, 'badges': [], 'level': 0,
            'referral_code': None, 'referred_by': None, 'referrals': 0,
            'win_streak': 0, 'max_streak': 0, 'total_preds': 0,
            'banned': False, 'language': 'hi',
            'daily_challenge_done': None, 'joined': datetime.now().isoformat()
        }
        save(data)
    ud = data[uid]
    defaults = {
        'premium': False, 'premium_expiry': None,
        'free_used': 0, 'free_date': None, 'pending_payment': None,
        'points': 0, 'badges': [], 'level': 0,
        'referral_code': None, 'referred_by': None, 'referrals': 0,
        'win_streak': 0, 'max_streak': 0, 'total_preds': 0,
        'banned': False, 'language': 'hi',
        'daily_challenge_done': None, 'joined': datetime.now().isoformat()
    }
    for k, v in defaults.items():
        if k not in ud: ud[k] = v
    # Generate referral code if missing
    if not ud.get('referral_code'):
        ud['referral_code'] = f"REF{uid[-6:]}"
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

def use_free(ud):
    ud['free_used'] = ud.get('free_used', 0) + 1

def free_remaining(ud):
    today = datetime.now().strftime('%Y-%m-%d')
    if ud.get('free_date') != today: return FREE_LIMIT
    return max(0, FREE_LIMIT - ud.get('free_used', 0))

def get_level(points):
    level_name = LEVELS[0][1]
    for pts, name in LEVELS:
        if points >= pts: level_name = name
    return level_name

def add_points(ud, pts):
    ud['points'] = ud.get('points', 0) + pts

def check_badges(ud):
    new_badges = []
    badges = ud.get('badges', [])
    total = ud.get('total_preds', 0)
    acc = ud.get('acc', [])
    wins = sum(1 for a in acc if a.get('bs_ok'))
    n = len(acc)
    pct = round(wins/n*100) if n else 0

    if total >= 1 and 'first_pred' not in badges:
        badges.append('first_pred'); new_badges.append('first_pred')
    if ud.get('win_streak', 0) >= 5 and 'streak_5' not in badges:
        badges.append('streak_5'); new_badges.append('streak_5')
    if ud.get('win_streak', 0) >= 10 and 'streak_10' not in badges:
        badges.append('streak_10'); new_badges.append('streak_10')
    if pct >= 70 and n >= 10 and 'accuracy_70' not in badges:
        badges.append('accuracy_70'); new_badges.append('accuracy_70')
    if pct >= 80 and n >= 10 and 'accuracy_80' not in badges:
        badges.append('accuracy_80'); new_badges.append('accuracy_80')
    if total >= 50 and 'predictions_50' not in badges:
        badges.append('predictions_50'); new_badges.append('predictions_50')
    if total >= 100 and 'predictions_100' not in badges:
        badges.append('predictions_100'); new_badges.append('predictions_100')
    if ud.get('referrals', 0) >= 1 and 'referral_1' not in badges:
        badges.append('referral_1'); new_badges.append('referral_1')
    if ud.get('referrals', 0) >= 5 and 'referral_5' not in badges:
        badges.append('referral_5'); new_badges.append('referral_5')
    if ud.get('premium') and 'premium_user' not in badges:
        badges.append('premium_user'); new_badges.append('premium_user')
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
    # Hot/Cold numbers
    num_counts = Counter(r['n'] for r in all_r[:30])
    hot = [str(x[0]) for x in num_counts.most_common(3)]
    cold = [str(x[0]) for x in num_counts.most_common()[:-4:-1]]
    # Risk meter
    risk = 'LOW 🟢' if conf >= 30 else 'MEDIUM 🟡' if conf >= 15 else 'HIGH 🔴'
    # Smart suggestion
    if wait: suggest = "⏳ WAIT — Pattern unclear"
    elif conf >= 30: suggest = "✅ STRONG signal — Khel sakte ho!"
    elif conf >= 15: suggest = "⚠️ MEDIUM signal — Careful khelo"
    else: suggest = "🛑 SKIP karo — Risky hai!"
    return {
        'bs':pred_bs,'bsc':round(bs_conf),
        'col':pcol,'cc':round(cc),
        'num':pn,'nc':round(nc2),
        'alts':alts,'src':src,'sk':sk,
        'lt':bs[0],'wait':wait,
        'hot':hot,'cold':cold,
        'risk':risk,'suggest':suggest,'conf':conf
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
        t += f"⚠️ Risk: {p['risk']}\n"
        t += f"💡 {p['suggest']}\n"
        t += f"🔴 Hot: `{', '.join(p['hot'])}` | 🔵 Cold: `{', '.join(p['cold'])}`\n"
    else:
        t += f"🔒 *COLOR, NUMBER & more* → Premium only\n"
        t += f"⚠️ Risk: {p['risk']}\n"
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
        "✅ Color prediction 🔴🟢🟣\n"
        "✅ Exact number prediction\n"
        "✅ Alternate numbers\n"
        "✅ Pattern analysis\n"
        "✅ Risk meter LOW/MEDIUM/HIGH\n"
        "✅ Smart suggestion (khelo ya ruko)\n"
        "✅ Hot & Cold numbers\n"
        "✅ Accuracy report /accuracy\n"
        "✅ Full history /history\n"
        "✅ Profile & badges /profile\n"
        "✅ Leaderboard /leaderboard\n\n"
        "💰 *PLANS:*\n"
        "🔹 *₹49* → 5 Days\n"
        "🔹 *₹99* → 15 Days\n"
        "🔹 *₹149* → Lifetime\n\n"
        "🎮 *Game Deposit (FREE Lifetime):*\n"
        "Register + ₹500 deposit → Screenshot bhejo\n\n"
        f"💳 UPI: `{UPI_ID}`\n\n"
        "👇 *Apna option choose karo:*"
    )

def get_premium_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎮 Game Register (FREE Premium)", callback_data="premium_game")],
        [InlineKeyboardButton("💳 UPI ₹49 - 5 Days", callback_data="premium_upi49"),
         InlineKeyboardButton("💳 UPI ₹99 - 15 Days", callback_data="premium_upi99")],
        [InlineKeyboardButton("💳 UPI ₹149 - Lifetime", callback_data="premium_upi149")],
        [InlineKeyboardButton("❓ Already paid? Screenshot bhejo", callback_data="premium_sent")],
    ])

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
    name = update.effective_user.first_name or "Bhai"

    # Referral handling
    args = ctx.args
    if args and args[0].startswith('REF') and not ud.get('referred_by'):
        ref_code = args[0]
        for rid, rud in data.items():
            if rud.get('referral_code') == ref_code and rid != str(uid):
                ud['referred_by'] = rid
                rud['referrals'] = rud.get('referrals', 0) + 1
                add_points(rud, 20)
                new_b = check_badges(rud)
                # Bonus free predictions for referrer
                rud['free_used'] = max(0, rud.get('free_used', 0) - 2)
                try:
                    await ctx.bot.send_message(
                        chat_id=int(rid),
                        text=f"🎉 *Naya referral!*\n\n👤 {name} ne tera link use kiya!\n+20 points mile!\n+2 free predictions bonus! 🎁",
                        parse_mode='Markdown'
                    )
                except: pass
                break

    save(data)
    welcome = random.choice(WELCOME_MESSAGES).format(name=name)
    rem = free_remaining(ud)
    level = get_level(ud.get('points', 0))
    status = "👑 *PREMIUM*" if prem else f"🆓 *FREE* ({rem}/{FREE_LIMIT} left today)"

    t = (
        f"{welcome}\n\n"
        "━━━━━━━━━━━━━━━━━\n"
        "⚡ *WINGO AI PREDICTOR*\n"
        "━━━━━━━━━━━━━━━━━\n\n"
        f"Status: {status}\n"
        f"Level: {level}\n\n"
        "*COMMANDS:*\n"
        "➕ /add `<period> <number>`\n"
        "✅ /result `<number>`\n"
        "🎯 /predict — Prediction lo\n"
        "📊 /accuracy — Accuracy _(Premium)_\n"
        "📋 /history — History _(Premium)_\n"
        "👤 /profile — Tera profile\n"
        "🏆 /leaderboard — Top players\n"
        "🎁 /refer — Referral link\n"
        "🎟️ /coupon — Coupon use karo\n"
        "💎 /premium — Upgrade karo\n"
        "❓ /faq — Help & FAQ\n"
        "🗑 /clear — Data clear\n\n"
        "━━━━━━━━━━━━━━━━━\n"
        "_Start: /add <period> <number>_"
    )
    await update.message.reply_text(t, parse_mode='Markdown')

async def cmd_profile(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    uid = update.effective_user.id
    ud = get_ud(data, uid)
    name = update.effective_user.first_name or "User"
    prem = is_premium(ud, uid)
    acc = ud.get('acc', [])
    wins = sum(1 for a in acc if a.get('bs_ok'))
    n = len(acc)
    pct = round(wins/n*100) if n else 0
    level = get_level(ud.get('points', 0))
    badges = ud.get('badges', [])
    badge_txt = ' '.join([BADGES.get(b,'') for b in badges]) if badges else 'None yet'
    exp = ud.get('premium_expiry')
    if prem and exp:
        exp_str = datetime.fromisoformat(exp).strftime('%d %b %Y')
        plan_txt = f"Premium till {exp_str}"
    elif prem:
        plan_txt = "Lifetime Premium 👑"
    else:
        plan_txt = f"Free ({free_remaining(ud)}/{FREE_LIMIT} left)"

    t = (
        f"━━━━━━━━━━━━━━━━━\n"
        f"👤 *{name}'s PROFILE*\n"
        f"━━━━━━━━━━━━━━━━━\n\n"
        f"🏅 Level: {level}\n"
        f"⭐ Points: {ud.get('points',0)}\n"
        f"📊 Plan: {plan_txt}\n\n"
        f"🎯 Total Predictions: {ud.get('total_preds',0)}\n"
        f"✅ Win Rate: {pct}% ({wins}/{n})\n"
        f"🔥 Best Streak: {ud.get('max_streak',0)}\n"
        f"👥 Referrals: {ud.get('referrals',0)}\n\n"
        f"🏆 *Badges:*\n{badge_txt}\n\n"
        f"📅 Joined: {ud.get('joined','')[:10]}"
    )
    await update.message.reply_text(t, parse_mode='Markdown')

async def cmd_leaderboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    scores = []
    for uid, ud in data.items():
        acc = ud.get('acc', [])
        n = len(acc)
        if n < 5: continue
        wins = sum(1 for a in acc if a.get('bs_ok'))
        pct = round(wins/n*100)
        scores.append((uid, pct, wins, n, ud.get('total_preds',0)))
    scores.sort(key=lambda x: (-x[1], -x[2]))
    t = "🏆 *LEADERBOARD — TOP 10*\n━━━━━━━━━━━━━━━━━\n\n"
    medals = ['🥇','🥈','🥉','4️⃣','5️⃣','6️⃣','7️⃣','8️⃣','9️⃣','🔟']
    for i, (uid, pct, wins, n, total) in enumerate(scores[:10]):
        ud = data[uid]
        name = f"User{uid[-4:]}"
        t += f"{medals[i]} {name} — {pct}% ({wins}/{n})\n"
    if not scores:
        t += "_Abhi koi data nahi hai_"
    await update.message.reply_text(t, parse_mode='Markdown')

async def cmd_refer(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    uid = update.effective_user.id
    ud = get_ud(data, uid)
    save(data)
    ref_code = ud.get('referral_code', f"REF{str(uid)[-6:]}")
    bot_username = (await ctx.bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start={ref_code}"
    t = (
        "🎁 *REFERRAL PROGRAM*\n"
        "━━━━━━━━━━━━━━━━━\n\n"
        f"Tera referral link:\n`{ref_link}`\n\n"
        "📢 Dost ko bhejo — jab join kare:\n"
        "✅ Tujhe +20 points mile\n"
        "✅ Tujhe +2 free predictions bonus\n"
        "✅ 5 referral pe special badge!\n\n"
        f"👥 Abhi tak referrals: *{ud.get('referrals',0)}*"
    )
    await update.message.reply_text(t, parse_mode='Markdown')

async def cmd_coupon(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    uid = update.effective_user.id
    ud = get_ud(data, uid)
    args = ctx.args
    if not args:
        await update.message.reply_text(
            "🎟️ *COUPON*\n\nFormat: `/coupon <CODE>`\nExample: `/coupon WELCOME50`",
            parse_mode='Markdown')
        return
    code = args[0].upper()
    coupons = data.get('__coupons__', {})
    if code not in coupons:
        await update.message.reply_text("❌ Invalid coupon code!", parse_mode='Markdown')
        return
    cp = coupons[code]
    used_by = cp.get('used_by', [])
    if str(uid) in used_by:
        await update.message.reply_text("❌ Ye coupon already use kar chuke ho!", parse_mode='Markdown')
        return
    if cp.get('max_uses') and len(used_by) >= cp['max_uses']:
        await update.message.reply_text("❌ Ye coupon expire ho gaya!", parse_mode='Markdown')
        return
    used_by.append(str(uid))
    cp['used_by'] = used_by
    reward = cp.get('reward', 'free5days')
    if reward == 'free5days':
        ud['premium'] = True
        exp = datetime.now() + timedelta(days=5)
        ud['premium_expiry'] = exp.isoformat()
        msg = "🎉 *Coupon Applied!*\n\n✅ 5 Days Premium activated!"
    elif reward == 'free15days':
        ud['premium'] = True
        exp = datetime.now() + timedelta(days=15)
        ud['premium_expiry'] = exp.isoformat()
        msg = "🎉 *Coupon Applied!*\n\n✅ 15 Days Premium activated!"
    elif reward == 'points100':
        add_points(ud, 100)
        msg = "🎉 *Coupon Applied!*\n\n✅ +100 Points mile!"
    else:
        msg = "🎉 *Coupon Applied!*"
    save(data)
    await update.message.reply_text(msg, parse_mode='Markdown')

async def cmd_faq(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    t = (
        "❓ *FAQ & HELP*\n"
        "━━━━━━━━━━━━━━━━━\n\n"
        "🔹 *Bot kaise use karein?*\n"
        "   /add 10644 7 — result add karo\n"
        "   /predict — prediction lo\n"
        "   /result 7 — verify karo\n\n"
        "🔹 *Premium kaise milega?*\n"
        "   /premium — options dekhо\n\n"
        "🔹 *Free limit kya hai?*\n"
        "   5 predictions/day free\n\n"
        "🔹 *Referral kaise kaam karta hai?*\n"
        "   /refer — link lo, share karo\n\n"
        "🔹 *Coupon kahan se milega?*\n"
        "   Owner se ya special events pe\n\n"
        "🔹 *Data clear hoga kya?*\n"
        "   /clear se sirf results clear hote hain, premium safe rahega\n\n"
        "🔹 *Contact/Support?*\n"
        "   Bot ke andar screenshot bhejo"
    )
    await update.message.reply_text(t, parse_mode='Markdown')

async def cmd_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    args = ctx.args
    if not args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return
    msg = ' '.join(args)
    data = load()
    sent = 0
    failed = 0
    for uid in data.keys():
        if uid.startswith('__'): continue
        try:
            await ctx.bot.send_message(
                chat_id=int(uid),
                text=f"📢 *ANNOUNCEMENT*\n\n{msg}",
                parse_mode='Markdown'
            )
            sent += 1
        except:
            failed += 1
    await update.message.reply_text(f"✅ Broadcast done!\nSent: {sent} | Failed: {failed}")

async def cmd_addcoupon(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    args = ctx.args
    if len(args) < 3:
        await update.message.reply_text(
            "Usage: /addcoupon <CODE> <reward> <max_uses>\n"
            "Rewards: free5days, free15days, points100\n"
            "Example: /addcoupon WELCOME50 free5days 100"
        )
        return
    code = args[0].upper()
    reward = args[1]
    max_uses = int(args[2])
    data = load()
    if '__coupons__' not in data:
        data['__coupons__'] = {}
    data['__coupons__'][code] = {'reward': reward, 'max_uses': max_uses, 'used_by': []}
    save(data)
    await update.message.reply_text(f"✅ Coupon `{code}` created!\nReward: {reward} | Max uses: {max_uses}", parse_mode='Markdown')

async def cmd_ban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    args = ctx.args
    if not args:
        await update.message.reply_text("Usage: /ban <user_id>")
        return
    target_id = str(args[0])
    data = load()
    ud = get_ud(data, target_id)
    ud['banned'] = True
    save(data)
    try:
        await ctx.bot.send_message(chat_id=int(target_id), text="⛔ Aapko bot se ban kar diya gaya hai.")
    except: pass
    await update.message.reply_text(f"⛔ User {target_id} banned!")

async def cmd_unban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    args = ctx.args
    if not args:
        await update.message.reply_text("Usage: /unban <user_id>")
        return
    target_id = str(args[0])
    data = load()
    ud = get_ud(data, target_id)
    ud['banned'] = False
    save(data)
    await update.message.reply_text(f"✅ User {target_id} unbanned!")

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
    await update.message.reply_text(premium_msg(), parse_mode='Markdown', reply_markup=get_premium_keyboard())

async def callback_premium(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    d = query.data

    if d == "premium_game":
        txt = (
            "🎮 *GAME REGISTER KARKE FREE PREMIUM PAO!*\n\n"
            "1️⃣ Neeche se kisi ek game choose karo\n"
            "2️⃣ Register karo\n"
            "3️⃣ Minimum ₹500 deposit karo\n"
            "4️⃣ Screenshot bhejo → *Lifetime Premium!* 🎉"
        )
        await query.edit_message_text(txt, parse_mode='Markdown', reply_markup=get_game_keyboard())

    elif d in ["premium_upi49", "premium_upi99", "premium_upi149"]:
        amt = {"premium_upi49":"₹49 (5 Days)","premium_upi99":"₹99 (15 Days)","premium_upi149":"₹149 (Lifetime)"}[d]
        txt = (
            f"💳 *UPI PAYMENT — {amt}*\n\n"
            f"UPI ID: `{UPI_ID}`\n\n"
            "Steps:\n"
            "1️⃣ UPI ID copy karo\n"
            f"2️⃣ {amt.split('(')[0].strip()} pay karo\n"
            "3️⃣ Screenshot is bot mein bhejo\n"
            "4️⃣ Verify hote hi access milega!\n\n"
            "⚠️ _Screenshot mein amount clearly dikhni chahiye_"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="premium_back")]])
        await query.edit_message_text(txt, parse_mode='Markdown', reply_markup=kb)

    elif d == "premium_sent":
        txt = (
            "✅ *Screenshot bhejo!*\n\n"
            "Is bot mein directly screenshot bhejo.\n"
            "Verify karke access diya jayega.\n\n"
            "⏱ _Thoda time lag sakta hai_"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="premium_back")]])
        await query.edit_message_text(txt, parse_mode='Markdown', reply_markup=kb)

    elif d == "premium_back":
        await query.edit_message_text(premium_msg(), parse_mode='Markdown', reply_markup=get_premium_keyboard())

async def handle_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    uid = update.effective_user.id
    user = update.effective_user
    ud = get_ud(data, uid)

    if is_premium(ud, uid):
        await update.message.reply_text("👑 Aap already Premium hain!", parse_mode='Markdown')
        return

    await update.message.reply_text(
        "📸 *Screenshot mil gaya!*\n\n"
        "⏳ Aapka UID verify ho raha hai, thoda time lag sakta hai.\n"
        "✅ Verify hone ke baad aapko access mil jayega!",
        parse_mode='Markdown'
    )

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
        await ctx.bot.send_message(chat_id=5125916435, text=msg, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Forward error: {e}")

async def cmd_approve(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    args = ctx.args
    if not args:
        await update.message.reply_text("Usage: /approve <user_id> [days]\n0 = Lifetime")
        return
    target_id = str(args[0])
    days = int(args[1]) if len(args) > 1 else PREMIUM_DAYS
    data = load()
    ud = get_ud(data, target_id)
    ud['premium'] = True
    ud['badges'] = ud.get('badges', [])
    if 'premium_user' not in ud['badges']:
        ud['badges'].append('premium_user')
    if days == 0:
        ud['premium_expiry'] = None
        exp_txt = "Lifetime"
    else:
        exp = datetime.now() + timedelta(days=days)
        ud['premium_expiry'] = exp.isoformat()
        exp_txt = exp.strftime('%d %b %Y')
    save(data)
    try:
        await ctx.bot.send_message(
            chat_id=int(target_id),
            text=(
                "🎉 *Congratulations! PREMIUM ACTIVATED!*\n\n"
                f"✅ Payment verify ho gaya!\n"
                f"📅 Expiry: *{exp_txt}*\n\n"
                "Ab unlimited predictions lo!\n"
                "/predict se shuru karo 🚀"
            ),
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Notify error: {e}")
    await update.message.reply_text(f"✅ User {target_id} ko Premium diya! ({exp_txt})")

async def cmd_reject(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
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
                "Screenshot verify nahi ho saka.\n\n"
                "Reasons:\n"
                "• Amount kam tha\n"
                "• Screenshot clear nahi tha\n"
                "• Wrong UPI ID pe payment\n\n"
                "Dobara try karo /premium"
            ),
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Reject error: {e}")
    await update.message.reply_text(f"❌ User {target_id} reject kiya.")

async def cmd_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    args = ctx.args
    if not args:
        await update.message.reply_text("Usage: /cancel <user_id>")
        return
    target_id = str(args[0])
    data = load()
    ud = get_ud(data, target_id)
    ud['premium'] = False
    ud['premium_expiry'] = None
    save(data)
    try:
        await ctx.bot.send_message(
            chat_id=int(target_id),
            text="⚠️ *Aapka Premium Cancel Ho Gaya!*\n\nDobara lene ke liye /premium pe jao.",
            parse_mode='Markdown'
        )
    except: pass
    await update.message.reply_text(f"✅ User {target_id} ka premium cancel kiya!")

async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    data = load()
    total = len([k for k in data.keys() if not k.startswith('__')])
    prem = sum(1 for uid, ud in data.items() if not uid.startswith('__') and ud.get('premium'))
    banned = sum(1 for uid, ud in data.items() if not uid.startswith('__') and ud.get('banned'))
    active_today = 0
    today = datetime.now().strftime('%Y-%m-%d')
    for uid, ud in data.items():
        if uid.startswith('__'): continue
        if ud.get('free_date') == today and ud.get('free_used', 0) > 0:
            active_today += 1
    coupons = data.get('__coupons__', {})
    await update.message.reply_text(
        f"📊 *BOT STATS*\n\n"
        f"👥 Total Users: {total}\n"
        f"👑 Premium Users: {prem}\n"
        f"🆓 Free Users: {total - prem}\n"
        f"⚡ Active Today: {active_today}\n"
        f"⛔ Banned: {banned}\n"
        f"🎟️ Coupons: {len(coupons)}",
        parse_mode='Markdown'
    )

async def cmd_add(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    uid = update.effective_user.id
    ud = get_ud(data, uid)

    if ud.get('banned'):
        await update.message.reply_text("⛔ Aap ban hain.")
        return

    prem = is_premium(ud, uid)
    args = ctx.args
    if not args or len(args) < 2:
        await update.message.reply_text("❌ Format: `/add <period> <number>`\nExample: `/add 10644 7`", parse_mode='Markdown')
        return
    try:
        period = args[0]
        n = int(args[1])
        if not 0 <= n <= 9: raise ValueError
    except:
        await update.message.reply_text("❌ Number must be 0-9", parse_mode='Markdown')
        return

    if not prem:
        if not check_free_limit(ud):
            save(data)
            await update.message.reply_text(premium_msg(), parse_mode='Markdown', reply_markup=get_premium_keyboard())
            return
        use_free(ud)

    entry = {'n':n,'period':period,'bs':'BIG' if is_big(n) else 'SMALL','col':get_col(n)}
    ud['results'].insert(0, entry)
    if len(ud['results'])>500: ud['results'].pop()
    ud['total_preds'] = ud.get('total_preds', 0) + 1
    add_points(ud, 2)
    new_badges = check_badges(ud)
    p = predict(ud['results'], ud['acc'])
    ud['last_pred'] = p
    save(data)

    ce = {'red':'🔴','green':'🟢','violet':'🟣'}
    be = '🔵' if is_big(n) else '🔴'
    rem_txt = "" if prem else f"\n🆓 Free left today: *{free_remaining(ud)}*"
    added = (f"✅ *Added!*\n"
             f"Period: `{period}` | {be} `{n}` {'BIG' if is_big(n) else 'SMALL'} "
             f"{ce.get(get_col(n),'⚪')} {get_col(n).upper()}\n"
             f"⭐ Points: {ud.get('points',0)} | {get_level(ud.get('points',0))}{rem_txt}\n\n")
    await update.message.reply_text(added + fmt_pred(p, period, prem), parse_mode='Markdown')

    if new_badges:
        badge_txt = '\n'.join([f"🏅 {BADGES.get(b,'')}" for b in new_badges])
        await update.message.reply_text(f"🎉 *New Badge Earned!*\n\n{badge_txt}", parse_mode='Markdown')

    if not prem and free_remaining(ud) == 0:
        await update.message.reply_text(
            "⚠️ *Aaj ki free predictions khatam!*\nKal dobara aao ya Premium lo 👇",
            parse_mode='Markdown', reply_markup=get_premium_keyboard()
        )

async def cmd_result(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    uid = update.effective_user.id
    ud = get_ud(data, uid)
    prem = is_premium(ud, uid)

    args = ctx.args
    if not args:
        await update.message.reply_text("❌ Format: `/result <number>`", parse_mode='Markdown')
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

        # Streak tracking
        if bs_ok:
            ud['win_streak'] = ud.get('win_streak', 0) + 1
            if ud['win_streak'] > ud.get('max_streak', 0):
                ud['max_streak'] = ud['win_streak']
            add_points(ud, 5)
        else:
            ud['win_streak'] = 0

        new_badges = check_badges(ud)
        wins = sum(1 for a in ud['acc'] if a['bs_ok'])
        tot = len(ud['acc'])
        pct = round(wins/tot*100) if tot else 0
        streak = ud.get('win_streak', 0)
        streak_txt = f"🔥 Streak: {streak}" if streak > 1 else ""

        if bs_ok and col_ok:
            fb = "✅ *PERFECT! BIG/SMALL + Color correct!* 🎉"
        elif bs_ok:
            fb = f"✅ *BIG/SMALL correct!*\nColor: pred {p['col'].upper()} → got {abs_col.upper()}"
        else:
            fb = f"❌ *WRONG*\nPred: {p['bs']} {p['col'].upper()} → Got: {abs_bs} {abs_col.upper()}\nAI learning..."
        txt = f"{fb}\n📊 Accuracy: *{pct}%* ({wins}/{tot}) {streak_txt}\n\n"

        if new_badges:
            badge_txt = '\n'.join([f"🏅 {BADGES.get(b,'')}" for b in new_badges])
            txt += f"🎉 *New Badge!* {badge_txt}\n\n"

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
        await update.message.reply_text(premium_msg(), parse_mode='Markdown', reply_markup=get_premium_keyboard())
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
        await update.message.reply_text("🔒 *Accuracy report Premium feature hai!*\n\n/premium se upgrade karo.", parse_mode='Markdown', reply_markup=get_premium_keyboard())
        return
    acc = ud['acc']
    if not acc:
        await update.message.reply_text("📊 No data yet. Use /result after each round.", parse_mode='Markdown')
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
         f"✅ Hit: {wins} | ❌ Miss: {n-wins} | 📈 Total: {n}\n"
         f"🔥 Best Streak: {ud.get('max_streak',0)}\n\n")
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
        await update.message.reply_text("🔒 *History Premium feature hai!*\n\n/premium se upgrade karo.", parse_mode='Markdown', reply_markup=get_premium_keyboard())
        return
    if not ud['results']:
        await update.message.reply_text("No results yet.", parse_mode='Markdown')
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
        pts = data[uid].get('points', 0)
        badges = data[uid].get('badges', [])
        ref_code = data[uid].get('referral_code')
        referrals = data[uid].get('referrals', 0)
        data[uid] = {
            'results':[],'acc':[],'last_pred':None,
            'premium':prem,'premium_expiry':exp,
            'free_used':0,'free_date':None,'pending_payment':None,
            'points':pts,'badges':badges,'level':0,
            'referral_code':ref_code,'referred_by':None,'referrals':referrals,
            'win_streak':0,'max_streak':0,'total_preds':0,
            'banned':False,'language':'hi',
            'daily_challenge_done':None,'joined':datetime.now().isoformat()
        }
        save(data)
    await update.message.reply_text("🗑 Data cleared! (Premium & points safe hain)", parse_mode='Markdown')

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
    app.add_handler(CommandHandler("profile", cmd_profile))
    app.add_handler(CommandHandler("leaderboard", cmd_leaderboard))
    app.add_handler(CommandHandler("refer", cmd_refer))
    app.add_handler(CommandHandler("coupon", cmd_coupon))
    app.add_handler(CommandHandler("faq", cmd_faq))
    app.add_handler(CommandHandler("approve", cmd_approve))
    app.add_handler(CommandHandler("reject", cmd_reject))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CommandHandler("ban", cmd_ban))
    app.add_handler(CommandHandler("unban", cmd_unban))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))
    app.add_handler(CommandHandler("addcoupon", cmd_addcoupon))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("help", cmd_start))
    app.add_handler(CallbackQueryHandler(callback_premium, pattern="^premium_"))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    logger.info("Bot started!")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
