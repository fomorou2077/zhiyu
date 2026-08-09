"""
API Key 诊断脚本
检查 API Key 是否正确配置和生效
"""

import sys
sys.path.insert(0, '.')

print("=" * 60)
print("API Key 诊断")
print("=" * 60)

# 1. 检查 .env 文件
print("\n[1] 检查 .env 文件:")
print("-" * 40)
try:
    with open('.env', 'r') as f:
        for line in f:
            if 'DASHSCOPE_API_KEY' in line and not line.strip().startswith('#'):
                print(f"  找到: {line.strip()[:50]}...")
                key = line.split('=')[1].strip()
                print(f"  Key 长度: {len(key)}")
                print(f"  Key 前5位: {key[:5]}...")
except Exception as e:
    print(f"  读取失败: {e}")

# 2. 检查 settings 对象
print("\n[2] 检查 settings 配置:")
print("-" * 40)
try:
    from app.config import settings
    print(f"  settings.dashscope_api_key: {settings.dashscope_api_key[:10]}... (长度: {len(settings.dashscope_api_key)})")
except Exception as e:
    print(f"  读取失败: {e}")

# 3. 检查 dashscope 模块
print("\n[3] 检查 dashscope 模块:")
print("-" * 40)
try:
    import dashscope
    print(f"  dashscope.api_key: {dashscope.api_key[:10]}... (长度: {len(dashscope.api_key)})")
except Exception as e:
    print(f"  读取失败: {e}")

# 4. 测试 API 调用
print("\n[4] 测试 API 调用:")
print("-" * 40)
try:
    import asyncio
    from app.services.baichuan_service import chat_with_ai

    async def test():
        try:
            result = await chat_with_ai(
                messages=[{"role": "user", "content": "测试"}],
                enable_search=False,
                model="qwen-turbo"
            )
            print(f"  [成功] 响应: {result[:50]}...")
            return True
        except Exception as e:
            print(f"  [失败] {e}")
            return False

    success = asyncio.run(test())
    if not success:
        print("\n  问题可能是:")
        print("  1. API Key 无效或已过期")
        print("  2. 需要在阿里云百炼平台启用相关服务")
        print("  3. 模型名称不正确")
        print("  4. 网络问题")
except Exception as e:
    print(f"  测试失败: {e}")

# 5. 解决方案
print("\n" + "=" * 60)
print("解决方案:")
print("=" * 60)
print("""
1. 确认 API Key 有效性:
   - 登录阿里云百炼平台
   - 检查 Key 是否启用
   - 确认是否开通了 qwen-turbo 模型

2. 重启后端服务:
   - 停止当前服务 (Ctrl+C)
   - 重新启动: python run.py

3. 如果 Key 确实无效，需要:
   - 在阿里云百炼平台申请新的 Key
   - 更新 .env 文件中的 DASHSCOPE_API_KEY
   - 重启服务
""")
