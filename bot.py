import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import discord
from discord import app_commands
from discord.ext import tasks
import datetime

# --- RenderのWeb Service対策（簡易サーバー） ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

threading.Thread(target=run_web_server, daemon=True).start()
# ------------------------------------------------

JST = datetime.timezone(datetime.timedelta(hours=9))
TARGET_DATE = datetime.datetime(2027, 1, 1, 0, 0, 0, tzinfo=JST)
TARGET_UNIX = int(TARGET_DATE.timestamp())

# Renderの環境変数からトークンを読み込む
TOKEN = os.getenv("TOKEN")
# 年越しメッセージを送りたいチャンネルのID（不要なら 0 のまま）
ANNOUNCE_CHANNEL_ID = 0 

class CountdownBot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)
        self.announced = False

    async def setup_hook(self):
        await self.tree.sync()
        self.check_new_year.start()

    @tasks.loop(seconds=1)
    async def check_new_year(self):
        if ANNOUNCE_CHANNEL_ID == 0 or self.announced:
            return
        
        now = datetime.datetime.now(JST)
        if now >= TARGET_DATE:
            channel = self.get_channel(ANNOUNCE_CHANNEL_ID)
            if channel:
                await channel.send("🎉 **2027年になりました！あけましておめでとうございます！** 🎍")
                self.announced = True

bot = CountdownBot()

@bot.event
async def on_ready():
    print(f"ログインしました: {bot.user}")

@bot.tree.command(name="countdown", description="2027年までの残り時間をリアルタイムで表示します")
async def countdown(interaction: discord.Interaction):
    now = datetime.datetime.now(JST)
    diff = TARGET_DATE - now

    if diff.total_seconds() <= 0:
        await interaction.response.send_message("🎉 すでに2027年を迎えています！")
        return

    days = diff.days
    hours, remainder = divmod(diff.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    embed = discord.Embed(
        title="⏳ 2027年までのリアルタイムカウントダウン",
        description=(
            f"2027年1月1日まであと...\n"
            f"## <t:{TARGET_UNIX}:R>\n\n"
            f"📊 **詳細（コマンド実行時点）**\n"
            f"`{days}日 {hours}時間 {minutes}分 {seconds}秒`"
        ),
        color=discord.Color.gold()
    )
    await interaction.response.send_message(embed=embed)

bot.run(TOKEN)