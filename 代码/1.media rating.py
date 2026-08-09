import pandas as pd
import re

class MediaCredibilityEvaluator:
    def __init__(self, white_list_path):
        self.df = pd.read_excel(white_list_path)
        # 清洗列名（跳过第一列自动索引）
        self.df.columns = ['_idx', '服务名称', '服务地址', '许可证编号']
        self.df = self.df.drop(columns=['_idx'], errors='ignore')
        for col in ['服务名称', '服务地址', '许可证编号']:
            self.df[col] = self.df[col].astype(str).str.strip()

        # 提取主域名
        self.df['主域名'] = self.df['服务地址'].apply(self._extract_main_domain)
        # 判断是否为政务平台（.gov.cn 或 许可证含“政务平台”）
        self.df['是否政务'] = self.df.apply(
            lambda r: r['服务地址'].endswith('.gov.cn') or '政务平台' in r['许可证编号'], axis=1
        )

        # 预计算冲突信息
        self._compute_conflicts()

    @staticmethod
    def _extract_main_domain(url_str):
        """提取主域名（去掉www和公共后缀后的核心部分）"""
        first_url = url_str.split('；')[0].split(';')[0].strip()
        first_url = re.sub(r'^https?://', '', first_url)
        first_url = re.sub(r'^www\d*\.', '', first_url)
        suffixes = ['com.cn','org.cn','net.cn','gov.cn','edu.cn','ac.cn',
                    'com','cn','org','net','gov','edu','tv','info','cc']
        suffixes.sort(key=len, reverse=True)
        for s in suffixes:
            if first_url.endswith('.' + s):
                first_url = first_url[: -len(s)-1]
                break
        parts = first_url.split('.')
        return parts[-1].lower() if parts else first_url.lower()

    def _compute_conflicts(self):
        """检测全表冲突，标记每条记录是否涉及信息矛盾"""
        # 同一服务名称对应多个不同许可证
        name_lic_counts = self.df.groupby('服务名称')['许可证编号'].nunique()
        multi_lic_names = name_lic_counts[name_lic_counts > 1].index
        self.df['同服务多许可'] = self.df['服务名称'].isin(multi_lic_names)

        # 同一主域名下存在多个不同许可证的服务
        domain_lic = self.df.groupby('主域名')['许可证编号'].apply(set)
        multi_lic_domains = domain_lic[domain_lic.apply(len) > 1].index
        self.df['同域名多许可'] = self.df['主域名'].isin(multi_lic_domains)

        # 重复记录但信息不一致
        dup_mask = self.df.duplicated(subset=['服务名称', '服务地址', '许可证编号'], keep=False)
        # 如果一条记录是重复的，但某些重复组内许可证有差异，则视为矛盾重复
        self.df['矛盾重复'] = False
        for _, group in self.df[dup_mask].groupby(['服务名称', '服务地址']):
            if group['许可证编号'].nunique() > 1:
                self.df.loc[group.index, '矛盾重复'] = True

    # ---------- 评分函数 ----------
    def _score_A1(self, row):
        lic = row['许可证编号']
        if lic in ['无', 'nan', 'None', '']:
            return 0
        if re.match(r'^\d{11}', lic):  # 典型国家级许可证 10120xxxxx
            return 30
        if '政务平台' in lic or row['是否政务']:
            return 25
        if '地方许可' in lic:
            return 20
        return 0

    def _score_B1(self, row):
        """名称-域名关联评分（使用增强映射表，不依赖pypinyin）"""
        name = row['服务名称']
        domain = row['主域名']
        # 常用媒体关键词映射
        known_map = {
            '人民': 'people', '新华': 'xinhua', '央视': 'cctv', '央广': 'cnr',
            '光明': 'gmw', '中国军': '81', '中国青年': 'youth', '中国日报': 'chinadaily',
            '环球': 'huanqiu', '澎湃': 'thepaper', '界面': 'jiemian', '中国网': 'china',
            '中国经济': 'ce', '中国西藏': 'tibet', '中国台湾': 'taiwan', '中工': 'workercn',
            '中国妇女': 'cnwomen', '中国教育': 'jyb', '中国文明': 'wenming',
        }
        for key, val in known_map.items():
            if key in name and val in domain:
                return 15
            if key in name and domain in val:
                return 12

        # 直接包含
        name_lower = name.lower()
        if domain in name_lower or name_lower in domain:
            return 15
        # 英文缩写匹配（如 CCTV → cctv）
        eng_parts = re.findall(r'[a-zA-Z0-9]+', name)
        for ep in eng_parts:
            if ep.lower() == domain or ep.lower() in domain:
                return 15
            if domain in ep.lower():
                return 12
        # 通用关键词弱关联
        common = ['news', 'gov', 'tv', 'radio', 'daily', 'china', 'cn']
        if any(kw in domain and kw in name_lower for kw in common):
            return 8
        return 5

    def _score_B2(self, row):
        """信息唯一性：无冲突则15分，否则0分"""
        if row['同服务多许可'] or row['同域名多许可']:
            return 0
        return 15

    def _score_C1(self, row):
        """地址书写规范"""
        addr = row['服务地址']
        if addr in ['', 'nan', 'None']:
            return 4
        # 多个分号分隔的网站视为有多个域名，但仍属于规范格式
        if '；' in addr or ';' in addr:
            return 8
        return 10

    def _score_C2(self, row):
        """记录冲突：矛盾重复为0，否则10"""
        return 0 if row['矛盾重复'] else 10

    def _score_D1(self, row):
        """政务与公共属性加分"""
        if row['是否政务']:
            return 20
        if re.match(r'^\d{11}', row['许可证编号']):
            return 10
        if '地方许可' in row['许可证编号']:
            return 5
        return 0

    def evaluate(self):
        df = self.df.copy()
        df['A1许可级别'] = df.apply(self._score_A1, axis=1)
        df['B1名称关联'] = df.apply(self._score_B1, axis=1)
        df['B2信息唯一性'] = df.apply(self._score_B2, axis=1)
        df['C1地址规范'] = df.apply(self._score_C1, axis=1)
        df['C2记录一致性'] = df.apply(self._score_C2, axis=1)
        df['D1政务属性'] = df.apply(self._score_D1, axis=1)

        score_cols = ['A1许可级别', 'B1名称关联', 'B2信息唯一性',
                      'C1地址规范', 'C2记录一致性', 'D1政务属性']
        df['总分'] = df[score_cols].sum(axis=1)

        def level(score):
            if score >= 90: return '完全可信'
            if score >= 75: return '高度可信'
            if score >= 60: return '基本可信'
            return '存疑'

        df['信任等级'] = df['总分'].apply(level)
        df.loc[df['许可证编号'].isin(['无', 'nan', 'None', '']), '信任等级'] = '待分类（无许可证信息）'

        self.result_df = df
        return df

    def save_report(self, output_path):
        if self.result_df is None:
            self.evaluate()
        out_cols = ['服务名称', '服务地址', '许可证编号', '主域名',
                    'A1许可级别', 'B1名称关联', 'B2信息唯一性',
                    'C1地址规范', 'C2记录一致性', 'D1政务属性', '总分', '信任等级']
        self.result_df[out_cols].to_excel(output_path, index=False)
        print(f"报告已保存至: {output_path}")


if __name__ == "__main__":
    # 使用绝对路径或确保文件在当前目录
    evaluator = MediaCredibilityEvaluator("WHITE.xlsx")
    result = evaluator.evaluate()

    print("信任等级分布：")
    print(result['信任等级'].value_counts())
    print("\n分数统计：")
    print(result['总分'].describe())

    # 查看部分典型评分
    print("\n示例——人民网：")
    print(result[result['服务名称'] == '人民网'][['服务名称', 'A1许可级别', 'B1名称关联', 'B2信息唯一性', 'D1政务属性', '总分', '信任等级']].to_string(index=False))

    # 检查冲突条目
    conflicts = result[(result['B2信息唯一性'] == 0) | (result['C2记录一致性'] == 0)]
    print(f"\n涉及信息冲突的条目数: {len(conflicts)}")
    if not conflicts.empty:
        print(conflicts[['服务名称', '服务地址', '许可证编号', '总分']].head(10).to_string(index=False))

    evaluator.save_report("媒体公信力评估报告.xlsx")