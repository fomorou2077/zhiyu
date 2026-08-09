"""
API HTTP 测试脚本
测试前端请求的实际地址
"""

import asyncio
import aiohttp
import json

BASE_URL = "http://localhost:8000"


async def test_apis():
    print("=" * 60)
    print("知舆系统 - API HTTP 测试")
    print("=" * 60)

    async with aiohttp.ClientSession() as session:

        # 测试 1: 健康检查
        print("\n[测试1] 健康检查")
        print("-" * 40)
        try:
            async with session.get(f"{BASE_URL}/health") as resp:
                result = await resp.json()
                print(f"  URL: GET {BASE_URL}/health")
                print(f"  Status: {resp.status}")
                print(f"  Response: {result}")
        except aiohttp.ClientConnectorError:
            print(f"  [ERROR] 无法连接到 {BASE_URL}")
            print("  请确保后端服务已启动: python run.py")
            return

        # 测试 2: 热度预测 API
        print("\n[测试2] 热度预测 API")
        print("-" * 40)
        try:
            async with session.post(
                f"{BASE_URL}/predict/ai-predict",
                json={
                    "title": "测试视频标题",
                    "tags": ["测试", "科技"],
                    "category": "tech",
                    "description": "这是一个测试视频",
                    "duration": 300,
                    "author_avg_heat": 100
                }
            ) as resp:
                print(f"  URL: POST {BASE_URL}/predict/ai-predict")
                print(f"  Status: {resp.status}")
                result = await resp.json()
                print(f"  Response: {json.dumps(result, ensure_ascii=False)[:200]}")

                if resp.status == 200:
                    print("  [OK] 热度预测 API 正常工作")
                else:
                    print("  [ERROR] API 返回错误")
        except Exception as e:
            print(f"  [ERROR] {e}")

        # 测试 3: 观点对冲 API
        print("\n[测试3] 观点对冲 API")
        print("-" * 40)
        try:
            async with session.post(
                f"{BASE_URL}/bias/analyze",
                json={
                    "content": "人工智能将改变未来",
                    "use_online": False
                }
            ) as resp:
                print(f"  URL: POST {BASE_URL}/bias/analyze")
                print(f"  Status: {resp.status}")
                result = await resp.json()
                print(f"  Response: {json.dumps(result, ensure_ascii=False)[:200]}")

                if resp.status == 200:
                    print("  [OK] 观点对冲 API 正常工作")
        except Exception as e:
            print(f"  [ERROR] {e}")

        # 测试 4: CORS 测试
        print("\n[测试4] CORS 跨域测试")
        print("-" * 40)
        try:
            async with session.get(
                f"{BASE_URL}/health",
                headers={"Origin": "http://localhost:8000"}
            ) as resp:
                cors_headers = {
                    "Access-Control-Allow-Origin": resp.headers.get("Access-Control-Allow-Origin", "Not Set"),
                }
                print(f"  CORS Header: {cors_headers}")
                print("  [OK] CORS 配置正常" if cors_headers["Access-Control-Allow-Origin"] else "  [WARNING] CORS 可能有问题")
        except Exception as e:
            print(f"  [ERROR] {e}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_apis())
