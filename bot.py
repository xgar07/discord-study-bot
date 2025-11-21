import os
from datetime import datetime, timezone, timedelta, time

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

# =============================
# LOAD ENV FIRST !!
# =============================
load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
REMINDER_CHANNEL_ID = os.getenv("REMINDER_CHANNEL_ID")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# =============================
# BOT READY
# =============================
@bot.event
async def on_ready():
    print(f"Bot logged in as {bot.user}")

    # Start reminder loop
    if not daily_reminder.is_running():
        daily_reminder.start()
        print("Daily reminder started.")
    
    print("All systems OK.")

# =============================
# DAILY REMINDER LOOP (07:00 WIB)
# =============================
@tasks.loop(time=time(hour=7, minute=0))
async def daily_reminder():
    """
    Mengirim reminder harian setiap jam 07:00 WIB.
    Railway berjalan di UTC, jadi loop time() harus tetap time() lokal
    dan discord.py akan menyesuaikannya.
    """
    if REMINDER_CHANNEL_ID is None:
        print("Reminder skipped — REMINDER_CHANNEL_ID not set.")
        return

    channel = bot.get_channel(int(REMINDER_CHANNEL_ID))
    if channel:
        await channel.send("📢 **Good morning! Jangan lupa belajar hari ini yaa!** ✨")
        print("Reminder sent.")
    else:
        print("Reminder failed — Channel not found.")

# =============================
# COMMAND: set reminder channel
# =============================
@bot.tree.command(name="setreminder", description="Set channel untuk daily reminder")
async def set_reminder(interaction: discord.Interaction):
    global REMINDER_CHANNEL_ID

    REMINDER_CHANNEL_ID = interaction.channel.id

    # update ke .env file kalau kamu mau (opsional)
    with open(".env", "a") as f:
        f.write(f"\nREMINDER_CHANNEL_ID={REMINDER_CHANNEL_ID}")

    await interaction.response.send_message(
        f"📌 Reminder channel diset ke: {interaction.channel.mention}"
    )

# =============================
# SYNC SLASH COMMANDS
# =============================
@bot.event
async def on_connect():
    try:
        bot.tree.sync()
        print("Slash commands synced.")
    except Exception as e:
        print("Slash sync failed:", e)

# =============================
# RUN BOT
# =============================
bot.run(TOKEN)
