import discord

class PollButton(discord.ui.Button):
    def __init__(self, index: int, label_text: str):
        emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
        super().__init__(
            label=label_text[:80],
            emoji=emojis[index],
            style=discord.ButtonStyle.primary,
            custom_id=f"poll_opt_{index}"
        )
        self.index = index

    async def callback(self, interaction: discord.Interaction):
        view: PollView = self.view
        user_id = interaction.user.id

        # すでに同じ選択肢に投票していたら「取り消し」
        if view.votes.get(user_id) == self.index:
            del view.votes[user_id]
        else:
            # 未投票または別の選択肢なら「投票（変更）」
            view.votes[user_id] = self.index

        await interaction.response.edit_message(embed=view.build_embed(), view=view)


class ClosePollButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🔒 締め切り", style=discord.ButtonStyle.secondary, row=1)

    async def callback(self, interaction: discord.Interaction):
        view: PollView = self.view
        if interaction.user.id != view.host.id:
            await interaction.response.send_message("❌ アンケートを締め切れるのは作成者だけです！", ephemeral=True)
            return

        view.is_closed = True
        for item in view.children:
            item.disabled = True
        await interaction.response.edit_message(embed=view.build_embed(), view=view)


class PollView(discord.ui.View):
    def __init__(self, host: discord.Member, question: str, options: list[str]):
        super().__init__(timeout=43200)
        self.host = host
        self.question = question
        self.options = options
        self.votes: dict[int, int] = {}  # {user_id: option_index}
        self.is_closed = False

        for idx, opt in enumerate(options):
            self.add_item(PollButton(idx, opt))
        self.add_item(ClosePollButton())

    def build_embed(self) -> discord.Embed:
        total_votes = len(self.votes)
        emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]

        counts = [0] * len(self.options)
        for chosen_idx in self.votes.values():
            counts[chosen_idx] += 1

        max_count = max(counts) if counts else 0

        if self.is_closed:
            title = f"🔒 【終了】{self.question}"
            color = discord.Color.dark_gray()
        else:
            title = f"📊 {self.question}"
            color = discord.Color.blurple()

        lines = []
        for idx, opt in enumerate(self.options):
            c = counts[idx]
            pct = round((c / total_votes) * 100) if total_votes > 0 else 0
            filled = round(pct / 10)
            bar = "█" * filled + "░" * (10 - filled)
            crown = " 👑" if (self.is_closed and c > 0 and c == max_count) else ""
            lines.append(f"{emojis[idx]} **{opt}**{crown}\n`{bar}` **{pct}%**（{c}票）")

        embed = discord.Embed(
            title=title,
            description="\n\n".join(lines),
            color=color
        )
        embed.set_footer(text=f"作成者: {self.host.display_name} ｜ 総投票数: {total_votes}票（同じボタン再押しで取消）")
        return embed
