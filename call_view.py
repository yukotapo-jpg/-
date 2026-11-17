import discord

class CallRecruitView(discord.ui.View):
    def __init__(self, host: discord.Member, topic: str, vc_channel: discord.VoiceChannel = None):
        super().__init__(timeout=43200)
        self.host = host
        self.topic = topic
        self.vc_channel = vc_channel
        self.join_now: list[discord.Member] = []
        self.join_later: list[discord.Member] = []
        self.is_closed = False

    def build_embed(self) -> discord.Embed:
        if self.is_closed:
            title = "🔒 通話募集は終了しました"
            color = discord.Color.dark_gray()
        else:
            title = f"🎙️ 通話募集：【{self.topic}】"
            color = discord.Color.green()

        desc = f"**募集主：** {self.host.mention}\n"
        if self.vc_channel and not self.is_closed:
            desc += f"**集合場所：** {self.vc_channel.mention}（クリックで参加！）\n"
        else:
            desc += "**集合場所：** ボイスチャンネル（誰でも参加OK）\n"

        embed = discord.Embed(title=title, description=desc, color=color)

        now_text = "\n".join(f"・{m.mention}" for m in self.join_now) if self.join_now else "（まだいません）"
        embed.add_field(name=f"🎙️ 今すぐ行く！（{len(self.join_now)}人）", value=now_text, inline=True)

        later_text = "\n".join(f"・{m.mention}" for m in self.join_later) if self.join_later else "（なし）"
        embed.add_field(name=f"⏳ あとで行く！（{len(self.join_later)}人）", value=later_text, inline=True)

        total = len(self.join_now) + len(self.join_later)
        embed.set_footer(text=f"反応してくれた人数: {total}人")
        return embed

    @discord.ui.button(label="🎙️ 今すぐ行く！", style=discord.ButtonStyle.success)
    async def now_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        if user in self.join_now:
            await interaction.response.send_message("✅ すでに「今すぐ行く！」に入っています！", ephemeral=True)
            return
        if user in self.join_later:
            self.join_later.remove(user)
        self.join_now.append(user)

        await interaction.response.edit_message(embed=self.build_embed(), view=self)
        await interaction.followup.send(f"🎙️ {self.host.mention} **{user.display_name}** さんが「今すぐ行く！」を押しました！")

    @discord.ui.button(label="⏳ あとで行く！", style=discord.ButtonStyle.primary)
    async def later_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        if user in self.join_later:
            await interaction.response.send_message("✅ すでに「あとで行く！」に入っています！", ephemeral=True)
            return
        if user in self.join_now:
            self.join_now.remove(user)
        self.join_later.append(user)

        await interaction.response.edit_message(embed=self.build_embed(), view=self)
        await interaction.followup.send(f"⏳ {self.host.mention} **{user.display_name}** さんが「あとで行く！」を押しました！")

    @discord.ui.button(label="❌ 取り消し", style=discord.ButtonStyle.danger)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        if user in self.join_now:
            self.join_now.remove(user)
        elif user in self.join_later:
            self.join_later.remove(user)
        else:
            await interaction.response.send_message("リストに入っていません。", ephemeral=True)
            return
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="🔒 締め切り", style=discord.ButtonStyle.secondary)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host.id:
            await interaction.response.send_message("❌ 締め切れるのは募集主だけです！", ephemeral=True)
            return
        self.is_closed = True
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(embed=self.build_embed(), view=self)
