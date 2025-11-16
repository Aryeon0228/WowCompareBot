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
            'improvements': [],
            'advice': []  # 서술형 조언
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

        # 서술형 조언 생성
        self._generate_dps_advice(result)

        return result

    def _generate_dps_advice(self, result: Dict):
        """DPS에 대한 서술형 조언을 생성합니다"""
        advice = []
        summary = result.get('summary', {})

        # 총 DPS 차이에 대한 조언
        if 'total_dps' in summary:
            dps_diff_percent = summary['total_dps']['diff_percent']
            dps_diff = summary['total_dps']['diff']

            if dps_diff_percent > 10:
                advice.append(f"목표 캐릭터 대비 {abs(dps_diff_percent):.1f}% 더 높은 DPS를 기록했습니다! 훌륭한 향상입니다. 현재 사용 중인 로테이션과 스킬 우선순위를 유지하세요.")
            elif dps_diff_percent > 0:
                advice.append(f"목표 캐릭터보다 {dps_diff_percent:.1f}% 향상되었습니다. 꾸준히 개선되고 있네요!")
            elif dps_diff_percent > -10:
                advice.append(f"목표 캐릭터보다 {abs(dps_diff_percent):.1f}% 낮은 DPS를 기록했습니다. 스킬 우선순위와 로테이션을 다시 점검해보세요.")
            else:
                advice.append(f"목표 캐릭터 대비 {abs(dps_diff_percent):.1f}% 낮은 수치입니다. 아래 스킬 사용 패턴을 면밀히 비교하여 개선점을 찾아보세요.")

        # 스킬 사용 패턴 분석
        skills = result.get('skills', [])
        if skills:
            # Casts가 많이 감소한 스킬
            decreased_casts = [s for s in skills if s['casts']['diff'] < -5]
            if decreased_casts:
                skill_names = [s['name'] for s in decreased_casts[:3]]
                advice.append(f"{', '.join(skill_names)} 스킬의 사용 빈도가 감소했습니다. 이 스킬들을 로테이션에서 놓치고 있지 않은지 확인하세요.")

            # Crit 확률이 개선된 스킬
            improved_crit = [s for s in skills if s['crit_percent']['diff'] > 5]
            if improved_crit:
                skill_names = [s['name'] for s in improved_crit[:2]]
                advice.append(f"{', '.join(skill_names)} 스킬의 치명타율이 향상되었습니다. 좋은 장비 개선 또는 버프 활용입니다!")

            # Uptime이 중요한 DoT 스킬 분석
            dot_skills = [s for s in skills if s['uptime_percent']['before'] > 0 or s['uptime_percent']['after'] > 0]
            low_uptime = [s for s in dot_skills if s['uptime_percent']['after'] < 80 and s['uptime_percent']['diff'] < 0]
            if low_uptime:
                skill_names = [s['name'] for s in low_uptime[:2]]
                advice.append(f"{', '.join(skill_names)}의 Uptime이 감소했습니다. DoT/버프 유지율을 높이기 위해 타이머를 활용하거나 갱신 시점을 개선하세요.")

        # 누락된 스킬에 대한 조언
        missing_skills = result.get('missing_skills', [])
        if missing_skills:
            advice.append(f"목표 캐릭터가 사용한 {', '.join(missing_skills[:3])} 스킬을 사용하지 않았습니다. 이 스킬들이 로테이션에 포함되어야 하는지 확인하세요.")

        result['advice'] = advice

    def compare_tank(self) -> Dict:
        """탱커 역할의 두 CSV를 비교합니다"""
        result = {
            'role': 'TANK',
            'summary': {},
            'damage_sources': [],
            'improvements': [],
            'advice': []  # 서술형 조언
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

        # 서술형 조언 생성
        self._generate_tank_advice(result)

        return result

    def _generate_tank_advice(self, result: Dict):
        """탱커에 대한 서술형 조언을 생성합니다"""
        advice = []
        summary = result.get('summary', {})

        # 총 DTPS 차이에 대한 조언
        if 'total_dtps' in summary:
            dtps_diff_percent = summary['total_dtps']['diff_percent']
            dtps_diff = summary['total_dtps']['diff']

            if dtps_diff_percent < -10:
                advice.append(f"목표 캐릭터 대비 받은 피해가 {abs(dtps_diff_percent):.1f}% 감소했습니다! 훌륭한 생존력 향상입니다. 현재 방어 스킬 사용 패턴을 유지하세요.")
            elif dtps_diff_percent < 0:
                advice.append(f"목표 캐릭터보다 {abs(dtps_diff_percent):.1f}% 적은 피해를 받았습니다. 좋은 개선입니다!")
            elif dtps_diff_percent < 10:
                advice.append(f"목표 캐릭터보다 {dtps_diff_percent:.1f}% 더 많은 피해를 받았습니다. 방어 스킬 사용 타이밍을 개선해보세요.")
            else:
                advice.append(f"목표 캐릭터 대비 {dtps_diff_percent:.1f}% 더 많은 피해를 받았습니다. 피해 감소 스킬의 적극적인 활용과 위치 선정을 점검하세요.")

        # Mitigated 분석
        if 'mitigated' in summary:
            mit_diff = summary['mitigated']['diff']
            if mit_diff > 0:
                advice.append(f"피해 감소량이 증가했습니다. 방어 쿨다운을 효과적으로 사용하고 있습니다!")
            elif mit_diff < 0:
                advice.append(f"피해 감소량이 감소했습니다. 방어 쿨다운(블록, 회피, 피해감소 버프 등)을 더 자주 사용하세요.")

        # Miss % 분석
        if 'avg_miss_percent' in summary:
            miss_diff = summary['avg_miss_percent']['diff']
            miss_after = summary['avg_miss_percent']['after']
            if miss_diff > 2:
                advice.append(f"회피율이 {miss_diff:.1f}% 향상되었습니다. 회피/무기막기 스탯이나 스킬 활용이 개선되었네요!")
            elif miss_after < 10:
                advice.append(f"현재 회피율이 {miss_after:.1f}%로 낮습니다. 회피/무기막기 관련 스킬과 장비를 점검해보세요.")

        # 피해 소스 분석
        damage_sources = result.get('damage_sources', [])
        if damage_sources:
            increased_sources = [s for s in damage_sources if s['dtps']['diff'] > 100]
            if increased_sources:
                source_names = [s['name'] for s in increased_sources[:3]]
                advice.append(f"{', '.join(source_names)}로부터 받은 피해가 크게 증가했습니다. 이 공격 패턴에 맞는 방어 스킬을 사용하거나 위치를 조정하세요.")

        result['advice'] = advice

    def compare_healer(self) -> Dict:
        """힐러 역할의 두 CSV를 비교합니다"""
        result = {
            'role': 'HEALER',
            'summary': {},
            'heals': [],
            'improvements': [],
            'advice': []  # 서술형 조언
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

        # 서술형 조언 생성
        self._generate_healer_advice(result)

        return result

    def _generate_healer_advice(self, result: Dict):
        """힐러에 대한 서술형 조언을 생성합니다"""
        advice = []
        summary = result.get('summary', {})

        # 총 HPS 차이에 대한 조언
        if 'total_hps' in summary:
            hps_diff_percent = summary['total_hps']['diff_percent']
            hps_diff = summary['total_hps']['diff']

            if hps_diff_percent > 10:
                advice.append(f"목표 캐릭터 대비 {hps_diff_percent:.1f}% 더 높은 HPS를 기록했습니다! 훌륭한 힐링 성능입니다. 다만 오버힐 수치를 확인하여 불필요한 힐이 없는지 체크하세요.")
            elif hps_diff_percent > 0:
                advice.append(f"목표 캐릭터보다 {hps_diff_percent:.1f}% 향상된 힐링량입니다. 좋은 개선입니다!")
            elif hps_diff_percent > -10:
                advice.append(f"목표 캐릭터보다 {abs(hps_diff_percent):.1f}% 낮은 힐링량입니다. 힐 스킬 사용 빈도와 타이밍을 개선해보세요.")
            else:
                advice.append(f"목표 캐릭터 대비 {abs(hps_diff_percent):.1f}% 낮은 힐링량입니다. 마나 관리와 힐 우선순위를 재점검하세요.")

        # Overheal % 분석
        if 'avg_overheal_percent' in summary:
            overheal_diff = summary['avg_overheal_percent']['diff']
            overheal_after = summary['avg_overheal_percent']['after']

            if overheal_after > 40:
                advice.append(f"오버힐이 {overheal_after:.1f}%로 높습니다. 체력이 이미 충분한 대상을 힐하고 있을 수 있습니다. 힐 타겟 우선순위를 조정하여 마나 효율을 높이세요.")
            elif overheal_diff < -5:
                advice.append(f"오버힐이 {abs(overheal_diff):.1f}% 감소했습니다. 효율적인 힐링으로 개선되었네요!")
            elif overheal_diff > 5:
                advice.append(f"오버힐이 {overheal_diff:.1f}% 증가했습니다. 불필요한 힐을 줄이고 마나 효율을 개선하세요.")

        # 힐 스킬 사용 패턴 분석
        heals = result.get('heals', [])
        if heals:
            # HPS가 크게 감소한 스킬
            decreased_hps = [h for h in heals if h['hps']['diff'] < -100]
            if decreased_hps:
                skill_names = [h['name'] for h in decreased_hps[:3]]
                advice.append(f"{', '.join(skill_names)} 스킬의 사용이 감소했습니다. 이 스킬들을 로테이션에 더 자주 포함시켜보세요.")

            # Crit 확률이 개선된 스킬
            improved_crit = [h for h in heals if h['crit_percent']['diff'] > 5]
            if improved_crit:
                skill_names = [h['name'] for h in improved_crit[:2]]
                advice.append(f"{', '.join(skill_names)} 스킬의 치명타율이 향상되었습니다. 좋은 장비 개선입니다!")

            # Casts가 많이 증가한 스킬
            increased_casts = [h for h in heals if h['casts']['diff'] > 10]
            if increased_casts:
                skill_names = [h['name'] for h in increased_casts[:2]]
                # 오버힐이 높으면 경고
                if overheal_after > 35:
                    advice.append(f"{', '.join(skill_names)} 스킬 사용이 증가했지만 오버힐이 높습니다. 힐 타이밍을 조정하세요.")

        result['advice'] = advice

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
