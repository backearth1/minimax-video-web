# MiniMax Video Generation Tool

一个简洁的MiniMax视频生成工具，支持多人同时使用，用完即清空。

## 功能特性

- 🎯 多用户并发支持（10-20人同时使用）
- 🖼️ 单图/批量图片上传  
- 📁 文件夹批量上传
- 🎬 实时视频生成状态追踪
- 📊 完整的API调用日志
- 🔄 WebSocket实时更新
- 🧹 用完即清空，无数据持久化

## 技术栈

### 后端
- Python 3.9+ + FastAPI
- 内存存储（无数据库）
- WebSocket实时通信

### 前端
- 纯HTML/CSS/JavaScript
- Tailwind CSS样式
- 原生WebSocket客户端

## 架构

```
┌─────────────┐    ┌─────────────┐
│   浏览器     │    │   FastAPI   │
│ (HTML/JS)   │────│  (Python)   │
└─────────────┘    └─────────────┘
                           │
                   ┌─────────────┐
                   │ 内存存储     │
                   │ (临时数据)   │
                   └─────────────┘
```

## 快速开始

### 方式一：使用启动脚本 (推荐)

```bash
# 1. 克隆项目
git clone <repository-url>
cd minimax-video-web

# 2. 运行启动脚本（自动创建虚拟环境和安装依赖）
./start.sh

# 3. 访问应用
http://localhost:8000
```

### 方式二：手动运行

```bash
# 1. 克隆项目
git clone <repository-url>
cd minimax-video-web

# 2. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 启动服务
python main.py

# 5. 访问应用
http://localhost:8000
```

### 方式三：Docker

```bash
# 使用Docker Compose
docker-compose up -d

# 或直接构建运行
docker build -t minimax-video-tool .
docker run -p 8000:8000 minimax-video-tool

# 访问应用
http://localhost:8000
```

### 测试API

```bash
# 测试基本功能
python test_api.py
```

## 主要API接口

- `POST /api/upload` - 上传图片文件
- `POST /api/generate` - 创建视频生成任务
- `GET /api/task/{task_id}` - 查询任务状态
- `WebSocket /ws/{session_id}` - 实时状态更新

## 项目结构

```
minimax-video-web/
├── main.py              # FastAPI主程序
├── static/              # 静态文件(HTML/CSS/JS)
│   ├── index.html       # 主页面
│   ├── style.css        # 样式文件
│   └── app.js           # 前端逻辑
├── uploads/             # 临时上传目录
├── requirements.txt     # Python依赖
├── Dockerfile          # Docker配置
├── docker-compose.yml  # Docker Compose配置
├── start.sh            # 启动脚本
├── test_api.py         # API测试脚本
└── README.md           # 说明文档
```

## 使用说明

### 1. 获取MiniMax API Key
- 访问 [MiniMax官网](https://www.minimaxi.com/) 注册账号
- 在控制台获取API Key

### 2. 使用工具
1. **选择API URL**: 根据网络环境选择国内或海外节点
2. **输入API Key**: 粘贴您的MiniMax API Key
3. **编写提示词**: 描述您想要生成的视频内容
4. **上传图片**: 支持单图或批量文件夹上传
5. **配置参数**: 选择模型、时长、分辨率等
6. **开始生成**: 点击按钮开始生成，实时查看进度

### 3. 支持的图片格式
- JPG/JPEG
- PNG  
- 最大20MB
- 建议分辨率: 最短边大于300px

### 4. 模型说明
- **MiniMax-Hailuo-02**: 主推模型，支持6s/10s，768P/1080P
- **I2V-01**: 图转视频基础模型
- **I2V-01-Director**: 导演模式，更好的故事性
- **I2V-01-live**: 直播模式，适合人物生成
- **S2V-01**: 主体参考模式，保持角色一致性

## 注意事项

- ⚠️ 本工具仅为测试用途，不存储用户数据
- ⚠️ API Key请妥善保管，不要泄露给他人
- ⚠️ 视频生成时间较长，请耐心等待
- ⚠️ 网络环境可能影响生成速度

## 常见问题

**Q: 视频生成失败怎么办？**
A: 检查API Key是否正确，网络是否稳定，图片格式是否支持

**Q: 可以同时生成多少个视频？**
A: 建议不超过20个并发任务，避免API限流

**Q: 生成的视频在哪里？**  
A: 生成成功后可直接在页面预览和下载，不会保存在服务器

**Q: 支持哪些浏览器？**
A: 建议使用Chrome、Firefox、Safari等现代浏览器