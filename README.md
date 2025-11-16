# WoW Compare Bot

와우 클래식 Warcraftlogs CSV 파일 2개를 비교해서 퍼포먼스 차이를 분석해주는 디스코드 봇입니다.

## 주요 기능

### 자동 역할 감지
CSV 파일의 컬럼을 분석해서 자동으로 역할을 판단합니다:
- **DPS** - "DPS" 컬럼 있음
- **탱커** - "DTPS" 컬럼 있음
- **힐러** - "HPS" 컬럼 있음

### 역할별 비교 지표

#### DPS 분석
- 총 DPS 차이
- 주요 스킬 시전 횟수(Casts) 비교
- 치명타율(Crit %) 차이
- DoT 스킬 Uptime % 비교
- 누락된 스킬 확인

#### 탱커 분석
- 총 받은 피해(DTPS) 비교
- Mitigated (피해 감소율) 비교
- Miss % (회피율) 비교
- 주요 피해 소스별 비교

#### 힐러 분석
- 총 HPS 비교
- Overheal % 비교
- 주요 힐 스킬 사용 빈도
- 치명타율 비교

## 설치 및 실행

### 1. 필수 요구사항
- Python 3.10 이상
- pip

### 2. 패키지 설치
```bash
pip install -r requirements.txt
```

### 3. Discord Bot 생성 및 토큰 발급

1. [Discord Developer Portal](https://discord.com/developers/applications)에 접속
2. "New Application" 클릭하여 새 애플리케이션 생성
3. 좌측 메뉴에서 "Bot" 선택
4. "Add Bot" 클릭
5. "Reset Token" 클릭하여 토큰 생성 (토큰을 복사해서 안전하게 보관)
6. **Privileged Gateway Intents** 섹션에서 다음 항목 활성화:
   - ✅ Message Content Intent (중요!)

### 4. 환경 변수 설정

`.env.example` 파일을 복사하여 `.env` 파일 생성:
```bash
cp .env.example .env
```

`.env` 파일을 열어서 디스코드 봇 토큰을 입력하세요:
```
DISCORD_TOKEN=여기에_복사한_봇_토큰_붙여넣기
```

### 5. 봇을 서버에 초대

1. Discord Developer Portal에서 좌측 "OAuth2" → "URL Generator" 선택
2. **Scopes**에서 `bot` 선택
3. **Bot Permissions**에서 다음 권한 선택:
   - ✅ Send Messages (메시지 보내기)
   - ✅ Embed Links (링크 첨부)
   - ✅ Attach Files (파일 첨부)
   - ✅ Read Message History (메시지 기록 보기)
4. 생성된 URL로 접속하여 봇을 서버에 초대

### 6. 봇 실행
```bash
python bot.py
```

봇이 성공적으로 실행되면 다음과 같은 메시지가 표시됩니다:
```
WowCompareBot 봇이 성공적으로 연결되었습니다!
Bot ID: 1234567890
------
```

## 사용 방법

### Discord에서 사용하기

1. Warcraftlogs에서 CSV 파일 2개를 다운로드합니다
2. 디스코드 채널에 두 파일을 첨부합니다
3. `!compare` 명령어를 입력합니다
4. 봇이 자동으로 역할을 감지하고 분석 결과를 Discord Embed로 출력합니다

### 명령어

- `!compare` - CSV 파일 2개를 비교 분석
- `!help_compare` - 사용법 안내

## CSV 구조 참고

### DPS CSV 예시
```
Name, Amount, Casts, Avg Cast, Hits, Avg Hit, Crit %, Uptime %, DPS
Shadowbolt, 6537007$19.84%6.54M, 145, 1.5, 140, 46692, 25.5%, 0%, 1234.5
```

### 탱커 CSV 예시
```
Name, Amount, Casts, Hits, Avg Hit, Uptime %, Miss %, Mitigated, DTPS
Melee, 125000$45.2%125K, 0, 85, 1470, 0%, 12.5%, 5000, 234.5
```

### 힐러 CSV 예시
```
Name, Amount, Casts, Avg Cast, Hits, Avg Hit, Crit %, Uptime %, Overheal, HPS
Flash Heal, 345000$28.5%345K, 85, 2.5, 85, 4058, 18.2%, 0%, 25.5%, 456.7
```

## 파일 구조

```
WowCompareBot/
├── bot.py              # 메인 봇 코드
├── analyzer.py         # CSV 비교 로직
├── config.py           # 설정 파일
├── .env               # 봇 토큰 (보안)
├── requirements.txt   # Python 패키지
└── README.md          # 사용 설명서
```

## 주요 기능 상세

### Amount 필드 파싱
- 형식: `"6537007$19.84%6.54M"`
- 실제값, 퍼센트, M 단위로 자동 파싱

### 에러 처리
- 파일 형식 오류 감지
- 잘못된 CSV 구조 확인
- 역할 감지 실패 시 안내 메시지

### 한글 지원
- UTF-8 인코딩 지원
- 한글 스킬명 정상 처리

## 개선 제안 기능

봇은 분석 결과를 바탕으로 자동으로 개선 포인트를 제안합니다:
- DPS: 새로운 스킬 사용, 누락된 스킬 알림
- 탱커: 받은 피해 감소 확인
- 힐러: 오버힐 효율 개선 확인

## 라이선스

MIT License

## 문의

이슈나 개선 사항은 GitHub Issues를 통해 제안해주세요.
