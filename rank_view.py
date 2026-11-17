import discord

class RoomControlView(discord.ui.View):
    def __init__(self, parent_view: "RankRecruitView"):
        super().__init__(timeout=43200)
        self.parent_view = parent_view

    @discord.ui.button(label="🚪 部屋から抜ける", style=discord.ButtonStyle.danger)
    async def leave_room_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        if user.id == self.parent_view.host.id:
            await interaction.response.send_message("❌ 募集主は「部屋から抜ける」を使えません。終わる場合は「💥 ルーム解散」を押してください！", ephemeral=True)
            return

        if user not in self.parent_view.participants:
            await interaction.response.send_message("❌ すでに参加リストから抜けています。", ephemeral=True)
            return

        await interaction.response.send_message("👋 専用ルームから退出しました！（チャンネルが非表示になります）", ephemeral=True)
        await self.parent_view.remove_member_from_room(user)

    @discord.ui.button(label="💥 ルーム解散・チャンネル削除", style=discord.ButtonStyle.secondary)
    async def delete_room_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.parent_view.host.id:
            await interaction.response.send_message("❌ ルームを解散できるのは募集主だけです！", ephemeral=True)
            return

        await interaction.response.send_message("💥 チャンネルを削除してルームを解散します...")
        await self.parent_view.close_and_cleanup()


class RankRecruitView(discord.ui.View):
    def __init__(self, host: discord.Member, game: str, max_slots: int, rank_req: str, start_time: str, text_ch: discord.TextChannel = None, voice_ch: discord.VoiceChannel = None):
        super().__init__(timeout=43200)
        self.host = host
        self.game = game
        self.max_slots = max_slots
        self.rank_req = rank_req
        self.start_time = start_time
        self.text_ch = text_ch
        self.voice_ch = voice_ch
        self.participants: list[discord.Member] = []
        self.sub_members: list[discord.Member] = []
        self.is_closed = False
        self.panel_message: discord.Message = None

    def build_embed(self) -> discord.Embed:
        remaining = max(0, self.max_slots - len(self.participants))
        if self.is_closed:
            status = "🔒 募集終了（ルーム解散済み）"
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

        if self.text_ch and self.voice_ch and not self.is_closed:
            embed.add_field(
                name="🚪 専用ルーム（参加者のみ表示）",
                value=f"💬 {self.text_ch.mention} / 🔊 {self.voice_ch.mention}",
                inline=False
            )

        p_text = "\n".join(f"{i+1}. {m.mention}" for i, m in enumerate(self.participants)) if self.participants else "（まだいません）"
        embed.add_field(name=f"🙋 参加者（{len(self.participants)} / {self.max_slots}人）", value=p_text, inline=False)

        if self.sub_members:
            s_text = "\n".join(f"・{m.mention}" for m in self.sub_members)
            embed.add_field(name=f"⏳ 補欠・行けたら行く（{len(self.sub_members)}人）", value=s_text, inline=False)

        return embed

    async def grant_room_access(self, member: discord.Member):
        target = discord.Object(id=member.id)
        if self.text_ch:
            await self.text_ch.set_permissions(target, view_channel=True, send_messages=True, read_message_history=True)
        if self.voice_ch:
            await self.voice_ch.set_permissions(target, view_channel=True, connect=True, speak=True)

    async def revoke_room_access(self, member: discord.Member):
        target = discord.Object(id=member.id)
        # ★ただ権限を消す(None)のではなく、明示的に「閲覧・接続を拒否(False)」にして完全に見えなくする！
        if self.text_ch:
            await self.text_ch.set_permissions(target, view_channel=False, send_messages=False)
        if self.voice_ch:
            await self.voice_ch.set_permissions(target, view_channel=False, connect=False)
            if member.voice and member.voice.channel and member.voice.channel.id == self.voice_ch.id:
                try:
                    await member.move_to(None)
                except Exception:
                    pass

    async def remove_member_from_room(self, user: discord.Member):
        if user in self.participants:
            self.participants.remove(user)
        await self.revoke_room_access(user)
        if self.text_ch:
            await self.text_ch.send(f"🚪 {user.display_name} さんが専用ルームから抜けました。")
        if self.panel_message:
            await self.panel_message.edit(embed=self.build_embed(), view=self)

    async def close_and_cleanup(self):
        self.is_closed = True
        for item in self.children:
            item.disabled = True
        if self.panel_message:
            try:
                await self.panel_message.edit(embed=self.build_embed(), view=self)
            except Exception:
                pass
        if self.text_ch:
            try:
                await self.text_ch.delete(reason="ランク募集終了のため自動削除")
            except Exception:
                pass
        if self.voice_ch:
            try:
                await self.voice_ch.delete(reason="ランク募集終了のため自動削除")
            except Exception:
                pass

    @discord.ui.button(label="🙋 参加する", style=discord.ButtonStyle.success)
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        if user.id == self.host.id:
            await interaction.response.send_message("👑 あなたは募集主なので最初から参加＆入室権限があります！", ephemeral=True)
            return
        if user in self.participants:
            await interaction.response.send_message("✅ すでに参加リストに入っています！", ephemeral=True)
            return
        if len(self.participants) >= self.max_slots:
            await interaction.response.send_message("❌ 定員がいっぱいです！", ephemeral=True)
            return

        if user in self.sub_members:
            self.sub_members.remove(user)
        self.participants.append(user)

        await self.grant_room_access(user)
        just_filled = (len(self.participants) == self.max_slots)
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

        if self.text_ch:
            await self.text_ch.send(f"👋 {user.mention} さんが参加しました！（専用VCにも入室できます）")

        if just_filled:
            mentions = " ".join([self.host.mention] + [m.mention for m in self.participants])
            await interaction.followup.send(f"🎉 **【{self.game}】のメンバーが全員集まりました！**\n{mentions}")

    @discord.ui.button(label="⏳ 補欠", style=discord.ButtonStyle.secondary)
    async def sub_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        if user.id == self.host.id:
            await interaction.response.send_message("👑 募集主は補欠になれません！", ephemeral=True)
            return
        if user in self.sub_members:
            await interaction.response.send_message("✅ すでに補欠リストに入っています！", ephemeral=True)
            return
        if user in self.participants:
            self.participants.remove(user)
            await self.revoke_room_access(user)
        self.sub_members.append(user)
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="❌ キャンセル", style=discord.ButtonStyle.danger)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        if user in self.participants:
            self.participants.remove(user)
            await self.revoke_room_access(user)
            if self.text_ch:
                await self.text_ch.send(f"🚪 {user.display_name} さんが参加をキャンセルしてルームから抜けました。")
        elif user in self.sub_members:
            self.sub_members.remove(user)
        else:
            await interaction.response.send_message("参加リストに入っていません。", ephemeral=True)
            return
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="💥 解散・締め切り", style=discord.ButtonStyle.secondary)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host.id:
            await interaction.response.send_message("❌ 募集を解散できるのは募集主だけです！", ephemeral=True)
            return
        await interaction.response.send_message("💥 募集を終了し、専用チャンネルを削除しました！", ephemeral=True)
        await self.close_and_cleanup()
