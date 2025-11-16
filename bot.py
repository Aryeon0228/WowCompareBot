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

    # 전체 통계 (한 줄로)
    stats_parts = []
    if 'total_dps' in summary:
        dps_data = summary['total_dps']
        dps_diff = dps_data['diff']
        dps_diff_percent = dps_data['diff_percent']
        indicator = "📈" if dps_diff > 0 else "📉" if dps_diff < 0 else "➖"
        sign = "+" if dps_diff > 0 else ""
        stats_parts.append(f"**DPS:** {dps_data['after']:.1f} ({sign}{dps_diff_percent:.1f}%) {indicator}")

    if 'total_damage' in summary:
        dmg_data = summary['total_damage']
        dmg_m_before = dmg_data['before'] / 1_000_000
        dmg_m_after = dmg_data['after'] / 1_000_000
        stats_parts.append(f"**총 데미지:** {dmg_m_after:.2f}M")

    if 'total_casts' in summary:
        casts_data = summary['total_casts']
        stats_parts.append(f"**시전:** {casts_data['after']}")

    if 'avg_crit' in summary:
        crit_data = summary['avg_crit']
        crit_sign = "+" if crit_data['diff'] > 0 else ""
        stats_parts.append(f"**평균 치명타:** {crit_data['after']:.1f}% ({crit_sign}{crit_data['diff']:.1f}%)")

    if stats_parts:
        embed.add_field(name="📊 전체 통계", value=" | ".join(stats_parts), inline=False)

    # 상위 기여도 스킬
    top_contributors = result.get('top_contributors', [])
    if top_contributors:
        contrib_text = ""
        for i, skill in enumerate(top_contributors[:5], 1):
            contrib_text += f"{i}. **{skill['name']}** - {skill['percent']:.1f}%\n"
        embed.add_field(name="🏆 상위 기여도 스킬", value=contrib_text.strip(), inline=True)

    # 주요 스킬 상세 비교 (기여도 순으로 상위 3개)
    skills = result.get('skills', [])
    if skills:
        top_skills = sorted(skills, key=lambda x: x['contribution_percent']['after'], reverse=True)[:3]

        skills_text = ""
        for skill in top_skills:
            # 기본 정보
            contrib_diff = skill['contribution_percent']['diff']
            contrib_sign = "+" if contrib_diff > 0 else ""

            skills_text += f"**{skill['name']}** ({skill['contribution_percent']['after']:.1f}%, {contrib_sign}{contrib_diff:.1f}%)\n"

            # Casts
            casts_diff = skill['casts']['diff']
            casts_indicator = "↑" if casts_diff > 0 else "↓" if casts_diff < 0 else "-"
            skills_text += f"  시전: {skill['casts']['after']} ({casts_indicator}{abs(casts_diff)})"

            # Avg Hit
            if 'avg_hit' in skill and skill['avg_hit']['after'] > 0:
                avg_diff_pct = (skill['avg_hit']['diff'] / skill['avg_hit']['before'] * 100) if skill['avg_hit']['before'] > 0 else 0
                if abs(avg_diff_pct) > 1:
                    avg_sign = "+" if avg_diff_pct > 0 else ""
                    skills_text += f" | 평균: {skill['avg_hit']['after']:.0f} ({avg_sign}{avg_diff_pct:.1f}%)"

            skills_text += "\n"

            # Crit %
            crit_diff = skill['crit_percent']['diff']
            if abs(crit_diff) > 0.5:
                crit_sign = "+" if crit_diff > 0 else ""
                skills_text += f"  치명타: {skill['crit_percent']['after']:.1f}% ({crit_sign}{crit_diff:.1f}%)\n"

            # Uptime (DoT 스킬)
            if skill['uptime_percent']['after'] > 0 or skill['uptime_percent']['before'] > 0:
                uptime_diff = skill['uptime_percent']['diff']
                uptime_sign = "+" if uptime_diff > 0 else ""
                uptime_indicator = "✓" if skill['uptime_percent']['after'] >= 80 else "⚠️"
                skills_text += f"  {uptime_indicator} Uptime: {skill['uptime_percent']['after']:.1f}% ({uptime_sign}{uptime_diff:.1f}%)\n"

            # 시전 효율성
            if 'damage_per_cast' in skill and skill['damage_per_cast']['after'] > 0:
                dpc_diff_pct = (skill['damage_per_cast']['diff'] / skill['damage_per_cast']['before'] * 100) if skill['damage_per_cast']['before'] > 0 else 0
                if abs(dpc_diff_pct) > 5:
                    dpc_sign = "+" if dpc_diff_pct > 0 else ""
                    skills_text += f"  효율성: {skill['damage_per_cast']['after']:.0f}/cast ({dpc_sign}{dpc_diff_pct:.1f}%)\n"

            skills_text += "\n"

        if skills_text:
            embed.add_field(name="🎯 주요 스킬 상세", value=skills_text.strip(), inline=False)


def add_tank_fields(embed: discord.Embed, result: dict):
    """탱커 분석 결과를 Embed에 추가"""
    summary = result.get('summary', {})

    # 전체 통계
    stats_parts = []
    if 'total_dtps' in summary:
        dtps_data = summary['total_dtps']
        dtps_diff = dtps_data['diff']
        dtps_diff_percent = dtps_data['diff_percent']
        indicator = "📉" if dtps_diff < 0 else "📈" if dtps_diff < 0 else "➖"
        sign = "+" if dtps_diff > 0 else ""
        stats_parts.append(f"**DTPS:** {dtps_data['after']:.1f} ({sign}{dtps_diff_percent:.1f}%) {indicator}")

    if 'total_damage_taken' in summary:
        dmg_data = summary['total_damage_taken']
        dmg_m = dmg_data['after'] / 1_000_000
        stats_parts.append(f"**총 피해:** {dmg_m:.2f}M")

    if 'avg_miss_percent' in summary:
        miss_data = summary['avg_miss_percent']
        miss_sign = "+" if miss_data['diff'] > 0 else ""
        stats_parts.append(f"**회피율:** {miss_data['after']:.1f}% ({miss_sign}{miss_data['diff']:.1f}%)")

    if 'avg_uptime' in summary:
        uptime_data = summary['avg_uptime']
        uptime_sign = "+" if uptime_data['diff'] > 0 else ""
        stats_parts.append(f"**버프 유지:** {uptime_data['after']:.1f}% ({uptime_sign}{uptime_data['diff']:.1f}%)")

    if stats_parts:
        embed.add_field(name="📊 전체 통계", value=" | ".join(stats_parts), inline=False)

    # 피해 감소 (Mitigated)
    if 'mitigated' in summary:
        mit_data = summary['mitigated']
        mit_diff = mit_data['diff']
        mit_diff_pct = mit_data['diff_percent']
        indicator = "✓" if mit_diff > 0 else "⚠️"
        sign = "+" if mit_diff > 0 else ""
        mit_m = mit_data['after'] / 1_000_000

        embed.add_field(
            name=f"{indicator} 피해 감소 (Mitigated)",
            value=f"**{mit_m:.2f}M** ({sign}{mit_diff_pct:.1f}%)",
            inline=True
        )

    # 주요 피해 소스 (기여도 순)
    damage_sources = result.get('damage_sources', [])
    if damage_sources:
        top_sources = sorted(damage_sources, key=lambda x: x['contribution_percent']['after'], reverse=True)[:4]

        sources_text = ""
        for source in top_sources:
            contrib = source['contribution_percent']['after']
            contrib_diff = source['contribution_percent']['diff']
            contrib_sign = "+" if contrib_diff > 0 else ""

            dtps_diff = source['dtps']['diff']
            dtps_indicator = "↑" if dtps_diff > 0 else "↓" if dtps_diff < 0 else "-"

            sources_text += f"**{source['name']}** ({contrib:.1f}%, {contrib_sign}{contrib_diff:.1f}%)\n"
            sources_text += f"  DTPS: {source['dtps']['after']:.1f} ({dtps_indicator}{abs(dtps_diff):.1f})"

            # Avg Hit
            if 'avg_hit' in source and source['avg_hit']['after'] > 0:
                avg_diff = source['avg_hit']['diff']
                if abs(avg_diff) > 100:
                    avg_sign = "+" if avg_diff > 0 else ""
                    sources_text += f" | 평균: {source['avg_hit']['after']:.0f} ({avg_sign}{avg_diff:.0f})"

            sources_text += "\n\n"

        if sources_text:
            embed.add_field(name="⚔️ 주요 피해 소스", value=sources_text.strip(), inline=False)

    # 방어 스킬 (Mitigation skills with uptime)
    mitigation_skills = result.get('mitigation_skills', [])
    if mitigation_skills:
        # Uptime 차이가 큰 순으로
        top_mit = sorted(mitigation_skills, key=lambda x: abs(x['uptime_percent']['diff']), reverse=True)[:3]

        mit_text = ""
        for skill in top_mit:
            uptime = skill['uptime_percent']['after']
            uptime_diff = skill['uptime_percent']['diff']
            uptime_sign = "+" if uptime_diff > 0 else ""
            uptime_icon = "✓" if uptime >= 70 else "⚠️"

            mit_text += f"{uptime_icon} **{skill['name']}**: {uptime:.1f}% ({uptime_sign}{uptime_diff:.1f}%)\n"

        if mit_text:
            embed.add_field(name="🛡️ 방어 스킬 유지율", value=mit_text.strip(), inline=False)


def add_healer_fields(embed: discord.Embed, result: dict):
    """힐러 분석 결과를 Embed에 추가"""
    summary = result.get('summary', {})

    # 전체 통계
    stats_parts = []
    if 'total_hps' in summary:
        hps_data = summary['total_hps']
        hps_diff = hps_data['diff']
        hps_diff_percent = hps_data['diff_percent']
        indicator = "📈" if hps_diff > 0 else "📉" if hps_diff < 0 else "➖"
        sign = "+" if hps_diff > 0 else ""
        stats_parts.append(f"**HPS:** {hps_data['after']:.1f} ({sign}{hps_diff_percent:.1f}%) {indicator}")

    if 'total_healing' in summary:
        heal_data = summary['total_healing']
        heal_m = heal_data['after'] / 1_000_000
        stats_parts.append(f"**총 힐량:** {heal_m:.2f}M")

    if 'total_casts' in summary:
        casts_data = summary['total_casts']
        stats_parts.append(f"**시전:** {casts_data['after']}")

    if 'avg_crit' in summary:
        crit_data = summary['avg_crit']
        crit_sign = "+" if crit_data['diff'] > 0 else ""
        stats_parts.append(f"**평균 치명타:** {crit_data['after']:.1f}% ({crit_sign}{crit_data['diff']:.1f}%)")

    if stats_parts:
        embed.add_field(name="📊 전체 통계", value=" | ".join(stats_parts), inline=False)

    # 오버힐
    if 'avg_overheal_percent' in summary:
        overheal_data = summary['avg_overheal_percent']
        overheal_diff = overheal_data['diff']
        indicator = "✓" if overheal_diff < 0 else "⚠️"
        sign = "+" if overheal_diff > 0 else ""

        embed.add_field(
            name=f"{indicator} 평균 오버힐",
            value=f"**{overheal_data['after']:.1f}%** ({sign}{overheal_diff:.1f}%)",
            inline=True
        )

    # 상위 기여도 힐 스킬
    top_contributors = result.get('top_contributors', [])
    if top_contributors:
        contrib_text = ""
        for i, heal in enumerate(top_contributors[:5], 1):
            contrib_text += f"{i}. **{heal['name']}** - {heal['percent']:.1f}%\n"
        embed.add_field(name="🏆 상위 기여도 스킬", value=contrib_text.strip(), inline=True)

    # 주요 힐 스킬 상세 비교 (기여도 순으로 상위 3개)
    heals = result.get('heals', [])
    if heals:
        top_heals = sorted(heals, key=lambda x: x['contribution_percent']['after'], reverse=True)[:3]

        heals_text = ""
        for heal in top_heals:
            # 기본 정보
            contrib_diff = heal['contribution_percent']['diff']
            contrib_sign = "+" if contrib_diff > 0 else ""

            heals_text += f"**{heal['name']}** ({heal['contribution_percent']['after']:.1f}%, {contrib_sign}{contrib_diff:.1f}%)\n"

            # Casts & HPS
            casts_diff = heal['casts']['diff']
            casts_indicator = "↑" if casts_diff > 0 else "↓" if casts_diff < 0 else "-"
            hps_diff = heal['hps']['diff']
            hps_sign = "+" if hps_diff > 0 else ""

            heals_text += f"  시전: {heal['casts']['after']} ({casts_indicator}{abs(casts_diff)})"
            heals_text += f" | HPS: {heal['hps']['after']:.1f} ({hps_sign}{hps_diff:.1f})\n"

            # Avg Hit
            if 'avg_hit' in heal and heal['avg_hit']['after'] > 0:
                avg_diff_pct = (heal['avg_hit']['diff'] / heal['avg_hit']['before'] * 100) if heal['avg_hit']['before'] > 0 else 0
                if abs(avg_diff_pct) > 1:
                    avg_sign = "+" if avg_diff_pct > 0 else ""
                    heals_text += f"  평균 힐: {heal['avg_hit']['after']:.0f} ({avg_sign}{avg_diff_pct:.1f}%)\n"

            # Crit %
            crit_diff = heal['crit_percent']['diff']
            if abs(crit_diff) > 0.5:
                crit_sign = "+" if crit_diff > 0 else ""
                heals_text += f"  치명타: {heal['crit_percent']['after']:.1f}% ({crit_sign}{crit_diff:.1f}%)\n"

            # Uptime (HoT 스킬)
            if 'uptime_percent' in heal and (heal['uptime_percent']['after'] > 0 or heal['uptime_percent']['before'] > 0):
                uptime_diff = heal['uptime_percent']['diff']
                uptime_sign = "+" if uptime_diff > 0 else ""
                uptime_indicator = "✓" if heal['uptime_percent']['after'] >= 80 else "⚠️"
                heals_text += f"  {uptime_indicator} Uptime: {heal['uptime_percent']['after']:.1f}% ({uptime_sign}{uptime_diff:.1f}%)\n"

            # Overheal
            if 'overheal_percent' in heal and heal['overheal_percent']['after'] > 0:
                overheal_diff = heal['overheal_percent']['diff']
                overheal_sign = "+" if overheal_diff > 0 else ""
                overheal_icon = "✓" if heal['overheal_percent']['after'] < 30 else "⚠️" if heal['overheal_percent']['after'] > 50 else "○"
                heals_text += f"  {overheal_icon} 오버힐: {heal['overheal_percent']['after']:.1f}% ({overheal_sign}{overheal_diff:.1f}%)\n"

            # 시전 효율성
            if 'heal_per_cast' in heal and heal['heal_per_cast']['after'] > 0:
                hpc_diff_pct = (heal['heal_per_cast']['diff'] / heal['heal_per_cast']['before'] * 100) if heal['heal_per_cast']['before'] > 0 else 0
                if abs(hpc_diff_pct) > 5:
                    hpc_sign = "+" if hpc_diff_pct > 0 else ""
                    heals_text += f"  효율성: {heal['heal_per_cast']['after']:.0f}/cast ({hpc_sign}{hpc_diff_pct:.1f}%)\n"

            heals_text += "\n"

        if heals_text:
            embed.add_field(name="💊 주요 힐 스킬 상세", value=heals_text.strip(), inline=False)


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
            value="⚔️ **DPS**: 총 DPS/데미지, 스킬 기여도, 평균 피해, 시전 효율성, 치명타율, DoT Uptime\n"
                  "🛡️ **탱커**: 받은 피해(DTPS), 피해 감소율, 회피율, 방어 스킬 유지율, 피해 소스 분석\n"
                  "💚 **힐러**: 총 HPS/힐량, 힐 기여도, 평균 힐, 시전 효율성, 치명타율, HoT Uptime, 오버힐",
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
⚔️ **DPS**: 총 DPS/데미지, 스킬 기여도, 평균 피해, 시전 효율성, 치명타율, DoT Uptime
🛡️ **탱커**: 받은 피해(DTPS), 피해 감소율, 회피율, 방어 스킬 유지율, 피해 소스 분석
💚 **힐러**: 총 HPS/힐량, 힐 기여도, 평균 힐, 시전 효율성, 치명타율, HoT Uptime, 오버힐

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
