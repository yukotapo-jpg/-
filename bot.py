import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import discord
from discord import app_commands
from discord.ext import tasks
import datetime
import random
from rank_view import RankRecruitView, RoomControlView

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

JST = datetime.timezone(datetime.timedelta(hours=9))
TARGET_DATE = datetime.datetime(2027, 1, 1, 0, 0, 0, tzinfo=JST)
TARGET_UNIX = int(TARGET_DATE.timestamp())

TOKEN = os.getenv("TOKEN")
ANNOUNCE_CHANNEL_ID = 0 
# 専用チャンネルを作りたいカテゴリID（0のままだと、コマンドを打った場所と同じカテゴリ内に作られます）
RECRUIT_CATEGORY_ID = 1572151858246459572

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

class RerollTeamView(discord.ui.View):
    def __init__(self, team_count: int, title: str, members: list[str] = None, vc_id: int = None, include_bots: bool = False):
        super().__init__(timeout=600)
        self.team_count = team_count
        self.title = title
        self.members = members
        self.vc_id = vc_id
        self.include_bots = include_bots
        self.reroll_count = 0

    @discord.ui.button(label="🔄 もう一回引き直す", style=discord.ButtonStyle.primary)
    async def reroll_button(self, interaction: discord.Interaction, button: discord.ui.Button):
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

@bot.tree.command(name="rank", description="専用テキスト＆VC付きのランク募集パネルを作成します")
@app_commands.describe(
    game="ゲーム名（例: Valorant, Apex, スト6）",
    slots="あと何人募集するか（例: 2）",
    rank="ランク帯や条件（省略可）",
    time="開始時間（省略可）"
)
async def rank_recruit(interaction: discord.Interaction, game: str, slots: app_commands.Range[int, 1, 20], rank: str = "指定なし・誰でもOK", time: str = "集まり次第"):
    guild = interaction.guild
    host = interaction.user

    # カテゴリを決定（指定があればそのカテゴリ、なければコマンドを実行した場所のカテゴリ）
    category = guild.get_channel(RECRUIT_CATEGORY_ID) if RECRUIT_CATEGORY_ID != 0 else interaction.channel.category

    # 最初は全員非表示、募集主とBotだけアクセス可能な権限設定
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, connect=True, speak=True, manage_channels=True),
        host: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, connect=True, speak=True)
    }

    try:
        text_ch = await guild.create_text_channel(name=f"💬｜{game}-募集", category=category, overwrites=overwrites)
        voice_ch = await guild.create_voice_channel(name=f"🔊｜{game}-通話", category=category, overwrites=overwrites)
    except discord.Forbidden:
        await interaction.response.send_message("❌ チャンネルを作成する権限がありません！Botのロールに「チャンネルの管理」または「管理者」権限を付けてください。", ephemeral=True)
        return

    view = RankRecruitView(host=host, game=game, max_slots=slots, rank_req=rank, start_time=time, text_ch=text_ch, voice_ch=voice_ch)
    await interaction.response.send_message(embed=view.build_embed(), view=view)
    view.panel_message = await interaction.original_response()

    # 専用テキストチャンネル内に「抜ける・解散」操作パネルを投稿
    room_embed = discord.Embed(
        title=f"🚪 【{game}】専用ルームへようこそ！",
        description=(
            f"ここは **{host.display_name}** さんの募集に参加したメンバーだけの専用ルームです。\n"
            f"・途中で抜ける場合は下の **「🚪 部屋から抜ける」** を押してください。\n"
            f"・解散する場合は募集主が **「💥 ルーム解散」** を押すとチャンネルが自動削除されます。"
        ),
        color=discord.Color.teal()
    )
    await text_ch.send(content=f"{host.mention} 専用ルームを作成しました！", embed=room_embed, view=RoomControlView(view))

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
