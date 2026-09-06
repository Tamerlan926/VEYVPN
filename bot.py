#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, sys, json, uuid, asyncio, random, logging, time
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()

import qrcode, aiosqlite, httpx
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest
from aiogram.client.default import DefaultBotProperties
from yookassa import Configuration, Payment

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class Config:
    BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "")
    SERVER_HOST = os.getenv("SERVER_HOST", "185.23.238.20")
    TARGET_PORT = int(os.getenv("TARGET_PORT", "8443"))
    TARGET_INBOUND_ID = int(os.getenv("TARGET_INBOUND_ID", "7"))
    XUI_BASE_URL = os.getenv("XUI_PANEL_URL", "").rstrip("/")
    XUI_USER = os.getenv("XUI_PANEL_USER", "")
    XUI_PASS = os.getenv("XUI_PANEL_PASS", "")
    REALITY_PUBKEY = os.getenv("REALITY_PUBKEY", "")
    REALITY_SHORT_IDS = [x.strip() for x in os.getenv("REALITY_SHORT_IDS", "").split(",") if x.strip()]
    REALITY_SNI = os.getenv("REALITY_SNI", "aws.amazon.com")
    REALITY_FP = os.getenv("REALITY_FP", "chrome")
    PRICES = {"1_day": 0, "1_month": 99, "3_months": 250, "6_months": 450, "1_year": 799}
    YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID", "")
    YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY", "")
    DB_PATH = "data/shadowvpn.db"
    SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "@Ghost18274")
    SERVER_NAME = "ВЕЙVPN"
    BOT_ADMINS = [int(x.strip()) for x in os.getenv("BOT_ADMINS", "").split(",") if x.strip()]

async def init_db():
    os.makedirs(os.path.dirname(Config.DB_PATH), exist_ok=True)
    async with aiosqlite.connect(Config.DB_PATH) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS users (
            tg_id INTEGER PRIMARY KEY, username TEXT, email TEXT, vpn_key TEXT,
            expire_date TEXT, is_active INTEGER DEFAULT 0, trial_used INTEGER DEFAULT 0,
            promo_shakriev_used INTEGER DEFAULT 0, promo_shakrievt_active INTEGER DEFAULT 0,
            promo_shakrievtz_active INTEGER DEFAULT 0, promo_king_used INTEGER DEFAULT 0,
            promo_halalsh_used INTEGER DEFAULT 0, referred_by INTEGER DEFAULT NULL,
            last_active TEXT, created_at TEXT)""")
        try: await db.execute("ALTER TABLE users ADD COLUMN last_active TEXT")
        except: pass
        try: await db.execute("ALTER TABLE users ADD COLUMN promo_halalsh_used INTEGER DEFAULT 0")
        except: pass
        try: await db.execute("ALTER TABLE users ADD COLUMN referred_by INTEGER DEFAULT NULL")
        except: pass
        await db.execute("""CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT, tg_id INTEGER, amount INTEGER,
            period TEXT, yookassa_id TEXT, status TEXT DEFAULT 'pending', created_at TEXT, paid_at TEXT)""")
        try: await db.execute("ALTER TABLE payments ADD COLUMN paid_at TEXT")
        except: pass
        await db.execute("""CREATE TABLE IF NOT EXISTS counter (
            id INTEGER PRIMARY KEY, current_val INTEGER DEFAULT 0)""")
        await db.execute("INSERT OR IGNORE INTO counter (id, current_val) VALUES (1, 0)")
        await db.commit()
    logger.info("✅ Database initialized")

async def get_user(tid):
    async with aiosqlite.connect(Config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        r = await db.execute("SELECT * FROM users WHERE tg_id=?", (tid,))
        row = await r.fetchone()
        return dict(row) if row else None

async def create_user(tid, un="", ref_by=None):
    async with aiosqlite.connect(Config.DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users (tg_id,username,created_at,last_active,referred_by) VALUES (?,?,?,?,?)", 
                        (tid, un, datetime.now().isoformat(), datetime.now().isoformat(), ref_by))
        if ref_by:
            try:
                cur = await db.execute("SELECT expire_date, is_active FROM users WHERE tg_id=?", (ref_by,))
                row = await cur.fetchone()
                if row:
                    exp_str = row["expire_date"]
                    is_active = row["is_active"]
                    current_exp = datetime.fromisoformat(exp_str) if exp_str and is_active else datetime.now()
                    new_exp = current_exp + timedelta(days=7)
                    new_exp_str = new_exp.strftime("%Y-%m-%d %H:%M:%S")
                    await db.execute("UPDATE users SET expire_date=?, is_active=1 WHERE tg_id=?", (new_exp_str, ref_by))
                    logger.info(f"🎁 Ref bonus: +7 days for user {ref_by}")
                    try: await bot.send_message(ref_by, f"🎉 <b>Bonus received!</b>\nFriend joined.\n<b>7 days</b> added!")
                    except: pass
            except Exception as e: logger.error(f"Ref error: {e}")
        await db.commit()

async def update_user(tid, **kw):
    if not kw: return
    async with aiosqlite.connect(Config.DB_PATH) as db:
        s = ", ".join(f"{k}=?" for k in kw); v = list(kw.values())+[tid]
        await db.execute(f"UPDATE users SET {s} WHERE tg_id=?", v); await db.commit()

async def track_activity(tid):
    async with aiosqlite.connect(Config.DB_PATH) as db:
        await db.execute("UPDATE users SET last_active=? WHERE tg_id=?", (datetime.now().isoformat(), tid))
        await db.commit()

async def log_pay(tid, amt, per, yid):
    async with aiosqlite.connect(Config.DB_PATH) as db:
        await db.execute("INSERT INTO payments (tg_id,amount,period,yookassa_id,created_at) VALUES (?,?,?,?,?)", 
                        (tid,amt,per,yid,datetime.now().isoformat())); await db.commit()

async def upd_pay(yid, st):
    async with aiosqlite.connect(Config.DB_PATH) as db:
        await db.execute("UPDATE payments SET status=?, paid_at=? WHERE yookassa_id=?", 
                        (st, datetime.now().isoformat() if st=="paid" else None, yid)); await db.commit()

async def get_pay(yid):
    async with aiosqlite.connect(Config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        r = await db.execute("SELECT * FROM payments WHERE yookassa_id=?", (yid,)); row = await r.fetchone()
        return dict(row) if row else None

async def get_next_client_number():
    async with aiosqlite.connect(Config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("BEGIN IMMEDIATE")
        cur = await db.execute("SELECT current_val FROM counter WHERE id=1")
        row = await cur.fetchone()
        next_num = (row["current_val"] if row else 0) + 1
        await db.execute("UPDATE counter SET current_val=? WHERE id=1", (next_num,))
        await db.commit()
        return next_num

async def trial_ok(tid): u = await get_user(tid); return u and u.get("trial_used",0)==0
async def use_trial(tid): await update_user(tid, trial_used=1)

class XUI:
    def __init__(self): self.base, self.u, self.p, self.c, self.ok = Config.XUI_BASE_URL, Config.XUI_USER, Config.XUI_PASS, None, False
    async def __aenter__(self): self.c = httpx.AsyncClient(verify=False, timeout=30, follow_redirects=True, cookies=httpx.Cookies()); return self
    async def __aexit__(self,*a): 
        if self.c: await self.c.aclose()
    def _json(self,t):
        try: t=t.strip(); s,e=t.find("{"),t.rfind("}")+1; return json.loads(t[s:e] if s!=-1 and e!=0 else t)
        except: return None
    async def login(self):
        try:
            r = await self.c.post(f"{self.base}/login", data={"username":self.u,"password":self.p}, headers={"Content-Type":"application/x-www-form-urlencoded"})
            d = self._json(r.text); self.ok = d.get("success") if d else False; return self.ok
        except Exception as e: logger.error(f"❌ Login: {e}"); return False
    async def add_cl(self, iid, email, cuid, exp, tid):
        if not self.ok and not await self.login(): return False
        try:
            r = await self.c.get(f"{self.base}/panel/api/inbounds/get/{iid}")
            ib = self._json(r.text)
            if not ib or not ib.get("success"): return False
            inbound = ib.get("obj")
            if not inbound: return False
            settings = inbound.get("settings", {})
            if isinstance(settings, str):
                try: settings = json.loads(settings)
                except: return False
            prefix = f"VEYVPN-{tid}-"
            settings["clients"] = [c for c in settings.get("clients", []) if not c.get("email", "").startswith(prefix)]
            new_client = {
                "id": cuid, "email": email, "flow": "xtls-rprx-vision",
                "limitIp": 0, "totalGB": 0, "expiryTime": exp,
                "enable": True, "tgId": "", "subId": ""
            }
            settings.setdefault("clients", []).append(new_client)
            payload = {
                "id": iid, "port": inbound.get("port"), "protocol": inbound.get("protocol"),
                "settings": json.dumps(settings, ensure_ascii=False),
                "streamSettings": inbound.get("streamSettings"),
                "sniffing": inbound.get("sniffing"), "remark": inbound.get("remark"),
                "enable": True, "expiryTime": 0, "total": 0,
                "listen": inbound.get("listen", ""), "tag": inbound.get("tag", "")
            }
            r = await self.c.post(f"{self.base}/panel/api/inbounds/update/{iid}", 
                                data=payload, headers={"Content-Type":"application/x-www-form-urlencoded"})
            d = self._json(r.text)
            if d and d.get("success"):
                logger.info(f"✅ Client {email} added")
                await self.c.post(f"{self.base}/panel/api/inbounds/restart", 
                                headers={"Content-Type":"application/x-www-form-urlencoded"})
                return True
            else:
                logger.error(f"❌ Update failed: {d.get('msg') if d else r.text[:200]}")
                return False
        except Exception as e: 
            logger.error(f" Add client error: {e}")
            return False

def link(em, cu, pt):
    sid = random.choice(Config.REALITY_SHORT_IDS) if Config.REALITY_SHORT_IDS else ""
    return f"vless://{cu}@{Config.SERVER_HOST}:{pt}?type=tcp&security=reality&flow=xtls-rprx-vision&pbk={Config.REALITY_PUBKEY}&sid={sid}&fp={Config.REALITY_FP}&sni={Config.REALITY_SNI}#{em}"

bot = Bot(token=Config.BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

WELCOME = f""" <b>{Config.SERVER_NAME} — Premium VPN</b>

⚡ <b>Why us?</b>
• Instant key issuance
• VLESS + Reality protocol
• Speed up to 100 Mbps
• Full anonymity & no logs

 <b>Tariffs:</b>
 1 day — Free test
💰 1 month — 99₽
🔥 3 months — 250₽
⚡ 6 months — 450₽
👑 1 year — 799₽

 Support: {Config.SUPPORT_USERNAME}"""

SETUP_TEXT = """📱 <b>Setup VEYVPN</b>

📲 <b>Recommended app: Happ</b>
(Also: Hiddify, Streisand, FoXray, v2rayNG)

<b>1️ Download app:</b>
 iPhone: App Store → Happ
🤖 Android: Happ.apk / v2rayNG

<b>2️ Add connection:</b>
• Tap "+" → "Import" or paste key
• Or scan QR-code

<b>3️⃣ Connect:</b>
• Select profile → "Connect" • Done! 🎉

️ <b>Settings:</b> DNS: 8.8.8.8 | Route: Global | Mux: Off"""

FAQ_TEXT = f"""❓ <b>FAQ</b>

<b>Q: How to extend subscription?</b>
A: Buy new period in "Buy VPN" section.

<b>Q: How many devices?</b>
A: Unlimited.

<b>Q: Traffic limit?</b>
A: No limit, unlimited traffic.

💬 Support: {Config.SUPPORT_USERNAME}"""

def kb_main():
    k = InlineKeyboardBuilder()
    k.button(text=" My Subscription", web_app=types.WebAppInfo(url="https://prismatic-cucurucho-d9e591.netlify.app/app.html"))
    k.button(text="🛒 Buy", callback_data="buy")
    k.button(text="🔑 Keys", callback_data="my_keys")
    k.button(text="📱 Setup", callback_data="setup")
    k.button(text="💬 Promo", callback_data="promo_info")
    k.button(text="❓ FAQ", callback_data="faq")
    k.adjust(1,2,2)
    return k.as_markup()

def kb_main_tariffs():
    k = InlineKeyboardBuilder()
    k.button(text="🆓 1 day (test)", callback_data="buy_1_day")
    k.button(text="💰 1 mo | 99₽", callback_data="buy_1_month")
    k.button(text=" 3 mo | 250₽", callback_data="buy_3_months")
    k.button(text="⚡ 6 mo | 450₽", callback_data="buy_6_months")
    k.button(text="👑 1 yr | 799₽", callback_data="buy_1_year")
    k.button(text="🔙 Back", callback_data="back")
    k.adjust(1); return k.as_markup()

@dp.message(Command("start"))
async def start(m: types.Message):
    tid, un = m.from_user.id, m.from_user.username or ""
    ref_id = None
    if m.text and len(m.text.split()) > 1:
        arg = m.text.split()[1]
        if arg.startswith("ref_"):
            try: ref_id = int(arg.split("_")[1])
            except: pass
    await create_user(tid, un, ref_id)
    await track_activity(tid)
    logging.info(f"🆕 New: {tid} (Ref by: {ref_id})")
    async with aiosqlite.connect(Config.DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM users")
        total = (await cur.fetchone())[0]
    welcome_text = "<b>" + str(total) + " users</b>\n\n" + WELCOME
    await m.answer(welcome_text, reply_markup=kb_main())

@dp.callback_query(F.data=="back")
async def back(cb: types.CallbackQuery):
    try: await cb.message.edit_text(WELCOME, reply_markup=kb_main())
    except: await cb.answer()

@dp.callback_query(F.data=="profile")
async def prof(cb: types.CallbackQuery):
    u = await get_user(cb.from_user.id)
    if not u: return await cb.answer("❌", show_alert=True)
    st = "🟢 "+u["expire_date"].split()[0] if u.get("is_active") and u.get("expire_date") and datetime.fromisoformat(u["expire_date"])>datetime.now() else "❌"
    txt = f"👤 <b>Profile</b>\n🆔 <code>{cb.from_user.id}</code>\n <code>{u.get('email') or '—'}</code>\n⏳ {st}"
    k = InlineKeyboardBuilder(); k.button(text="🔑 Keys", callback_data="my_keys"); k.button(text="🔙 Back", callback_data="back"); k.adjust(2)
    try: await cb.message.edit_text(txt, reply_markup=k.as_markup())
    except: await cb.answer()

@dp.callback_query(F.data=="buy")
async def buy(cb: types.CallbackQuery):
    try: await cb.message.edit_text("💎 <b>Select Tariff</b>", reply_markup=kb_main_tariffs())
    except: await cb.answer()

@dp.callback_query(F.data.startswith("buy_"))
async def do_buy(cb: types.CallbackQuery):
    tid, per = cb.from_user.id, cb.data.split("_", 1)[1]
    u = await get_user(tid)
    if not u: return await cb.answer("❌ Error", show_alert=True)
    if per == "1_day":
        if not await trial_ok(tid): return await cb.answer("⚠️ Test already used!", show_alert=True)
        await use_trial(tid)
        return await make_sub(cb.message if hasattr(cb,'message') else cb, tid, 1)
    base_price = Config.PRICES.get(per, 99)
    final_price = base_price
    discount_msg = ""
    if u.get("promo_shakrievtz_active"):
        final_price = int(base_price * 0.9)
        discount_msg = " (-10% ShakrievTZ)"
        await update_user(tid, promo_shakrievtz_active=0)
    elif per == "1_month" and u.get("promo_shakrievt_active"):
        final_price = int(base_price * 0.95)
        discount_msg = " (-5% ShakrievT)"
        await update_user(tid, promo_shakrievt_active=0)
    days = {"1_month":30,"3_months":90,"6_months":180,"1_year":365}.get(per, 0)
    try: await cb.message.edit_text(" Creating payment...")
    except: pass
    try:
        Configuration.account_id = Config.YOOKASSA_SHOP_ID
        Configuration.secret_key = Config.YOOKASSA_SECRET_KEY
        bm = await bot.get_me()
        pay = await asyncio.to_thread(Payment.create, {"amount":{"value":f"{final_price}.00","currency":"RUB"},"confirmation":{"type":"redirect","return_url":f"https://t.me/{bm.username}"},"capture":True,"description":f"{Config.SERVER_NAME} {per}{discount_msg}"})
        await log_pay(tid, final_price, per, pay.id)
        kb = InlineKeyboardBuilder()
        kb.button(text="💳 Pay", url=pay.confirmation.confirmation_url)
        kb.button(text="✅ I paid", callback_data=f"check_{pay.id}")
        kb.button(text=" Back", callback_data="buy"); kb.adjust(1)
        await cb.message.edit_text(f"💳 <b>Payment</b>\n💰 {final_price}₽ |  {days} days\n <code>{pay.id}</code>{discount_msg}", reply_markup=kb.as_markup())
    except Exception as e: 
        logger.error(f" YooKassa: {e}")
        await cb.message.edit_text("❌ Payment creation error.")

@dp.callback_query(F.data.startswith("check_"))
async def check(cb: types.CallbackQuery):
    pid, tid = cb.data.split("_")[1], cb.from_user.id
    await cb.answer("⏳ Checking...", show_alert=True)
    try:
        pd = await get_pay(pid)
        if not pd: return await cb.message.edit_text("❌ Payment not found")
        Configuration.account_id = Config.YOOKASSA_SHOP_ID
        Configuration.secret_key = Config.YOOKASSA_SECRET_KEY
        pay = await asyncio.to_thread(Payment.find_one, pid)
        if pay.status == 'succeeded':
            per = pd.get("period","1_month")
            days = {"1_day":1,"1_month":30,"3_months":90,"6_months":180,"1_year":365}.get(per,30)
            await upd_pay(pid,"paid")
            await cb.message.edit_text("✅ <b>Payment confirmed!</b>\nCreating connection...")
            await make_sub(cb.message, tid, days)
        elif pay.status == 'pending':
            await cb.message.edit_text(" Payment pending...")
        else:
            await cb.message.edit_text(f"❌ Status: {pay.status}")
    except Exception as e: 
        logger.error(f"❌ Check error: {e}")
        await cb.message.edit_text(f"❌ Verification error\nID: <code>{pid}</code>")

async def make_sub(msg, tid, days):
    try: await msg.edit_text(" Creating connection...")
    except: await msg.answer(" Creating connection...")
    num = await get_next_client_number()
    em = f"🚀 VEYVPN-{num}"
    cu = str(uuid.uuid4())
    exp_t = int((datetime.now()+timedelta(days=days)).timestamp()*1000)
    exp_d = (datetime.now()+timedelta(days=days)).strftime("%Y-%m-%d %H:%M")
    async with XUI() as api:
        if not await api.add_cl(Config.TARGET_INBOUND_ID, em, cu, exp_t, tid): 
            return await msg.answer(" Connection creation error")
    lnk = link(em, cu, Config.TARGET_PORT)
    await update_user(tid, email=em, vpn_key=lnk, expire_date=exp_d, is_active=1)
    qr = qrcode.make(lnk); qp = f"/tmp/qr_{tid}.png"; qr.save(qp,"PNG")
    k = InlineKeyboardBuilder()
    k.button(text=" Setup", callback_data="setup")
    k.button(text=" Keys", callback_data="my_keys")
    k.button(text="🔙 Menu", callback_data="back")
    k.adjust(1,2)
    await msg.answer(f"<code>{lnk}</code>")
    await msg.answer_photo(FSInputFile(qp), caption="📱 Scan QR or tap button below")
    kb_app = InlineKeyboardBuilder()
    kb_app.button(text=" Open in Hiddify", url=f"hiddify://import/{lnk}")
    kb_app.button(text=" Open in Streisand", url=f"streisand://import/{lnk}")
    kb_app.adjust(1)
    await msg.answer(f"✅ <b>Activated!</b>\n📧 <code>{em}</code>\n⏳ Until: <code>{exp_d}</code>\n\n👇 <b>Tap to add to app:</b>", reply_markup=kb_app.as_markup())
    try: os.remove(qp)
    except: pass

@dp.callback_query(F.data=="my_keys")
async def keys(cb: types.CallbackQuery):
    u = await get_user(cb.from_user.id)
    if not u or not u.get("vpn_key"):
        k = InlineKeyboardBuilder(); k.button(text="🛒 Buy", callback_data="buy"); k.button(text=" Back", callback_data="back")
        try: await cb.message.edit_text("❌ <b>No active keys</b>", reply_markup=k.as_markup())
        except: await cb.answer()
        return
    k = InlineKeyboardBuilder(); k.button(text=" Show", callback_data="show_key"); k.button(text=" Back", callback_data="back"); k.adjust(1)
    try: await cb.message.edit_text(f"🔑 <b>Your Key</b>\n📧 <code>{u['email']}</code>", reply_markup=k.as_markup())
    except: await cb.answer()

@dp.callback_query(F.data=="show_key")
async def show_key(cb: types.CallbackQuery):
    u = await get_user(cb.from_user.id)
    if not u or not u.get("vpn_key"): return await cb.answer("❌", show_alert=True)
    await cb.answer(f" {u['vpn_key']}", show_alert=True)

@dp.callback_query(F.data=="setup")
async def setup(cb: types.CallbackQuery):
    k = InlineKeyboardBuilder(); k.button(text="🔙 Back", callback_data="back")
    try: await cb.message.edit_text(SETUP_TEXT, reply_markup=k.as_markup())
    except: await cb.answer()

@dp.callback_query(F.data=="faq")
async def faq(cb: types.CallbackQuery):
    k = InlineKeyboardBuilder(); k.button(text=" Back", callback_data="back")
    try: await cb.message.edit_text(FAQ_TEXT, reply_markup=k.as_markup())
    except: await cb.answer()

@dp.callback_query(F.data=="promo_info")
async def promo_info(cb: types.CallbackQuery):
    await cb.answer()
    await cb.message.answer(f" <b>How to get promo?</b>\n\nContact admin: {Config.SUPPORT_USERNAME}\nThen type:\n<code>/promo your_code</code>")

@dp.message(Command("promo"))
async def cmd_promo(msg: types.Message):
    args = msg.text.split()
    if len(args) < 2: return await msg.answer(" Example: <code>/promo Shakriev</code>")
    tid, code = msg.from_user.id, args[1].strip().upper()
    u = await get_user(tid)
    if not u: return await msg.answer("❌ First /start")
    if code == "SHAKRIEV":
        if u.get("promo_shakriev_used"): return await msg.answer("⚠️ Already used Shakriev!")
        await update_user(tid, promo_shakriev_used=1)
        await msg.answer("✅ <b>Shakriev</b> activated!\n🎁 Creating 7-day access...")
        await make_sub(msg, tid, 7)
    elif code == "SHAKRIEVT":
        if u.get("promo_shakrievt_active"): return await msg.answer("️ ShakrievT discount already active!")
        await update_user(tid, promo_shakrievt_active=1)
        price = int(99 * 0.95)
        kb = InlineKeyboardBuilder(); kb.button(text=f"💳 1 month | {price}₽", callback_data="buy_1_month"); kb.button(text=" Menu", callback_data="back"); kb.adjust(1)
        await msg.answer("✅ <b>ShakrievT</b> activated!\n💸 -5% discount on 1 month.")
        await msg.answer(f"🎉 <b>Discounted Tariff:</b>\n💰 1 month — <b>{price}₽</b>", reply_markup=kb.as_markup())
    elif code == "SHAKRIEVTZ":
        if u.get("promo_shakrievtz_active"): return await msg.answer("⚠️ ShakrievTZ discount already active!")
        await update_user(tid, promo_shakrievtz_active=1)
        prices = {"1_month": int(99*0.9), "3_months": int(250*0.9), "6_months": int(450*0.9), "1_year": int(799*0.9)}
        kb = InlineKeyboardBuilder()
        for p in ["1_month", "3_months", "6_months", "1_year"]:
            days = {"1_month":30, "3_months":90, "6_months":180, "1_year":365}[p]
            kb.button(text=f"💳 {days} days | {prices[p]}₽", callback_data=f"buy_{p}")
        kb.button(text="🔙 Menu", callback_data="back"); kb.adjust(1)
        await msg.answer("✅ <b>ShakrievTZ</b> activated!\n💸 -10% discount on all tariffs.")
        await msg.answer(" <b>Tariffs with -10%:</b>", reply_markup=kb.as_markup())
    elif code == "KING":
        if u.get("promo_king_used"): return await msg.answer("⚠️ King already used!")
        await update_user(tid, promo_king_used=1)
        await msg.answer("✅ <b>King</b> activated!\n Issuing 1 year free access...")
        await make_sub(msg, tid, 365)
    elif code == "HALALSH":
        if u.get("promo_halalsh_used"): return await msg.answer("⚠️ HalalSH already used!")
        await update_user(tid, promo_halalsh_used=1)
        await msg.answer("✅ <b>HalalSH</b> activated!\n🎁 Issuing 1 month free access...")
        await make_sub(msg, tid, 30)
    else:
        await msg.answer("❌ Promo code not found.")

@dp.message(Command("stats"))
async def cmd_stats(msg: types.Message):
    if Config.BOT_ADMINS and msg.from_user.id not in Config.BOT_ADMINS: return await msg.answer(" Admins only.")
    async with aiosqlite.connect(Config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT COUNT(*) as total FROM users"); total_users = (await cur.fetchone())["total"]
        cur = await db.execute("SELECT COUNT(*) as active FROM users WHERE is_active = 1"); active_users = (await cur.fetchone())["active"]
        cur = await db.execute("SELECT COUNT(*) as paid FROM payments WHERE status = 'paid'"); total_payments = (await cur.fetchone())["paid"]
        cur = await db.execute("SELECT COALESCE(SUM(amount), 0) as revenue FROM payments WHERE status = 'paid'"); revenue = (await cur.fetchone())["revenue"]
    await msg.answer(f" <b>Stats</b>\n\n Users: <b>{total_users}</b>\n✅ Active: <b>{active_users}</b>\n💳 Payments: <b>{total_payments}</b>\n💰 Revenue: <b>{revenue}₽</b>")

@dp.message(Command("reset_promos"))
async def cmd_reset_promos(msg: types.Message):
    if Config.BOT_ADMINS and msg.from_user.id not in Config.BOT_ADMINS: return await msg.answer("🔒 Admins only.")
    try:
        async with aiosqlite.connect(Config.DB_PATH) as db:
            cursor = await db.execute("UPDATE users SET promo_shakriev_used = 0, promo_shakrievt_active = 0, promo_shakrievtz_active = 0, promo_king_used = 0, promo_halalsh_used = 0")
            await db.commit()
        await msg.answer(f"✅ <b>All promos reset!</b>\n Affected: <b>{cursor.rowcount}</b> users")
    except Exception as e:
        await msg.answer(f" Error: {e}")

async def main():
    logger.info(f"🚀 {Config.SERVER_NAME} Final | Port:{Config.TARGET_PORT} | Inbound:{Config.TARGET_INBOUND_ID}")
    if not Config.BOT_TOKEN: logger.error("❌ No token"); sys.exit(1)
    await init_db()
    if Config.YOOKASSA_SHOP_ID and Config.YOOKASSA_SECRET_KEY: 
        Configuration.account_id, Configuration.secret_key = Config.YOOKASSA_SHOP_ID, Config.YOOKASSA_SECRET_KEY
        logger.info("✅ YooKassa configured")
    logger.info("✅ Ready!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: logger.info("👋 Stopped")
    except Exception as e: logger.error(f" {e}", exc_info=True); sys.exit(1)