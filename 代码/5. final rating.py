import pandas as pd

df_original = pd.read_excel("综合媒体评级报告.xlsx", sheet_name=0)
df_review = pd.read_excel("媒体复核建议.xlsx", sheet_name=0)
print("原始报告列名:", df_original.columns.tolist())
print("复核报告列名:", df_review.columns.tolist())

def find_column(col_list, keyword):
    for col in col_list:
        if keyword in col:
            return col
    return None

score_col = find_column(df_review.columns, "复核后总分")
level_col = find_column(df_review.columns, "复核后等级")
reason_col = find_column(df_review.columns, "复核理由")

if score_col is None:
    raise KeyError("复核表中未找到'复核后总分'列，请检查文件")

df_review_subset = df_review[['服务名称', score_col, level_col, reason_col]].copy()
df_review_subset.rename(columns={
    score_col: '复核后总分',
    level_col: '复核后等级',
    reason_col: '复核理由'
}, inplace=True)

df_merged = df_original.merge(df_review_subset, on='服务名称', how='left')
mask = df_merged['复核后总分'].notna()
df_merged.loc[mask, '最终总分'] = df_merged.loc[mask, '复核后总分']
df_merged.loc[mask, '综合信任等级'] = df_merged.loc[mask, '复核后等级']
df_merged['是否复核'] = mask
df_merged.drop(columns=['复核后总分', '复核后等级'], inplace=True)

output_columns = [
    '服务名称', '服务地址', '许可证编号', '主域名',
    '是否政务', 'A1许可级别', 'B1名称关联', 'B2信息唯一性',
    'C1地址规范', 'C2记录一致性', 'D1政务属性', '静态总分',
    '命中辟谣次数', '动态扣分', '最终总分', '综合信任等级',
    '是否复核', '复核理由'
]

for col in output_columns:
    if col not in df_merged.columns:
        df_merged[col] = ''

df_merged[output_columns].to_excel("统一评级报告.xlsx", index=False)
print("整合完成 输出文件：统一评级报告.xlsx")
print("复核媒体数量:", mask.sum())