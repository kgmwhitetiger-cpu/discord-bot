# [신고 명령어 수정본]
@bot.tree.command(name="신고", description="비매너 유저를 신고합니다.")
@app_commands.describe(
    닉네임="디플닉X / 유저의 고유 아이디 입력",
    사유="비매너 행위 내용 및 사유",
    이미지="증거 스크린샷 이미지 (선택)"
)
async def report_command(
    interaction: discord.Interaction, 
    닉네임: str, 
    사유: str, 
    이미지: discord.Attachment = None
):
    # 3초 타임아웃 방지를 위해 비공개 응답 대기 상태 생성
    await interaction.response.defer(ephemeral=True)

    try:
        name = 닉네임.strip()
        user_reason = 사유.strip()
        reporter_id = str(interaction.user.id)
        today = datetime.now().strftime("%Y-%m-%d")

        if name not in reports_db:
            reports_db[name] = {"count": 0, "reasons": [], "history": {}}

        # 하루 1회 동일 유저 신고 제한 검사
        user_history = reports_db[name].get("history", {})
        if reporter_id in user_history and user_history[reporter_id] == today:
            await interaction.followup.send(
                f"❌ 오늘 이미 `{name}` 님을 신고하셨습니다. (동일 대상은 하루 1회만 신고 가능)", 
                ephemeral=True
            )
            return

        # 신고 데이터 등록 및 오늘 날짜 기록
        reports_db[name]["count"] += 1
        reports_db[name]["reasons"].append(user_reason)
        if "history" not in reports_db[name]:
            reports_db[name]["history"] = {}
        reports_db[name]["history"][reporter_id] = today
        
        save_data(reports_db)

        current_count = reports_db[name]["count"]
        goa_level = get_goa_level(current_count)

        embed = discord.Embed(
            title="🚨 고아헌터존 신고 접수",
            color=discord.Color.red()
        )
        embed.add_field(name="신고 대상(아이디)", value=f"`{name}`", inline=True)
        embed.add_field(name="누적 중첩", value=f"**{current_count} 회**", inline=True)
        embed.add_field(name="고아 등급", value=f"**{goa_level}**", inline=True)
        embed.add_field(name="최신 신고 사유", value=f"```{user_reason}```", inline=False)
        embed.set_footer(text=f"신고자: {interaction.user.display_name}")

        if 이미지:
            embed.set_image(url=이미지.url)

        # defer 사용 후에는 followup.send로 응답
        await interaction.followup.send("신고가 성공적으로 접수되었습니다!", ephemeral=True)

        target_channel = discord.utils.get(interaction.guild.text_channels, name="고아헌터존")
        if target_channel:
            await target_channel.send(embed=embed)
        else:
            await interaction.channel.send(embed=embed)

    except Exception as e:
        print("신고 처리 중 에러 발생:")
        traceback.print_exc()
        await interaction.followup.send(f"오류가 발생했습니다: {e}", ephemeral=True)


# [고아리스트 명령어 수정본]
@bot.tree.command(name="고아리스트", description="현재 등록된 고아 리스트를 확인합니다.")
async def list_command(interaction: discord.Interaction):
    await interaction.response.defer() # 타임아웃 방지

    if not reports_db:
        await interaction.followup.send("현재 등록된 명단이 없습니다.")
        return

    embed = discord.Embed(
        title="📋 고아헌터존 - 누적 신고 명단",
        color=discord.Color.dark_red()
    )

    for name, data in reports_db.items():
        count = data["count"]
        level = get_goa_level(count)
        embed.add_field(
            name=f"👤 {name}",
            value=f"• 등급: **{level}** | 중첩: **{count}회**",
            inline=False
        )

    await interaction.followup.send(embed=embed)
