import pandas as pd
import re
from typing import Tuple, Dict, Optional
from config import ROLE_IDENTIFIERS


class WowLogAnalyzer:
    """Warcraft Logs CSV 파일을 분석하고 비교하는 클래스"""

    def __init__(self, csv1_path: str, csv2_path: str):
        self.csv1_path = csv1_path
        self.csv2_path = csv2_path
        self.df1 = None
        self.df2 = None
        self.role = None

    def load_csvs(self) -> bool:
        """CSV 파일들을 로드합니다"""
        try:
            self.df1 = pd.read_csv(self.csv1_path, encoding='utf-8')
            self.df2 = pd.read_csv(self.csv2_path, encoding='utf-8')
            return True
        except Exception as e:
            print(f"CSV 로드 오류: {e}")
            return False

    def detect_role(self) -> Optional[str]:
        """CSV의 컬럼을 분석해서 역할을 자동으로 감지합니다"""
        columns = self.df1.columns.tolist()

        if 'DPS' in columns:
            self.role = 'DPS'
        elif 'DTPS' in columns:
            self.role = 'TANK'
        elif 'HPS' in columns:
            self.role = 'HEALER'
        else:
            self.role = None

        return self.role

    def parse_amount(self, value: str) -> Tuple[float, float, float]:
        """
        Amount 필드 파싱: "6537007$19.84%6.54M" 형식
        Returns: (실제값, 퍼센트, M단위값)
        """
        if pd.isna(value) or value == '':
            return 0.0, 0.0, 0.0

        try:
            # $ 기준으로 분리
            parts = str(value).split('$')
            actual = float(parts[0]) if len(parts) > 0 else 0.0

            if len(parts) > 1:
                # % 기준으로 분리
                percent_part = parts[1]
                percent_match = re.search(r'([\d.]+)%', percent_part)
                percent = float(percent_match.group(1)) if percent_match else 0.0

                # M 단위 추출
                m_match = re.search(r'([\d.]+)M', percent_part)
                m_value = float(m_match.group(1)) if m_match else 0.0
            else:
                percent = 0.0
                m_value = 0.0

            return actual, percent, m_value
        except Exception as e:
            print(f"Amount 파싱 오류: {value}, {e}")
            return 0.0, 0.0, 0.0

    def parse_percentage(self, value: str) -> float:
        """퍼센트 값을 파싱합니다 (예: "25.5%" -> 25.5)"""
        if pd.isna(value) or value == '':
            return 0.0

        try:
            # % 제거하고 float 변환
            return float(str(value).replace('%', ''))
        except:
            return 0.0

    def parse_number(self, value) -> float:
        """일반 숫자 값을 파싱합니다 (문자열을 float로 변환)"""
        if pd.isna(value) or value == '':
            return 0.0

        try:
            # 이미 숫자면 그대로 반환
            if isinstance(value, (int, float)):
                return float(value)
            # 문자열이면 변환
            return float(str(value).replace(',', ''))
        except:
            return 0.0

    def compare_dps(self) -> Dict:
        """DPS 역할의 두 CSV를 비교합니다"""
        result = {
            'role': 'DPS',
            'summary': {},
            'skills': [],
            'missing_skills': [],
            'improvements': []
        }

        # 총 DPS 비교
        total_dps1 = self.df1['DPS'].apply(self.parse_number).sum() if 'DPS' in self.df1.columns else 0
        total_dps2 = self.df2['DPS'].apply(self.parse_number).sum() if 'DPS' in self.df2.columns else 0
        dps_diff = total_dps2 - total_dps1
        dps_diff_percent = (dps_diff / total_dps1 * 100) if total_dps1 > 0 else 0

        result['summary']['total_dps'] = {
            'before': total_dps1,
            'after': total_dps2,
            'diff': dps_diff,
            'diff_percent': dps_diff_percent
        }

        # 스킬별 비교
        skills1 = set(self.df1['Name'].tolist())
        skills2 = set(self.df2['Name'].tolist())

        # 공통 스킬 비교
        common_skills = skills1.intersection(skills2)
        for skill in common_skills:
            skill_data1 = self.df1[self.df1['Name'] == skill].iloc[0]
            skill_data2 = self.df2[self.df2['Name'] == skill].iloc[0]

            # Casts 비교
            casts1 = int(self.parse_number(skill_data1.get('Casts', 0)))
            casts2 = int(self.parse_number(skill_data2.get('Casts', 0)))

            # Crit % 비교
            crit1 = self.parse_percentage(skill_data1.get('Crit %', '0%'))
            crit2 = self.parse_percentage(skill_data2.get('Crit %', '0%'))

            # Uptime % 비교 (DoT 스킬용)
            uptime1 = self.parse_percentage(skill_data1.get('Uptime %', '0%'))
            uptime2 = self.parse_percentage(skill_data2.get('Uptime %', '0%'))

            result['skills'].append({
                'name': skill,
                'casts': {'before': casts1, 'after': casts2, 'diff': casts2 - casts1},
                'crit_percent': {'before': crit1, 'after': crit2, 'diff': crit2 - crit1},
                'uptime_percent': {'before': uptime1, 'after': uptime2, 'diff': uptime2 - uptime1}
            })

        # 누락된 스킬 확인
        missing_in_new = skills1 - skills2
        new_skills = skills2 - skills1

        if missing_in_new:
            result['missing_skills'] = list(missing_in_new)
        if new_skills:
            result['improvements'].append(f"새로운 스킬 사용: {', '.join(new_skills)}")

        return result

    def compare_tank(self) -> Dict:
        """탱커 역할의 두 CSV를 비교합니다"""
        result = {
            'role': 'TANK',
            'summary': {},
            'damage_sources': [],
            'improvements': []
        }

        # 총 받은 피해(DTPS) 비교
        total_dtps1 = self.df1['DTPS'].apply(self.parse_number).sum() if 'DTPS' in self.df1.columns else 0
        total_dtps2 = self.df2['DTPS'].apply(self.parse_number).sum() if 'DTPS' in self.df2.columns else 0
        dtps_diff = total_dtps2 - total_dtps1
        dtps_diff_percent = (dtps_diff / total_dtps1 * 100) if total_dtps1 > 0 else 0

        result['summary']['total_dtps'] = {
            'before': total_dtps1,
            'after': total_dtps2,
            'diff': dtps_diff,
            'diff_percent': dtps_diff_percent
        }

        # Mitigated 비교
        if 'Mitigated' in self.df1.columns:
            total_mitigated1 = self.df1['Mitigated'].apply(self.parse_number).sum()
            total_mitigated2 = self.df2['Mitigated'].apply(self.parse_number).sum()
            result['summary']['mitigated'] = {
                'before': total_mitigated1,
                'after': total_mitigated2,
                'diff': total_mitigated2 - total_mitigated1
            }

        # Miss % 평균 비교
        if 'Miss %' in self.df1.columns:
            avg_miss1 = self.df1['Miss %'].apply(self.parse_percentage).mean()
            avg_miss2 = self.df2['Miss %'].apply(self.parse_percentage).mean()
            result['summary']['avg_miss_percent'] = {
                'before': avg_miss1,
                'after': avg_miss2,
                'diff': avg_miss2 - avg_miss1
            }

        # 주요 피해 소스별 비교
        sources1 = set(self.df1['Name'].tolist())
        sources2 = set(self.df2['Name'].tolist())

        common_sources = sources1.intersection(sources2)
        for source in common_sources:
            source_data1 = self.df1[self.df1['Name'] == source].iloc[0]
            source_data2 = self.df2[self.df2['Name'] == source].iloc[0]

            dtps1 = self.parse_number(source_data1.get('DTPS', 0))
            dtps2 = self.parse_number(source_data2.get('DTPS', 0))

            result['damage_sources'].append({
                'name': source,
                'dtps': {'before': dtps1, 'after': dtps2, 'diff': dtps2 - dtps1}
            })

        # 개선 제안
        if dtps_diff < 0:
            result['improvements'].append("받은 피해가 감소했습니다. 좋은 개선입니다!")

        return result

    def compare_healer(self) -> Dict:
        """힐러 역할의 두 CSV를 비교합니다"""
        result = {
            'role': 'HEALER',
            'summary': {},
            'heals': [],
            'improvements': []
        }

        # 총 HPS 비교
        total_hps1 = self.df1['HPS'].apply(self.parse_number).sum() if 'HPS' in self.df1.columns else 0
        total_hps2 = self.df2['HPS'].apply(self.parse_number).sum() if 'HPS' in self.df2.columns else 0
        hps_diff = total_hps2 - total_hps1
        hps_diff_percent = (hps_diff / total_hps1 * 100) if total_hps1 > 0 else 0

        result['summary']['total_hps'] = {
            'before': total_hps1,
            'after': total_hps2,
            'diff': hps_diff,
            'diff_percent': hps_diff_percent
        }

        # Overheal % 평균 비교
        avg_overheal1 = 0
        avg_overheal2 = 0
        if 'Overheal' in self.df1.columns:
            # Overheal은 퍼센트 형식일 수 있음
            avg_overheal1 = self.df1['Overheal'].apply(lambda x: self.parse_percentage(x) if isinstance(x, str) else self.parse_number(x)).mean()
            avg_overheal2 = self.df2['Overheal'].apply(lambda x: self.parse_percentage(x) if isinstance(x, str) else self.parse_number(x)).mean()
            result['summary']['avg_overheal_percent'] = {
                'before': avg_overheal1,
                'after': avg_overheal2,
                'diff': avg_overheal2 - avg_overheal1
            }

        # 힐 스킬별 비교
        heals1 = set(self.df1['Name'].tolist())
        heals2 = set(self.df2['Name'].tolist())

        common_heals = heals1.intersection(heals2)
        for heal in common_heals:
            heal_data1 = self.df1[self.df1['Name'] == heal].iloc[0]
            heal_data2 = self.df2[self.df2['Name'] == heal].iloc[0]

            # Casts 비교
            casts1 = int(self.parse_number(heal_data1.get('Casts', 0)))
            casts2 = int(self.parse_number(heal_data2.get('Casts', 0)))

            # Crit % 비교
            crit1 = self.parse_percentage(heal_data1.get('Crit %', '0%'))
            crit2 = self.parse_percentage(heal_data2.get('Crit %', '0%'))

            # HPS 비교
            hps1 = self.parse_number(heal_data1.get('HPS', 0))
            hps2 = self.parse_number(heal_data2.get('HPS', 0))

            result['heals'].append({
                'name': heal,
                'casts': {'before': casts1, 'after': casts2, 'diff': casts2 - casts1},
                'crit_percent': {'before': crit1, 'after': crit2, 'diff': crit2 - crit1},
                'hps': {'before': hps1, 'after': hps2, 'diff': hps2 - hps1}
            })

        # 개선 제안
        if avg_overheal2 < avg_overheal1:
            result['improvements'].append("오버힐이 감소했습니다. 효율적인 힐링입니다!")

        return result

    def analyze(self) -> Optional[Dict]:
        """전체 분석을 수행합니다"""
        if not self.load_csvs():
            return None

        role = self.detect_role()
        if not role:
            return {'error': '역할을 감지할 수 없습니다. CSV 형식을 확인해주세요.'}

        if role == 'DPS':
            return self.compare_dps()
        elif role == 'TANK':
            return self.compare_tank()
        elif role == 'HEALER':
            return self.compare_healer()
        else:
            return {'error': f'지원하지 않는 역할입니다: {role}'}
