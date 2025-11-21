# bot.py
import discord
from discord import app_commands
from discord.ext import commands, tasks

import os
import json
import random
import datetime

from dotenv import load_dotenv
from pathlib import Path

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
CLIENT_ID = os.getenv("CLIENT_ID")

REMINDER_CHANNEL_ID = os.getenv("REMINDER_CHANNEL_ID")
REMINDER_CHANNEL_ID = int(REMINDER_CHANNEL_ID) if REMINDER_CHANNEL_ID else None

REMINDER_PATH = Path("data/reminder.json")
if not REMINDER_PATH.exists():
    REMINDER_PATH.write_text(json.dumps({"users": {}}, indent=2))

def load_reminder():
    return json.loads(REMINDER_PATH.read_text())

def save_reminder(d):
    REMINDER_PATH.write_text(json.dumps(d, indent=2))


DATA_PATH = Path("data/study_log.json")
DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
if not DATA_PATH.exists():
    DATA_PATH.write_text(json.dumps({"active_sessions": {}, "logs": [], "progress": []}, indent=2))

def load_data():
    return json.loads(DATA_PATH.read_text())

def save_data(d):
    DATA_PATH.write_text(json.dumps(d, indent=2))

def iso_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def duration_hms(seconds: int):
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    parts = []
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    parts.append(f"{s}s")
    return " ".join(parts)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

GUILD_ID = 1402907249315282966

@bot.event
async def on_ready():
    print(f"Bot logged in as {bot.user} (ID: {bot.user.id})")

    # Sync slash commands
    try:
         await tree.sync(guild=discord.Object(id=GUILD_ID))
         print(f"Slash commands synced to guild {GUILD_ID}")
    except Exception as e:
        print("Could not sync commands:", e)

    if not check_reminders.is_running():
        check_reminders.start()
        print("Personal reminder started.")

    # Start daily reminder
    if not daily_reminder.is_running():
        daily_reminder.start()
        print("Daily reminder started.")

# ---------- /study start ----------
@tree.command(name="study_start", description="Mulai sesi belajar (mulai timer)")
async def study_start(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    user_id = str(interaction.user.id)
    data = load_data()

    if user_id in data["active_sessions"]:
        start_iso = data["active_sessions"][user_id]
        embed = discord.Embed(title="Sesi sudah berjalan",
                              description=f"Kamu sudah memulai sesi tadi pada `{start_iso}` (UTC).",
                              color=0xE59A2F)
        await interaction.followup.send(embed=embed, ephemeral=True)
        return

    data["active_sessions"][user_id] = iso_now()
    save_data(data)
    embed = discord.Embed(title="Sesi dimulai ✅",
                          description="Timer belajar dimulai. Fokus 25-50 menit, lalu istirahat singkat!",
                          color=0x57F287,
                          timestamp=datetime.datetime.now(datetime.timezone.utc))
    embed.add_field(name="Mulai (UTC)", value=data["active_sessions"][user_id], inline=False)
    await interaction.followup.send(embed=embed, ephemeral=True)

# ---------- /study stop ----------
@tree.command(name="study_stop", description="Hentikan sesi belajar dan simpan durasi")
async def study_stop(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    user_id = str(interaction.user.id)
    data = load_data()

    if user_id not in data["active_sessions"]:
        await interaction.followup.send("Belum ada sesi yang berjalan. Mulai dulu pake `/study_start`.", ephemeral=True)
        return

    start_iso = data["active_sessions"].pop(user_id)
    start_dt = datetime.datetime.fromisoformat(start_iso)
    end_dt = datetime.datetime.now(datetime.timezone.utc)
    delta = end_dt - start_dt
    seconds = int(delta.total_seconds())

    log_entry = {
        "user_id": user_id,
        "start": start_iso,
        "end": end_dt.isoformat(),
        "duration_seconds": seconds,
        "duration_human": duration_hms(seconds),
        "saved_at": iso_now()
    }
    data["logs"].append(log_entry)
    save_data(data)

    embed = discord.Embed(title="Sesi diberhentikan ✅",
                          description=f"Durasi: **{log_entry['duration_human']}**",
                          timestamp=end_dt,
                          color=0x5865F2)
    embed.add_field(name="Mulai (UTC)", value=start_iso, inline=True)
    embed.add_field(name="Selesai (UTC)", value=end_dt.isoformat(), inline=True)
    await interaction.followup.send(embed=embed, ephemeral=True)

# ---------- /progress add ----------
@tree.command(name="progress_add", description="Tambahkan catatan progres singkat")
@app_commands.describe(text="Deskripsikan apa yang sudah kamu kerjakan (singkat).")
async def progress_add(interaction: discord.Interaction, text: str):
    await interaction.response.defer(ephemeral=True)
    data = load_data()
    entry = {
        "user_id": str(interaction.user.id),
        "text": text,
        "created_at": iso_now()
    }
    data["progress"].append(entry)
    save_data(data)
    await interaction.followup.send(f"Progress disimpan: `{text}`", ephemeral=True)

# ---------- /progress list ----------
@tree.command(name="progress_list", description="Tampilkan list progressmu (10 terakhir)")
@app_commands.describe(limit="Jumlah item terakhir yang ingin ditampilkan (default 10).")
async def progress_list(interaction: discord.Interaction, limit: int = 10):
    await interaction.response.defer(ephemeral=True)
    data = load_data()
    uid = str(interaction.user.id)
    items = [p for p in data["progress"] if p["user_id"] == uid]
    items = items[-limit:]
    if not items:
        await interaction.followup.send("Belum ada progress yang disimpan.", ephemeral=True)
        return

    embed = discord.Embed(title="Progress Terakhir", color=0x2F3136, timestamp=datetime.datetime.now(datetime.timezone.utc))
    for it in reversed(items):
        t = it["created_at"]
        text = it["text"]
        embed.add_field(name=t, value=text, inline=False)
    await interaction.followup.send(embed=embed, ephemeral=True)

# ---------- optional: show summary ----------
@tree.command(name="study_summary", description="Ringkasan sesi belajar (hari ini)")
async def study_summary(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    data = load_data()
    uid = str(interaction.user.id)
    # filter logs for this user and for today (UTC)
    today = datetime.datetime.now(datetime.timezone.utc).date()

    user_logs = [l for l in data["logs"] if l["user_id"] == uid and datetime.datetime.fromisoformat(l["saved_at"]).date() == today]
    if not user_logs:
        await interaction.followup.send("Belum ada sesi untuk hari ini.", ephemeral=True)
        return
    total_seconds = sum(l["duration_seconds"] for l in user_logs)
    embed = discord.Embed(title="Ringkasan Hari Ini", color=0x57F287)
    embed.add_field(name="Jumlah sesi", value=str(len(user_logs)))
    embed.add_field(name="Total waktu", value=duration_hms(total_seconds))
    # show up to 5 last sessions
    for l in user_logs[-5:]:
        embed.add_field(name=l["start"], value=l["duration_human"], inline=False)
    await interaction.followup.send(embed=embed, ephemeral=True)

#COMMAND SET REMINDER
@tree.command(name="set_reminder", description="Atur jam harian untuk reminder belajar (format HH:MM, WIB)")
@app_commands.describe(time_str="Contoh: 07:30")
async def set_reminder(interaction: discord.Interaction, time_str: str):

    await interaction.response.defer(ephemeral=True)

    # Validasi format
    try:
        hour, minute = map(int, time_str.split(":"))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
    except:
        await interaction.followup.send("Format salah! Gunakan HH:MM, contoh: `07:30`", ephemeral=True)
        return

    reminder = load_reminder()
    reminder["users"][str(interaction.user.id)] = time_str
    save_reminder(reminder)

    await interaction.followup.send(
        f"⏰ Reminder diset setiap hari jam **{time_str} WIB**.\nAku bakal ingetin kamu buat belajar! 📚🔥",
        ephemeral=True
    )
#COMMAND REMOVE REMINDER
@tree.command(name="remove_reminder", description="Hapus reminder harianmu")
async def remove_reminder(interaction: discord.Interaction):

    await interaction.response.defer(ephemeral=True)

    reminder = load_reminder()
    uid = str(interaction.user.id)

    if uid in reminder["users"]:
        reminder["users"].pop(uid)
        save_reminder(reminder)
        await interaction.followup.send("❌ Reminder kamu sudah dimatikan.", ephemeral=True)
    else:
        await interaction.followup.send("Kamu belum punya reminder aktif.", ephemeral=True)

#CEK REMINDER ALL USER
@tasks.loop(minutes=1)
async def check_reminders():
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7)))
    current = now.strftime("%H:%M")

    reminder = load_reminder()
    for uid, time_str in reminder["users"].items():
        if time_str == current:
            user = await bot.fetch_user(int(uid))
            if user:
                motivational = random.choice([
                    "Small progress is still progress 🌱",
                    "Your future self will thank you.",
                    "Discipline beats motivation ✨",
                    "One step at a time. You got this! 💪",
                    "Consistent > perfect. Keep going! 🔥"
                ])
                try:
                    await user.send(f"⏰ **Reminder belajar!**\n{motivational}")
                except:
                    print(f"DM ke {uid} gagal.")


# DAILY REMINDER
@tasks.loop(time=datetime.time(hour=19, minute=0, tzinfo=datetime.timezone(datetime.timedelta(hours=7))))
async def daily_reminder():
    channel = bot.get_channel(REMINDER_CHANNEL_ID)
    if channel:
        await channel.send("Selamat Malam! Jangan lupa belajar hari ini yaw! Semangat 💪📚")
    else:
        print("Reminder channel not found!")


# Run bot
if __name__ == "__main__":
    if not TOKEN:
        print("Error: DISCORD_TOKEN environment variable not set.")
    else:
        bot.run(TOKEN)