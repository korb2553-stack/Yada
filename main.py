# -*- coding: utf-8 -*-
"""
🧸 ตู้คีบตุ๊กตา — Discord Bot  (discord.py 2.x)
  • เลื่อนกรงเล็บซ้าย/ขวา → กดคีบ (มี GIF ตอนคีบ)   • 1 โทเค็น = 1 รอบ · คีบ ×10 · ออโต้
  • ออนห้องเสียงครบเวลา = +1 โทเค็น + สุ่มดรอปน้ำยาเพิ่มโชค ×2 ×3 ×5 (ใช้ได้ 5 นาที)
  • สัตว์ 41 แบบ 7 ระดับ (ธรรมดา→มิสติก + ซีเคร็ท "หมูเด้ง" 1%) · กระเป๋า · !กระเป๋า @คน
  • เทรดในห้องส่วนตัว ต้องกดยอมรับทั้งสองฝ่าย · บอร์ดอันดับรีเฟรชทุก 10 วิ
  • ปรับเรท/เวลา/น้ำยาได้ในดิสคอร์ดด้วย /ตั้งค่าตู้
ไฟล์ที่ต้องมี: main.py, animals.py, art.py, requirements.txt (รูปใน assets/ บอทสร้างให้เองถ้ายังไม่มี)
"""
import asyncio
import json
import os
import random
import sys
import time
import traceback
from collections import Counter
from pathlib import Path
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

import art
from animals import EMPTY, MACHINE, PRIZE, RARITY, RARITY_ORDER, ROSTER, SECRET

BASE = Path(__file__).resolve().parent
ASSETS = BASE / "assets"
DATA_FILE = Path(os.getenv("DATA_FILE") or BASE / "data.json")

# ════════════════════════ ตั้งค่า (แก้ตรงนี้ได้เลย) ════════════════════════
GRID = 5                       # จำนวนช่องตุ๊กตาในตู้
IDLE_TIMEOUT = 90              # วินาทีที่ไม่กดอะไร บอทจะคีบให้เอง
NOTICE_DELETE_AFTER = 180      # แจ้งเตือนในห้องจะลบเองใน (วินาที) ; None = ไม่ลบ
COUNT_DEAFENED = False         # True = คนที่ปิดหูฟัง (deafen) ก็นับเวลา
MAX_AUTO = 200                 # ออโต้สูงสุดต่อครั้ง
MAX_GIVE = 10000               # แจก/หักโทเค็นสูงสุดต่อครั้ง
BOARD_REFRESH = 10             # บอร์ดอันดับรีเฟรชทุกกี่วินาที
TRADE_TIMEOUT = 600            # ห้องเทรดหมดอายุเมื่อไม่มีใครกด (วินาที)
TRADE_ROOM_DELETE_AFTER = 60   # เทรดจบแล้วลบห้องใน (วินาที)
ENABLE_PREFIX, PREFIX = True, "!"   # คำสั่งพิมพ์ !กระเป๋า (ต้องเปิด Message Content Intent)
STATUS_TEXT = "ตู้คีบตุ๊กตา 🧸 /คีบ"
STREAMING = True               # สถานะ Streaming สีม่วง
STREAM_URL = "https://www.twitch.tv/discord"
OWNER_IDS = {int(x) for x in os.getenv("OWNER_IDS", "").replace(",", " ").split() if x.isdigit()}

# เรทเริ่มต้น (แก้ในดิสคอร์ดได้ด้วย /ตั้งค่าตู้ — ค่าที่ตั้งจะเก็บใน data.json แยกแต่ละเซิร์ฟเวอร์)
DEFAULT_RATES = dict(
    voice_minutes=5,           # ออนห้องเสียงกี่นาที = 1 โทเค็น
    win_mult=1.0,              # ตัวคูณโอกาสคีบติดทุกตัว
    empty_weight=36.0,         # น้ำหนักโผล่ "ช่องว่าง" (คีบไปก็ไม่ได้อะไร) ; 0 = ปิด
    secret_rate=1.0,           # % ต่อรอบ ที่จะได้ตุ๊กตาซีเคร็ท (หมูเด้ง)
    potion_drop=3.0,           # % ต่อนาที (ต่อคนที่ออนห้องเสียง) ที่น้ำยาจะดรอป
    potion_weights=[60, 30, 10],   # สัดส่วนดรอป ×2 : ×3 : ×5
    potion_minutes=5,          # น้ำยา 1 ขวดใช้ได้กี่นาที
)
POTIONS = (2, 3, 5)


# ════════════════════════ ที่เก็บข้อมูล (data.json) ════════════════════════
class Store:
    def __init__(self, path: Path):
        self.path = path
        self.data = {"guilds": {}}
        if path.exists():
            try:
                self.data = json.loads(path.read_text("utf-8"))
            except Exception:
                path.rename(path.with_name(f"{path.name}.broken-{int(time.time())}"))

    def g(self, gid):
        return self.data["guilds"].setdefault(str(gid), {"config": {}, "users": {}})

    def cfg(self, gid):
        return self.g(gid).setdefault("config", {})

    def user(self, gid, uid):
        u = self.g(gid).setdefault("users", {}).setdefault(str(uid), {})
        for k in ("tokens", "voice_min", "earned", "plays", "wins"):
            u.setdefault(k, 0)
        u.setdefault("inv", {})
        u.setdefault("potions", {})
        return u

    def save(self):
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), "utf-8")
        os.replace(tmp, self.path)


store = Store(DATA_FILE)
ACTIVE = set()   # (guild_id, user_id) ที่กำลังเล่นอยู่
TRADES = {}      # (guild_id, user_id) -> Trade


def rates(gid):
    r = store.cfg(gid).get("rates") or {}
    out = {**DEFAULT_RATES, **{k: v for k, v in r.items() if k != "prizes"}}
    out["prizes"] = r.get("prizes", {})
    return out


def set_rate(gid, **kw):
    store.cfg(gid).setdefault("rates", {}).update(kw)
    store.save()


def pstat(gid, p):
    ov = rates(gid)["prizes"].get(p["id"], {})
    return ov.get("chance", p["chance"]), ov.get("weight", p["weight"])


def eff_chance(gid, p, luck=1):
    """โอกาสคีบติดจริง (รวมเรทรวม + น้ำยา) ; น้ำยาไม่ทำให้เกิน 95%"""
    if p["id"] == "empty":
        return 0.0
    ch = pstat(gid, p)[0] * rates(gid)["win_mult"] * luck
    return max(0.0, min(0.95 if luck > 1 else 1.0, ch))


def pool(gid):
    ps = [p for p in MACHINE]
    ws = [max(0.0, float(pstat(gid, p)[1])) for p in ps]
    ew = float(rates(gid)["empty_weight"])
    if ew > 0:
        ps.append(EMPTY)
        ws.append(ew)
    if sum(ws) <= 0:
        ws = [1.0] * len(ps)
    return ps, ws


def active_luck(u):
    po = u.get("potion")
    if po and po.get("until", 0) > time.time():
        return po["mult"], po["until"]
    if po:
        u.pop("potion", None)
    return 1, None


def roll(gid, u, slot):
    """ผลการคีบ 1 ครั้ง → (ตุ๊กตาที่ได้, ติดไหม) ; ซีเคร็ทสุ่มได้ทุกรอบไม่ว่าจะคีบช่องไหน"""
    if SECRET and random.random() < rates(gid)["secret_rate"] / 100:
        return random.choice(SECRET), True
    luck, _ = active_luck(u)
    return slot, random.random() < eff_chance(gid, slot, luck)


def apply_result(u, prize, win):
    if win:
        u["wins"] += 1
        u["inv"][prize["id"]] = u["inv"].get(prize["id"], 0) + 1


# ════════════════════════ บอท ════════════════════════
intents = discord.Intents.default()
intents.members = True            # ต้องเปิด "Server Members Intent"
intents.voice_states = True
intents.message_content = ENABLE_PREFIX   # ต้องเปิด "Message Content Intent" (สำหรับ !กระเป๋า)


class ClawBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=PREFIX, intents=intents, help_command=None)

    async def setup_hook(self):
        await asyncio.to_thread(art.ensure_assets, ASSETS)
        self.add_view(MenuView())
        voice_tick.start()
        board_tick.start()
        gid = os.getenv("GUILD_ID", "")
        if gid.isdigit():  # ตั้ง GUILD_ID = คำสั่งขึ้นทันที (เหมาะตอนทดสอบ)
            g = discord.Object(int(gid))
            self.tree.copy_global_to(guild=g)
            await self.tree.sync(guild=g)
        else:
            await self.tree.sync()


bot = ClawBot()


@bot.event
async def on_ready():
    print(f"✅ ออนไลน์แล้ว: {bot.user} ({len(bot.guilds)} เซิร์ฟเวอร์)")
    act = discord.Streaming(name=STATUS_TEXT, url=STREAM_URL) if STREAMING else discord.Game(STATUS_TEXT)
    await bot.change_presence(activity=act, status=discord.Status.online)


async def is_owner(i):
    return i.user.id in OWNER_IDS or await bot.is_owner(i.user)


def owner_only():
    async def pred(i: discord.Interaction):
        if await is_owner(i):
            return True
        raise app_commands.CheckFailure("owner")
    return app_commands.check(pred)


@bot.tree.error
async def on_app_error(i: discord.Interaction, err):
    if isinstance(err, app_commands.CheckFailure):
        msg = "🔒 คำสั่งนี้ใช้ได้เฉพาะเจ้าของบอทน้า"
    else:
        traceback.print_exception(type(err), err, err.__traceback__)
        msg = "ขออภัย เกิดข้อผิดพลาดนิดหน่อย 🥲 ลองใหม่อีกครั้งน้า"
    try:
        if i.response.is_done():
            await i.followup.send(msg, ephemeral=True)
        else:
            await i.response.send_message(msg, ephemeral=True)
    except Exception:
        pass


@bot.event
async def on_command_error(ctx, err):
    if isinstance(err, commands.CommandNotFound):
        return
    if isinstance(err, (commands.MemberNotFound, commands.BadArgument)):
        return await ctx.reply("หาคนนี้ไม่เจอน้า 🥺 ลอง `!กระเป๋า @ชื่อ`", mention_author=False)
    traceback.print_exception(type(err), err, err.__traceback__)


# ════════════════════════ ตัวช่วย ════════════════════════
def files(*names):
    return [discord.File(ASSETS / n, filename=n) for n in names if (ASSETS / n).exists()]


def pct(x):
    return f"{round(x * 100)}%"


def info(title, desc, color=0xF48FB1):
    return discord.Embed(title=title, description=desc, color=color)


def luck_line(u):
    m, until = active_luck(u)
    return f"🍀 น้ำยาเพิ่มโชค **×{m}** · หมดเวลา <t:{int(until)}:T> (<t:{int(until)}:R>)" if m > 1 else None


async def respond(i, *, embed=None, view=None, fl=(), replace=False):
    """ตอบแบบเห็นคนเดียว (ephemeral) หรือแทนที่ข้อความเดิม (replace=True)"""
    if replace:
        await i.response.edit_message(embed=embed, view=view, attachments=list(fl))
    else:
        kw = dict(ephemeral=True)
        if embed is not None:
            kw["embed"] = embed
        if view is not None:
            kw["view"] = view
        if fl:
            kw["files"] = list(fl)
        await i.response.send_message(**kw)


def tier_summary(gid):
    r, lines = rates(gid), []
    for tier in RARITY_ORDER:
        if tier == "secret":
            continue
        ps = [p for p in MACHINE if p["rarity"] == tier]
        if not ps:
            continue
        cs = [eff_chance(gid, p) for p in ps]
        lo, hi = pct(min(cs)), pct(max(cs))
        rn, re_, _ = RARITY[tier]
        lines.append(f"{re_} **{rn}** ×{len(ps)} · คีบติด {lo if lo == hi else lo + '–' + hi}")
    sec = ", ".join(f"{p['emoji']} {p['name']}" for p in SECRET)
    lines.append(f"🔒 **ซีเคร็ท** {sec} · โผล่ **{r['secret_rate']:g}%** ทุกรอบ (ไม่เห็นในตู้)")
    return "\n".join(lines)


def no_token_embed(gid):
    e = info("🪙 โทเค็นหมดแล้ว",
             f"ต้องมี **1 โทเค็น** ต่อ 1 รอบ\n\n🎧 อยู่ในห้องเสียง **{rates(gid)['voice_minutes']} นาที** = +1 โทเค็น\n👑 หรือรอเจ้าของบอทเสกให้~",
             0xFFB74D)
    e.set_thumbnail(url="attachment://token.png")
    return e


def menu_embed(gid):
    m = store.cfg(gid).get("menu", {})
    default = (
        "ยินดีต้อนรับสู่ตู้คีบตุ๊กตาสุดน่ารัก~ 💖\n\n"
        "🪙 **1 โทเค็น = 1 รอบ**\n"
        f"🎧 อยู่ในห้องเสียงครบ **{rates(gid)['voice_minutes']} นาที** = ได้ **+1 โทเค็น**\n"
        "🍀 ออนห้องเสียงลุ้นน้ำยาเพิ่มโชค ×2 ×3 ×5\n"
        "👑 หรือรอเจ้าของบอทเสกโทเค็นให้~\n\n"
        "กดปุ่มด้านล่างได้เลย ✨")
    e = discord.Embed(title=m.get("title") or "🧸 ตู้คีบตุ๊กตาน้อยน่ารัก",
                      description=m.get("description") or default, color=0xF48FB1)
    e.set_image(url="attachment://menu_banner.png")
    e.set_footer(text="กดปุ่มด้านล่างเพื่อเริ่มเล่น 🎀")
    return e


# ════════════════════════ แจ้งเตือน (แยกกันทุกแบบ) ════════════════════════
async def _send_notice(guild, member, e, fl, fallback=None, delete_after=None):
    ch = guild.get_channel(store.cfg(guild.id).get("token_channel") or 0) or fallback
    try:
        if ch:
            await ch.send(embed=e, files=fl, delete_after=delete_after, allowed_mentions=discord.AllowedMentions.none())
        else:
            await member.send(embed=e, files=fl)  # ไม่ได้ตั้งห้อง → ส่ง DM
    except discord.HTTPException:
        pass


async def notify_tokens(guild, member, amount, reason, fallback=None, delete_after=None):
    """🪙 แจ้งเตือนได้รับโทเค็น"""
    u = store.user(guild.id, member.id)
    e = discord.Embed(title="🪙 ได้รับโทเค็นแล้ว!", color=0xFFD54F,
                      description=f"{member.mention} ได้รับ **+{amount}** โทเค็น ✨\n{reason}")
    e.add_field(name="💰 โทเค็นคงเหลือ", value=f"**{u['tokens']}** เหรียญ · เล่นได้ {u['tokens']} รอบ")
    e.set_thumbnail(url="attachment://token.png")
    e.set_footer(text=f"อยู่ในห้องเสียงครบ {rates(guild.id)['voice_minutes']} นาที = +1 โทเค็น")
    await _send_notice(guild, member, e, files("token.png"), fallback, delete_after)


async def notify_potion(guild, member, mult, fallback=None, delete_after=None, reason="🎧 ดรอปจากการออนห้องเสียง"):
    """🍀 แจ้งเตือนได้รับน้ำยาเพิ่มโชค"""
    n = store.user(guild.id, member.id)["potions"].get(str(mult), 0)
    mins = rates(guild.id)["potion_minutes"]
    e = discord.Embed(title=f"🍀 ได้รับน้ำยาเพิ่มโชค ×{mult}!", color=0xB39DDB,
                      description=f"{member.mention} ได้รับ **ขวดน้ำยาโชค ×{mult}** 🧪\n{reason}\n\nใช้ได้ **{mins} นาที** · กดปุ่ม 🍀 น้ำยา บนเมนู หรือพิมพ์ `/น้ำยา`")
    e.add_field(name="🧪 ที่มีอยู่", value=f"×{mult} จำนวน **{n}** ขวด")
    e.set_thumbnail(url=f"attachment://potion_{mult}.png")
    await _send_notice(guild, member, e, files(f"potion_{mult}.png"), fallback, delete_after)


def _win_extra(rarity):
    return {"rare": "\n💜 ว้าว! ของหายากเลยนะเนี่ย~",
            "epic": "\n💎✨ **มหากาพย์!** สุดยอดไปเลย~",
            "legend": "\n🌟✨ **ตำนานมาแล้วว!!** ✨🌟",
            "mystic": "\n🔮✨ **มิสติก!!** แทบไม่มีใครเคยเห็น ✨🔮",
            "secret": "\n🔒✨ **ซีเคร็ทสุดลับ!!** ทั้งเซิร์ฟต้องรู้ ✨🔒"}.get(rarity, "")


async def announce_win(guild, channel, player, prize):
    """🎉 แจ้งเตือนคีบตุ๊กตาได้"""
    await asyncio.to_thread(art.ensure_scene, ASSETS, prize["id"], "grab")
    rn, re_, color = RARITY[prize["rarity"]]
    u = store.user(guild.id, player.id)
    e = discord.Embed(title="🎉 คีบตุ๊กตาได้แล้ว!!", color=color,
                      description=f"{player.mention} คีบ {prize['emoji']} **{prize['name']}** ได้สำเร็จ! 🎊{_win_extra(prize['rarity'])}")
    e.add_field(name="ระดับ", value=f"{re_} {rn}")
    e.add_field(name="ในกระเป๋ามีแล้ว", value=f"×{u['inv'].get(prize['id'], 0)}")
    e.set_image(url=f"attachment://claw_grab_{prize['id']}.png")
    e.set_thumbnail(url=f"attachment://plush_{prize['id']}.png")
    e.set_footer(text="เล่นได้ที่ /คีบ · ดูของสะสมที่ /กระเป๋า")
    ch = guild.get_channel(store.cfg(guild.id).get("win_channel") or 0) or channel
    try:
        await ch.send(content=player.mention, embed=e, allowed_mentions=discord.AllowedMentions(users=[player]),
                      files=files(f"claw_grab_{prize['id']}.png", f"plush_{prize['id']}.png"))
    except (discord.HTTPException, AttributeError):
        pass


def _sorted_counts(counter):
    items = [(PRIZE[k], n) for k, n in counter.items() if k in PRIZE and n > 0]
    items.sort(key=lambda t: (-RARITY_ORDER.index(t[0]["rarity"]), t[0]["name"]))
    return items


async def announce_batch(guild, channel, player, got, n):
    items = _sorted_counts(got)
    if not items:
        return
    best = items[0][0]
    await asyncio.to_thread(art.ensure_scene, ASSETS, best["id"], "grab")
    lines = [f"{p['emoji']} **{p['name']}** ×{c} · {RARITY[p['rarity']][1]} {RARITY[p['rarity']][0]}" for p, c in items[:12]]
    if len(items) > 12:
        lines.append(f"…และอีก {len(items) - 12} แบบ")
    e = discord.Embed(title=f"🎉 {player.display_name} คีบ {n} ครั้ง!", color=RARITY[best["rarity"]][2],
                      description=f"{player.mention} ได้ตุ๊กตา **{sum(got.values())}** ตัว{_win_extra(best['rarity'])}\n\n" + "\n".join(lines))
    e.set_image(url=f"attachment://claw_grab_{best['id']}.png")
    e.set_thumbnail(url=f"attachment://plush_{best['id']}.png")
    ch = guild.get_channel(store.cfg(guild.id).get("win_channel") or 0) or channel
    try:
        await ch.send(embed=e, allowed_mentions=discord.AllowedMentions.none(),
                      files=files(f"claw_grab_{best['id']}.png", f"plush_{best['id']}.png"))
    except (discord.HTTPException, AttributeError):
        pass


# ════════════════════════ ตัวเกมตู้คีบ ════════════════════════
def render_machine(slots, pos):
    """แบบข้อความ (ใช้สำรองถ้าสร้างรูปไม่ได้)"""
    rows = [["⬜"] * GRID for _ in range(3)]
    rows[0][pos] = "🪝"
    return "\n".join(["".join(r) for r in rows] + ["".join(p["emoji"] for p in slots), "🟪" * GRID])


async def machine_files(ids, pos):
    try:
        buf = await asyncio.to_thread(art.machine_png, ids, pos)
        return [discord.File(buf, filename="machine.png")]
    except Exception:
        traceback.print_exc()
        return None


class ClawView(discord.ui.View):
    def __init__(self, ix, slots):
        super().__init__(timeout=IDLE_TIMEOUT)
        self.ix, self.slots = ix, slots
        self.ids = [p["id"] for p in slots]
        self.gid, self.user_id = ix.guild.id, ix.user.id
        self.key = (self.gid, self.user_id)
        self.pos = GRID // 2
        self.done = False
        self.use_img = True
        self.started = time.monotonic()
        self.sync()

    def sync(self):
        self.left.disabled = self.done or self.pos <= 0
        self.right.disabled = self.done or self.pos >= GRID - 1
        self.go.disabled = self.done

    def embed(self, note=None, gif=False):
        p = self.slots[self.pos]
        rn, re_, color = RARITY[p["rarity"]]
        u = store.user(self.gid, self.user_id)
        luck, _ = active_luck(u)
        if self.use_img:
            desc = note or "เลื่อนกรงเล็บ ⬅️ ➡️ ไปเหนือตุ๊กตาที่ชอบ แล้วกด **🪝 คีบ!**"
        else:
            desc = render_machine(self.slots, self.pos) + (f"\n\n**{note}**" if note else "")
        e = discord.Embed(title="🧸 ตู้คีบตุ๊กตา", description=desc, color=color)
        if self.use_img:
            e.set_image(url="attachment://claw.gif" if gif else "attachment://machine.png")
        if p["id"] == "empty":
            val = f"{p['emoji']} **ช่องว่าง**\nไม่มีตุ๊กตาในช่องนี้ — คีบไปก็ไม่ได้อะไรน้า"
        else:
            val = (f"{p['emoji']} **{p['name']}**\n{re_} {rn} · โอกาสคีบติด **{pct(eff_chance(self.gid, p, luck))}**"
                   + (f" 🍀×{luck}" if luck > 1 else ""))
        e.add_field(name="🎯 ใต้กรงเล็บตอนนี้", value=val, inline=False)
        ll = luck_line(u)
        if ll:
            e.add_field(name="น้ำยา", value=ll, inline=False)
        e.set_footer(text=f"เหลือโทเค็น {u['tokens']} · ไม่กดภายใน {IDLE_TIMEOUT} วิ บอทจะคีบให้เอง")
        return e

    async def interaction_check(self, i):
        if i.user.id != self.user_id:
            await i.response.send_message("นี่ไม่ใช่ตู้ของคุณน้า 🥺 พิมพ์ /คีบ เพื่อเล่นของตัวเองได้เลย", ephemeral=True)
            return False
        return True

    async def move(self, i, d):
        if self.done:
            return await i.response.defer()
        if time.monotonic() - self.started > 600:  # เล่นนานเกิน 10 นาที → คีบให้เลย
            return await self.grab(i)
        self.pos = max(0, min(GRID - 1, self.pos + d))
        self.sync()
        kw = dict(view=self)
        if self.use_img:
            fl = await machine_files(self.ids, self.pos)
            if fl is None:
                self.use_img = False
            else:
                kw["attachments"] = fl
        kw["embed"] = self.embed()
        await i.response.edit_message(**kw)

    @discord.ui.button(label="ซ้าย", emoji="⬅️", style=discord.ButtonStyle.secondary)
    async def left(self, i: discord.Interaction, b: discord.ui.Button):
        await self.move(i, -1)

    @discord.ui.button(label="คีบ!", emoji="🪝", style=discord.ButtonStyle.success)
    async def go(self, i: discord.Interaction, b: discord.ui.Button):
        await self.grab(i)

    @discord.ui.button(label="ขวา", emoji="➡️", style=discord.ButtonStyle.secondary)
    async def right(self, i: discord.Interaction, b: discord.ui.Button):
        await self.move(i, 1)

    async def on_timeout(self):
        await self.grab(None)

    async def grab(self, i):
        if self.done:
            return
        self.done = True
        self.stop()
        self.sync()
        guild, player = self.ix.guild, self.ix.user
        slot = self.slots[self.pos]
        u = store.user(self.gid, self.user_id)
        prize, win = roll(self.gid, u, slot)
        apply_result(u, prize, win)   # บันทึกผลก่อนเล่นแอนิเมชัน กันของหายถ้าเน็ตสะดุด
        store.save()
        edit = self.ix.edit_original_response
        if i is not None:
            try:
                await i.response.defer()
                edit = i.edit_original_response
            except Exception:
                traceback.print_exc()
        shown = False
        if self.use_img:
            try:  # 🎞️ GIF ตอนคีบ
                buf, secs = await asyncio.to_thread(art.grab_gif, self.ids, self.pos, prize["id"], win, prize["id"] != slot["id"])
                await edit(embed=self.embed("🪝 กำลังคีบ... ลุ้นนนน!", gif=True), view=self,
                           attachments=[discord.File(buf, filename="claw.gif")])
                await asyncio.sleep(secs)
                shown = True
            except Exception:
                traceback.print_exc()
        if not shown:
            try:
                await edit(embed=self.embed("🤏 กำลังคีบ... ลุ้นนนน!"), view=self)
                await asyncio.sleep(2.5)
            except Exception:
                traceback.print_exc()
        ACTIVE.discard(self.key)

        rn, re_, color = RARITY[prize["rarity"]]
        mode, sid = ("grab", prize["id"]) if win else ("miss", slot["id"])
        try:
            await asyncio.to_thread(art.ensure_scene, ASSETS, sid, mode)
        except Exception:
            traceback.print_exc()
        img = f"claw_{mode}_{sid}.png"
        if win:
            title = {"secret": "🔒✨ ซีเคร็ท!! คีบติดแล้ว", "mystic": "🔮✨ มิสติก!! คีบติดแล้ว"}.get(prize["rarity"], "🎉 คีบติดแล้ว!!")
            e = discord.Embed(title=title, color=color,
                              description=f"คุณได้ {prize['emoji']} **{prize['name']}** ({re_} {rn}) มาครองแล้ว~\nเก็บไว้ในกระเป๋าเรียบร้อย 👜✨")
        elif slot["id"] == "empty":
            e = discord.Embed(title="💨 คีบโดนแต่ลม", color=0xB0BEC5,
                              description="ช่องนั้นว่างเปล่า... ไม่ได้อะไรเลยน้า 🥲\nรอบหน้าเล็งตุ๊กตาให้ดีๆ นะ")
        else:
            e = discord.Embed(title="💦 อ๊ะ! ตุ๊กตาหลุดมือ", color=0xB0BEC5,
                              description=f"{slot['emoji']} **{slot['name']}** ลื่นหลุดไปซะแล้ว...\nอีกนิดเดียวเอง ลองใหม่น้า 🥺")
        e.set_image(url=f"attachment://{img}")
        e.set_footer(text=f"โทเค็นคงเหลือ {u['tokens']}")
        again = AgainView(self.ix)
        try:
            await edit(embed=e, view=again, attachments=files(img))
        except Exception:
            traceback.print_exc()
            try:
                e.set_image(url=None)
                await edit(embed=e, view=again, attachments=[])
            except Exception:
                pass
        if win:
            await announce_win(guild, self.ix.channel, player, prize)


class AgainView(discord.ui.View):
    def __init__(self, ix):
        super().__init__(timeout=180)
        self.ix, self.used = ix, False

    async def interaction_check(self, i):
        if i.user.id != self.ix.user.id:
            await i.response.send_message("ปุ่มนี้ของคนที่เล่นอยู่น้า 🥺", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        if not self.used:
            try:
                await self.ix.edit_original_response(view=None)
            except Exception:
                pass

    @discord.ui.button(label="เล่นอีกรอบ", emoji="🔁", style=discord.ButtonStyle.success)
    async def again(self, i: discord.Interaction, b: discord.ui.Button):
        self.used = True
        await start_game(i, replace=True)

    @discord.ui.button(label="คีบ ×10", emoji="🔟", style=discord.ButtonStyle.primary)
    async def x10(self, i: discord.Interaction, b: discord.ui.Button):
        self.used = True
        await run_batch(i, 10, replace=True)

    @discord.ui.button(label="กระเป๋า", emoji="👜", style=discord.ButtonStyle.secondary)
    async def bag(self, i: discord.Interaction, b: discord.ui.Button):
        self.used = True
        await show_bag(i, replace=True)


async def start_game(i: discord.Interaction, replace=False):
    if i.guild is None:
        return await respond(i, embed=info("ใช้ในเซิร์ฟเวอร์เท่านั้นน้า", "ลองพิมพ์ /คีบ ในเซิร์ฟเวอร์ดูนะ 🧸"), replace=replace)
    gid, key = i.guild.id, (i.guild.id, i.user.id)
    if key in ACTIVE:
        return await respond(i, embed=info("🎮 คุณมีเกมที่เล่นค้างอยู่", f"จบรอบเดิมก่อนน้า (ถ้าไม่กด บอทจะคีบให้เองใน {IDLE_TIMEOUT} วินาที)"), replace=replace)
    u = store.user(gid, i.user.id)
    if u["tokens"] < 1:
        return await respond(i, embed=no_token_embed(gid), fl=files("token.png"), replace=replace)
    u["tokens"] -= 1
    u["plays"] += 1
    store.save()
    ACTIVE.add(key)
    ps, ws = pool(gid)
    view = ClawView(i, random.choices(ps, weights=ws, k=GRID))
    try:
        fl = await machine_files(view.ids, view.pos)
        if fl is None:
            view.use_img = False
        await respond(i, embed=view.embed(), view=view, fl=fl or [], replace=replace)
    except Exception:  # เปิดเกมไม่สำเร็จ → คืนโทเค็น
        ACTIVE.discard(key)
        u["tokens"] += 1
        u["plays"] -= 1
        store.save()
        raise


async def run_batch(i: discord.Interaction, n: int, replace=False):
    """คีบหลายครั้งรวดเดียว (ปุ่ม ×10 และ /ออโต้) — ไม่มีแอนิเมชัน แต่ใช้เรท/น้ำยา/ซีเคร็ทเหมือนเล่นปกติ"""
    if i.guild is None:
        return await respond(i, embed=info("ใช้ในเซิร์ฟเวอร์เท่านั้นน้า", "ลองพิมพ์ /ออโต้ ในเซิร์ฟเวอร์ดูนะ 🧸"), replace=replace)
    gid, uid = i.guild.id, i.user.id
    if (gid, uid) in ACTIVE:
        return await respond(i, embed=info("🎮 คุณมีเกมที่เล่นค้างอยู่", "จบรอบเดิมก่อนน้า"), replace=replace)
    u = store.user(gid, uid)
    asked, n = n, min(n, u["tokens"], MAX_AUTO)
    if n < 1:
        return await respond(i, embed=no_token_embed(gid), fl=files("token.png"), replace=replace)
    u["tokens"] -= n
    u["plays"] += n
    ps, ws = pool(gid)
    got = Counter()
    for _ in range(n):
        slots = random.choices(ps, weights=ws, k=GRID)
        prize, win = roll(gid, u, random.choice(slots))
        if win:
            apply_result(u, prize, win)
            got[prize["id"]] += 1
    store.save()
    items, wins = _sorted_counts(got), sum(got.values())
    lines = [f"{p['emoji']} **{p['name']}** ×{c} · {RARITY[p['rarity']][1]} {RARITY[p['rarity']][0]}" for p, c in items[:25]]
    if len(items) > 25:
        lines.append(f"…และอีก {len(items) - 25} แบบ")
    best = items[0][0] if items else None
    e = info(f"🔟 คีบออโต้ {n} ครั้ง" if asked != 10 else "🔟 คีบ ×10",
             ("\n".join(lines) or "รอบนี้ไม่ติดเลย... เอาใหม่น้า 🥺")
             + (f"\n\n{_win_extra(best['rarity']).strip()}" if best and best["rarity"] in ("epic", "legend", "mystic", "secret") else ""),
             RARITY[best["rarity"]][2] if best else 0xB0BEC5)
    note = f" (ขอ {asked} แต่โทเค็นพอแค่ {n})" if n < asked and u["tokens"] == 0 else ""
    e.add_field(name="📊 สรุป", value=f"คีบ {n} ครั้ง{note} · ติด **{wins}** · พลาด {n - wins}\nโทเค็นคงเหลือ **{u['tokens']}**", inline=False)
    ll = luck_line(u)
    if ll:
        e.add_field(name="น้ำยา", value=ll, inline=False)
    fl = files(f"plush_{best['id']}.png") if best else []
    if best:
        e.set_thumbnail(url=f"attachment://plush_{best['id']}.png")
    await respond(i, embed=e, view=AgainView(i), fl=fl, replace=replace)
    if wins:
        await announce_batch(i.guild, i.channel, i.user, got, n)


# ════════════════════════ โทเค็น · กระเป๋า · น้ำยา ════════════════════════
async def show_tokens(i: discord.Interaction, replace=False):
    if i.guild is None:
        return
    r = rates(i.guild.id)
    u = store.user(i.guild.id, i.user.id)
    vm = min(u["voice_min"], r["voice_minutes"])
    bar = ("🟩" * vm + "⬜" * (r["voice_minutes"] - vm)) if r["voice_minutes"] <= 15 else f"{vm}/{r['voice_minutes']}"
    e = info(f"🪙 โทเค็นของ {i.user.display_name}", f"คงเหลือ **{u['tokens']}** โทเค็น (เล่นได้ {u['tokens']} รอบ)", 0xFFD54F)
    e.add_field(name="🎧 ความคืบหน้าในห้องเสียง", value=f"{bar}  {vm}/{r['voice_minutes']} นาที → +1 โทเค็น", inline=False)
    e.add_field(name="📈 สะสมทั้งหมด", value=f"{u['earned']} โทเค็น")
    ll = luck_line(u)
    if ll:
        e.add_field(name="น้ำยา", value=ll, inline=False)
    e.set_thumbnail(url="attachment://token.png")
    await respond(i, embed=e, fl=files("token.png"), replace=replace)


async def build_bag(guild, target):
    u = store.user(guild.id, target.id)
    owned = _sorted_counts(Counter(u["inv"]))
    lines = [f"{p['emoji']} **{p['name']}** ×{n} · {RARITY[p['rarity']][1]} {RARITY[p['rarity']][0]}" for p, n in owned]
    desc = "\n".join(lines) or "ยังว่างเปล่า... ไปคีบตุ๊กตากันเถอะ! 🧸"
    if len(desc) > 3800:
        desc = desc[:3800] + "\n…"
    e = info(f"👜 กระเป๋าของ {target.display_name}", desc)
    e.add_field(name="🧸 สะสมแล้ว", value=f"{sum(n for _, n in owned)} ตัว · {len(owned)}/{len(ROSTER)} แบบ")
    e.add_field(name="🎮 สถิติ", value=f"เล่น {u['plays']} รอบ · คีบติด {u['wins']} ครั้ง")
    e.add_field(name="🪙 โทเค็น", value=str(u["tokens"]))
    pots = " · ".join(f"×{m} **{u['potions'].get(str(m), 0)}**" for m in POTIONS)
    e.add_field(name="🧪 น้ำยาเพิ่มโชค", value=pots, inline=False)
    ll = luck_line(u)
    if ll:
        e.add_field(name="กำลังใช้", value=ll, inline=False)
    fl = []
    if owned:
        try:
            buf = await asyncio.to_thread(art.bag_image, [(p["id"], n) for p, n in owned], ASSETS)
            fl = [discord.File(buf, filename="bag.png")]
            e.set_image(url="attachment://bag.png")
        except Exception:
            traceback.print_exc()
    return e, fl


async def show_bag(i: discord.Interaction, member: Optional[discord.Member] = None, replace=False):
    if i.guild is None:
        return
    e, fl = await build_bag(i.guild, member or i.user)
    await respond(i, embed=e, fl=fl, replace=replace)


@bot.command(name="กระเป๋า", aliases=["bag"])
async def prefix_bag(ctx, member: Optional[discord.Member] = None):
    """!กระเป๋า @คน — ดูกระเป๋าของคนที่แท็ก (ไม่แท็ก = ของตัวเอง)"""
    if ctx.guild is None:
        return
    e, fl = await build_bag(ctx.guild, member or ctx.author)
    await ctx.reply(embed=e, files=fl, mention_author=False)


def potion_embed(gid, uid):
    u = store.user(gid, uid)
    luck, until = active_luck(u)
    mins = rates(gid)["potion_minutes"]
    e = info("🧪 น้ำยาเพิ่มโชค",
             f"ใช้แล้วโอกาสคีบติดคูณตามขวด นาน **{mins} นาที**\nดรอปจากการออนห้องเสียงแบบสุ่ม ✨", 0xB39DDB)
    for m in POTIONS:
        e.add_field(name=f"🍀 ×{m}", value=f"มี **{u['potions'].get(str(m), 0)}** ขวด")
    ll = luck_line(u)
    e.add_field(name="สถานะ", value=ll or "ยังไม่ได้ใช้น้ำยา", inline=False)
    e.set_footer(text="ใช้ได้ทีละ 1 ขวด — รอให้หมดเวลาก่อนใช้ขวดต่อไป")
    e.set_thumbnail(url=f"attachment://potion_{luck if luck > 1 else 5}.png")
    return e


class PotionView(discord.ui.View):
    def __init__(self, gid, uid):
        super().__init__(timeout=120)
        self.gid, self.uid = gid, uid
        u = store.user(gid, uid)
        luck, _ = active_luck(u)
        for m in POTIONS:
            n = u["potions"].get(str(m), 0)
            b = discord.ui.Button(label=f"ใช้ ×{m} (มี {n})", emoji="🍀", style=discord.ButtonStyle.success,
                                  disabled=(n < 1 or luck > 1))
            b.callback = self._make(m)
            self.add_item(b)

    def _make(self, m):
        async def cb(i: discord.Interaction):
            u = store.user(self.gid, self.uid)
            luck, _ = active_luck(u)
            if luck == 1 and u["potions"].get(str(m), 0) >= 1:
                u["potions"][str(m)] -= 1
                u["potion"] = {"mult": m, "until": time.time() + rates(self.gid)["potion_minutes"] * 60}
                store.save()
            await show_potions(i, replace=True)
        return cb

    async def interaction_check(self, i):
        if i.user.id != self.uid:
            await i.response.send_message("ขวดน้ำยาของคนอื่นน้า 🥺", ephemeral=True)
            return False
        return True


async def show_potions(i: discord.Interaction, replace=False):
    if i.guild is None:
        return
    u = store.user(i.guild.id, i.user.id)
    luck, _ = active_luck(u)
    await respond(i, embed=potion_embed(i.guild.id, i.user.id), view=PotionView(i.guild.id, i.user.id),
                  fl=files(f"potion_{luck if luck > 1 else 5}.png"), replace=replace)


# ════════════════════════ บอร์ดอันดับ (รีเฟรชทุก 10 วินาที) ════════════════════════
def board_embed(guild):
    users = store.g(guild.id).get("users", {})
    ranked = sorted(((uid, u) for uid, u in users.items() if u.get("plays", 0) > 0),
                    key=lambda kv: (-kv[1]["plays"], -kv[1].get("wins", 0)))[:10]
    medals = ["🥇", "🥈", "🥉"] + [f"`{n:>2}.`" for n in range(4, 11)]
    lines = []
    for m, (uid, u) in zip(medals, ranked):
        owned = len([k for k, v in u.get("inv", {}).items() if v > 0 and k in PRIZE])
        lines.append(f"{m} <@{uid}> — **{u['plays']:,}** ครั้ง · ติด {u.get('wins', 0):,} · สะสม {owned}/{len(ROSTER)}")
    e = discord.Embed(title="🏆 อันดับคนคีบตุ๊กตาเยอะที่สุด", color=0xFFD54F,
                      description="\n".join(lines) or "ยังไม่มีใครเล่นเลย~ เป็นคนแรกสิ! 🧸")
    e.set_thumbnail(url="attachment://trophy.png")
    e.set_footer(text=f"🔄 อัปเดตทุก {BOARD_REFRESH} วินาที")
    e.timestamp = discord.utils.utcnow()
    return e


@tasks.loop(seconds=BOARD_REFRESH)
async def board_tick():
    try:
        for guild in list(bot.guilds):
            cfg = store.data["guilds"].get(str(guild.id), {}).get("config", {})
            ref = cfg.get("board_msg")
            ch = guild.get_channel(ref[0]) if ref else None
            if not ch:
                continue
            try:
                await ch.get_partial_message(ref[1]).edit(embed=board_embed(guild))
            except discord.NotFound:
                cfg["board_msg"] = None
            except discord.HTTPException:
                pass
    except Exception:
        traceback.print_exc()


@board_tick.before_loop
async def _board_before():
    await bot.wait_until_ready()


# ════════════════════════ เทรดตุ๊กตา ════════════════════════
class Trade:
    def __init__(self, guild, a, b, origin):
        self.guild, self.a, self.b, self.origin = guild, a, b, origin
        self.offer = {a.id: {}, b.id: {}}
        self.ok = set()
        self.room = self.msg = self.view = None
        self.closed = False

    def lines(self, uid):
        return "\n".join(f"{PRIZE[k]['emoji']} {PRIZE[k]['name']} ×{n}" for k, n in self.offer[uid].items() if n > 0) or "— ยังไม่ได้ใส่ของ —"

    def total(self):
        return sum(n for o in self.offer.values() for n in o.values())

    def embed(self, note=None):
        e = discord.Embed(title="🔄 ห้องเทรดตุ๊กตา", color=0x81D4FA,
                          description=note or "กด ➕ ใส่ของที่จะแลก แล้ว ✅ ยอมรับ ทั้งสองฝ่าย\n(ถ้าใครแก้ของ การยอมรับจะรีเซ็ตเพื่อความปลอดภัย)")
        for u in (self.a, self.b):
            e.add_field(name=f"{u.display_name} · {'✅ ยอมรับแล้ว' if u.id in self.ok else '⏳ รอยอมรับ'}", value=self.lines(u.id))
        e.set_thumbnail(url="attachment://trade.png")
        return e

    async def refresh(self, note=None):
        if self.msg and not self.closed:
            await self.msg.edit(embed=self.embed(note), view=self.view)

    def release(self):
        self.closed = True
        for u in (self.a, self.b):
            TRADES.pop((self.guild.id, u.id), None)
        if self.view:
            self.view.stop()

    async def _cleanup(self):
        await asyncio.sleep(TRADE_ROOM_DELETE_AFTER)
        try:
            await self.room.delete()
        except Exception:
            pass

    async def cancel(self, reason):
        if self.closed:
            return
        self.release()
        try:
            await self.msg.edit(embed=discord.Embed(title="❌ ยกเลิกการเทรด", description=reason, color=0xEF9A9A), view=None)
        except Exception:
            pass
        asyncio.create_task(self._cleanup())

    async def finish(self):
        if self.closed:
            return
        gid = self.guild.id
        inv = {u.id: store.user(gid, u.id)["inv"] for u in (self.a, self.b)}
        for uid, items in self.offer.items():
            if any(inv[uid].get(k, 0) < n for k, n in items.items()):
                self.ok.clear()
                return await self.refresh("⚠️ ของในกระเป๋าไม่พอ (อาจเพิ่งถูกใช้/เทรดไป) — แก้ของแล้วยอมรับใหม่")
        for uid, items in self.offer.items():
            other = self.b.id if uid == self.a.id else self.a.id
            for k, n in items.items():
                if n <= 0:
                    continue
                inv[uid][k] -= n
                if inv[uid][k] <= 0:
                    inv[uid].pop(k)
                inv[other][k] = inv[other].get(k, 0) + n
        store.save()
        self.release()
        e = discord.Embed(title="🤝 เทรดสำเร็จ!", color=0xA5D6A7,
                          description=f"{self.a.mention} ⇄ {self.b.mention}\nแลกเปลี่ยนตุ๊กตากันเรียบร้อย 🎉")
        e.add_field(name=f"{self.a.display_name} ให้", value=self.lines(self.a.id))
        e.add_field(name=f"{self.b.display_name} ให้", value=self.lines(self.b.id))
        e.set_thumbnail(url="attachment://trade.png")
        e.set_footer(text=f"ห้องนี้จะถูกลบใน {TRADE_ROOM_DELETE_AFTER} วินาที")
        try:
            await self.msg.edit(embed=e, view=None)
        except Exception:
            pass
        ch = self.guild.get_channel(store.cfg(gid).get("win_channel") or 0) or self.origin
        if ch and getattr(ch, "id", None) != self.room.id:  # แจ้งเตือนเทรดสำเร็จ นอกห้องเทรดด้วย
            try:
                await ch.send(embed=e, files=files("trade.png"), allowed_mentions=discord.AllowedMentions.none())
            except Exception:
                pass
        asyncio.create_task(self._cleanup())


class QtyModal(discord.ui.Modal):
    def __init__(self, trade, pid):
        p = PRIZE[pid]
        super().__init__(title=f"ใส่จำนวน: {p['name']}"[:45])
        self.trade, self.pid = trade, pid
        self.qty = discord.ui.TextInput(label="จำนวนที่จะเสนอ (0 = เอาออก)", default="1", max_length=4)
        self.add_item(self.qty)

    async def on_submit(self, i: discord.Interaction):
        t = self.trade
        try:
            q = int(self.qty.value.strip())
        except ValueError:
            return await i.response.send_message("ใส่เป็นตัวเลขน้า", ephemeral=True)
        have = store.user(t.guild.id, i.user.id)["inv"].get(self.pid, 0)
        q = max(0, min(q, have))
        if q:
            t.offer[i.user.id][self.pid] = q
        else:
            t.offer[i.user.id].pop(self.pid, None)
        t.ok.clear()
        await i.response.send_message(f"✅ ตั้ง {PRIZE[self.pid]['emoji']} {PRIZE[self.pid]['name']} ×{q} แล้ว", ephemeral=True)
        await t.refresh()


class PickSelect(discord.ui.Select):
    def __init__(self, trade, options, ph):
        super().__init__(placeholder=ph, options=options, min_values=1, max_values=1)
        self.trade = trade

    async def callback(self, i: discord.Interaction):
        await i.response.send_modal(QtyModal(self.trade, self.values[0]))


class PickerView(discord.ui.View):
    def __init__(self, trade, uid):
        super().__init__(timeout=120)
        inv = store.user(trade.guild.id, uid)["inv"]
        owned = _sorted_counts(Counter(inv))
        self.has_items = bool(owned)
        for c in range(0, min(len(owned), 125), 25):
            opts = [discord.SelectOption(label=f"{p['name']} (มี {n})"[:100], value=p["id"], emoji=p["emoji"],
                                         description=RARITY[p["rarity"]][0]) for p, n in owned[c:c + 25]]
            self.add_item(PickSelect(trade, opts, f"เลือกตุ๊กตาที่จะเสนอ ({c // 25 + 1})"))


class TradeView(discord.ui.View):
    def __init__(self, trade):
        super().__init__(timeout=TRADE_TIMEOUT)
        self.t = trade

    async def interaction_check(self, i):
        if i.user.id not in (self.t.a.id, self.t.b.id):
            await i.response.send_message("นี่เป็นห้องเทรดของคนอื่นน้า", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="ใส่ของ", emoji="➕", style=discord.ButtonStyle.primary)
    async def add(self, i: discord.Interaction, b: discord.ui.Button):
        v = PickerView(self.t, i.user.id)
        if not v.has_items:
            return await i.response.send_message("กระเป๋าคุณไม่มีตุ๊กตาให้เสนอเลยน้า 🥺", ephemeral=True)
        await i.response.send_message("เลือกตุ๊กตาที่จะเสนอ 👇", view=v, ephemeral=True)

    @discord.ui.button(label="ล้างของฉัน", emoji="🧹", style=discord.ButtonStyle.secondary)
    async def clear(self, i: discord.Interaction, b: discord.ui.Button):
        self.t.offer[i.user.id].clear()
        self.t.ok.clear()
        await i.response.edit_message(embed=self.t.embed(), view=self)

    @discord.ui.button(label="ยอมรับ", emoji="✅", style=discord.ButtonStyle.success)
    async def accept(self, i: discord.Interaction, b: discord.ui.Button):
        t = self.t
        if t.total() == 0:
            return await i.response.send_message("ยังไม่มีของในการเทรดเลยน้า", ephemeral=True)
        t.ok.add(i.user.id)
        if len(t.ok) == 2:
            await i.response.defer()
            await t.finish()
        else:
            await i.response.edit_message(embed=t.embed(), view=self)

    @discord.ui.button(label="ยกเลิก", emoji="❌", style=discord.ButtonStyle.danger)
    async def cancel(self, i: discord.Interaction, b: discord.ui.Button):
        await i.response.defer()
        await self.t.cancel(f"{i.user.display_name} ยกเลิกการเทรด")

    async def on_timeout(self):
        await self.t.cancel("หมดเวลา (ไม่มีใครกดนานเกินไป)")


async def make_room(i, other):
    """สร้างห้องแยกสำหรับเทรด: ลองกระทู้ส่วนตัวก่อน ถ้าไม่ได้ค่อยสร้างห้องข้อความชั่วคราว"""
    name = f"เทรด-{i.user.display_name[:14]}-{other.display_name[:14]}"
    parent = i.channel if isinstance(i.channel, discord.TextChannel) else getattr(i.channel, "parent", None)
    try:
        th = await parent.create_thread(name=name, type=discord.ChannelType.private_thread,
                                        invitable=False, auto_archive_duration=60)
        await th.add_user(i.user)
        await th.add_user(other)
        return th
    except Exception:
        pass
    po = discord.PermissionOverwrite
    ow = {i.guild.default_role: po(view_channel=False),
          i.user: po(view_channel=True, send_messages=True, read_message_history=True),
          other: po(view_channel=True, send_messages=True, read_message_history=True),
          i.guild.me: po(view_channel=True, send_messages=True, manage_channels=True)}
    return await i.guild.create_text_channel(name, overwrites=ow, category=getattr(parent, "category", None), reason="ห้องเทรดตุ๊กตา")


# ════════════════════════ เมนูถาวร ════════════════════════
class MenuView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="เล่นตู้คีบ", emoji="🧸", style=discord.ButtonStyle.success, custom_id="claw:play", row=0)
    async def play(self, i: discord.Interaction, b: discord.ui.Button):
        await start_game(i)

    @discord.ui.button(label="คีบ ×10", emoji="🔟", style=discord.ButtonStyle.primary, custom_id="claw:x10", row=0)
    async def x10(self, i: discord.Interaction, b: discord.ui.Button):
        await run_batch(i, 10)

    @discord.ui.button(label="กระเป๋า", emoji="👜", style=discord.ButtonStyle.primary, custom_id="claw:bag", row=0)
    async def bag(self, i: discord.Interaction, b: discord.ui.Button):
        await show_bag(i)

    @discord.ui.button(label="โทเค็นของฉัน", emoji="🪙", style=discord.ButtonStyle.secondary, custom_id="claw:tokens", row=1)
    async def tokens(self, i: discord.Interaction, b: discord.ui.Button):
        await show_tokens(i)

    @discord.ui.button(label="น้ำยา", emoji="🍀", style=discord.ButtonStyle.secondary, custom_id="claw:potion", row=1)
    async def potion(self, i: discord.Interaction, b: discord.ui.Button):
        await show_potions(i)

    @discord.ui.button(label="วิธีเล่น", emoji="📖", style=discord.ButtonStyle.secondary, custom_id="claw:help", row=1)
    async def help(self, i: discord.Interaction, b: discord.ui.Button):
        gid = i.guild.id if i.guild else 0
        r = rates(gid)
        await respond(i, embed=info(
            "📖 วิธีเล่น",
            "1️⃣ กด **เล่นตู้คีบ** (ใช้ 1 โทเค็น)\n2️⃣ กด ⬅️ ➡️ เลื่อนกรงเล็บไปเหนือตุ๊กตาที่ชอบ\n3️⃣ กด **🪝 คีบ!** แล้วลุ้นเลย\n"
            "🔟 **คีบ ×10** / `/ออโต้` = คีบรวดเดียวหลายรอบ\n"
            f"🎧 อยู่ห้องเสียงครบ {r['voice_minutes']} นาที = +1 โทเค็น (และลุ้นน้ำยาโชค)\n"
            "🔄 `/เทรด @คน` แลกตุ๊กตากันในห้องส่วนตัว · `!กระเป๋า @คน` ดูกระเป๋าเพื่อน\n\n"
            f"**ระดับตุ๊กตา ({len(ROSTER)} แบบ)**\n{tier_summary(gid)}"))


# ════════════════════════ คำสั่ง Slash (ผู้เล่น) ════════════════════════
@bot.tree.command(name="คีบ", description="เล่นตู้คีบตุ๊กตา (ใช้ 1 โทเค็น)")
@app_commands.guild_only()
async def cmd_play(i: discord.Interaction):
    await start_game(i)


@bot.tree.command(name="ออโต้", description="คีบอัตโนมัติหลายรอบรวดเดียว (ใช้โทเค็นรอบละ 1)")
@app_commands.guild_only()
@app_commands.rename(n="จำนวนครั้ง")
@app_commands.describe(n=f"คีบกี่ครั้ง (สูงสุด {MAX_AUTO})")
async def cmd_auto(i: discord.Interaction, n: app_commands.Range[int, 1, MAX_AUTO]):
    await run_batch(i, n)


@bot.tree.command(name="กระเป๋า", description="ดูตุ๊กตาที่คีบได้")
@app_commands.guild_only()
@app_commands.rename(member="ผู้ใช้")
@app_commands.describe(member="อยากดูกระเป๋าของใคร (เว้นว่าง = ของตัวเอง)")
async def cmd_bag(i: discord.Interaction, member: Optional[discord.Member] = None):
    await show_bag(i, member)


@bot.tree.command(name="โทเค็น", description="ดูจำนวนโทเค็นของคุณ")
@app_commands.guild_only()
async def cmd_tokens(i: discord.Interaction):
    await show_tokens(i)


@bot.tree.command(name="น้ำยา", description="ดู/ใช้น้ำยาเพิ่มโชค ×2 ×3 ×5")
@app_commands.guild_only()
async def cmd_potion(i: discord.Interaction):
    await show_potions(i)


@bot.tree.command(name="อันดับ", description="ดูอันดับคนคีบตุ๊กตาเยอะที่สุด")
@app_commands.guild_only()
async def cmd_rank(i: discord.Interaction):
    await respond(i, embed=board_embed(i.guild), fl=files("trophy.png"))


@bot.tree.command(name="เทรด", description="ชวนเพื่อนแลกตุ๊กตากันในห้องส่วนตัว")
@app_commands.guild_only()
@app_commands.rename(member="ผู้ใช้")
@app_commands.describe(member="คนที่จะเทรดด้วย")
async def cmd_trade(i: discord.Interaction, member: discord.Member):
    gid = i.guild.id
    if member.id == i.user.id or member.bot:
        return await i.response.send_message("เทรดกับตัวเองหรือบอทไม่ได้น้า 🥺", ephemeral=True)
    if (gid, i.user.id) in TRADES or (gid, member.id) in TRADES:
        return await i.response.send_message("คุณหรือเพื่อนกำลังเทรดอยู่ รอจบก่อนน้า", ephemeral=True)
    await i.response.defer(ephemeral=True)
    try:
        room = await make_room(i, member)
    except Exception:
        traceback.print_exc()
        return await i.followup.send("สร้างห้องเทรดไม่ได้ 🥲 บอทต้องมีสิทธิ์ Create Private Threads (หรือ Manage Channels)", ephemeral=True)
    t = Trade(i.guild, i.user, member, i.channel)
    t.room, t.view = room, TradeView(t)
    TRADES[(gid, i.user.id)] = TRADES[(gid, member.id)] = t
    t.msg = await room.send(content=f"{i.user.mention} {member.mention}", embed=t.embed(), view=t.view,
                            files=files("trade.png"), allowed_mentions=discord.AllowedMentions(users=[i.user, member]))
    await i.followup.send(f"✅ สร้างห้องเทรดแล้ว {room.mention}", ephemeral=True)


# ════════════════════════ คำสั่ง Slash (เจ้าของบอท) ════════════════════════
@bot.tree.command(name="เมนู", description="(เจ้าของบอท) โพสต์เมนูตู้คีบถาวรในห้องนี้")
@app_commands.guild_only()
@owner_only()
async def cmd_menu(i: discord.Interaction):
    await i.response.defer(ephemeral=True)
    msg = await i.channel.send(embed=menu_embed(i.guild.id), view=MenuView(), files=files("menu_banner.png"))
    store.cfg(i.guild.id)["menu_msg"] = [msg.channel.id, msg.id]
    store.save()
    await i.followup.send("✅ โพสต์เมนูแล้ว", ephemeral=True)


@bot.tree.command(name="แก้เมนู", description="(เจ้าของบอท) แก้ข้อความบนเมนูตู้คีบ")
@app_commands.guild_only()
@owner_only()
@app_commands.rename(title="หัวข้อ", text="ข้อความ")
@app_commands.describe(title="หัวข้อใหม่", text="ข้อความใหม่ (ขึ้นบรรทัดใหม่ใช้ \\n)")
async def cmd_edit_menu(i: discord.Interaction, title: Optional[str] = None, text: Optional[str] = None):
    m = store.cfg(i.guild.id).setdefault("menu", {})
    if title:
        m["title"] = title
    if text:
        m["description"] = text.replace("\\n", "\n")
    store.save()
    ref, done = store.cfg(i.guild.id).get("menu_msg"), False
    if ref:
        try:
            ch = i.guild.get_channel(ref[0]) or await bot.fetch_channel(ref[0])
            await (await ch.fetch_message(ref[1])).edit(embed=menu_embed(i.guild.id))
            done = True
        except discord.HTTPException:
            pass
    await i.response.send_message("✅ แก้เมนูแล้ว" if done else "✅ บันทึกแล้ว (ใช้ /เมนู เพื่อโพสต์เมนูใหม่)", ephemeral=True)


@bot.tree.command(name="บอร์ด", description="(เจ้าของบอท) โพสต์บอร์ดอันดับที่รีเฟรชเองทุก 10 วินาที")
@app_commands.guild_only()
@owner_only()
async def cmd_board(i: discord.Interaction):
    await i.response.defer(ephemeral=True)
    msg = await i.channel.send(embed=board_embed(i.guild), files=files("trophy.png"))
    store.cfg(i.guild.id)["board_msg"] = [msg.channel.id, msg.id]
    store.save()
    await i.followup.send(f"✅ โพสต์บอร์ดแล้ว (รีเฟรชทุก {BOARD_REFRESH} วินาที)", ephemeral=True)


@bot.tree.command(name="ตั้งห้อง", description="(เจ้าของบอท) ตั้งห้องแจ้งเตือน (เว้นห้องว่าง = ล้างค่า)")
@app_commands.guild_only()
@owner_only()
@app_commands.rename(kind="ประเภท", channel="ห้อง")
@app_commands.choices(kind=[
    app_commands.Choice(name="🪙 ห้องแจ้งเตือนได้โทเค็น/น้ำยา", value="token_channel"),
    app_commands.Choice(name="🎉 ห้องแจ้งเตือนคีบตุ๊กตาได้/เทรดสำเร็จ", value="win_channel"),
])
async def cmd_set_channel(i: discord.Interaction, kind: app_commands.Choice[str], channel: Optional[discord.TextChannel] = None):
    store.cfg(i.guild.id)[kind.value] = channel.id if channel else None
    store.save()
    await i.response.send_message(f"✅ ตั้ง **{kind.name}** เป็น {channel.mention if channel else 'ค่าเริ่มต้น'} แล้ว", ephemeral=True)


@bot.tree.command(name="แจกโทเค็น", description=f"(เจ้าของบอท) เสกโทเค็นให้สมาชิก (สูงสุด {MAX_GIVE:,})")
@app_commands.guild_only()
@owner_only()
@app_commands.rename(member="ผู้ใช้", amount="จำนวน")
async def cmd_give(i: discord.Interaction, member: discord.Member, amount: app_commands.Range[int, 1, MAX_GIVE]):
    u = store.user(i.guild.id, member.id)
    u["tokens"] += amount
    u["earned"] += amount
    store.save()
    await i.response.send_message(f"✅ แจก **{amount:,}** โทเค็นให้ {member.mention} แล้ว (คงเหลือ {u['tokens']:,})", ephemeral=True)
    await notify_tokens(i.guild, member, amount, "👑 เจ้าของบอทเสกให้~", fallback=i.channel)


@bot.tree.command(name="หักโทเค็น", description=f"(เจ้าของบอท) หักโทเค็นสมาชิก (สูงสุด {MAX_GIVE:,})")
@app_commands.guild_only()
@owner_only()
@app_commands.rename(member="ผู้ใช้", amount="จำนวน")
async def cmd_take(i: discord.Interaction, member: discord.Member, amount: app_commands.Range[int, 1, MAX_GIVE]):
    u = store.user(i.guild.id, member.id)
    took = min(amount, u["tokens"])
    u["tokens"] -= took
    store.save()
    await i.response.send_message(f"✅ หัก {member.mention} {took:,} โทเค็นแล้ว (คงเหลือ {u['tokens']:,})", ephemeral=True)


@bot.tree.command(name="แจกน้ำยา", description="(เจ้าของบอท) เสกน้ำยาเพิ่มโชคให้สมาชิก")
@app_commands.guild_only()
@owner_only()
@app_commands.rename(member="ผู้ใช้", mult="ระดับ", amount="จำนวน")
@app_commands.choices(mult=[app_commands.Choice(name=f"×{m}", value=m) for m in POTIONS])
async def cmd_give_potion(i: discord.Interaction, member: discord.Member, mult: app_commands.Choice[int],
                          amount: app_commands.Range[int, 1, 100] = 1):
    u = store.user(i.guild.id, member.id)
    u["potions"][str(mult.value)] = u["potions"].get(str(mult.value), 0) + amount
    store.save()
    await i.response.send_message(f"✅ แจกน้ำยา ×{mult.value} จำนวน {amount} ขวดให้ {member.mention} แล้ว", ephemeral=True)
    await notify_potion(i.guild, member, mult.value, fallback=i.channel, reason="👑 เจ้าของบอทเสกให้~")


# ════════════════════════ หน้าปรับเรท (เจ้าของบอท) ════════════════════════
def num(s, lo, hi, what, cast=float):
    try:
        v = cast(str(s).strip().replace("%", ""))
    except ValueError:
        raise ValueError(f"{what}: ใส่เป็นตัวเลขน้า")
    if not lo <= v <= hi:
        raise ValueError(f"{what}: ใส่ระหว่าง {lo:g}–{hi:g}")
    return v


class RateModal(discord.ui.Modal):
    def __init__(self, title, fields, apply):
        super().__init__(title=title[:45])
        self.apply, self.inputs = apply, {}
        for key, label, default, required in fields:
            ti = discord.ui.TextInput(label=label[:45], default=str(default), max_length=60, required=required)
            self.add_item(ti)
            self.inputs[key] = ti

    async def on_submit(self, i: discord.Interaction):
        try:
            msg = self.apply({k: v.value.strip() for k, v in self.inputs.items()})
        except ValueError as ex:
            msg = f"❌ {ex}"
        await i.response.send_message(msg, ephemeral=True)


def settings_embed(gid):
    r = rates(gid)
    ps, ws = pool(gid)
    empty_share = r["empty_weight"] / sum(ws) if sum(ws) and r["empty_weight"] > 0 else 0
    w = r["potion_weights"]
    e = info("⚙️ ตั้งค่าตู้คีบ", "กดปุ่มด้านล่างเพื่อปรับ — มีผลทันที เฉพาะเซิร์ฟเวอร์นี้", 0x90CAF9)
    e.add_field(name="⏱️ เวลาออนต่อโทเค็น", value=f"{r['voice_minutes']} นาที = 1 โทเค็น")
    e.add_field(name="🎯 เรทรวม", value=f"×{r['win_mult']:g} (ตัวคูณโอกาสคีบติดทุกตัว)")
    e.add_field(name="💨 ช่องว่าง", value=f"น้ำหนัก {r['empty_weight']:g} (โผล่ ~{empty_share * 100:.1f}% ต่อช่อง)")
    e.add_field(name="🔒 ซีเคร็ท", value=f"{r['secret_rate']:g}% ทุกรอบ")
    e.add_field(name="🍀 น้ำยา", value=f"ดรอป {r['potion_drop']:g}%/นาที · ×2:×3:×5 = {w[0]:g}:{w[1]:g}:{w[2]:g} · ใช้ได้ {r['potion_minutes']} นาที")
    e.add_field(name="🧸 ปรับรายตัว", value=f"{len(r['prizes'])} ตัวที่ปรับไว้")
    return e


def rates_table(gid):
    ps, ws = pool(gid)
    tot = sum(ws)
    lines = []
    for p, wt in zip(ps, ws):
        if p["id"] == "empty":
            lines.append(f"{p['emoji']} ช่องว่าง · โผล่ {wt / tot * 100:.1f}%")
        else:
            lines.append(f"{p['emoji']} {p['name']} {RARITY[p['rarity']][1]} · คีบติด {pct(eff_chance(gid, p))} · โผล่ {wt / tot * 100:.1f}%")
    r = rates(gid)
    lines.append(f"🔒 ซีเคร็ท {', '.join(p['name'] for p in SECRET)} · {r['secret_rate']:g}% ทุกรอบ")
    return info("📋 เรททั้งหมด", "\n".join(lines)[:4000], 0x90CAF9)


def find_prize(text):
    q = text.strip().lower()
    return next((p for p in ROSTER if p["id"] == q or p["name"].lower() == q), None) or \
        next((p for p in ROSTER if q and (q in p["name"].lower() or q in p["id"])), None)


class SettingsView(discord.ui.View):
    def __init__(self, gid):
        super().__init__(timeout=600)
        self.gid = gid

    async def interaction_check(self, i):
        if await is_owner(i):
            return True
        await i.response.send_message("🔒 เฉพาะเจ้าของบอทน้า", ephemeral=True)
        return False

    @discord.ui.button(label="เวลาออน/โทเค็น", emoji="⏱️", style=discord.ButtonStyle.primary, row=0)
    async def b_time(self, i: discord.Interaction, b: discord.ui.Button):
        gid = self.gid

        def ap(v):
            m = num(v["m"], 1, 600, "นาที", int)
            set_rate(gid, voice_minutes=m)
            return f"✅ ตอนนี้ออนห้องเสียง **{m} นาที = 1 โทเค็น**"
        await i.response.send_modal(RateModal("เวลาออนต่อโทเค็น", [("m", "กี่นาที ต่อ 1 โทเค็น (1–600)", rates(gid)["voice_minutes"], True)], ap))

    @discord.ui.button(label="เรทรวม/ช่องว่าง/ซีเคร็ท", emoji="🎯", style=discord.ButtonStyle.primary, row=0)
    async def b_rate(self, i: discord.Interaction, b: discord.ui.Button):
        gid, r = self.gid, rates(self.gid)

        def ap(v):
            wm = num(v["wm"], 0.1, 5, "เรทรวม")
            ew = num(v["ew"], 0, 500, "ช่องว่าง")
            sr = num(v["sr"], 0, 100, "ซีเคร็ท")
            set_rate(gid, win_mult=wm, empty_weight=ew, secret_rate=sr)
            return f"✅ เรทรวม ×{wm:g} · ช่องว่าง {ew:g} · ซีเคร็ท {sr:g}%"
        await i.response.send_modal(RateModal("เรทรวม", [
            ("wm", "เรทรวม ตัวคูณโอกาสคีบติด (0.1–5)", r["win_mult"], True),
            ("ew", "น้ำหนักช่องว่าง (0–500 · 0=ปิด)", r["empty_weight"], True),
            ("sr", "ซีเคร็ท % ต่อรอบ (0–100)", r["secret_rate"], True)], ap))

    @discord.ui.button(label="เรทรายตัว", emoji="🧸", style=discord.ButtonStyle.primary, row=0)
    async def b_prize(self, i: discord.Interaction, b: discord.ui.Button):
        gid = self.gid

        def ap(v):
            p = find_prize(v["name"])
            if not p:
                raise ValueError("หาตุ๊กตาชื่อนี้ไม่เจอ (พิมพ์ชื่อหรือรหัส เช่น หมี / bear)")
            if p["rarity"] == "secret":
                raise ValueError("ซีเคร็ทปรับที่ปุ่ม 🎯 เรทรวม/ซีเคร็ท")
            ov = dict(rates(gid)["prizes"])
            cur = dict(ov.get(p["id"], {}))
            if v["chance"]:
                cur["chance"] = num(v["chance"], 0, 100, "โอกาสคีบติด") / 100
            if v["weight"]:
                cur["weight"] = num(v["weight"], 0, 1000, "น้ำหนักโผล่")
            ov[p["id"]] = cur
            set_rate(gid, prizes=ov)
            c, w = pstat(gid, p)
            return f"✅ {p['emoji']} {p['name']} · คีบติด {pct(c)} · น้ำหนักโผล่ {w:g}"
        await i.response.send_modal(RateModal("เรทรายตัว", [
            ("name", "ชื่อ/รหัสตุ๊กตา (เช่น หมี หรือ bear)", "", True),
            ("chance", "โอกาสคีบติด % (เว้นว่าง=ไม่แก้)", "", False),
            ("weight", "น้ำหนักโผล่ในตู้ (เว้นว่าง=ไม่แก้)", "", False)], ap))

    @discord.ui.button(label="น้ำยา", emoji="🍀", style=discord.ButtonStyle.primary, row=1)
    async def b_potion(self, i: discord.Interaction, b: discord.ui.Button):
        gid, r = self.gid, rates(self.gid)

        def ap(v):
            dr = num(v["dr"], 0, 100, "โอกาสดรอป")
            ws = [num(x, 0, 1000, "สัดส่วน") for x in v["w"].replace(" ", "").split(",")]
            if len(ws) != 3 or sum(ws) <= 0:
                raise ValueError("สัดส่วนต้องมี 3 ค่า เช่น 60,30,10")
            mins = num(v["m"], 1, 120, "นาที", int)
            set_rate(gid, potion_drop=dr, potion_weights=ws, potion_minutes=mins)
            return f"✅ ดรอป {dr:g}%/นาที · ×2:×3:×5 = {ws[0]:g}:{ws[1]:g}:{ws[2]:g} · ใช้ได้ {mins} นาที"
        await i.response.send_modal(RateModal("ตั้งค่าน้ำยา", [
            ("dr", "โอกาสดรอป % ต่อนาที (0–100)", r["potion_drop"], True),
            ("w", "สัดส่วนดรอป ×2,×3,×5", ",".join(f"{x:g}" for x in r["potion_weights"]), True),
            ("m", "ใช้ได้กี่นาที (1–120)", r["potion_minutes"], True)], ap))

    @discord.ui.button(label="ดูเรททั้งหมด", emoji="📋", style=discord.ButtonStyle.secondary, row=1)
    async def b_table(self, i: discord.Interaction, b: discord.ui.Button):
        await i.response.send_message(embed=rates_table(self.gid), ephemeral=True)

    @discord.ui.button(label="รีเซ็ตเรท", emoji="🔄", style=discord.ButtonStyle.danger, row=1)
    async def b_reset(self, i: discord.Interaction, b: discord.ui.Button):
        store.cfg(self.gid).pop("rates", None)
        store.save()
        await i.response.edit_message(embed=settings_embed(self.gid), view=self)


@bot.tree.command(name="ตั้งค่าตู้", description="(เจ้าของบอท) ปรับเรท/เวลาออน/น้ำยา ของตู้คีบ")
@app_commands.guild_only()
@owner_only()
async def cmd_settings(i: discord.Interaction):
    await i.response.send_message(embed=settings_embed(i.guild.id), view=SettingsView(i.guild.id), ephemeral=True)


# ════════════════════════ ออนห้องเสียง = ได้โทเค็น + สุ่มดรอปน้ำยา ════════════════════════
@tasks.loop(seconds=60)
async def voice_tick():
    try:
        earned, drops = [], []
        for guild in bot.guilds:
            r = rates(guild.id)
            afk = guild.afk_channel
            for vc in guild.voice_channels:
                if afk and vc.id == afk.id:
                    continue
                for m in vc.members:
                    if m.bot or (not COUNT_DEAFENED and (m.voice.self_deaf or m.voice.deaf)):
                        continue
                    u = store.user(guild.id, m.id)
                    u["voice_min"] += 1
                    if u["voice_min"] >= r["voice_minutes"]:
                        u["voice_min"] = 0
                        u["tokens"] += 1
                        u["earned"] += 1
                        earned.append((guild, m, vc))
                    if random.random() * 100 < r["potion_drop"]:
                        mult = random.choices(POTIONS, weights=r["potion_weights"], k=1)[0]
                        u["potions"][str(mult)] = u["potions"].get(str(mult), 0) + 1
                        drops.append((guild, m, mult))
        store.save()
        for guild, m, vc in earned:
            await notify_tokens(guild, m, 1, f"🎧 ออนไลน์ในห้อง {vc.mention} ครบ {rates(guild.id)['voice_minutes']} นาที",
                                delete_after=NOTICE_DELETE_AFTER)
        for guild, m, mult in drops:
            await notify_potion(guild, m, mult, delete_after=NOTICE_DELETE_AFTER)
    except Exception:
        traceback.print_exc()


@voice_tick.before_loop
async def _before():
    await bot.wait_until_ready()


# ════════════════════════ เริ่มทำงาน ════════════════════════
def load_token():
    t = os.getenv("DISCORD_TOKEN")
    if t:
        return t.strip()
    f = BASE / "token.txt"
    if f.exists():
        return f.read_text("utf-8").strip()
    sys.exit("❌ ไม่พบโทเค็นบอท: ใส่ในตัวแปร DISCORD_TOKEN หรือสร้างไฟล์ token.txt แล้ววางโทเค็นลงไป")


if __name__ == "__main__":
    bot.run(load_token())
