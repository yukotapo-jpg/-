import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import discord
from discord import app_commands
from discord.ext import tasks
import datetime
import random

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

TOKEN = os.getenv("TOKEN")
ANNOUNCE_CHANNEL_ID = 0 

# チーム分け結果を見やすいEmbedにする共通関数
def create_team_embed(members: list[str], team_count: int, title: str, reroll_count: int = 0) -> discord.Embed:
    shuffled = members.copy()
    random.shuffle(shuffled)
    teams = [shuffled[i::team_count] for i in range(team_count)]
    team_labels = ["🔴 チームA", "🔵 チームB", "🟢 チームC", "🟡 チームD", "🟣 チームE", "🟠 チームF"]

    embed = discord.Embed(title=title, color=discord.Color.blurple())
    for idx, team in enumerate(teams):
        label = team_labels[idx] if idx < len(team_labels) else f"⚪ チーム{idx + 1}"
        member_list = "\n".join(f"・{m}" for m in team) if team else "（メンバーなし）"
        embed.add_field(name=f"{label}（{len(team)}人）", value=member_list, inline=True)
    
    if reroll_count > 0:
        embed.set_footer(text=f"🔄 やり直し回数: {reroll_count}回目")
    return embed

# --- 🔄 やり直しボタンの仕組み ---
class RerollTeamView(discord.ui.View):
    def __init__(self, team_count: int, title: str, members: list[str] = None, vc_id: int = None, include_bots: bool = False):
        super().__init__(timeout=600)  # 10分間ボタンが有効
        self.team_count = team_count
        self.title = title
        self.members = members
        self.vc_id = vc_id
        self.include_bots = include_bots
        self.reroll_count = 0

    @discord.ui.button(label="🔄 もう一回引き直す", style=discord.ButtonStyle.primary)
    async def reroll_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # VCからのチーム分けの場合は最新メンバーを再取得
        if self.vc_id:
            vc = interaction.guild.get_channel(self.vc_id)
            if not vc:
                await interaction.response.send_message("❌ ボイスチャンネルが見つかりませんでした。", ephemeral=True)
                return
            current_members = [m.display_name for m in vc.members if self.include_bots or not m.bot]
        else:
            current_members = self.members

        if len(current_members) < self.team_count:
            await interaction.response.send_message(f"❌ メンバーが足りません（現在 {len(current_members)}人 / 必要 {self.team_count}人以上）", ephemeral=True)
            return

        self.reroll_count += 1
        embed = create_team_embed(current_members, self.team_count, self.title, self.reroll_count)
        await interaction.response.edit_message(embed=embed, view=self)
# ----------------------------------

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

# 1. カウントダウンコマンド
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

# 2. VCメンバー自動チーム分けコマンド（ボタン付き）
@bot.tree.command(name="team_vc", description="今入っているボイスチャンネルのメンバーを自動でチーム分けします")
@app_commands.describe(teams="分けるチーム数（デフォルトは2チーム）", include_bots="Botもメンバーに含めるか")
async def team_vc(interaction: discord.Interaction, teams: app_commands.Range[int, 2, 10] = 2, include_bots: bool = False):
    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.response.send_message("❌ 先にボイスチャンネルに参加してからコマンドを実行してください！", ephemeral=True)
        return

    vc = interaction.user.voice.channel
    members = [m.display_name for m in vc.members if include_bots or not m.bot]

    if len(members) < teams:
        await interaction.response.send_message(f"❌ メンバーが足りません（現在 {len(members)}人 / 必要 {teams}人以上）", ephemeral=True)
        return

    title = f"🎲 ボイスチャンネル「{vc.name}」のチーム分け結果"
    embed = create_team_embed(members, teams, title)
    view = RerollTeamView(team_count=teams, title=title, vc_id=vc.id, include_bots=include_bots)
    await interaction.response.send_message(embed=embed, view=view)

# 3. テキスト入力チーム分けコマンド（ボタン付き）
@bot.tree.command(name="team_text", description="入力した名前をスペース区切りでランダムにチーム分けします")
@app_commands.describe(names="メンバーの名前（例: 田中 佐藤 鈴木 高橋）", teams="分けるチーム数（デフォルトは2チーム）")
async def team_text(interaction: discord.Interaction, names: str, teams: app_commands.Range[int, 2, 10] = 2):
    members = [name.strip() for name in names.replace("　", " ").split(" ") if name.strip()]

    if len(members) < teams:
        await interaction.response.send_message(f"❌ メンバーが足りません（現在 {len(members)}人 / 必要 {teams}人以上）", ephemeral=True)
        return

    title = "🎲 メンバーのチーム分け結果"
    embed = create_team_embed(members, teams, title)
    view = RerollTeamView(team_count=teams, title=title, members=members)
    await interaction.response.send_message(embed=embed, view=view)

bot.run(TOKEN)
