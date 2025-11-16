import discord
from discord.ext import commands
import os
import asyncio
import matplotlib
matplotlib.use('Agg')  # GUI 없이 이미지 생성
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
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
    """전역 에러 핸들러"""
    if isinstance(error, commands.CommandInvokeError):
        original_error = error.original

        if isinstance(original_error, discord.Forbidden):
            # 권한 부족 에러
            try:
                await ctx.send(
                    "❌ 봇에게 필요한 권한이 없습니다.\n"
                    "서버 관리자에게 다음 권한을 부여해달라고 요청하세요:\n"
                    "• 메시지 보내기 (Send Messages)\n"
                    "• 링크 첨부 (Embed Links)\n"
                    "• 파일 첨부 (Attach Files)"
                )
            except discord.Forbidden:
                # 메시지 전송조차 불가능한 경우
                print(f"[ERROR] Cannot send messages in channel {ctx.channel.id} - Missing permissions")
            return

        # 기타 에러는 로그만 출력
        print(f"[ERROR] Command {ctx.command} failed: {original_error}")
        try:
            await ctx.send(f"❌ 명령어 실행 중 오류가 발생했습니다: {str(original_error)[:100]}")
        except:
            pass

    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ 필수 인자가 누락되었습니다: {error.param}")
    elif isinstance(error, commands.CommandNotFound):
        # CommandNotFound는 무시 (사용자가 잘못된 명령어 입력)
        pass
    else:
        print(f"[ERROR] Unhandled error: {error}")


async def safe_send_embed(ctx, embed, fallback_message=None):
    """Embed를 안전하게 전송합니다. 권한이 없으면 일반 메시지로 전송합니다."""
    try:
        await ctx.send(embed=embed)
        return True
    except discord.Forbidden:
        # Embed 전송 권한이 없으면 일반 텍스트로 시도
        if fallback_message:
            try:
                await ctx.send(fallback_message)
                return True
            except discord.Forbidden:
                # 메시지 전송조차 불가능한 경우
                print(f"[ERROR] Cannot send messages in channel {ctx.channel.id}")
                return False
        else:
            try:
                await ctx.send(
                    "❌ 봇에게 Embed 전송 권한이 없습니다. "
                    "서버 관리자에게 '링크 첨부(Embed Links)' 권한을 부여해달라고 요청하세요."
                )
                return False
            except discord.Forbidden:
                print(f"[ERROR] Cannot send messages in channel {ctx.channel.id}")
                return False
    except Exception as e:
        print(f"[ERROR] Failed to send embed: {e}")
        return False


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
    try:
        status_msg = await ctx.send("⏳ 분석 중...")
    except discord.Forbidden:
        print(f"[ERROR] Cannot send status message in channel {ctx.channel.id} - Missing permissions")
        return

    try:
        # 타이핑 중 표시
        async with ctx.typing():
            analyzer = WowLogAnalyzer(file1_path, file2_path)
            result = analyzer.analyze()

        if result is None or 'error' in result:
            error_msg = result.get('error', '알 수 없는 오류') if result else '분석 실패'
            try:
                await status_msg.edit(content=f"❌ {error_msg}")
            except discord.Forbidden:
                print(f"[ERROR] Cannot edit message in channel {ctx.channel.id}")
            return

        # 결과를 Embed로 출력
        embed = create_embed(result, csv_files[0].filename, csv_files[1].filename)

        # 그래프 생성
        graph_path = None
        try:
            graph_path = create_comparison_graph(result, csv_files[0].filename, csv_files[1].filename)
        except Exception as e:
            print(f"[WARNING] Graph creation failed: {e}")

        try:
            await status_msg.edit(content="✅ 분석 완료!")
        except discord.Forbidden:
            print(f"[ERROR] Cannot edit message in channel {ctx.channel.id}")

        # Embed와 그래프 전송
        try:
            if graph_path and os.path.exists(graph_path):
                file = discord.File(graph_path, filename="comparison_graph.png")
                embed.set_image(url="attachment://comparison_graph.png")
                await ctx.send(embed=embed, file=file)
            else:
                await safe_send_embed(ctx, embed, fallback_message="분석이 완료되었지만 Embed 권한이 없어 결과를 표시할 수 없습니다.")
        except discord.Forbidden:
            await safe_send_embed(ctx, embed, fallback_message="분석이 완료되었지만 Embed 권한이 없어 결과를 표시할 수 없습니다.")
        finally:
            # 그래프 파일 삭제
            if graph_path and os.path.exists(graph_path):
                try:
                    os.remove(graph_path)
                except:
                    pass

    except Exception as e:
        try:
            await status_msg.edit(content=f"❌ 분석 오류: {e}")
        except:
            print(f"[ERROR] Cannot edit status message: {e}")
    finally:
        # 임시 파일 삭제
        try:
            os.remove(file1_path)
            os.remove(file2_path)
        except:
            pass


def create_comparison_graph(result: dict, file1_name: str, file2_name: str) -> str:
    """비교 그래프를 생성하고 파일 경로를 반환합니다"""
    role = result.get('role', 'UNKNOWN')

    # 한글 폰트 설정 (시스템에 따라 다를 수 있음)
    plt.rcParams['font.family'] = 'DejaVu Sans'
    plt.rcParams['axes.unicode_minus'] = False

    fig, ax = plt.subplots(figsize=(12, 6))

    if role == 'DPS':
        # DPS 그래프: 총 DPS 비교
        summary = result.get('summary', {})
        if 'total_dps' in summary:
            dps_data = summary['total_dps']
            categories = ['Target', 'You']
            values = [dps_data['before'], dps_data['after']]

            colors = ['#FF6B6B', '#4ECDC4']
            bars = ax.bar(categories, values, color=colors, alpha=0.8, edgecolor='black', linewidth=1.5)

            ax.set_ylabel('DPS', fontsize=14, fontweight='bold')
            ax.set_title('Total DPS Comparison', fontsize=16, fontweight='bold', pad=20)
            ax.grid(axis='y', alpha=0.3, linestyle='--')

            # 값 표시
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{height:.1f}',
                       ha='center', va='bottom', fontsize=12, fontweight='bold')

            # 차이 표시
            diff_percent = dps_data['diff_percent']
            diff_text = f"Difference: {diff_percent:+.1f}%"
            color = 'green' if diff_percent > 0 else 'red' if diff_percent < 0 else 'gray'
            ax.text(0.5, 0.95, diff_text, transform=ax.transAxes,
                   fontsize=13, ha='center', va='top',
                   bbox=dict(boxstyle='round', facecolor=color, alpha=0.3))

    elif role == 'TANK':
        # 탱커 그래프: DTPS 비교
        summary = result.get('summary', {})
        if 'total_dtps' in summary:
            dtps_data = summary['total_dtps']
            categories = ['Target', 'You']
            values = [dtps_data['before'], dtps_data['after']]

            # DTPS는 낮을수록 좋으므로 색상 반전
            colors = ['#FF6B6B', '#4ECDC4'] if dtps_data['diff'] < 0 else ['#4ECDC4', '#FF6B6B']
            bars = ax.bar(categories, values, color=colors, alpha=0.8, edgecolor='black', linewidth=1.5)

            ax.set_ylabel('DTPS (Damage Taken)', fontsize=14, fontweight='bold')
            ax.set_title('Damage Taken Comparison (Lower is Better)', fontsize=16, fontweight='bold', pad=20)
            ax.grid(axis='y', alpha=0.3, linestyle='--')

            # 값 표시
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{height:.1f}',
                       ha='center', va='bottom', fontsize=12, fontweight='bold')

            # 차이 표시 (탱커는 감소가 좋음)
            diff_percent = dtps_data['diff_percent']
            diff_text = f"Difference: {diff_percent:+.1f}%"
            color = 'green' if diff_percent < 0 else 'red' if diff_percent > 0 else 'gray'
            ax.text(0.5, 0.95, diff_text, transform=ax.transAxes,
                   fontsize=13, ha='center', va='top',
                   bbox=dict(boxstyle='round', facecolor=color, alpha=0.3))

    elif role == 'HEALER':
        # 힐러 그래프: HPS 비교
        summary = result.get('summary', {})
        if 'total_hps' in summary:
            hps_data = summary['total_hps']
            categories = ['Target', 'You']
            values = [hps_data['before'], hps_data['after']]

            colors = ['#FF6B6B', '#4ECDC4']
            bars = ax.bar(categories, values, color=colors, alpha=0.8, edgecolor='black', linewidth=1.5)

            ax.set_ylabel('HPS', fontsize=14, fontweight='bold')
            ax.set_title('Total HPS Comparison', fontsize=16, fontweight='bold', pad=20)
            ax.grid(axis='y', alpha=0.3, linestyle='--')

            # 값 표시
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{height:.1f}',
                       ha='center', va='bottom', fontsize=12, fontweight='bold')

            # 차이 표시
            diff_percent = hps_data['diff_percent']
            diff_text = f"Difference: {diff_percent:+.1f}%"
            color = 'green' if diff_percent > 0 else 'red' if diff_percent < 0 else 'gray'
            ax.text(0.5, 0.95, diff_text, transform=ax.transAxes,
                   fontsize=13, ha='center', va='top',
                   bbox=dict(boxstyle='round', facecolor=color, alpha=0.3))

    plt.tight_layout()

    # 파일 저장
    graph_path = 'temp_csvs/comparison_graph.png'
    os.makedirs('temp_csvs', exist_ok=True)
    plt.savefig(graph_path, dpi=100, bbox_inches='tight', facecolor='white')
    plt.close()

    return graph_path


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

    # 서술형 조언
    if result.get('advice'):
        advice_text = '\n\n'.join([f"• {adv}" for adv in result['advice']])
        embed.add_field(name="📝 상세 조언", value=advice_text, inline=False)

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
    embed = discord.Embed(
        title="📖 WoW Compare Bot 사용법",
        description="Warcraftlogs CSV 파일 2개를 비교해서 퍼포먼스 차이를 분석합니다.",
        color=COLOR_BLUE
    )

    embed.add_field(
        name="사용 방법",
        value="1. Warcraftlogs에서 CSV 파일 2개를 다운로드\n"
              "2. 디스코드에 **비교하고 싶은 목표 캐릭터의 CSV를 먼저** 첨부\n"
              "3. **내 캐릭터의 CSV를 두 번째로** 첨부\n"
              "4. `!compare` 명령어 입력\n"
              "5. 자동으로 역할(DPS/Tank/Healer)을 감지하고 분석 결과 출력",
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

    # 일반 텍스트 대체 메시지
    fallback = (
        "📖 **WoW Compare Bot 사용법**\n\n"
        "**사용 방법:**\n"
        "1. Warcraftlogs에서 CSV 파일 2개를 다운로드\n"
        "2. 디스코드에 **비교하고 싶은 목표 캐릭터의 CSV를 먼저** 첨부\n"
        "3. **내 캐릭터의 CSV를 두 번째로** 첨부\n"
        "4. `!compare` 명령어 입력\n"
        "5. 자동으로 역할(DPS/Tank/Healer)을 감지하고 분석 결과 출력\n\n"
        "**지원하는 역할:**\n"
        "⚔️ DPS: 총 DPS, 스킬 시전 횟수, 치명타율, DoT Uptime 비교\n"
        "🛡️ 탱커: 받은 피해(DTPS), 피해 감소율, 회피율 비교\n"
        "💚 힐러: 총 HPS, 오버힐, 힐 스킬 사용 빈도, 치명타율 비교\n\n"
        "**명령어:**\n"
        "`!compare` - CSV 파일 2개 비교\n"
        "`!help_compare` - 이 도움말 표시"
    )

    await safe_send_embed(ctx, embed, fallback_message=fallback)


# 봇 실행
if __name__ == '__main__':
    if not DISCORD_TOKEN:
        print("❌ DISCORD_TOKEN이 설정되지 않았습니다. .env 파일을 확인해주세요.")
    else:
        bot.run(DISCORD_TOKEN)
