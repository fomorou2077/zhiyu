import pandas as pd
import re
import jieba
import jieba.analyse

WHITE_FILE = "WHITE.xlsx"
ARTICLE_FILE = "媒体文章数据.csv"
RUMOR_FILE = "辟谣平台_月度榜单_带主题标签.csv"
OUTPUT_FILE = "综合媒体评级报告.xlsx"
PENALTY_PER_MATCH = 20
EXEMPT_KEYWORDS = ["辟谣", "假消息", "不实信息", "澄清", "真相", "官方回应", "谣言"]

class StaticScorer:
    def __init__(self, white_df):
        self.df = white_df.copy()
        # 标准化列名（假设已处理）
        self._prepare_columns()
        self._extract_domain()
        self._detect_conflicts()
        self._compute_scores()

    def _prepare_columns(self):
        required = ['服务名称', '服务地址', '许可证编号']
        for col in required:
            if col not in self.df.columns:
                raise ValueError(f"白名单缺少必要列：{col}")
        self.df['服务名称'] = self.df['服务名称'].astype(str).str.strip()
        self.df['服务地址'] = self.df['服务地址'].astype(str).str.strip()
        self.df['许可证编号'] = self.df['许可证编号'].astype(str).str.strip()

    def _extract_main_domain(self, url_str):
        if pd.isna(url_str) or url_str in ['', 'nan', 'None']:
            return ''
        first_url = url_str.split('；')[0].split(';')[0].strip()
        first_url = re.sub(r'^https?://', '', first_url)
        first_url = re.sub(r'^www\d*\.', '', first_url)
        suffixes = ['com.cn', 'org.cn', 'net.cn', 'gov.cn', 'edu.cn', 'ac.cn',
                    'com', 'cn', 'org', 'net', 'gov', 'edu', 'tv', 'info', 'cc']
        suffixes.sort(key=len, reverse=True)
        for s in suffixes:
            if first_url.endswith('.' + s):
                first_url = first_url[:-len(s) - 1]
                break
        parts = first_url.split('.')
        return parts[-1].lower() if parts else first_url.lower()

    def _extract_domain(self):
        self.df['主域名'] = self.df['服务地址'].apply(self._extract_main_domain)
        self.df['是否政务'] = self.df.apply(
            lambda r: r['服务地址'].endswith('.gov.cn') or '政务平台' in r['许可证编号'],
            axis=1
        )

    def _detect_conflicts(self):
        name_lic_counts = self.df.groupby('服务名称')['许可证编号'].nunique()
        multi_lic_names = name_lic_counts[name_lic_counts > 1].index
        self.df['同服务多许可'] = self.df['服务名称'].isin(multi_lic_names)
        domain_lic = self.df.groupby('主域名')['许可证编号'].apply(set)
        multi_lic_domains = domain_lic[domain_lic.apply(len) > 1].index
        self.df['同域名多许可'] = self.df['主域名'].isin(multi_lic_domains)

        dup_mask = self.df.duplicated(subset=['服务名称', '服务地址', '许可证编号'], keep=False)
        self.df['矛盾重复'] = False
        for _, group in self.df[dup_mask].groupby(['服务名称', '服务地址']):
            if group['许可证编号'].nunique() > 1:
                self.df.loc[group.index, '矛盾重复'] = True

    def _score_A1(self, row):
        lic = row['许可证编号']
        if lic in ['无', 'nan', 'None', '']:
            return 0
        if re.match(r'^\d{11}', lic):  # 国家级许可证
            return 30
        if '政务平台' in lic or row['是否政务']:
            return 25
        if '地方许可' in lic:
            return 20
        return 0

    def _score_B1(self, row):
        name = row['服务名称']
        domain = row['主域名']
        if not domain:
            return 0
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
        name_lower = name.lower()
        if domain in name_lower or name_lower in domain:
            return 15
        eng_parts = re.findall(r'[a-zA-Z0-9]+', name)
        for ep in eng_parts:
            if ep.lower() == domain or ep.lower() in domain:
                return 15
            if domain in ep.lower():
                return 12
        common = ['news', 'gov', 'tv', 'radio', 'daily', 'china', 'cn']
        if any(kw in domain and kw in name_lower for kw in common):
            return 8
        return 5

    def _score_B2(self, row):
        if row['同服务多许可'] or row['同域名多许可']:
            return 0
        return 15

    def _score_C1(self, row):
        addr = row['服务地址']
        if addr in ['', 'nan', 'None']:
            return 4
        if '；' in addr or ';' in addr:
            return 8
        return 10

    def _score_C2(self, row):
        return 0 if row['矛盾重复'] else 10

    def _score_D1(self, row):
        if row['是否政务']:
            return 20
        if re.match(r'^\d{11}', row['许可证编号']):
            return 10
        if '地方许可' in row['许可证编号']:
            return 5
        return 0

    def _compute_scores(self):
        self.df['A1许可级别'] = self.df.apply(self._score_A1, axis=1)
        self.df['B1名称关联'] = self.df.apply(self._score_B1, axis=1)
        self.df['B2信息唯一性'] = self.df.apply(self._score_B2, axis=1)
        self.df['C1地址规范'] = self.df.apply(self._score_C1, axis=1)
        self.df['C2记录一致性'] = self.df.apply(self._score_C2, axis=1)
        self.df['D1政务属性'] = self.df.apply(self._score_D1, axis=1)
        score_cols = ['A1许可级别', 'B1名称关联', 'B2信息唯一性',
                      'C1地址规范', 'C2记录一致性', 'D1政务属性']
        self.df['静态总分'] = self.df[score_cols].sum(axis=1)

    def get_scores(self):
        # 关键修改：增加了 '服务地址' 和 '许可证编号' 列
        return self.df[['服务名称', '服务地址', '许可证编号', '主域名', '是否政务',
                        'A1许可级别', 'B1名称关联', 'B2信息唯一性',
                        'C1地址规范', 'C2记录一致性', 'D1政务属性', '静态总分']]

def extract_keywords(rumor_text, top_k=5):
    text_clean = re.sub(r'[，,。！？；：""''（）《》【】]', ' ', rumor_text)
    keywords = jieba.analyse.extract_tags(text_clean, topK=top_k, withWeight=False)
    return [kw for kw in keywords if len(kw) >= 2]


def is_hit(title, content, keywords):
    combined = (title + " " + content).lower()
    for exempt in EXEMPT_KEYWORDS:
        if exempt in combined:
            return False, []
    hit_kws = [kw for kw in keywords if kw.lower() in combined]
    return len(hit_kws) > 0, hit_kws


def compute_dynamic_penalty(article_df, rumor_df):
    rumor_df = rumor_df.copy()
    rumor_df['keywords'] = rumor_df['black_name'].apply(lambda x: extract_keywords(x))
    hit_records = []
    for _, art in article_df.iterrows():
        media = art['media_name']
        title = art['title']
        content = art['content'] if pd.notna(art['content']) else ""
        total_hits = 0
        for _, rum in rumor_df.iterrows():
            hit, _ = is_hit(title, content, rum['keywords'])
            if hit:
                total_hits += 1
        hit_records.append({'media_name': media, 'total_hits': total_hits})
    hit_df = pd.DataFrame(hit_records)
    penalty = hit_df.groupby('media_name')['total_hits'].sum().reset_index()
    penalty.columns = ['服务名称', '命中辟谣次数']
    penalty['动态扣分'] = penalty['命中辟谣次数'] * PENALTY_PER_MATCH
    return penalty

def main():
    print("综合媒体公信力评价")
    white_df = pd.read_excel(WHITE_FILE, sheet_name=0)
    if white_df.columns[0] == 1:
        white_df.columns = ['_idx', '服务名称', '服务地址', '许可证编号']
        white_df = white_df.drop(columns=['_idx'])
    else:
        pass
    if '服务名称' not in white_df.columns:
        print("错误 名单缺少'服务名称'列")
        return

    print(f"名单媒体数量: {len(white_df)}")

    scorer = StaticScorer(white_df)
    static_scores = scorer.get_scores()
    print("静态评分完成")

    try:
        article_df = pd.read_csv(ARTICLE_FILE, encoding='utf-8-sig')
        if 'media_name' not in article_df.columns:
            print("错误 文章文件缺少'media_name'列")
            return
        article_df['media_name'] = article_df['media_name'].astype(str).str.strip()
        rumor_df = pd.read_csv(RUMOR_FILE, encoding='utf-8-sig')
        if 'black_name' not in rumor_df.columns:
            print("错误 辟谣榜单缺少'black_name'列")
            return
        penalty_df = compute_dynamic_penalty(article_df, rumor_df)
        print(f"动态评分完成，涉及 {len(penalty_df)} 家媒体有文章记录")
    except FileNotFoundError:
        print("未找到文章文件或辟谣文件，将仅使用静态评分")
        penalty_df = pd.DataFrame(columns=['服务名称', '命中辟谣次数', '动态扣分'])

    final = static_scores.merge(penalty_df, on='服务名称', how='left')
    final['命中辟谣次数'] = final['命中辟谣次数'].fillna(0).astype(int)
    final['动态扣分'] = final['动态扣分'].fillna(0)
    final['最终总分'] = final['静态总分'] - final['动态扣分']
    final['最终总分'] = final['最终总分'].clip(lower=0)

    def level(score):
        if score >= 90:
            return '完全可信'
        if score >= 75:
            return '高度可信'
        if score >= 60:
            return '基本可信'
        return '存疑（建议复核）'

    final['综合信任等级'] = final['最终总分'].apply(level)
    no_lic = final['A1许可级别'] == 0
    no_article = final['命中辟谣次数'] == 0
    final.loc[no_lic & (final['动态扣分'] == 0), '综合信任等级'] = '待核实（无许可证且无内容）'
    out_cols = [
        '服务名称', '服务地址', '许可证编号', '主域名',
        '是否政务', 'A1许可级别', 'B1名称关联', 'B2信息唯一性',
        'C1地址规范', 'C2记录一致性', 'D1政务属性', '静态总分',
        '命中辟谣次数', '动态扣分', '最终总分', '综合信任等级'
    ]
    for col in out_cols:
        if col not in final.columns:
            final[col] = ''
    final[out_cols].to_excel(OUTPUT_FILE, index=False)

    print(f"\n综合评级完成！报告已保存至: {OUTPUT_FILE}")
    print("\n评级分布:")
    print(final['综合信任等级'].value_counts())
    print("\n得分统计:")
    print(final['最终总分'].describe())

if __name__ == "__main__":
    main()