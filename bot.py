import os
import json
import logging
from datetime import datetime
from collections import Counter
from telegram import Update
from telegram.ext import (
    Application, CommandHandler,
    ContextTypes, MessageHandler, filters
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN", "8724922311:AAHbErc51Ly8sJN9pYPxyRwy-aZwojC8Cj0")
DATA_FILE = "data.json"

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
            json.dump(data,f)
    except Exception as e:
        logger.error(f"Save error: {e}")

def get_ud(data, uid):
    uid = str(uid)
    if uid not in data:
        data[uid] = {'results':[], 'acc':[], 'last_pred':None}
    return data[uid]

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

def fmt_pred(p, period=None):
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
    t += f"{ce.get(p['col'],'⚪')} *COLOR:* `{p['col'].upper()}` — {p['cc']}%\n"
    t += f"🎯 *NUMBER:* `{p['num']}` — {p['nc']}%\n"
    t += f"🔢 *Alternates:* `{', '.join(map(str,p['alts']))}`\n"
    t += f"\n📊 Pattern: `{p['src']}`\n"
    t += f"🔥 Streak: `{p['sk']}× {p['lt']}`\n"
    t += "\n━━━━━━━━━━━━━━━━━\n"
    t += "_Verify with: /result <number>_"
    return t

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    t = ("🎮 *WINGO AI PREDICTOR*\n"
         "━━━━━━━━━━━━━━━━━\n\n"
         "Self-learning N-gram predictor\n\n"
         "*COMMANDS:*\n"
         "➕ /add `<period> <number>`\n"
         "    _e.g. /add 10644 7_\n\n"
         "✅ /result `<number>`\n"
         "    _e.g. /result 7_\n\n"
         "🎯 /predict — Get prediction\n"
         "📊 /accuracy — Accuracy report\n"
         "📋 /history — Last 10 results\n"
         "🗑 /clear — Clear my data\n\n"
         "━━━━━━━━━━━━━━━━━\n"
         "_Start: /add <period> <number>_")
    await update.message.reply_text(t, parse_mode='Markdown')

async def cmd_add(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    uid = update.effective_user.id
    ud = get_ud(data, uid)
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
    entry = {'n':n,'period':period,'bs':'BIG' if is_big(n) else 'SMALL','col':get_col(n)}
    ud['results'].insert(0, entry)
    if len(ud['results'])>500: ud['results'].pop()
    p = predict(ud['results'], ud['acc'])
    ud['last_pred'] = p
    save(data)
    ce = {'red':'🔴','green':'🟢','violet':'🟣'}
    be = '🔵' if is_big(n) else '🔴'
    added = (f"✅ *Added!*\n"
             f"Period: `{period}` | {be} `{n}` {('BIG' if is_big(n) else 'SMALL')} "
             f"{ce.get(get_col(n),'⚪')} {get_col(n).upper()}\n"
             f"Total: {len(ud['results'])} results\n\n")
    await update.message.reply_text(added + fmt_pred(p, period), parse_mode='Markdown')

async def cmd_result(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    uid = update.effective_user.id
    ud = get_ud(data, uid)
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
    txt += fmt_pred(new_p)
    await update.message.reply_text(txt, parse_mode='Markdown')

async def cmd_predict(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    uid = update.effective_user.id
    ud = get_ud(data, uid)
    p = predict(ud['results'], ud['acc'])
    ud['last_pred'] = p
    save(data)
    period = ud['results'][0].get('period','') if ud['results'] else None
    await update.message.reply_text(fmt_pred(p, period), parse_mode='Markdown')

async def cmd_accuracy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    uid = update.effective_user.id
    ud = get_ud(data, uid)
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
        data[uid] = {'results':[],'acc':[],'last_pred':None}
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
    app.add_handler(CommandHandler("help", cmd_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    logger.info("Bot started!")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
