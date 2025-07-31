#!/usr/bin/env python3
"""
简单的API测试脚本
"""

import requests
import time

def test_api():
    base_url = "http://localhost:5211"
    
    print("🧪 测试 MiniMax Video Tool API")
    print("=" * 40)
    
    # 测试主页
    try:
        response = requests.get(f"{base_url}/")
        if response.status_code == 200:
            print("✅ 主页访问正常")
        else:
            print(f"❌ 主页访问失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 无法连接到服务器: {e}")
        return False
    
    # 测试文件上传API（需要先启动服务）
    try:
        # 创建一个测试文件
        test_data = b"test image data"
        files = {'files': ('test.jpg', test_data, 'image/jpeg')}
        
        response = requests.post(f"{base_url}/api/upload", files=files)
        if response.status_code == 200:
            print("✅ 文件上传API正常")
        else:
            print(f"⚠️ 文件上传API测试失败: {response.status_code}")
    except Exception as e:
        print(f"⚠️ 文件上传测试错误: {e}")
    
    print("\n🎉 基本测试完成！")
    print("💡 如需完整测试，请：")
    print("   1. 在浏览器中访问 http://localhost:5211")
    print("   2. 准备有效的MiniMax API Key")
    print("   3. 上传图片并测试视频生成")
    
    return True

if __name__ == "__main__":
    test_api()