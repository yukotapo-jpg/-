import os
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import discord
from discord import app_commands
from discord.ext import tasks
import datetime
import random

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

RATE_FILE = "rates.json"
DEFAULT_RATE = 1000

def load_rates() -> dict:
    if os.path.exists(RATE_FILE):
        try:
            with open(RATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_rates(rates: dict):
    with open(RATE_FILE, "w", encoding="utf-8") as f:
        json.dump(rates, f, ensure_ascii=False, indent=2)

def split_teams(members: list[dict], team_count: int, balance: bool) -> list[list[dict]]:
    if not balance:
        shuffled = members.copy()
        random.shuffle(shuffled)
        return [shuffled[i::team_count] for i in range(team_count)]

    candidates = []
    for _ in range(100):
        shuffled = members.copy()
        random.shuffle(shuffled)
        teams = [shuffled[i::team_count] for i in range(team_count)]
        totals = [sum(m["rate"] for m in t) for t in teams]
        diff = max(totals) - min(totals)
        candidates.append((diff, teams))

    candidates.sort(key=lambda x: x[0])
    top_choices = [c[1] for c in candidates[:5]]
    return random.choice(top_choices)

def create_team_embed(members: list[dict], team_count: int, title: str, balance: bool, reroll_count: int = 0) -> discord.Embed:
    teams = split_teams(members, team_count, balance)
    team_labels = ["🔴 チームA", "🔵 チームB", "🟢 チームC", "🟡 チームD", "🟣 チームE", "🟠 チームF"]

    mode_text = "⚖️ 実力バランス均等モード" if balance else "🎲 完全ランダムモード"
    embed = discord.Embed(title=title, description=f"モード：**{mode_text}**", color=discord.Color.blurple())

    for idx, team in enumerate(teams):
        label = team_labels[idx] if idx < len(team_labels) else f"⚪ チーム{idx + 1}"
        total_rate = sum(m["rate"] for m in team)
        avg_rate = round(total_rate / len(team)) if team else 0
        
        if balance:
            member_list = "\n".join(f"・{m['name']} (`{m['rate']}`)" for m in team) if team else "（メンバーなし）"
            field_name = f"{label}（合計: {total_rate} / 平均: {avg_rate}）"
        else:
            member_list = "\n".join(f"・{m['name']}" for m in team) if team else "（メンバーなし）"
            field_name = f"{label}（{len(team)}人）"
            
        embed.add_field(name=field_name, value=member_list, inline=True)
    
    if reroll_count > 0:
        embed.set_footer(text=f"🔄 やり直し回数: {reroll_count}回目")
    return embed
class RerollTeamView(discord.ui.View):
    def __init__(self, team_count: int, title: str, balance: bool, members: list[dict] = None, vc_id: int = None, include_bots: bool = False):
        super().__init__(timeout=600)
        self.team_count = team_count
        self.title = title
        self.balance = balance
        self.members = members
        self.vc_id = vc_id
        self.include_bots = include_bots
        self.reroll_count = 0

    @discord.ui.button(label="🔄 もう一回引き直す", style=discord.ButtonStyle.primary)
    async def reroll_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        rates = load_rates()
        if self.vc_id:
            vc = interaction.guild.get_channel(self.vc_id)
            if not vc:
                await interaction.response.send_message("❌ ボイスチャンネルが見つかりませんでした。", ephemeral=True)
                return
            current_members = [
                {"name": m.display_name, "rate": rates.get(str(m.id), rates.get(m.display_name, DEFAULT_RATE))}
                for m in vc.members if self.include_bots or not m.bot
            ]
        else:
            current_members = [
                {"name": m["name"], "rate": rates.get(m["name"], m["rate"])}
                for m in self.members
            ]

        if len(current_members) < self.team_count:
            await interaction.response.send_message(f"❌ メンバーが足りません（現在 {len(current_members)}人 / 必要 {self.team_count}人以上）", ephemeral=True)
            return

        self.reroll_count += 1
        embed = create_team_embed(current_members, self.team_count, self.title, self.balance, self.reroll_count)
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

@bot.tree.command(name="set_rate", description="メンバーの強さ指数（レート）を登録・変更します")
@app_commands.describe(member="対象のDiscordメンバー", rate="強さ指数（例: 1500 や 80 など好きな数字）")
async def set_rate(interaction: discord.Interaction, member: discord.Member, rate: app_commands.Range[int, 1, 99999]):
    rates = load_rates()
    rates[str(member.id)] = rate
    rates[member.display_name] = rate
    save_rates(rates)
    await interaction.response.send_message(f"✅ **{member.display_name}** の強さ指数を **`{rate}`** に設定しました！")

@bot.tree.command(name="rates", description="現在登録されているメンバーの強さ指数一覧を表示します")
async def show_rates(interaction: discord.Interaction):
    rates = load_rates()
    user_entries = []
    for key, val in rates.items():
        if key.isdigit():
            member = interaction.guild.get_member(int(key))
            name = member.display_name if member else f"ユーザー({key})"
            user_entries.append((name, val))

    if not user_entries:
        await interaction.response.send_message(f"まだ誰もレートが登録されていません（全員デフォルト `{DEFAULT_RATE}` 扱いです）。\n`/set_rate` で登録できます！", ephemeral=True)
        return

    user_entries.sort(key=lambda x: x[1], reverse=True)
    lines = [f"**{i+1}位** {name} ： `{val}`" for i, (name, val) in enumerate(user_entries)]
    embed = discord.Embed(
        title="📊 メンバー強さ指数（レート）一覧",
        description="\n".join(lines) + f"\n\n※未登録メンバーは自動で `{DEFAULT_RATE}` になります",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="team_vc", description="今入っているボイスチャンネルのメンバーをチーム分けします")
@app_commands.describe(teams="分けるチーム数", balance="強さ指数（レート）を考慮するか", include_bots="Botも含めるか")
async def team_vc(interaction: discord.Interaction, teams: app_commands.Range[int, 2, 10] = 2, balance: bool = True, include_bots: bool = False):
    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.response.send_message("❌ 先にボイスチャンネルに参加してからコマンドを実行してください！", ephemeral=True)
        return

    vc = interaction.user.voice.channel
    rates = load_rates()
    members = [
        {"name": m.display_name, "rate": rates.get(str(m.id), rates.get(m.display_name, DEFAULT_RATE))}
        for m in vc.members if include_bots or not m.bot
    ]

    if len(members) < teams:
        await interaction.response.send_message(f"❌ メンバーが足りません（現在 {len(members)}人 / 必要 {teams}人以上）", ephemeral=True)
        return

    title = f"🎲 ボイスチャンネル「{vc.name}」のチーム分け結果"
    embed = create_team_embed(members, teams, title, balance)
    view = RerollTeamView(team_count=teams, title=title, balance=balance, vc_id=vc.id, include_bots=include_bots)
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="team_text", description="入力した名前をスペース区切りでチーム分けします")
@app_commands.describe(names="メンバーの名前（例: 田中 佐藤 鈴木 高橋）", teams="分けるチーム数", balance="強さ指数（レート）を考慮するか")
async def team_text(interaction: discord.Interaction, names: str, teams: app_commands.Range[int, 2, 10] = 2, balance: bool = True):
    raw_names = [name.strip() for name in names.replace("　", " ").split(" ") if name.strip()]
    if len(raw_names) < teams:
        await interaction.response.send_message(f"❌ メンバーが足りません（現在 {len(raw_names)}人 / 必要 {teams}人以上）", ephemeral=True)
        return

    rates = load_rates()
    members = [{"name": n, "rate": rates.get(n, DEFAULT_RATE)} for n in raw_names]

    title = "🎲 メンバーのチーム分け結果"
    embed = create_team_embed(members, teams, title, balance)
    view = RerollTeamView(team_count=teams, title=title, balance=balance, members=members)
    await interaction.response.send_message(embed=embed, view=view)

bot.run(TOKEN)
