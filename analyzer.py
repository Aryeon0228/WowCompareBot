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

    def compare_dps(self) -> Dict:
        """DPS 역할의 두 CSV를 비교합니다"""
        result = {
            'role': 'DPS',
            'summary': {},
            'skills': [],
            'missing_skills': [],
            'improvements': [],
            'top_contributors': []
        }

        # 총 DPS 비교
        total_dps1 = self.df1['DPS'].sum() if 'DPS' in self.df1.columns else 0
        total_dps2 = self.df2['DPS'].sum() if 'DPS' in self.df2.columns else 0
        dps_diff = total_dps2 - total_dps1
        dps_diff_percent = (dps_diff / total_dps1 * 100) if total_dps1 > 0 else 0

        result['summary']['total_dps'] = {
            'before': total_dps1,
            'after': total_dps2,
            'diff': dps_diff,
            'diff_percent': dps_diff_percent
        }

        # 총 데미지량 비교 (Amount)
        if 'Amount' in self.df1.columns:
            total_amount1 = sum(self.parse_amount(str(amt))[0] for amt in self.df1['Amount'])
            total_amount2 = sum(self.parse_amount(str(amt))[0] for amt in self.df2['Amount'])
            amount_diff = total_amount2 - total_amount1
            amount_diff_percent = (amount_diff / total_amount1 * 100) if total_amount1 > 0 else 0

            result['summary']['total_damage'] = {
                'before': total_amount1,
                'after': total_amount2,
                'diff': amount_diff,
                'diff_percent': amount_diff_percent
            }

        # 총 시전 수 비교
        total_casts1 = self.df1['Casts'].sum() if 'Casts' in self.df1.columns else 0
        total_casts2 = self.df2['Casts'].sum() if 'Casts' in self.df2.columns else 0

        result['summary']['total_casts'] = {
            'before': total_casts1,
            'after': total_casts2,
            'diff': total_casts2 - total_casts1
        }

        # 평균 치명타율
        if 'Crit %' in self.df1.columns:
            avg_crit1 = self.df1['Crit %'].apply(self.parse_percentage).mean()
            avg_crit2 = self.df2['Crit %'].apply(self.parse_percentage).mean()

            result['summary']['avg_crit'] = {
                'before': avg_crit1,
                'after': avg_crit2,
                'diff': avg_crit2 - avg_crit1
            }

        # 스킬별 비교
        skills1 = set(self.df1['Name'].tolist())
        skills2 = set(self.df2['Name'].tolist())

        # 공통 스킬 비교
        common_skills = skills1.intersection(skills2)
        for skill in common_skills:
            skill_data1 = self.df1[self.df1['Name'] == skill].iloc[0]
            skill_data2 = self.df2[self.df2['Name'] == skill].iloc[0]

            # Amount 파싱 (총량, 기여도%, M단위)
            amount1, percent1, m1 = self.parse_amount(str(skill_data1.get('Amount', '0')))
            amount2, percent2, m2 = self.parse_amount(str(skill_data2.get('Amount', '0')))

            # Casts 비교
            casts1 = skill_data1.get('Casts', 0)
            casts2 = skill_data2.get('Casts', 0)

            # Crit % 비교
            crit1 = self.parse_percentage(skill_data1.get('Crit %', '0%'))
            crit2 = self.parse_percentage(skill_data2.get('Crit %', '0%'))

            # Uptime % 비교 (DoT 스킬용)
            uptime1 = self.parse_percentage(skill_data1.get('Uptime %', '0%'))
            uptime2 = self.parse_percentage(skill_data2.get('Uptime %', '0%'))

            # Avg Hit 비교
            avg_hit1 = skill_data1.get('Avg Hit', 0)
            avg_hit2 = skill_data2.get('Avg Hit', 0)

            # Hits 비교
            hits1 = skill_data1.get('Hits', 0)
            hits2 = skill_data2.get('Hits', 0)

            # 시전 효율성 (데미지 per Cast)
            dpc1 = amount1 / casts1 if casts1 > 0 else 0
            dpc2 = amount2 / casts2 if casts2 > 0 else 0

            # 적중률
            hit_rate1 = (hits1 / casts1 * 100) if casts1 > 0 else 0
            hit_rate2 = (hits2 / casts2 * 100) if casts2 > 0 else 0

            skill_info = {
                'name': skill,
                'amount': {'before': amount1, 'after': amount2, 'diff': amount2 - amount1},
                'contribution_percent': {'before': percent1, 'after': percent2, 'diff': percent2 - percent1},
                'casts': {'before': casts1, 'after': casts2, 'diff': casts2 - casts1},
                'crit_percent': {'before': crit1, 'after': crit2, 'diff': crit2 - crit1},
                'uptime_percent': {'before': uptime1, 'after': uptime2, 'diff': uptime2 - uptime1},
                'avg_hit': {'before': avg_hit1, 'after': avg_hit2, 'diff': avg_hit2 - avg_hit1},
                'damage_per_cast': {'before': dpc1, 'after': dpc2, 'diff': dpc2 - dpc1},
                'hit_rate': {'before': hit_rate1, 'after': hit_rate2, 'diff': hit_rate2 - hit_rate1}
            }

            result['skills'].append(skill_info)

        # 상위 기여도 스킬 (After 기준)
        top_skills = sorted(result['skills'], key=lambda x: x['contribution_percent']['after'], reverse=True)[:5]
        result['top_contributors'] = [{'name': s['name'], 'percent': s['contribution_percent']['after']} for s in top_skills]

        # 누락된 스킬 확인
        missing_in_new = skills1 - skills2
        new_skills = skills2 - skills1

        if missing_in_new:
            result['missing_skills'] = list(missing_in_new)
        if new_skills:
            result['improvements'].append(f"새로운 스킬 사용: {', '.join(new_skills)}")

        # 개선 제안 생성
        for skill in result['skills']:
            # Uptime이 낮은 DoT 스킬
            if skill['uptime_percent']['before'] > 0 or skill['uptime_percent']['after'] > 0:
                if skill['uptime_percent']['after'] < 80 and skill['uptime_percent']['after'] > 0:
                    result['improvements'].append(f"{skill['name']} DoT 유지율 향상 필요 ({skill['uptime_percent']['after']:.1f}%)")

            # Casts가 크게 감소한 주요 스킬
            if skill['contribution_percent']['before'] > 10 and skill['casts']['diff'] < -10:
                result['improvements'].append(f"{skill['name']} 시전 횟수 감소 ({skill['casts']['diff']:+d})")

            # 평균 피해가 크게 증가한 스킬
            if skill['avg_hit']['diff'] > 0 and skill['avg_hit']['before'] > 0:
                increase_pct = (skill['avg_hit']['diff'] / skill['avg_hit']['before']) * 100
                if increase_pct > 20:
                    result['improvements'].append(f"{skill['name']} 평균 피해 크게 증가 (+{increase_pct:.1f}%)")

        return result

    def compare_tank(self) -> Dict:
        """탱커 역할의 두 CSV를 비교합니다"""
        result = {
            'role': 'TANK',
            'summary': {},
            'damage_sources': [],
            'improvements': [],
            'mitigation_skills': []
        }

        # 총 받은 피해(DTPS) 비교
        total_dtps1 = self.df1['DTPS'].sum() if 'DTPS' in self.df1.columns else 0
        total_dtps2 = self.df2['DTPS'].sum() if 'DTPS' in self.df2.columns else 0
        dtps_diff = total_dtps2 - total_dtps1
        dtps_diff_percent = (dtps_diff / total_dtps1 * 100) if total_dtps1 > 0 else 0

        result['summary']['total_dtps'] = {
            'before': total_dtps1,
            'after': total_dtps2,
            'diff': dtps_diff,
            'diff_percent': dtps_diff_percent
        }

        # 총 받은 피해량 비교 (Amount)
        if 'Amount' in self.df1.columns:
            total_damage1 = sum(self.parse_amount(str(amt))[0] for amt in self.df1['Amount'])
            total_damage2 = sum(self.parse_amount(str(amt))[0] for amt in self.df2['Amount'])
            damage_diff = total_damage2 - total_damage1
            damage_diff_percent = (damage_diff / total_damage1 * 100) if total_damage1 > 0 else 0

            result['summary']['total_damage_taken'] = {
                'before': total_damage1,
                'after': total_damage2,
                'diff': damage_diff,
                'diff_percent': damage_diff_percent
            }

        # Mitigated 비교
        if 'Mitigated' in self.df1.columns:
            total_mitigated1 = self.df1['Mitigated'].sum()
            total_mitigated2 = self.df2['Mitigated'].sum()
            mit_diff = total_mitigated2 - total_mitigated1
            mit_diff_percent = (mit_diff / total_mitigated1 * 100) if total_mitigated1 > 0 else 0

            result['summary']['mitigated'] = {
                'before': total_mitigated1,
                'after': total_mitigated2,
                'diff': mit_diff,
                'diff_percent': mit_diff_percent
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

        # 평균 Uptime (방어 버프 유지율)
        if 'Uptime %' in self.df1.columns:
            avg_uptime1 = self.df1['Uptime %'].apply(self.parse_percentage).mean()
            avg_uptime2 = self.df2['Uptime %'].apply(self.parse_percentage).mean()
            result['summary']['avg_uptime'] = {
                'before': avg_uptime1,
                'after': avg_uptime2,
                'diff': avg_uptime2 - avg_uptime1
            }

        # 주요 피해 소스별 비교
        sources1 = set(self.df1['Name'].tolist())
        sources2 = set(self.df2['Name'].tolist())

        common_sources = sources1.intersection(sources2)
        for source in common_sources:
            source_data1 = self.df1[self.df1['Name'] == source].iloc[0]
            source_data2 = self.df2[self.df2['Name'] == source].iloc[0]

            # Amount 파싱
            amount1, percent1, m1 = self.parse_amount(str(source_data1.get('Amount', '0')))
            amount2, percent2, m2 = self.parse_amount(str(source_data2.get('Amount', '0')))

            dtps1 = source_data1.get('DTPS', 0)
            dtps2 = source_data2.get('DTPS', 0)

            # Avg Hit
            avg_hit1 = source_data1.get('Avg Hit', 0)
            avg_hit2 = source_data2.get('Avg Hit', 0)

            # Uptime % (방어 스킬 유지율)
            uptime1 = self.parse_percentage(source_data1.get('Uptime %', '0%'))
            uptime2 = self.parse_percentage(source_data2.get('Uptime %', '0%'))

            # Miss %
            miss1 = self.parse_percentage(source_data1.get('Miss %', '0%'))
            miss2 = self.parse_percentage(source_data2.get('Miss %', '0%'))

            source_info = {
                'name': source,
                'amount': {'before': amount1, 'after': amount2, 'diff': amount2 - amount1},
                'contribution_percent': {'before': percent1, 'after': percent2, 'diff': percent2 - percent1},
                'dtps': {'before': dtps1, 'after': dtps2, 'diff': dtps2 - dtps1},
                'avg_hit': {'before': avg_hit1, 'after': avg_hit2, 'diff': avg_hit2 - avg_hit1},
                'uptime_percent': {'before': uptime1, 'after': uptime2, 'diff': uptime2 - uptime1},
                'miss_percent': {'before': miss1, 'after': miss2, 'diff': miss2 - miss1}
            }

            result['damage_sources'].append(source_info)

            # 방어 스킬 (Uptime이 있는 것들)
            if uptime1 > 0 or uptime2 > 0:
                result['mitigation_skills'].append(source_info)

        # 개선 제안 생성
        if dtps_diff < 0:
            result['improvements'].append(f"받은 피해(DTPS) 감소: {dtps_diff:.1f} ({dtps_diff_percent:+.1f}%)")

        if 'mitigated' in result['summary']:
            mit_pct = result['summary']['mitigated']['diff_percent']
            if mit_pct > 10:
                result['improvements'].append(f"피해 감소량 크게 증가: +{mit_pct:.1f}%")

        if 'avg_miss_percent' in result['summary']:
            miss_diff = result['summary']['avg_miss_percent']['diff']
            if miss_diff > 5:
                result['improvements'].append(f"회피율 증가: +{miss_diff:.1f}%")

        # Uptime 낮은 방어 스킬 체크
        for skill in result['mitigation_skills']:
            if skill['uptime_percent']['after'] < 50 and skill['uptime_percent']['after'] > 0:
                result['improvements'].append(f"{skill['name']} 유지율 향상 필요 ({skill['uptime_percent']['after']:.1f}%)")

        return result

    def compare_healer(self) -> Dict:
        """힐러 역할의 두 CSV를 비교합니다"""
        result = {
            'role': 'HEALER',
            'summary': {},
            'heals': [],
            'improvements': [],
            'top_contributors': []
        }

        # 총 HPS 비교
        total_hps1 = self.df1['HPS'].sum() if 'HPS' in self.df1.columns else 0
        total_hps2 = self.df2['HPS'].sum() if 'HPS' in self.df2.columns else 0
        hps_diff = total_hps2 - total_hps1
        hps_diff_percent = (hps_diff / total_hps1 * 100) if total_hps1 > 0 else 0

        result['summary']['total_hps'] = {
            'before': total_hps1,
            'after': total_hps2,
            'diff': hps_diff,
            'diff_percent': hps_diff_percent
        }

        # 총 힐량 비교 (Amount)
        if 'Amount' in self.df1.columns:
            total_heal1 = sum(self.parse_amount(str(amt))[0] for amt in self.df1['Amount'])
            total_heal2 = sum(self.parse_amount(str(amt))[0] for amt in self.df2['Amount'])
            heal_diff = total_heal2 - total_heal1
            heal_diff_percent = (heal_diff / total_heal1 * 100) if total_heal1 > 0 else 0

            result['summary']['total_healing'] = {
                'before': total_heal1,
                'after': total_heal2,
                'diff': heal_diff,
                'diff_percent': heal_diff_percent
            }

        # 총 시전 수 비교
        total_casts1 = self.df1['Casts'].sum() if 'Casts' in self.df1.columns else 0
        total_casts2 = self.df2['Casts'].sum() if 'Casts' in self.df2.columns else 0

        result['summary']['total_casts'] = {
            'before': total_casts1,
            'after': total_casts2,
            'diff': total_casts2 - total_casts1
        }

        # 평균 치명타율
        if 'Crit %' in self.df1.columns:
            avg_crit1 = self.df1['Crit %'].apply(self.parse_percentage).mean()
            avg_crit2 = self.df2['Crit %'].apply(self.parse_percentage).mean()

            result['summary']['avg_crit'] = {
                'before': avg_crit1,
                'after': avg_crit2,
                'diff': avg_crit2 - avg_crit1
            }

        # Overheal % 평균 비교
        if 'Overheal' in self.df1.columns:
            # Overheal은 퍼센트 형식일 수 있음
            avg_overheal1 = self.df1['Overheal'].apply(lambda x: self.parse_percentage(x) if isinstance(x, str) else x).mean()
            avg_overheal2 = self.df2['Overheal'].apply(lambda x: self.parse_percentage(x) if isinstance(x, str) else x).mean()
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

            # Amount 파싱 (총량, 기여도%, M단위)
            amount1, percent1, m1 = self.parse_amount(str(heal_data1.get('Amount', '0')))
            amount2, percent2, m2 = self.parse_amount(str(heal_data2.get('Amount', '0')))

            # Casts 비교
            casts1 = heal_data1.get('Casts', 0)
            casts2 = heal_data2.get('Casts', 0)

            # Crit % 비교
            crit1 = self.parse_percentage(heal_data1.get('Crit %', '0%'))
            crit2 = self.parse_percentage(heal_data2.get('Crit %', '0%'))

            # HPS 비교
            hps1 = heal_data1.get('HPS', 0)
            hps2 = heal_data2.get('HPS', 0)

            # Avg Hit 비교
            avg_hit1 = heal_data1.get('Avg Hit', 0)
            avg_hit2 = heal_data2.get('Avg Hit', 0)

            # Hits 비교
            hits1 = heal_data1.get('Hits', 0)
            hits2 = heal_data2.get('Hits', 0)

            # Uptime % (HoT 힐 유지율)
            uptime1 = self.parse_percentage(heal_data1.get('Uptime %', '0%'))
            uptime2 = self.parse_percentage(heal_data2.get('Uptime %', '0%'))

            # Overheal 비교
            overheal1 = self.parse_percentage(str(heal_data1.get('Overheal', '0%'))) if isinstance(heal_data1.get('Overheal', 0), str) else heal_data1.get('Overheal', 0)
            overheal2 = self.parse_percentage(str(heal_data2.get('Overheal', '0%'))) if isinstance(heal_data2.get('Overheal', 0), str) else heal_data2.get('Overheal', 0)

            # 시전 효율성 (힐량 per Cast)
            hpc1 = amount1 / casts1 if casts1 > 0 else 0
            hpc2 = amount2 / casts2 if casts2 > 0 else 0

            heal_info = {
                'name': heal,
                'amount': {'before': amount1, 'after': amount2, 'diff': amount2 - amount1},
                'contribution_percent': {'before': percent1, 'after': percent2, 'diff': percent2 - percent1},
                'casts': {'before': casts1, 'after': casts2, 'diff': casts2 - casts1},
                'crit_percent': {'before': crit1, 'after': crit2, 'diff': crit2 - crit1},
                'hps': {'before': hps1, 'after': hps2, 'diff': hps2 - hps1},
                'avg_hit': {'before': avg_hit1, 'after': avg_hit2, 'diff': avg_hit2 - avg_hit1},
                'uptime_percent': {'before': uptime1, 'after': uptime2, 'diff': uptime2 - uptime1},
                'overheal_percent': {'before': overheal1, 'after': overheal2, 'diff': overheal2 - overheal1},
                'heal_per_cast': {'before': hpc1, 'after': hpc2, 'diff': hpc2 - hpc1}
            }

            result['heals'].append(heal_info)

        # 상위 기여도 힐 스킬 (After 기준)
        top_heals = sorted(result['heals'], key=lambda x: x['contribution_percent']['after'], reverse=True)[:5]
        result['top_contributors'] = [{'name': h['name'], 'percent': h['contribution_percent']['after']} for h in top_heals]

        # 개선 제안 생성
        if hps_diff > 0:
            result['improvements'].append(f"HPS 증가: +{hps_diff:.1f} (+{hps_diff_percent:.1f}%)")

        if 'avg_overheal_percent' in result['summary']:
            overheal_diff = result['summary']['avg_overheal_percent']['diff']
            if overheal_diff < -5:
                result['improvements'].append(f"오버힐 감소: {overheal_diff:.1f}% (효율적인 힐링)")
            elif overheal_diff > 10:
                result['improvements'].append(f"오버힐 증가: +{overheal_diff:.1f}% (낭비 주의)")

        # HoT 유지율 체크
        for heal in result['heals']:
            if heal['uptime_percent']['before'] > 0 or heal['uptime_percent']['after'] > 0:
                if heal['uptime_percent']['after'] < 80 and heal['uptime_percent']['after'] > 0:
                    result['improvements'].append(f"{heal['name']} HoT 유지율 향상 필요 ({heal['uptime_percent']['after']:.1f}%)")

        # 평균 치명타율 개선
        if 'avg_crit' in result['summary']:
            crit_diff = result['summary']['avg_crit']['diff']
            if crit_diff > 5:
                result['improvements'].append(f"평균 치명타율 증가: +{crit_diff:.1f}%")

        # 효율성 개선 체크
        for heal in result['heals']:
            if heal['heal_per_cast']['before'] > 0:
                efficiency_change = (heal['heal_per_cast']['diff'] / heal['heal_per_cast']['before']) * 100
                if efficiency_change > 20 and heal['contribution_percent']['after'] > 5:
                    result['improvements'].append(f"{heal['name']} 시전 효율성 크게 증가 (+{efficiency_change:.1f}%)")

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
