# bot.py
import discord
from discord import app_commands
from discord.ext import commands, tasks
import os
import json
from datetime import datetime, timezone
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
CLIENT_ID = os.getenv("CLIENT_ID")

DATA_PATH = Path("data/study_log.json")
DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
if not DATA_PATH.exists():
    DATA_PATH.write_text(json.dumps({"active_sessions": {}, "logs": [], "progress": []}, indent=2))

def load_data():
    return json.loads(DATA_PATH.read_text())

def save_data(d):
    DATA_PATH.write_text(json.dumps(d, indent=2))

def iso_now():
    return datetime.now(timezone.utc).isoformat()

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
    # sync commands to guilds (global may take up to 1 hour to appear)
    try:
        await tree.sync()
        print("Slash commands synced.")
    except Exception as e:
        print("Could not sync commands:", e)

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
                          timestamp=datetime.now(timezone.utc))
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
    start_dt = datetime.fromisoformat(start_iso)
    end_dt = datetime.now(timezone.utc)
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

    embed = discord.Embed(title="Progress Terakhir", color=0x2F3136, timestamp=datetime.now(timezone.utc))
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
    today = datetime.now(timezone.utc).date()
    user_logs = [l for l in data["logs"] if l["user_id"] == uid and datetime.fromisoformat(l["saved_at"]).date() == today]
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

# Run bot
if __name__ == "__main__":
    if not TOKEN:
        print("Error: DISCORD_TOKEN environment variable not set.")
    else:
        bot.run(TOKEN)

print ("TOKEN",TOKEN)