import discord
from discord.ext import commands
import os
import asyncio
from analyzer import WowLogAnalyzer
from config import DISCORD_TOKEN, COMMAND_PREFIX, COLOR_GREEN, COLOR_RED, COLOR_BLUE


# 봇 인텐트 설정
intents = discord.Intents.default()
intents.message_content = True

# 봇 생성
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)


@bot.event
async def on_ready():
    """봇이 준비되었을 때 실행"""
    print(f'{bot.user.name} 봇이 성공적으로 연결되었습니다!')
    print(f'Bot ID: {bot.user.id}')
    print('------')


@bot.event
async def on_command_error(ctx, error):
    """명령어 실행 중 오류가 발생했을 때 처리"""
    if isinstance(error, commands.CommandInvokeError):
        original_error = error.original

        # 권한 오류 처리
        if isinstance(original_error, discord.Forbidden):
            if original_error.code == 50013:  # Missing Permissions
                try:
                    await ctx.send(
                        "❌ **권한 오류**: 봇에게 다음 권한이 필요합니다:\n"
                        "• 메시지 보내기 (Send Messages)\n"
                        "• 링크 삽입 (Embed Links)\n"
                        "• 파일 첨부 (Attach Files)\n\n"
                        "서버 설정 → 역할 → 봇 역할에서 위 권한들을 활성화해주세요."
                    )
                except:
                    # 메시지조차 보낼 수 없는 경우
                    print(f"❌ 권한 오류 발생 (채널: {ctx.channel.id}): {original_error}")
            else:
                await ctx.send(f"❌ Discord API 오류: {original_error}")
        else:
            await ctx.send(f"❌ 오류 발생: {original_error}")
    else:
        # 기타 오류는 기본 처리
        print(f"오류: {error}")


def can_send_embeds(ctx) -> bool:
    """봇이 임베드를 보낼 권한이 있는지 확인"""
    if ctx.guild is None:
        # DM에서는 항상 가능
        return True

    permissions = ctx.channel.permissions_for(ctx.guild.me)
    return permissions.send_messages and permissions.embed_links


@bot.command(name='compare')
async def compare(ctx):
    """
    !compare 명령어
    2개의 CSV 파일을 첨부하고 이 명령어를 입력하면 분석 결과를 출력합니다.
    """
    # 첨부파일 확인
    if len(ctx.message.attachments) != 2:
        await ctx.send("❌ CSV 파일 2개를 첨부해주세요!")
        return

    # CSV 파일인지 확인
    csv_files = [att for att in ctx.message.attachments if att.filename.endswith('.csv')]
    if len(csv_files) != 2:
        await ctx.send("❌ 두 파일 모두 CSV 형식이어야 합니다!")
        return

    # 파일 다운로드
    temp_dir = 'temp_csvs'
    os.makedirs(temp_dir, exist_ok=True)

    file1_path = os.path.join(temp_dir, csv_files[0].filename)
    file2_path = os.path.join(temp_dir, csv_files[1].filename)

    try:
        await csv_files[0].save(file1_path)
        await csv_files[1].save(file2_path)
    except Exception as e:
        await ctx.send(f"❌ 파일 다운로드 오류: {e}")
        return

    # 분석 시작 - 타이핑 표시와 함께
    status_msg = await ctx.send("⏳ 분석 중...")

    try:
        # 타이핑 중 표시
        async with ctx.typing():
            analyzer = WowLogAnalyzer(file1_path, file2_path)
            result = analyzer.analyze()

        if result is None or 'error' in result:
            error_msg = result.get('error', '알 수 없는 오류') if result else '분석 실패'
            await status_msg.edit(content=f"❌ {error_msg}")
            return

        # 결과를 Embed로 출력
        await status_msg.edit(content="✅ 분석 완료!")

        if can_send_embeds(ctx):
            embed = create_embed(result, csv_files[0].filename, csv_files[1].filename)
            await ctx.send(embed=embed)
        else:
            # 권한이 없으면 일반 텍스트로 전송
            text_result = create_text_result(result, csv_files[0].filename, csv_files[1].filename)
            await ctx.send(text_result)

    except Exception as e:
        await status_msg.edit(content=f"❌ 분석 오류: {e}")
    finally:
        # 임시 파일 삭제
        try:
            os.remove(file1_path)
            os.remove(file2_path)
        except:
            pass


def create_text_result(result: dict, file1_name: str, file2_name: str) -> str:
    """분석 결과를 일반 텍스트로 변환합니다 (권한이 없을 때 사용)"""
    role = result.get('role', 'UNKNOWN')

    # 역할에 따른 이모지 선택
    if role == 'DPS':
        emoji = "⚔️"
    elif role == 'TANK':
        emoji = "🛡️"
    elif role == 'HEALER':
        emoji = "💚"
    else:
        emoji = "📊"

    text = f"{emoji} **WoW Logs 비교 분석 - {role}**\n"
    text += f"**Before:** `{file1_name}`\n"
    text += f"**After:** `{file2_name}`\n"
    text += "─" * 40 + "\n\n"

    summary = result.get('summary', {})

    # 역할별 주요 지표
    if role == 'DPS' and 'total_dps' in summary:
        dps_data = summary['total_dps']
        dps_diff = dps_data['diff']
        indicator = "📈" if dps_diff > 0 else "📉" if dps_diff < 0 else "➖"
        sign = "+" if dps_diff > 0 else ""
        text += f"**💥 총 DPS**\n"
        text += f"Before: {dps_data['before']:.1f}\n"
        text += f"After: {dps_data['after']:.1f}\n"
        text += f"{indicator} 차이: {sign}{dps_diff:.1f} ({sign}{dps_data['diff_percent']:.1f}%)\n\n"

    elif role == 'TANK' and 'total_dtps' in summary:
        dtps_data = summary['total_dtps']
        dtps_diff = dtps_data['diff']
        indicator = "📉" if dtps_diff < 0 else "📈" if dtps_diff > 0 else "➖"
        sign = "+" if dtps_diff > 0 else ""
        text += f"**💔 총 받은 피해 (DTPS)**\n"
        text += f"Before: {dtps_data['before']:.1f}\n"
        text += f"After: {dtps_data['after']:.1f}\n"
        text += f"{indicator} 차이: {sign}{dtps_diff:.1f} ({sign}{dtps_data['diff_percent']:.1f}%)\n\n"

    elif role == 'HEALER' and 'total_hps' in summary:
        hps_data = summary['total_hps']
        hps_diff = hps_data['diff']
        indicator = "📈" if hps_diff > 0 else "📉" if hps_diff < 0 else "➖"
        sign = "+" if hps_diff > 0 else ""
        text += f"**💚 총 HPS**\n"
        text += f"Before: {hps_data['before']:.1f}\n"
        text += f"After: {hps_data['after']:.1f}\n"
        text += f"{indicator} 차이: {sign}{hps_diff:.1f} ({sign}{hps_data['diff_percent']:.1f}%)\n\n"

    # 개선 제안
    if result.get('improvements'):
        text += "**💡 개선 포인트**\n"
        for imp in result['improvements']:
            text += f"• {imp}\n"
        text += "\n"

    # 누락된 스킬
    if result.get('missing_skills'):
        text += "**⚠️ 사용하지 않은 스킬**\n"
        text += ', '.join(result['missing_skills']) + "\n\n"

    text += "─" * 40 + "\n"
    text += "⚠️ **참고**: 더 자세한 분석 결과를 보려면 봇에게 \"링크 삽입(Embed Links)\" 권한을 부여해주세요."

    return text


def create_embed(result: dict, file1_name: str, file2_name: str) -> discord.Embed:
    """분석 결과를 Discord Embed로 변환합니다"""
    role = result.get('role', 'UNKNOWN')

    # 역할에 따른 색상 선택
    if role == 'DPS':
        color = COLOR_RED
        emoji = "⚔️"
    elif role == 'TANK':
        color = COLOR_BLUE
        emoji = "🛡️"
    elif role == 'HEALER':
        color = COLOR_GREEN
        emoji = "💚"
    else:
        color = COLOR_BLUE
        emoji = "📊"

    embed = discord.Embed(
        title=f"{emoji} WoW Logs 비교 분석 - {role}",
        description=f"**Before:** `{file1_name}`\n**After:** `{file2_name}`",
        color=color
    )

    # 역할별 결과 추가
    if role == 'DPS':
        add_dps_fields(embed, result)
    elif role == 'TANK':
        add_tank_fields(embed, result)
    elif role == 'HEALER':
        add_healer_fields(embed, result)

    # 개선 제안
    if result.get('improvements'):
        improvements_text = '\n'.join([f"• {imp}" for imp in result['improvements']])
        embed.add_field(name="💡 개선 포인트", value=improvements_text, inline=False)

    # 누락된 스킬
    if result.get('missing_skills'):
        missing_text = ', '.join(result['missing_skills'])
        embed.add_field(name="⚠️ 사용하지 않은 스킬", value=missing_text, inline=False)

    embed.set_footer(text="WoW Compare Bot | Powered by Warcraftlogs")
    return embed


def add_dps_fields(embed: discord.Embed, result: dict):
    """DPS 분석 결과를 Embed에 추가"""
    summary = result.get('summary', {})

    # 총 DPS
    if 'total_dps' in summary:
        dps_data = summary['total_dps']
        dps_diff = dps_data['diff']
        dps_diff_percent = dps_data['diff_percent']

        indicator = "📈" if dps_diff > 0 else "📉" if dps_diff < 0 else "➖"
        sign = "+" if dps_diff > 0 else ""

        embed.add_field(
            name="💥 총 DPS",
            value=f"**Before:** {dps_data['before']:.1f}\n"
                  f"**After:** {dps_data['after']:.1f}\n"
                  f"{indicator} **차이:** {sign}{dps_diff:.1f} ({sign}{dps_diff_percent:.1f}%)",
            inline=False
        )

    # 주요 스킬 비교 (상위 5개)
    skills = result.get('skills', [])
    if skills:
        # Casts 차이가 큰 순으로 정렬
        top_skills = sorted(skills, key=lambda x: abs(x['casts']['diff']), reverse=True)[:5]

        skills_text = ""
        for skill in top_skills:
            casts_diff = skill['casts']['diff']
            crit_diff = skill['crit_percent']['diff']

            casts_indicator = "⬆️" if casts_diff > 0 else "⬇️" if casts_diff < 0 else "➖"
            crit_sign = "+" if crit_diff > 0 else ""

            skills_text += f"**{skill['name']}**\n"
            skills_text += f"  {casts_indicator} Casts: {skill['casts']['before']} → {skill['casts']['after']} ({casts_diff:+d})\n"
            skills_text += f"  🎯 Crit: {skill['crit_percent']['before']:.1f}% → {skill['crit_percent']['after']:.1f}% ({crit_sign}{crit_diff:.1f}%)\n"

            # Uptime이 있는 경우 (DoT 스킬)
            if skill['uptime_percent']['before'] > 0 or skill['uptime_percent']['after'] > 0:
                uptime_diff = skill['uptime_percent']['diff']
                uptime_sign = "+" if uptime_diff > 0 else ""
                skills_text += f"  ⏱️ Uptime: {skill['uptime_percent']['before']:.1f}% → {skill['uptime_percent']['after']:.1f}% ({uptime_sign}{uptime_diff:.1f}%)\n"

            skills_text += "\n"

        if skills_text:
            embed.add_field(name="🎯 주요 스킬 비교", value=skills_text.strip(), inline=False)


def add_tank_fields(embed: discord.Embed, result: dict):
    """탱커 분석 결과를 Embed에 추가"""
    summary = result.get('summary', {})

    # 총 DTPS
    if 'total_dtps' in summary:
        dtps_data = summary['total_dtps']
        dtps_diff = dtps_data['diff']
        dtps_diff_percent = dtps_data['diff_percent']

        # 탱커는 DTPS가 감소하는 것이 좋음
        indicator = "📉" if dtps_diff < 0 else "📈" if dtps_diff > 0 else "➖"
        sign = "+" if dtps_diff > 0 else ""

        embed.add_field(
            name="💔 총 받은 피해 (DTPS)",
            value=f"**Before:** {dtps_data['before']:.1f}\n"
                  f"**After:** {dtps_data['after']:.1f}\n"
                  f"{indicator} **차이:** {sign}{dtps_diff:.1f} ({sign}{dtps_diff_percent:.1f}%)",
            inline=False
        )

    # Mitigated
    if 'mitigated' in summary:
        mit_data = summary['mitigated']
        mit_diff = mit_data['diff']
        indicator = "📈" if mit_diff > 0 else "📉" if mit_diff < 0 else "➖"
        sign = "+" if mit_diff > 0 else ""

        embed.add_field(
            name="🛡️ 피해 감소 (Mitigated)",
            value=f"**Before:** {mit_data['before']:.1f}\n"
                  f"**After:** {mit_data['after']:.1f}\n"
                  f"{indicator} **차이:** {sign}{mit_diff:.1f}",
            inline=True
        )

    # Miss %
    if 'avg_miss_percent' in summary:
        miss_data = summary['avg_miss_percent']
        miss_diff = miss_data['diff']
        # Miss가 증가하는 것이 좋음 (회피)
        indicator = "📈" if miss_diff > 0 else "📉" if miss_diff < 0 else "➖"
        sign = "+" if miss_diff > 0 else ""

        embed.add_field(
            name="🌫️ 평균 회피율 (Miss %)",
            value=f"**Before:** {miss_data['before']:.1f}%\n"
                  f"**After:** {miss_data['after']:.1f}%\n"
                  f"{indicator} **차이:** {sign}{miss_diff:.1f}%",
            inline=True
        )

    # 주요 피해 소스
    damage_sources = result.get('damage_sources', [])
    if damage_sources:
        top_sources = sorted(damage_sources, key=lambda x: abs(x['dtps']['diff']), reverse=True)[:5]

        sources_text = ""
        for source in top_sources:
            dtps_diff = source['dtps']['diff']
            indicator = "⬆️" if dtps_diff > 0 else "⬇️" if dtps_diff < 0 else "➖"

            sources_text += f"**{source['name']}**\n"
            sources_text += f"  {indicator} DTPS: {source['dtps']['before']:.1f} → {source['dtps']['after']:.1f} ({dtps_diff:+.1f})\n\n"

        if sources_text:
            embed.add_field(name="⚔️ 주요 피해 소스", value=sources_text.strip(), inline=False)


def add_healer_fields(embed: discord.Embed, result: dict):
    """힐러 분석 결과를 Embed에 추가"""
    summary = result.get('summary', {})

    # 총 HPS
    if 'total_hps' in summary:
        hps_data = summary['total_hps']
        hps_diff = hps_data['diff']
        hps_diff_percent = hps_data['diff_percent']

        indicator = "📈" if hps_diff > 0 else "📉" if hps_diff < 0 else "➖"
        sign = "+" if hps_diff > 0 else ""

        embed.add_field(
            name="💚 총 HPS",
            value=f"**Before:** {hps_data['before']:.1f}\n"
                  f"**After:** {hps_data['after']:.1f}\n"
                  f"{indicator} **차이:** {sign}{hps_diff:.1f} ({sign}{hps_diff_percent:.1f}%)",
            inline=False
        )

    # Overheal %
    if 'avg_overheal_percent' in summary:
        overheal_data = summary['avg_overheal_percent']
        overheal_diff = overheal_data['diff']
        # Overheal이 감소하는 것이 좋음
        indicator = "📉" if overheal_diff < 0 else "📈" if overheal_diff > 0 else "➖"
        sign = "+" if overheal_diff > 0 else ""

        embed.add_field(
            name="💧 평균 오버힐 %",
            value=f"**Before:** {overheal_data['before']:.1f}%\n"
                  f"**After:** {overheal_data['after']:.1f}%\n"
                  f"{indicator} **차이:** {sign}{overheal_diff:.1f}%",
            inline=True
        )

    # 주요 힐 스킬
    heals = result.get('heals', [])
    if heals:
        top_heals = sorted(heals, key=lambda x: abs(x['hps']['diff']), reverse=True)[:5]

        heals_text = ""
        for heal in top_heals:
            hps_diff = heal['hps']['diff']
            casts_diff = heal['casts']['diff']
            crit_diff = heal['crit_percent']['diff']

            hps_indicator = "⬆️" if hps_diff > 0 else "⬇️" if hps_diff < 0 else "➖"
            casts_indicator = "⬆️" if casts_diff > 0 else "⬇️" if casts_diff < 0 else "➖"
            crit_sign = "+" if crit_diff > 0 else ""

            heals_text += f"**{heal['name']}**\n"
            heals_text += f"  {hps_indicator} HPS: {heal['hps']['before']:.1f} → {heal['hps']['after']:.1f} ({hps_diff:+.1f})\n"
            heals_text += f"  {casts_indicator} Casts: {heal['casts']['before']} → {heal['casts']['after']} ({casts_diff:+d})\n"
            heals_text += f"  🎯 Crit: {heal['crit_percent']['before']:.1f}% → {heal['crit_percent']['after']:.1f}% ({crit_sign}{crit_diff:.1f}%)\n\n"

        if heals_text:
            embed.add_field(name="💊 주요 힐 스킬 비교", value=heals_text.strip(), inline=False)


@bot.command(name='help_compare')
async def help_compare(ctx):
    """사용법 안내"""
    if can_send_embeds(ctx):
        # 권한이 있으면 Embed로 전송
        embed = discord.Embed(
            title="📖 WoW Compare Bot 사용법",
            description="Warcraftlogs CSV 파일 2개를 비교해서 퍼포먼스 차이를 분석합니다.",
            color=COLOR_BLUE
        )

        embed.add_field(
            name="사용 방법",
            value="1. Warcraftlogs에서 CSV 파일 2개를 다운로드\n"
                  "2. 디스코드에 두 파일을 첨부\n"
                  "3. `!compare` 명령어 입력\n"
                  "4. 자동으로 역할(DPS/Tank/Healer)을 감지하고 분석 결과 출력",
            inline=False
        )

        embed.add_field(
            name="지원하는 역할",
            value="⚔️ **DPS**: 총 DPS, 스킬 시전 횟수, 치명타율, DoT Uptime 비교\n"
                  "🛡️ **탱커**: 받은 피해(DTPS), 피해 감소율, 회피율 비교\n"
                  "💚 **힐러**: 총 HPS, 오버힐, 힐 스킬 사용 빈도, 치명타율 비교",
            inline=False
        )

        embed.add_field(
            name="명령어",
            value="`!compare` - CSV 파일 2개 비교\n"
                  "`!help_compare` - 이 도움말 표시",
            inline=False
        )

        await ctx.send(embed=embed)
    else:
        # 권한이 없으면 일반 텍스트로 전송
        help_text = """
📖 **WoW Compare Bot 사용법**
Warcraftlogs CSV 파일 2개를 비교해서 퍼포먼스 차이를 분석합니다.

**사용 방법:**
1. Warcraftlogs에서 CSV 파일 2개를 다운로드
2. 디스코드에 두 파일을 첨부
3. `!compare` 명령어 입력
4. 자동으로 역할(DPS/Tank/Healer)을 감지하고 분석 결과 출력

**지원하는 역할:**
⚔️ **DPS**: 총 DPS, 스킬 시전 횟수, 치명타율, DoT Uptime 비교
🛡️ **탱커**: 받은 피해(DTPS), 피해 감소율, 회피율 비교
💚 **힐러**: 총 HPS, 오버힐, 힐 스킬 사용 빈도, 치명타율 비교

**명령어:**
`!compare` - CSV 파일 2개 비교
`!help_compare` - 이 도움말 표시

⚠️ **참고**: 더 나은 형식의 메시지를 보려면 봇에게 "링크 삽입(Embed Links)" 권한을 부여해주세요.
        """
        await ctx.send(help_text.strip())


# 봇 실행
if __name__ == '__main__':
    if not DISCORD_TOKEN:
        print("❌ DISCORD_TOKEN이 설정되지 않았습니다. .env 파일을 확인해주세요.")
    else:
        bot.run(DISCORD_TOKEN)
