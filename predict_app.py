"""
知舆系统 - AI 辅助视频热度预测后端
基于 Flask 实现
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import random
from datetime import datetime

app = Flask(__name__, static_folder='.')
CORS(app)

# ============================================
# 配置
# ============================================
API_BASE = 'http://localhost:5000'

# ============================================
# 模拟历史视频库（20条记录）
# ============================================
HISTORY_VIDEOS = [
    {
        "id": 1,
        "summary": "这是一部关于Python编程入门的教学视频",
        "heat_curve": [45, 30, 25, 20, 18, 35, 80, 150, 200, 180, 160, 140, 120, 110, 100, 95, 85, 70, 55, 40, 35, 30, 28, 25],
        "risk_level": "低",
        "tags": ["编程", "Python", "教程", "入门"]
    },
    {
        "id": 2,
        "summary": "这是一部关于游戏直播的娱乐搞笑视频",
        "heat_curve": [120, 100, 90, 85, 80, 95, 140, 220, 280, 260, 240, 210, 180, 160, 145, 130, 120, 110, 95, 80, 70, 65, 60, 55],
        "risk_level": "中",
        "tags": ["游戏", "直播", "搞笑", "娱乐"]
    },
    {
        "id": 3,
        "summary": "这是一部探讨社会热点话题的评论视频",
        "heat_curve": [200, 180, 160, 150, 145, 200, 350, 500, 600, 550, 480, 420, 380, 350, 320, 290, 260, 230, 200, 180, 160, 150, 140, 130],
        "risk_level": "高",
        "tags": ["社会", "热点", "评论", "争议"]
    },
    {
        "id": 4,
        "summary": "这是一部美食制作教程视频",
        "heat_curve": [35, 25, 20, 18, 15, 22, 45, 90, 140, 160, 150, 135, 120, 105, 95, 85, 75, 65, 55, 48, 42, 38, 35, 32],
        "risk_level": "低",
        "tags": ["美食", "烹饪", "教程", "家常菜"]
    },
    {
        "id": 5,
        "summary": "这是一部科技产品测评视频",
        "heat_curve": [60, 45, 38, 32, 28, 35, 70, 120, 180, 200, 185, 165, 145, 130, 115, 100, 90, 80, 70, 62, 55, 50, 48, 45],
        "risk_level": "低",
        "tags": ["科技", "测评", "数码", "产品"]
    },
    {
        "id": 6,
        "summary": "这是一部健身减脂教程视频",
        "heat_curve": [50, 40, 35, 30, 28, 32, 55, 100, 150, 170, 155, 140, 125, 110, 100, 90, 80, 70, 62, 55, 50, 45, 42, 40],
        "risk_level": "低",
        "tags": ["健身", "减肥", "健康", "运动"]
    },
    {
        "id": 7,
        "summary": "这是一部探讨明星绯闻的娱乐八卦视频",
        "heat_curve": [300, 280, 260, 250, 240, 300, 450, 600, 700, 680, 620, 560, 500, 450, 400, 360, 320, 290, 260, 240, 220, 210, 200, 190],
        "risk_level": "高",
        "tags": ["娱乐", "明星", "八卦", "绯闻"]
    },
    {
        "id": 8,
        "summary": "这是一部儿童动画教育视频",
        "heat_curve": [80, 120, 150, 140, 130, 125, 120, 115, 110, 105, 100, 95, 90, 85, 80, 75, 70, 65, 60, 55, 50, 48, 45, 42],
        "risk_level": "低",
        "tags": ["儿童", "动画", "教育", "早教"]
    },
    {
        "id": 9,
        "summary": "这是一部美妆教程视频",
        "heat_curve": [55, 48, 42, 38, 35, 40, 65, 110, 160, 180, 165, 150, 135, 120, 108, 95, 85, 75, 68, 60, 55, 50, 48, 45],
        "risk_level": "低",
        "tags": ["美妆", "化妆", "教程", "女性"]
    },
    {
        "id": 10,
        "summary": "这是一部探讨政治话题的严肃评论视频",
        "heat_curve": [180, 160, 145, 135, 130, 180, 320, 480, 580, 540, 490, 440, 400, 360, 330, 300, 270, 245, 220, 200, 185, 175, 165, 155],
        "risk_level": "高",
        "tags": ["政治", "评论", "严肃", "分析"]
    },
    {
        "id": 11,
        "summary": "这是一部旅游 vlog 视频",
        "heat_curve": [40, 32, 28, 25, 22, 28, 50, 95, 145, 165, 150, 135, 120, 108, 98, 88, 78, 68, 60, 52, 46, 42, 40, 38],
        "risk_level": "低",
        "tags": ["旅游", "vlog", "风景", "旅行"]
    },
    {
        "id": 12,
        "summary": "这是一部汽车测评视频",
        "heat_curve": [65, 52, 45, 40, 35, 42, 75, 130, 190, 210, 195, 175, 155, 140, 125, 112, 100, 90, 80, 70, 62, 58, 55, 52],
        "risk_level": "低",
        "tags": ["汽车", "测评", "试驾", "新车"]
    },
    {
        "id": 13,
        "summary": "这是一部探讨情感话题的脱口秀视频",
        "heat_curve": [95, 85, 78, 72, 68, 75, 110, 170, 230, 250, 235, 210, 190, 170, 155, 140, 128, 115, 105, 95, 88, 82, 78, 75],
        "risk_level": "中",
        "tags": ["情感", "脱口秀", "话题", "生活"]
    },
    {
        "id": 14,
        "summary": "这是一部音乐翻唱视频",
        "heat_curve": [70, 60, 55, 50, 48, 55, 90, 150, 210, 235, 220, 200, 180, 162, 145, 130, 118, 105, 95, 85, 78, 72, 68, 65],
        "risk_level": "低",
        "tags": ["音乐", "翻唱", "歌曲", "演唱"]
    },
    {
        "id": 15,
        "summary": "这是一部揭秘网红造假事件的视频",
        "heat_curve": [250, 230, 210, 200, 195, 260, 420, 580, 650, 620, 570, 520, 470, 425, 385, 350, 315, 285, 255, 235, 215, 200, 190, 180],
        "risk_level": "高",
        "tags": ["网红", "揭秘", "造假", "事件"]
    },
    {
        "id": 16,
        "summary": "这是一部手工DIY制作教程视频",
        "heat_curve": [38, 30, 25, 22, 20, 25, 48, 88, 135, 155, 142, 128, 115, 102, 92, 82, 73, 64, 56, 50, 45, 42, 40, 38],
        "risk_level": "低",
        "tags": ["手工", "DIY", "制作", "教程"]
    },
    {
        "id": 17,
        "summary": "这是一部职场技能提升教程视频",
        "heat_curve": [42, 35, 30, 28, 25, 30, 55, 100, 155, 175, 162, 148, 132, 118, 105, 95, 85, 75, 66, 58, 52, 48, 45, 42],
        "risk_level": "低",
        "tags": ["职场", "技能", "提升", "工作"]
    },
    {
        "id": 18,
        "summary": "这是一部测评争议商品的视频",
        "heat_curve": [150, 135, 125, 118, 115, 165, 280, 420, 520, 490, 450, 405, 365, 330, 300, 272, 245, 220, 198, 180, 165, 155, 148, 140],
        "risk_level": "中",
        "tags": ["测评", "争议", "商品", "对比"]
    },
    {
        "id": 19,
        "summary": "这是一部萌宠日常记录视频",
        "heat_curve": [55, 48, 42, 38, 35, 40, 65, 115, 170, 195, 180, 162, 145, 130, 118, 105, 95, 85, 75, 66, 60, 55, 52, 50],
        "risk_level": "低",
        "tags": ["宠物", "萌宠", "猫狗", "可爱"]
    },
    {
        "id": 20,
        "summary": "这是一部探讨地域歧视话题的视频",
        "heat_curve": [220, 200, 185, 175, 170, 230, 380, 550, 640, 610, 560, 510, 460, 415, 375, 340, 305, 275, 248, 225, 208, 195, 185, 175],
        "risk_level": "高",
        "tags": ["地域", "歧视", "争议", "话题"]
    }
]


# ============================================
# 模拟 AI 分析函数
# ============================================
def analyze_content(title, tags, description):
    """
    模拟 AI 内容分析函数
    
    实际应用中可替换为:
    - OpenAI GPT API
    - 本地 LLM (如 ChatGLM, LLaMA)
    - 专业的视频理解模型
    
    Args:
        title: 视频标题
        tags: 标签列表
        description: 用户描述
    
    Returns:
        str: 内容概括文本
    """
    # 提取关键词
    keywords = []
    
    # 从标题提取
    title_keywords = ['编程', '游戏', '美食', '科技', '健身', '美妆', '旅游', '汽车', '音乐', 
                      '手工', '职场', '宠物', '儿童', '情感', '社会', '政治', '娱乐', '明星',
                      '测评', '教程', 'vlog', '直播', '动画', '翻唱', '评论']
    for kw in title_keywords:
        if kw in title:
            keywords.append(kw)
    
    # 从标签提取
    if tags:
        keywords.extend([t for t in tags if t])
    
    # 从描述提取
    desc_keywords = ['教学', '测评', '搞笑', '直播', '记录', '制作', '评论', '分析', '教程',
                     '入门', '进阶', '评测', '体验', '分享', '日常', '揭秘', '对比', '热门']
    for kw in desc_keywords:
        if kw in description:
            keywords.append(kw)
    
    # 去重
    keywords = list(set(keywords))[:5]
    
    # 生成概括文本
    topic_word = keywords[0] if keywords else '综合'
    type_word = '视频'
    
    # 根据关键词判断类型
    teaching_keywords = ['编程', '教学', '教程', '入门', '进阶', '技能']
    entertainment_keywords = ['游戏', '搞笑', '娱乐', '直播', '明星', '八卦']
    life_keywords = ['美食', '健身', '美妆', '旅游', '宠物', '手工', '日常']
    news_keywords = ['社会', '政治', '评论', '分析', '争议', '揭秘']
    tech_keywords = ['科技', '汽车', '测评', '数码', '产品']
    
    if any(k in keywords for k in teaching_keywords):
        type_desc = '教学视频'
    elif any(k in keywords for k in entertainment_keywords):
        type_desc = '娱乐视频'
    elif any(k in keywords for k in life_keywords):
        type_desc = '生活视频'
    elif any(k in keywords for k in news_keywords):
        type_desc = '评论视频'
    elif any(k in keywords for k in tech_keywords):
        type_desc = '测评视频'
    else:
        type_desc = '综合视频'
    
    summary = f"这是一部关于{topic_word}的{type_desc}"
    
    return summary, keywords


# ============================================
# 相似度匹配函数
# ============================================
def find_similar_videos(summary, keywords, limit=3):
    """
    根据内容相似度检索历史视频
    
    实际应用中可替换为:
    - Embedding 向量相似度 (使用 OpenAI embeddings, 或本地模型)
    - BM25 / TF-IDF 文本检索
    - 专门的视频内容理解模型
    
    Args:
        summary: 当前内容概括
        keywords: 关键词列表
        limit: 返回数量
    
    Returns:
        list: 最相似的视频列表
    """
    scored_videos = []
    
    for video in HISTORY_VIDEOS:
        score = 0
        
        # 关键词重叠计分
        for kw in keywords:
            if kw in video['summary'] or kw in video['tags']:
                score += 10
        
        # 描述词匹配
        for video_kw in video['tags']:
            if video_kw in summary:
                score += 5
        
        if score > 0:
            scored_videos.append((video, score))
    
    # 按相似度排序
    scored_videos.sort(key=lambda x: x[1], reverse=True)
    
    # 返回前 limit 个
    return [v[0] for v in scored_videos[:limit]]


# ============================================
# 预测算法
# ============================================
def predict_heat_curve(similar_videos, author_avg_heat):
    """
    基于相似视频预测热度曲线
    
    实际应用中可使用:
    - 时间序列模型 (ARIMA, Prophet)
    - 深度学习模型 (LSTM, Transformer)
    - 图神经网络 (GNN)
    
    Args:
        similar_videos: 相似视频列表
        author_avg_heat: 作者历史平均热度
    
    Returns:
        list: 预测的24小时热度数组
    """
    if not similar_videos:
        # 无相似视频，使用默认曲线
        base_curve = [30, 25, 22, 20, 18, 25, 50, 100, 150, 170, 155, 140, 
                      125, 110, 100, 90, 80, 70, 60, 52, 45, 40, 35, 32]
    else:
        # 取平均曲线
        avg_curve = []
        for i in range(24):
            avg_val = sum(v['heat_curve'][i] for v in similar_videos) / len(similar_videos)
            avg_curve.append(avg_val)
        base_curve = avg_curve
    
    # 根据作者历史平均热度调整
    if author_avg_heat > 0:
        scale_factor = author_avg_heat / 100
        adjusted_curve = [int(h * scale_factor) for h in base_curve]
    else:
        adjusted_curve = [int(h) for h in base_curve]
    
    return adjusted_curve


def generate_risk_advice(similar_videos, summary, keywords):
    """
    生成风险建议
    
    Args:
        similar_videos: 相似视频列表
        summary: 内容概括
        keywords: 关键词
    
    Returns:
        str: 风险提示文本
    """
    # 检查相似视频中最高风险等级
    risk_levels = [v['risk_level'] for v in similar_videos]
    
    high_risk_keywords = ['争议', '敏感', '政治', '歧视', '绯闻', '造假', '地域']
    medium_risk_keywords = ['明星', '八卦', '对比', '测评', '评论', '话题']
    
    # 关键词风险检测
    detected_risks = []
    for kw in keywords:
        if kw in high_risk_keywords:
            detected_risks.append(('高', kw))
        elif kw in medium_risk_keywords:
            detected_risks.append(('中', kw))
    
    # 生成建议
    if '高' in risk_levels or any(r[0] == '高' for r in detected_risks):
        risk_level = '高风险'
        suggestions = [
            '内容涉及敏感话题，建议谨慎发布',
            '可能引发争议，请确保内容合规',
            '建议删除或修改可能引起误解的部分',
            '发布前建议进行合规性审查'
        ]
        advice = random.choice(suggestions)
    elif '中' in risk_levels or any(r[0] == '中' for r in detected_risks):
        risk_level = '中风险'
        suggestions = [
            '内容有一定话题性，建议适度把握尺度',
            '注意避免涉及版权或隐私问题',
            '建议添加适当的免责声明',
            '内容较为中性，发布风险可控'
        ]
        advice = random.choice(suggestions)
    else:
        risk_level = '低风险'
        suggestions = [
            '内容健康正面，发布风险较低',
            '继续保持高质量创作',
            '建议保持稳定的更新频率',
            '内容方向良好，可放心发布'
        ]
        advice = random.choice(suggestions)
    
    return f"{risk_level}：{advice}", risk_level


# ============================================
# API 路由
# ============================================
@app.route('/api/ai-predict', methods=['POST'])
def ai_predict():
    """
    AI 辅助视频热度预测接口
    
    请求体:
    {
        "title": "视频标题",
        "tags": ["标签1", "标签2"],
        "category": "tech",
        "description": "视频描述",
        "duration": 600,
        "author_avg_heat": 1200
    }
    
    响应:
    {
        "hours": ["00:00", "01:00", ...],
        "predicted_heat": [12, 34, ...],
        "risk": "风险提示文本",
        "risk_level": "低/中/高",
        "similar_videos": ["视频A", "视频B"],
        "summary": "AI分析概括"
    }
    """
    try:
        data = request.get_json() or {}
        
        # 获取参数（使用默认值）
        title = data.get('title', '')
        tags = data.get('tags', [])
        category = data.get('category', 'general')
        description = data.get('description', '')
        duration = data.get('duration', 300)
        author_avg_heat = data.get('author_avg_heat', 100)
        
        # 如果 tags 是字符串（逗号分隔），转换为列表
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(',') if t.strip()]
        
        # ========== AI 分析（可替换为真实 API）==========
        summary, keywords = analyze_content(title, tags, description)
        # =================================================
        
        # ========== 相似度匹配（可替换为向量检索）==========
        similar_videos = find_similar_videos(summary, keywords)
        # =================================================
        
        # ========== 热度预测（可替换为 ML 模型）==========
        predicted_heat = predict_heat_curve(similar_videos, author_avg_heat)
        # =================================================
        
        # ========== 风险评估（可替换为专业审核模型）==========
        risk_advice, risk_level = generate_risk_advice(similar_videos, summary, keywords)
        # =================================================
        
        # 获取相似视频名称
        similar_names = [v['summary'].replace('这是一部关于', '').replace('的视频', '') 
                        for v in similar_videos[:3]]
        
        # 生成小时标签
        hours = [f"{h:02d}:00" for h in range(24)]
        
        return jsonify({
            'success': True,
            'hours': hours,
            'predicted_heat': predicted_heat,
            'risk': risk_advice,
            'risk_level': risk_level,
            'similar_videos': similar_names,
            'summary': summary,
            'keywords': keywords
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/history', methods=['GET'])
def get_history():
    """获取历史视频库（用于调试）"""
    return jsonify(HISTORY_VIDEOS)


@app.route('/')
def index():
    """返回预测页面"""
    return send_from_directory('.', 'predict.html')


# ============================================
# 启动应用
# ============================================
if __name__ == '__main__':
    print("=" * 50)
    print("知舆 - AI 辅助视频热度预测系统")
    print("=" * 50)
    print("后端服务启动中...")
    print("预测页面: http://localhost:5000")
    print("API 文档: http://localhost:5000/api/ai-predict")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=True)
