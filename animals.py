# -*- coding: utf-8 -*-
"""
animals.py — รายชื่อตุ๊กตาทั้งหมด + เรทเริ่มต้น (ปรับในดิสคอร์ดได้ด้วย /ตั้งค่าตู้)
  weight = โอกาสโผล่ในตู้ (ยิ่งมากยิ่งเจอบ่อย)   chance = โอกาสคีบติดตอนกด (0–1)
  ระดับ secret ไม่โชว์ในตู้ — มีโอกาสโผล่เองทุกรอบ (ค่าเริ่มต้น 1%)
"""

RARITY = {  # ชื่อ, อีโมจิ, สี embed
    "common":   ("ธรรมดา", "⚪", 0xF8BBD0),
    "uncommon": ("ไม่ธรรมดา", "🟢", 0xA5D6A7),
    "rare":     ("หายาก", "💜", 0xB39DDB),
    "epic":     ("มหากาพย์", "💎", 0x4FC3F7),
    "legend":   ("ตำนาน", "🌟", 0xFFD54F),
    "mystic":   ("มิสติก", "🔮", 0x7C4DFF),
    "secret":   ("ซีเคร็ท", "🔒", 0xFF80AB),
    "none":     ("ไม่มีของ", "⬜", 0xB0BEC5),
}
RARITY_ORDER = ["common", "uncommon", "rare", "epic", "legend", "mystic", "secret"]


def _a(id, name, emoji, rarity, weight, chance):
    return dict(id=id, name=name, emoji=emoji, rarity=rarity, weight=weight, chance=chance)


ROSTER = [
    # ── ธรรมดา (12): เจอบ่อย คีบง่าย
    _a("bear",     "น้องหมีน้ำผึ้ง",      "🧸", "common", 28, 0.55),
    _a("bunny",    "น้องกระต่ายพีช",     "🐰", "common", 28, 0.55),
    _a("cat",      "น้องแมวส้ม",         "🐱", "common", 28, 0.50),
    _a("duck",     "น้องเป็ดเหลือง",     "🐥", "common", 28, 0.50),
    _a("dog",      "น้องหมาจอมซน",       "🐶", "common", 28, 0.55),
    _a("hamster",  "แฮมสเตอร์แก้มป่อง",  "🐹", "common", 28, 0.55),
    _a("mouse",    "น้องหนูจี๊ด",         "🐭", "common", 28, 0.55),
    _a("sheep",    "แกะน้อยปุยเมฆ",      "🐑", "common", 28, 0.52),
    _a("cow",      "น้องวัวนมสีขาว",     "🐮", "common", 28, 0.52),
    _a("frog",     "กบเขียวใจดี",        "🐸", "common", 28, 0.50),
    _a("turtle",   "เต่าน้อยใจเย็น",     "🐢", "common", 28, 0.50),
    _a("babydino", "ไดโนน้อยฟักไข่",     "🦎", "common", 28, 0.50),
    # ── ไม่ธรรมดา (11)
    _a("panda",    "น้องแพนด้า",         "🐼", "uncommon", 12, 0.40),
    _a("pig",      "น้องหมูชมพู",        "🐷", "uncommon", 12, 0.40),
    _a("penguin",  "เพนกวินจอมเซ่อ",     "🐧", "uncommon", 12, 0.40),
    _a("koala",    "โคอาล่าขี้เซา",       "🐨", "uncommon", 12, 0.40),
    _a("fox",      "จิ้งจอกน้อยเจ้าเล่ห์", "🦊", "uncommon", 12, 0.40),
    _a("raccoon",  "แรคคูนจอมแอบ",       "🦝", "uncommon", 12, 0.40),
    _a("monkey",   "ลิงน้อยจอมซน",       "🐵", "uncommon", 12, 0.40),
    _a("elephant", "ช้างน้อยใจดี",        "🐘", "uncommon", 12, 0.38),
    _a("trike",    "ไทรเซราทอปส์",       "🦏", "uncommon", 12, 0.38),
    _a("stego",    "สเตโกซอรัส",         "🐊", "uncommon", 12, 0.38),
    _a("brachio",  "บราคิโอซอรัส",       "🦕", "uncommon", 12, 0.38),
    # ── หายาก (9)
    _a("giraffe",  "ยีราฟคอยาว",         "🦒", "rare", 5, 0.26),
    _a("lion",     "สิงโตขนฟู",          "🦁", "rare", 5, 0.26),
    _a("tiger",    "เสือน้อยลายสวย",     "🐯", "rare", 5, 0.26),
    _a("polar",    "หมีขั้วโลก",          "🐻", "rare", 5, 0.26),
    _a("dolphin",  "โลมาแสนรู้",          "🐬", "rare", 5, 0.26),
    _a("octopus",  "ปลาหมึกสีชมพู",      "🐙", "rare", 5, 0.26),
    _a("ptero",    "เทอโรซอร์ล่องลม",    "🦅", "rare", 5, 0.24),
    _a("trex",     "ที-เร็กซ์จอมพลัง",   "🦖", "rare", 5, 0.24),
    _a("unicorn",  "ยูนิคอร์นสายรุ้ง",   "🦄", "rare", 5, 0.22),
    # ── มหากาพย์ (3)
    _a("dragon",   "มังกรน้อยพ่นไฟ",     "🐉", "epic", 2, 0.14),
    _a("whale",    "วาฬน้อยใจกว้าง",     "🐳", "epic", 2, 0.14),
    _a("phoenix",  "ฟีนิกซ์เพลิงทอง",    "🔥", "epic", 2, 0.14),
    # ── ตำนาน (2)
    _a("maneki",   "แมวกวักนำโชค",       "🐈", "legend", 0.8, 0.08),
    _a("star",     "ดาวทองวิเศษ",        "⭐", "legend", 0.8, 0.08),
    # ── มิสติก (3): เหนือกว่าตำนาน โผล่น้อยมาก
    _a("wolf",     "หมาป่าจันทรา",       "🐺", "mystic", 0.3, 0.05),
    _a("fairy",    "ผีเสื้อนางฟ้า",       "🦋", "mystic", 0.3, 0.05),
    _a("deer",     "กวางเทพพนา",         "🦌", "mystic", 0.3, 0.05),
    # ── ซีเคร็ท (ไม่อยู่ในตู้ · เรทตั้งที่ secret_rate)
    _a("moodeng",  "หมูเด้ง",            "🦛", "secret", 0, 1.0),
]

PRIZE = {p["id"]: p for p in ROSTER}
MACHINE = [p for p in ROSTER if p["rarity"] != "secret"]
SECRET = [p for p in ROSTER if p["rarity"] == "secret"]
EMPTY = dict(id="empty", name="ช่องว่าง", emoji="💨", rarity="none", weight=0, chance=0.0)
