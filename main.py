import discord
from discord import app_commands
from discord.ext import commands
import os
import json
import asyncio
import traceback
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore

# Firebase DB 초기화
firebase_key_env = os.getenv("FIREBASE_KEY")

if firebase_key_env:
    cred_dict = json.loads(firebase_key_env)
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    KEY_PATH = os.path.join(BASE_DIR, "firebase_key.json")
    cred = credentials.Certificate(KEY_PATH)
    firebase_admin.initialize_app(cred)

db = firestore.client()

def get_goa_level(count: int) -> str:
    if count >= 25:
        return "level 6 goa"
    elif count >= 20:
        return "level 5 goa"
    elif count >= 15:
        return "level 4 goa"
    elif count >= 10:
        return "level 3 goa"
    elif count >= 5:
        return "level 2 goa"
    elif count >= 1:
        return "level 1 goa"
    return "None"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"로그인 성공: {bot.user.name}")
    try:
        synced = await bot.tree.sync()
        print(f"슬래시 명령어 {len(synced)}개 동기화 완료")
    except Exception as e:
        print(f"동기화 오류: {e}")

# [신고 명령어]
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
    # 가장 먼저 defer() 호출하여 디스코드 3초 타임아웃 방지
    await interaction.response.defer(ephemeral=True)

    try:
        name = 닉네임.strip()
        user_reason = 사유.strip()
        reporter_id = str(interaction.user.id)
        today = datetime.now().strftime("%Y-%m-%d")

        doc_ref = db.collection("reports").document(name)
        
        # Firestore 조회를 비동기로 처리하여 메인 루프 멈춤 방지
        doc = await asyncio.to_thread(doc_ref.get)

        if doc.exists:
            data = doc.to_dict()
        else:
            data = {"count": 0, "reasons": [], "history": {}}

        user_history = data.get("history", {})
        if user_history.get(reporter_id) == today:
            await interaction.followup.send(
                f"❌ 오늘 이미 `{name}` 님을 신고하셨습니다. (동일 대상은 하루 1회만 신고 가능)", 
                ephemeral=True
            )
            return

        data["count"] += 1
        data["reasons"].append(user_reason)
        if "history" not in data:
            data["history"] = {}
        data["history"][reporter_id] = today
        
        # Firestore 저장도 비동기 처리
        await asyncio.to_thread(doc_ref.set, data)

        current_count = data["count"]
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

# [고아리스트 명령어]
@bot.tree.command(name="고아리스트", description="현재 등록된 고아 리스트를 확인합니다.")
async def list_command(interaction: discord.Interaction):
    await interaction.response.defer()

    docs = await asyncio.to_thread(lambda: list(db.collection("reports").stream()))
    has_data = False

    embed = discord.Embed(
        title="📋 고아헌터존 - 누적 신고 명단",
        color=discord.Color.dark_red()
    )

    for doc in docs:
        has_data = True
        name = doc.id
        data = doc.to_dict()
        count = data.get("count", 0)
        level = get_goa_level(count)
        embed.add_field(
            name=f"👤 {name}",
            value=f"• 등급: **{level}** | 중첩: **{count}회**",
            inline=False
        )

    if not has_data:
        await interaction.followup.send("현재 등록된 명단이 없습니다.")
    else:
        await interaction.followup.send(embed=embed)

# [관리자 전용] /신고삭제 명령어
@bot.tree.command(name="신고삭제", description="[관리자 전용] 특정 유저의 신고 기록을 삭제합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def delete_command(interaction: discord.Interaction, 닉네임: str):
    await interaction.response.defer(ephemeral=True)
    name = 닉네임.strip()
    doc_ref = db.collection("reports").document(name)
    
    doc = await asyncio.to_thread(doc_ref.get)
    if doc.exists:
        await asyncio.to_thread(doc_ref.delete)
        await interaction.followup.send(f"✅ `{name}` 님의 신고 데이터가 삭제되었습니다.", ephemeral=True)
    else:
        await interaction.followup.send(f"❌ `{name}` 님은 등록되어 있지 않습니다.", ephemeral=True)

bot.run(os.getenv("DISCORD_TOKEN"))
