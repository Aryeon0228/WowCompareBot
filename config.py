import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 디스코드 봇 토큰
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

# 봇 설정
COMMAND_PREFIX = '!'

# 역할별 핵심 컬럼 정의
ROLE_IDENTIFIERS = {
    'DPS': 'DPS',
    'TANK': 'DTPS',
    'HEALER': 'HPS'
}

# 분석할 컬럼 매핑
DPS_COLUMNS = ['Name', 'Amount', 'Casts', 'Avg Cast', 'Hits', 'Avg Hit', 'Crit %', 'Uptime %', 'DPS']
TANK_COLUMNS = ['Name', 'Amount', 'Casts', 'Hits', 'Avg Hit', 'Uptime %', 'Miss %', 'Mitigated', 'DTPS']
HEALER_COLUMNS = ['Name', 'Amount', 'Casts', 'Avg Cast', 'Hits', 'Avg Hit', 'Crit %', 'Uptime %', 'Overheal', 'HPS']

# Embed 색상
COLOR_GREEN = 0x00ff00  # 개선됨
COLOR_RED = 0xff0000    # 악화됨
COLOR_BLUE = 0x0099ff   # 중립
