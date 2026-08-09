import pandas as pd
import re
import jieba
import jieba.analyse

PENALTY_PER_HIT_ARTICLE = 20  # 每篇命中文章扣分
EXEMPT_KEYWORDS = ["辟谣", "假消息", "不实信息", "澄清", "真相", "官方回应", "谣言"]

STOP_WORDS = set(
    ['的', '了', '是', '在', '和', '有', '会', '能', '可', '对', '与', '及', '为', '将', '并', '但', '也', '就', '都',
     '而', '又', '或', '即', '还', '更', '到', '从', '于', '上', '下', '之', '其', '这', '那', '他', '她', '它', '我',
     '你', '们', '个', '些', '种', '等', '的', '把', '被', '给', '让', '使', '叫', '用', '以', '因', '由', '随', '向',
     '往', '后', '前', '左', '右', '内', '外', '里', '中', '间', '边', '处', '方', '法', '种', '样', '数', '多', '少',
     '大', '小', '高', '低', '长', '短', '新', '老', '好', '坏', '美', '丑', '真', '假', '实', '虚', '正', '反', '无',
     '非', '与', '既', '且', '但', '或', '并', '所', '此', '彼', '每', '各', '某', '诸', '凡', '惟', '唯', '乃', '矣',
     '乎', '焉', '哉', '也', '矣', '乎', '焉', '哉'])

HIGH_RISK_HIT_RATIO = 0.8  # 命中比例超过80%视为“疑似算法异常”
MEDIUM_RISK_HIT_RATIO = 0.1  # 10%~80%按命中文章数扣分
LOW_RISK_HIT_RATIO = 0.05  # 5%以下不扣分

def extract_keywords(rumor_text, top_k=5):
    text_clean = re.sub(r'[，,。！？；：""''（）《》【】\s]', ' ', rumor_text)
    raw_keywords = jieba.analyse.extract_tags(text_clean, topK=top_k, withWeight=False)
    keywords = []
    for kw in raw_keywords:
        if len(kw) >= 2 and kw not in STOP_WORDS and not kw.isdigit():
            keywords.append(kw)
    long_phrases = re.findall(r'[\u4e00-\u9fa5]{4,}', rumor_text)
    for phrase in long_phrases:
        if phrase not in keywords and len(phrase) >= 4:
            keywords.append(phrase)
    keywords = list(dict.fromkeys(keywords))[:7]
    return keywords

def is_hit(title, content, keywords, rumor_text):

    combined = (title + " " + content).lower()
    for exempt in EXEMPT_KEYWORDS:
        if exempt in combined:
            return False, []
    if not keywords:
        return False, []
    missing = [kw for kw in keywords if kw.lower() not in combined]
    if missing:
        return False, []
    if not any(len(kw) >= 3 for kw in keywords):
        return False, []
    return True, keywords

def compute_article_stats(media_name, article_df, rumor_df):
    media_articles = article_df[article_df['media_name'] == media_name]
    if media_articles.empty:
        return 0, 0, 0, 0
    total_arts = len(media_articles)
    hit_arts = 0
    total_hits = 0
    exempt_arts = 0

    for _, art in media_articles.iterrows():
        title = art['title']
        content = art['content'] if pd.notna(art['content']) else ""
        combined = (title + " " + content).lower()
        is_exempt = any(ex in combined for ex in EXEMPT_KEYWORDS)
        if is_exempt:
            exempt_arts += 1
            continue
        art_hits = 0
        for _, rum in rumor_df.iterrows():
            if is_hit(title, content, rum['keywords'], rum['black_name'])[0]:
                art_hits += 1
        if art_hits > 0:
            hit_arts += 1
            total_hits += art_hits

    return total_arts, hit_arts, total_hits, exempt_arts

def compute_revised_score(static_score, total_articles, hit_articles, exempt_articles):
    if total_articles == 0:
        return static_score, "没有采集到文章，维持静态分"

    hit_ratio = hit_articles / total_articles
    if hit_ratio > HIGH_RISK_HIT_RATIO and total_articles >= 3:
        revised = static_score
        reason = f"命中文章比例{hit_ratio:.1%}，疑似匹配规则过宽，建议人工复核，暂维持静态分（{static_score}）"
        return revised, reason

    if hit_ratio <= LOW_RISK_HIT_RATIO:
        penalty = 0
        reason = f"命中文章比例{hit_ratio:.1%}，极低风险，不予扣分"
    elif hit_ratio <= MEDIUM_RISK_HIT_RATIO:
        penalty = hit_articles * PENALTY_PER_HIT_ARTICLE
        reason = f"命中文章比例{hit_ratio:.1%}，按命中文章数扣{penalty}分"
    else:
        penalty = hit_articles * PENALTY_PER_HIT_ARTICLE
        reason = f"命中文章比例{hit_ratio:.1%}，按命中文章数扣{penalty}分"

    revised = static_score - penalty
    revised = max(revised, 0)

    if exempt_articles > 0:
        bonus = min(exempt_articles * 5, 20)
        revised = min(revised + bonus, 100)
        reason += f"；主动辟谣{exempt_articles}篇，加{bonus}分"

    return revised, reason

def main():
    print("=" * 60)
    print("媒体信用复核")

    try:
        df_report = pd.read_excel("综合媒体评级报告.xlsx", sheet_name=0)
    except Exception as e:
        print(f"无法读取综合媒体评级报告: {e}")
        return

    required_cols = ['服务名称', '静态总分']
    for col in required_cols:
        if col not in df_report.columns:
            print(f"报告缺少列: {col}")
            return

    zero_media = df_report[df_report['最终总分'] == 0]['服务名称'].tolist()
    print(f"共 {len(zero_media)} 家媒体最终得分为0，需要进行复核")

    if not zero_media:
        print("没有需要复核的媒体，程序结束。")
        return

    try:
        df_article = pd.read_csv("媒体文章数据.csv", encoding='utf-8-sig')
        df_article['media_name'] = df_article['media_name'].astype(str).str.strip()
    except Exception as e:
        print(f"无法读取文章文件: {e}")
        return

    try:
        df_rumor = pd.read_csv("辟谣平台_月度榜单_带主题标签.csv", encoding='utf-8-sig')
        if 'keywords' in df_rumor.columns and isinstance(df_rumor['keywords'].iloc[0], list):
            pass
        else:
            print("正在提取谣言关键词...")
            df_rumor['keywords'] = df_rumor['black_name'].apply(extract_keywords)
    except Exception as e:
        print(f"无法读取辟谣榜单: {e}")
        return

    results = []
    for media in zero_media:
        static_score = df_report[df_report['服务名称'] == media]['静态总分'].values[0]
        total_arts, hit_arts, total_hits, exempt_arts = compute_article_stats(media, df_article, df_rumor)

        if total_arts == 0:
            revised = static_score
            reason = "没有采集到文章，维持静态分"
            level = "未评估（无文章）"
        else:
            revised, reason = compute_revised_score(static_score, total_arts, hit_arts, exempt_arts)
            if revised >= 90:
                level = "完全可信"
            elif revised >= 75:
                level = "高度可信"
            elif revised >= 60:
                level = "基本可信"
            else:
                level = "存疑（需人工复核）"

        results.append({
            '服务名称': media,
            '静态总分': static_score,
            '总文章数': total_arts,
            '命中文章数': hit_arts,
            '命中比例': f"{hit_arts / total_arts:.1%}" if total_arts > 0 else "N/A",
            '主动辟谣文章数': exempt_arts,
            '复核后总分': revised,
            '复核后等级': level,
            '复核理由': reason
        })

    df_out = pd.DataFrame(results)
    df_out = df_out.drop_duplicates(subset=['服务名称'], keep='first')
    output_file = "媒体复核建议.xlsx"
    df_out.to_excel(output_file, index=False)
    print(f"\n复核完成！报告已保存至: {output_file}")
    print("\n复核结果预览:")
    print(df_out[['服务名称', '静态总分', '命中比例', '主动辟谣文章数', '复核后总分', '复核后等级']].to_string(
        index=False))


if __name__ == "__main__":
    main()