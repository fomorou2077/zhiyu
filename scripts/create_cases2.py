"""
使用 zipfile 创建 docx 文件（不依赖 python-docx）
"""
import zipfile
import os
from datetime import datetime

def create_minimal_docx(filename, title, content):
    """创建最小的 docx 文件"""
    with zipfile.ZipFile(filename, 'w', zipfile.ZIP_DEFLATED) as docx:
        # [Content_Types].xml
        docx.writestr('[Content_Types].xml', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>''')

        # _rels/.rels
        docx.writestr('_rels/.rels', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>''')

        # word/_rels/document.xml.rels
        docx.writestr('word/_rels/document.xml.rels', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
</Relationships>''')

        # word/document.xml - 主要内容
        content_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p>
      <w:pPr>
        <w:jc w:val="center"/>
      </w:pPr>
      <w:r>
        <w:rPr>
          <w:b/>
          <w:sz w:val="48"/>
        </w:rPr>
        <w:t>{title}</w:t>
      </w:r>
    </w:p>
    {content}
    <w:sectPr>
      <w:pgSz w:w="12240" w:h="15840"/>
      <w:pgMar w:top="1440" w:right="1800" w:bottom="1440" w:left="1800"/>
    </w:sectPr>
  </w:body>
</w:document>'''

        docx.writestr('word/document.xml', content_xml)

def create_paragraph(text, bold=False):
    """创建段落"""
    bold_xml = '<w:b/>' if bold else ''
    return f'''<w:p>
      <w:r>
        <w:rPr>{bold_xml}</w:rPr>
        <w:t xml:space="preserve">{text}</w:t>
      </w:r>
    </w:p>'''

def create_heading(text, level=1):
    """创建标题"""
    size = 32 if level == 1 else 28
    return f'''<w:p>
      <w:pPr>
        <w:pStyle w:val="Heading{level}"/>
      </w:pPr>
      <w:r>
        <w:rPr>
          <w:b/>
          <w:sz w:val="{size}"/>
        </w:rPr>
        <w:t>{text}</w:t>
      </w:r>
    </w:p>'''

def create_cases():
    base_dir = 'static/cases'

    # 案例1：地域歧视风波
    content1 = create_heading('一、事件概述', 1)
    content1 += create_paragraph('2023年5月，某茶饮品牌在海南地区的广告宣传中，使用了以下文案："椰子里不喝椰子水，就像海南人不吃椰子鸡"。该文案被网友认为暗示"海南人必须吃椰子鸡"，涉嫌地域歧视。事件在抖音和小红书迅速发酵，24小时内登上微博热搜前三。')

    content1 += create_heading('二、舆情传播路径', 1)
    content1 += create_paragraph('• 5月18日 10:00 - 首发网友在小红书发布质疑帖')
    content1 += create_paragraph('• 5月18日 14:00 - 话题扩散至微博，引发2000+讨论')
    content1 += create_paragraph('• 5月18日 18:00 - 品牌方发现舆情，启动应急预案')
    content1 += create_paragraph('• 5月19日 00:00 - 品牌发布道歉声明')

    content1 += create_heading('三、企业应对措施', 1)
    content1 += create_paragraph('1. 6小时内删除所有争议广告物料')
    content1 += create_paragraph('2. 发布官方致歉声明，承认审核不严')
    content1 += create_paragraph('3. 承诺加强内容审核机制')
    content1 += create_paragraph('4. 邀请海南文化专家参与后续宣传设计')

    content1 += create_heading('四、舆论反馈', 1)
    content1 += create_paragraph('正面：快速响应态度获得部分认可')
    content1 += create_paragraph('负面：仍有部分网友认为道歉不够诚恳')
    content1 += create_paragraph('中性：多数用户关注后续整改措施')

    content1 += create_heading('五、经验教训', 1)
    content1 += create_paragraph('1. 避免使用地域刻板印象进行营销')
    content1 += create_paragraph('2. 跨界营销需提前进行文化敏感度测试')
    content1 += create_paragraph('3. 建立区域化内容的双重审核机制')
    content1 += create_paragraph('4. 舆情响应需在黄金4小时内完成首次表态')

    create_minimal_docx(f'{base_dir}/case1.docx', '某茶饮品牌广告地域歧视风波', content1)
    print('案例1创建成功')

    # 案例2：直播带货翻车
    content2 = create_heading('一、事件概述', 1)
    content2 += create_paragraph('2024年1月，某头部带货主播在直播间推销某保健品时，使用了"三天见效"、"无效退款"等宣传用语。职业打假人随即发布测评视频指出产品并无宣传功效，引发消费者集体投诉。')

    content2 += create_heading('二、违规问题点', 1)
    content2 += create_paragraph('1. 违反《广告法》关于保健食品不得宣传疗效的规定')
    content2 += create_paragraph('2. 使用绝对化用语"三天见效"')
    content2 += create_paragraph('3. 夸大产品功效误导消费者')
    content2 += create_paragraph('4. 未明确标注"广告"字样')

    content2 += create_heading('三、企业应对', 1)
    content2 += create_paragraph('• 主播团队发布道歉视频')
    content2 += create_paragraph('• 承诺"退一赔三"方案')
    content2 += create_paragraph('• 下架涉事产品')
    content2 += create_paragraph('• 暂停直播一周进行内部整顿')

    content2 += create_heading('四、监管部门处罚', 1)
    content2 += create_paragraph('市场监管部门立案调查，最终罚款50万元，并要求限期整改直播带货流程。')

    content2 += create_heading('五、经验教训', 1)
    content2 += create_paragraph('1. 直播话术必须遵守《广告法》')
    content2 += create_paragraph('2. 建立法务事前审核机制')
    content2 += create_paragraph('3. 避免使用绝对化宣传用语')
    content2 += create_paragraph('4. 保健品、药品类需特别谨慎')

    create_minimal_docx(f'{base_dir}/case2.docx', '某直播带货主播夸大功效翻车事件', content2)
    print('案例2创建成功')

    # 案例3：文案抄袭争议
    content3 = create_heading('一、事件概述', 1)
    content3 += create_paragraph('2024年8月，某国产手机品牌发布的新品宣传海报被国外设计师发现与自己的原创作品高度相似，相似度超过90%。设计师在社交媒体发布对比图，指责品牌方"拿来主义"。')

    content3 += create_heading('二、对比分析', 1)
    content3 += create_paragraph('• 色调搭配：几乎一致')
    content3 += create_paragraph('• 构图方式：采用相同视角')
    content3 += create_paragraph('• 核心元素：手机轮廓，光影效果高度重合')
    content3 += create_paragraph('• 唯一区别：更换了产品型号')

    content3 += create_heading('三、企业应对', 1)
    content3 += create_paragraph('1. 24小时内删除所有争议海报')
    content3 += create_paragraph('2. 发布官方道歉声明，承认"审核疏忽"')
    content3 += create_paragraph('3. 主动联系原作者，支付版权授权费用')
    content3 += create_paragraph('4. 承诺加强创意素材版权审查')

    content3 += create_heading('四、舆论走向', 1)
    content3 += create_paragraph('由于品牌方响应迅速、态度诚恳，舆论由最初的负面转为中性偏正面。部分用户对品牌的知错就改表示认可。')

    content3 += create_heading('五、经验教训', 1)
    content3 += create_paragraph('1. 创意素材需进行严格的版权审查')
    content3 += create_paragraph('2. 建立外部法律顾问团队提前规避风险')
    content3 += create_paragraph('3. 设计外包需签署完整的版权协议')
    content3 += create_paragraph('4. 舆情应对需"快、诚、实"')

    create_minimal_docx(f'{base_dir}/case3.docx', '某手机品牌新品海报抄袭争议', content3)
    print('案例3创建成功')

    # 案例4：高管不当言论
    content4 = create_heading('一、事件概述', 1)
    content4 += create_paragraph('2025年2月，某新能源车企CEO在新品发布会后接受媒体采访时，被问及如何看待不购买自家产品的消费者时，回答："不买我们品牌汽车的，那都是不懂车的。"该言论被剪辑成短视频疯传，引发网友群嘲。')

    content4 += create_heading('二、争议焦点', 1)
    content4 += create_paragraph('1. 使用贬低性表述"不懂车"')
    content4 += create_paragraph('2. 暗示只有购买自家产品才算"懂车"')
    content4 += create_paragraph('3. 傲慢态度引发消费者反感')
    content4 += create_paragraph('4. 言论被断章取义广泛传播')

    content4 += create_heading('三、企业应对', 1)
    content4 += create_paragraph('阶段一（2小时内）：企业官方账号发表声明，称原话被"断章取义"')
    content4 += create_paragraph('阶段二（6小时内）：CEO本人录制道歉视频，强调"尊重每一位消费者的选择"')
    content4 += create_paragraph('阶段三（24小时内）：企业宣布内部开展公关培训，强化高管发言规范')

    content4 += create_heading('四、舆论反馈', 1)
    content4 += create_paragraph('• 微博话题阅读量突破2亿')
    content4 += create_paragraph('• 部分网友表示"知错能改"，给予理解')
    content4 += create_paragraph('• 部分潜在用户表示"转粉"，不会再考虑该品牌')
    content4 += create_paragraph('• 竞品趁机营销，发布"尊重用户选择"的对比广告')

    content4 += create_heading('五、经验教训', 1)
    content4 += create_paragraph('1. 高管发言需经公关团队审核')
    content4 += create_paragraph('2. 避免使用绝对化、贬低性表述')
    content4 += create_paragraph('3. 出现争议应第一时间温和回应')
    content4 += create_paragraph('4. 建立高管媒体发言规范手册')

    create_minimal_docx(f'{base_dir}/case4.docx', '某车企CEO公开场合发表不当言论', content4)
    print('案例4创建成功')

    print('\n所有案例文档创建完成！')

if __name__ == '__main__':
    create_cases()
