import discord

class RankRecruitView(discord.ui.View):
    def __init__(self, host: discord.Member, game: str, max_slots: int, rank_req: str, start_time: str):
        super().__init__(timeout=43200)
        self.host = host
        self.game = game
        self.max_slots = max_slots
        self.rank_req = rank_req
        self.start_time = start_time
        self.participants: list[discord.Member] = []
        self.sub_members: list[discord.Member] = []
        self.is_closed = False

    def build_embed(self) -> discord.Embed:
        remaining = max(0, self.max_slots - len(self.participants))
        if self.is_closed:
            status = "🔒 募集終了"
            color = discord.Color.dark_gray()
        elif remaining == 0:
            status = "🎉 満員御礼！（定員達成）"
            color = discord.Color.green()
        else:
            status = f"🔥 募集中（あと **{remaining}** 人！）"
            color = discord.Color.orange()

        embed = discord.Embed(
            title=f"🎮 ランク募集：【{self.game}】",
            description=f"**ステータス：** {status}\n**募集主：** {self.host.mention}",
            color=color
        )
        embed.add_field(name="🏆 条件・ランク帯", value=self.rank_req, inline=True)
        embed.add_field(name="⏰ 開始時間", value=self.start_time, inline=True)

        p_text = "\n".join(f"{i+1}. {m.mention}" for i, m in enumerate(self.participants)) if self.participants else "（まだいません）"
        embed.add_field(name=f"🙋 参加者（{len(self.participants)} / {self.max_slots}人）", value=p_text, inline=False)

        if self.sub_members:
            s_text = "\n".join(f"・{m.mention}" for m in self.sub_members)
            embed.add_field(name=f"⏳ 補欠・行けたら行く（{len(self.sub_members)}人）", value=s_text, inline=False)

        return embed

    @discord.ui.button(label="🙋 参加する", style=discord.ButtonStyle.success)
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        if user in self.participants:
            await interaction.response.send_message("✅ すでに参加リストに入っています！", ephemeral=True)
            return
        if len(self.participants) >= self.max_slots:
            await interaction.response.send_message("❌ 定員がいっぱいです！", ephemeral=True)
            return

        if user in self.sub_members:
            self.sub_members.remove(user)
        self.participants.append(user)

        just_filled = (len(self.participants) == self.max_slots)
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

        if just_filled:
            mentions = " ".join([self.host.mention] + [m.mention for m in self.participants])
            await interaction.followup.send(f"🎉 **【{self.game}】のメンバーが全員集まりました！**\n{mentions}")

    @discord.ui.button(label="⏳ 補欠", style=discord.ButtonStyle.secondary)
    async def sub_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        if user in self.sub_members:
            await interaction.response.send_message("✅ すでに補欠リストに入っています！", ephemeral=True)
            return
        if user in self.participants:
            self.participants.remove(user)
        self.sub_members.append(user)
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="❌ キャンセル", style=discord.ButtonStyle.danger)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        if user in self.participants:
            self.participants.remove(user)
        elif user in self.sub_members:
            self.sub_members.remove(user)
        else:
            await interaction.response.send_message("参加リストに入っていません。", ephemeral=True)
            return
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="🔒 締め切り", style=discord.ButtonStyle.secondary)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host.id:
            await interaction.response.send_message("❌ 募集を締め切れるのは募集主だけです！", ephemeral=True)
            return
        self.is_closed = True
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(embed=self.build_embed(), view=self)
