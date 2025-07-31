#!/usr/bin/env python3
"""
MiniMax Video Generation Tool
一个简洁的MiniMax视频生成工具，支持多人同时使用
"""

import asyncio
import base64
import json
import os
import time
import uuid
from typing import Dict, List, Optional
from pathlib import Path

import httpx
from fastapi import FastAPI, File, Form, UploadFile, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import uvicorn

# 配置
UPLOAD_DIR = Path("uploads")
STATIC_DIR = Path("static")
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB

# 确保目录存在
UPLOAD_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)

# 创建FastAPI应用
app = FastAPI(title="MiniMax Video Generation Tool", version="1.0.0")

# 挂载静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")

# 内存中的任务存储
tasks_storage: Dict[str, dict] = {}
websocket_connections: Dict[str, WebSocket] = {}

# 用户统计数据
user_statistics: Dict[str, dict] = {
    # session_id: {
    #     "api_key_prefix": "sk-xxx...",
    #     "request_count": 0,
    #     "success_count": 0, 
    #     "fail_count": 0,
    #     "last_active": timestamp,
    #     "created_at": timestamp,
    #     "user_ip": "x.x.x.x"
    # }
}

# API Key统计
api_key_statistics: Dict[str, dict] = {
    # "sk-xxx...": {
    #     "request_count": 0,
    #     "success_count": 0,
    #     "fail_count": 0,
    #     "last_used": timestamp,
    #     "sessions": ["session1", "session2"]
    # }
}

# 数据模型
class VideoGenerationRequest(BaseModel):
    api_url: str
    api_key: str
    prompt: str
    model: str = "MiniMax-Hailuo-02"
    prompt_optimizer: bool = True
    watermark: bool = True
    videos_per_image: int = 1
    duration: int = 6
    resolution: str = "768P"
    images: List[str] = []  # base64编码的图片

class TaskStatus(BaseModel):
    task_id: str
    status: str  # preparing, queueing, processing, success, fail
    progress: int = 0
    message: str = ""
    trace_id: str = ""
    video_url: Optional[str] = None
    error: Optional[str] = None
    created_at: float
    updated_at: float

# WebSocket连接管理器
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        print(f"WebSocket connection established for session: {session_id}")

    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            print(f"WebSocket connection closed for session: {session_id}")

    async def send_personal_message(self, message: dict, session_id: str):
        if session_id in self.active_connections:
            try:
                await self.active_connections[session_id].send_text(json.dumps(message))
            except:
                # 连接已断开，移除
                self.disconnect(session_id)

manager = ConnectionManager()

# 统计功能辅助函数
def get_api_key_prefix(api_key: str) -> str:
    """获取API Key的后缀用于统计显示"""
    if len(api_key) <= 10:
        return "..." + api_key
    return "..." + api_key[-10:]

def update_user_statistics(session_id: str, api_key: str, client_ip: str, status: str = "request"):
    """更新用户统计信息"""
    api_key_prefix = get_api_key_prefix(api_key)
    current_time = time.time()
    
    # 更新用户统计
    if session_id not in user_statistics:
        user_statistics[session_id] = {
            "api_key_prefix": api_key_prefix,
            "request_count": 0,
            "success_count": 0,
            "fail_count": 0,
            "last_active": current_time,
            "created_at": current_time,
            "user_ip": client_ip
        }
    
    user_stats = user_statistics[session_id]
    user_stats["last_active"] = current_time
    
    if status == "request":
        user_stats["request_count"] += 1
    elif status == "success":
        user_stats["success_count"] += 1
    elif status == "fail":
        user_stats["fail_count"] += 1
    
    # 更新API Key统计
    if api_key_prefix not in api_key_statistics:
        api_key_statistics[api_key_prefix] = {
            "request_count": 0,
            "success_count": 0,
            "fail_count": 0,
            "last_used": current_time,
            "sessions": []
        }
    
    api_stats = api_key_statistics[api_key_prefix]
    api_stats["last_used"] = current_time
    
    if session_id not in api_stats["sessions"]:
        api_stats["sessions"].append(session_id)
    
    if status == "request":
        api_stats["request_count"] += 1
    elif status == "success":
        api_stats["success_count"] += 1
    elif status == "fail":
        api_stats["fail_count"] += 1

def cleanup_old_data():
    """清理超过1小时未活跃的用户数据"""
    current_time = time.time()
    one_hour_ago = current_time - 3600  # 1小时
    
    # 清理用户统计
    to_remove_users = []
    for session_id, stats in user_statistics.items():
        if stats["last_active"] < one_hour_ago:
            to_remove_users.append(session_id)
    
    for session_id in to_remove_users:
        del user_statistics[session_id]
        # 清理对应的任务数据
        to_remove_tasks = []
        for task_id, task_data in tasks_storage.items():
            # 这里需要根据session_id匹配任务，暂时清理旧任务
            if task_data.get("created_at", 0) < one_hour_ago:
                to_remove_tasks.append(task_id)
        
        for task_id in to_remove_tasks:
            del tasks_storage[task_id]
    
    # 清理API Key统计中的无效sessions
    for api_key, stats in api_key_statistics.items():
        stats["sessions"] = [s for s in stats["sessions"] if s in user_statistics]

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """返回主页面"""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    else:
        return HTMLResponse("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>MiniMax Video Tool</title>
        </head>
        <body>
            <h1>MiniMax Video Generation Tool</h1>
            <p>前端文件未找到，请检查 static/index.html 文件是否存在。</p>
        </body>
        </html>
        """)

@app.post("/api/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """上传图片文件"""
    uploaded_files = []
    
    for file in files:
        if not file.content_type.startswith('image/'):
            continue
            
        # 检查文件大小
        contents = await file.read()
        if len(contents) > MAX_FILE_SIZE:
            continue
            
        # 生成唯一文件名
        file_id = str(uuid.uuid4())
        file_ext = Path(file.filename).suffix
        file_path = UPLOAD_DIR / f"{file_id}{file_ext}"
        
        # 保存文件
        with open(file_path, "wb") as f:
            f.write(contents)
            
        # 转换为base64
        base64_data = base64.b64encode(contents).decode()
        mime_type = file.content_type or "image/jpeg"
        data_url = f"data:{mime_type};base64,{base64_data}"
        
        uploaded_files.append({
            "file_id": file_id,
            "filename": file.filename,
            "size": len(contents),
            "data_url": data_url
        })
    
    return JSONResponse({
        "success": True,
        "files": uploaded_files
    })

@app.post("/api/generate")
async def generate_videos(request: VideoGenerationRequest, req: Request):
    """创建视频生成任务"""
    session_id = str(uuid.uuid4())
    tasks = []
    
    # 获取客户端IP
    client_ip = req.client.host if req.client else "unknown"
    
    # 更新统计信息
    update_user_statistics(session_id, request.api_key, client_ip, "request")
    
    # 处理任务创建逻辑
    if request.images and len(request.images) > 0:
        # 有图片的情况：为每张图片创建任务
        for i, image_data in enumerate(request.images):
            for j in range(request.videos_per_image):
                task_id = str(uuid.uuid4())
                task = TaskStatus(
                    task_id=task_id,
                    status="preparing",
                    message="准备生成视频...",
                    created_at=time.time(),
                    updated_at=time.time()
                )
                
                tasks_storage[task_id] = task.model_dump()
                tasks.append(task_id)
                
                # 异步开始生成视频
                asyncio.create_task(
                    process_video_generation(
                        task_id, request, image_data, session_id
                    )
                )
    else:
        # 只有提示词没有图片的情况：创建纯文本视频生成任务
        for j in range(request.videos_per_image):
            task_id = str(uuid.uuid4())
            task = TaskStatus(
                task_id=task_id,
                status="preparing", 
                message="准备生成视频...",
                created_at=time.time(),
                updated_at=time.time()
            )
            
            tasks_storage[task_id] = task.model_dump()
            tasks.append(task_id)
            
            # 异步开始生成视频（无图片）
            asyncio.create_task(
                process_video_generation(
                    task_id, request, None, session_id
                )
            )
    
    return JSONResponse({
        "success": True,
        "session_id": session_id,
        "task_ids": tasks
    })

@app.get("/api/task/{task_id}")
async def get_task_status(task_id: str):
    """获取任务状态"""
    if task_id not in tasks_storage:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    
    return JSONResponse(tasks_storage[task_id])

@app.get("/admin", response_class=HTMLResponse)
async def admin_page():
    """管理员页面"""
    admin_html = """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Admin - MiniMax Video Tool</title>
        <link rel="icon" type="image/png" href="/static/mm_logo.png">
        <link rel="shortcut icon" type="image/png" href="/static/mm_logo.png">
        <link rel="apple-touch-icon" href="/static/mm_logo.png">
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            .refresh-animation {
                animation: spin 1s linear infinite;
            }
            @keyframes spin {
                from { transform: rotate(0deg); }
                to { transform: rotate(360deg); }
            }
        </style>
    </head>
    <body class="bg-gray-100 min-h-screen">
        <div class="container mx-auto px-4 py-6">
            <div class="flex justify-between items-center mb-6">
                <h1 class="text-3xl font-bold text-gray-900">🔧 Admin Dashboard</h1>
                <button id="refreshBtn" onclick="refreshData()" class="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">
                    <span id="refreshIcon">🔄</span> 刷新数据
                </button>
            </div>
            
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <!-- 在线用户统计 -->
                <div class="bg-white rounded-lg shadow-md p-6">
                    <h2 class="text-xl font-semibold mb-4">📊 在线用户统计</h2>
                    <div id="userStats" class="space-y-4">
                        <div class="text-center text-gray-500">加载中...</div>
                    </div>
                </div>
                
                <!-- API Key统计 -->
                <div class="bg-white rounded-lg shadow-md p-6">
                    <h2 class="text-xl font-semibold mb-4">🔑 API Key统计</h2>
                    <div id="apiKeyStats" class="space-y-4">
                        <div class="text-center text-gray-500">加载中...</div>
                    </div>
                </div>
                
                <!-- 系统信息 -->
                <div class="bg-white rounded-lg shadow-md p-6 lg:col-span-2">
                    <h2 class="text-xl font-semibold mb-4">💾 系统信息</h2>
                    <div id="systemInfo" class="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <div class="text-center text-gray-500">加载中...</div>
                    </div>
                </div>
            </div>
        </div>

        <script>
            async function fetchAdminData() {
                try {
                    const response = await fetch('/api/admin/stats');
                    const data = await response.json();
                    updateUI(data);
                } catch (error) {
                    console.error('获取数据失败:', error);
                }
            }

            function updateUI(data) {
                // 更新用户统计
                const userStatsDiv = document.getElementById('userStats');
                if (data.users && data.users.length > 0) {
                    userStatsDiv.innerHTML = data.users.map(user => `
                        <div class="border-l-4 border-blue-500 pl-4 py-2">
                            <div class="flex justify-between items-center">
                                <div>
                                    <div class="font-medium">用户 ${user.api_key_prefix}</div>
                                    <div class="text-sm text-gray-600">会话: ${user.session_id.substring(0, 8)}...</div>
                                    <div class="text-sm text-gray-600">IP: ${user.user_ip}</div>
                                </div>
                                <div class="text-right">
                                    <div class="text-sm">请求: ${user.request_count}</div>
                                    <div class="text-sm text-green-600">成功: ${user.success_count}</div>
                                    <div class="text-sm text-red-600">失败: ${user.fail_count}</div>
                                    <div class="text-xs text-gray-500">最后活跃: ${formatTime(user.last_active)}</div>
                                </div>
                            </div>
                        </div>
                    `).join('');
                } else {
                    userStatsDiv.innerHTML = '<div class="text-center text-gray-500">暂无在线用户</div>';
                }

                // 更新API Key统计
                const apiKeyStatsDiv = document.getElementById('apiKeyStats');
                if (data.api_keys && data.api_keys.length > 0) {
                    apiKeyStatsDiv.innerHTML = data.api_keys.map(key => `
                        <div class="border-l-4 border-green-500 pl-4 py-2">
                            <div class="flex justify-between items-center">
                                <div>
                                    <div class="font-medium">API Key ${key.api_key_prefix}</div>
                                    <div class="text-sm text-gray-600">活跃会话: ${key.sessions.length}</div>
                                </div>
                                <div class="text-right">
                                    <div class="text-sm">请求: ${key.request_count}</div>
                                    <div class="text-sm text-green-600">成功: ${key.success_count}</div>
                                    <div class="text-sm text-red-600">失败: ${key.fail_count}</div>
                                    <div class="text-xs text-gray-500">最后使用: ${formatTime(key.last_used)}</div>
                                </div>
                            </div>
                        </div>
                    `).join('');
                } else {
                    apiKeyStatsDiv.innerHTML = '<div class="text-center text-gray-500">暂无API Key使用记录</div>';
                }

                // 更新系统信息
                const systemInfoDiv = document.getElementById('systemInfo');
                systemInfoDiv.innerHTML = `
                    <div class="text-center">
                        <div class="text-2xl font-bold text-blue-600">${data.system.total_users}</div>
                        <div class="text-sm text-gray-600">总用户数</div>
                    </div>
                    <div class="text-center">
                        <div class="text-2xl font-bold text-green-600">${data.system.total_tasks}</div>
                        <div class="text-sm text-gray-600">总任务数</div>
                    </div>
                    <div class="text-center">
                        <div class="text-2xl font-bold text-purple-600">${data.system.active_websockets}</div>
                        <div class="text-sm text-gray-600">活跃连接</div>
                    </div>
                    <div class="text-center">
                        <div class="text-2xl font-bold text-orange-600">${data.system.total_api_keys}</div>
                        <div class="text-sm text-gray-600">使用的Key</div>
                    </div>
                `;
            }

            function formatTime(timestamp) {
                const date = new Date(timestamp * 1000);
                return date.toLocaleTimeString('zh-CN');
            }

            function refreshData() {
                const refreshIcon = document.getElementById('refreshIcon');
                refreshIcon.classList.add('refresh-animation');
                
                fetchAdminData().finally(() => {
                    setTimeout(() => {
                        refreshIcon.classList.remove('refresh-animation');
                    }, 1000);
                });
            }

            // 页面加载时获取数据
            document.addEventListener('DOMContentLoaded', fetchAdminData);
            
            // 每30秒自动刷新
            setInterval(fetchAdminData, 30000);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=admin_html)

@app.get("/api/admin/stats")
async def get_admin_stats():
    """获取管理员统计数据"""
    # 清理旧数据
    cleanup_old_data()
    
    # 准备用户统计数据
    users_data = []
    for session_id, stats in user_statistics.items():
        users_data.append({
            "session_id": session_id,
            "api_key_prefix": stats["api_key_prefix"],
            "request_count": stats["request_count"],
            "success_count": stats["success_count"],
            "fail_count": stats["fail_count"],
            "last_active": stats["last_active"],
            "created_at": stats["created_at"],
            "user_ip": stats["user_ip"]
        })
    
    # 准备API Key统计数据
    api_keys_data = []
    for api_key_prefix, stats in api_key_statistics.items():
        api_keys_data.append({
            "api_key_prefix": api_key_prefix,
            "request_count": stats["request_count"],
            "success_count": stats["success_count"],
            "fail_count": stats["fail_count"],
            "last_used": stats["last_used"],
            "sessions": stats["sessions"]
        })
    
    return JSONResponse({
        "users": users_data,
        "api_keys": api_keys_data,
        "system": {
            "total_users": len(user_statistics),
            "total_tasks": len(tasks_storage),
            "active_websockets": len(manager.active_connections),
            "total_api_keys": len(api_key_statistics)
        }
    })

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket连接端点"""
    await manager.connect(websocket, session_id)
    try:
        while True:
            # 接收消息保持连接活跃
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception:
        manager.disconnect(session_id)

async def process_video_generation(task_id: str, request: VideoGenerationRequest, 
                                 image_data: Optional[str], session_id: str):
    """处理单个视频生成任务"""
    try:
        # 更新任务状态
        await update_task_status(task_id, "queueing", "提交任务中...", session_id)
        
        # 准备API请求数据
        if request.model == 'S2V-01':
            # S2V-01模型使用subject_reference参数（必须有图片+提示词）
            payload = {
                "model": request.model,
                "prompt": request.prompt,
                "prompt_optimizer": request.prompt_optimizer,
                "subject_reference": [{
                    "type": "character",
                    "image": [image_data]
                }]
            }
            # S2V-01不支持duration和resolution参数
        else:
            # MiniMax-Hailuo-02模型
            payload = {
                "prompt": request.prompt,
                "model": request.model,
                "duration": request.duration,
                "prompt_optimizer": request.prompt_optimizer
            }
            
            # 如果有图片，添加first_frame_image参数
            if image_data:
                payload["first_frame_image"] = image_data
                
            if request.watermark:
                payload["watermark"] = "hailuo"
                
            # MiniMax-Hailuo-02支持分辨率设置
            if request.duration == 6:
                payload["resolution"] = request.resolution
            else:
                payload["resolution"] = "768P"
        
        # 发送生成请求
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{request.api_url}/video_generation",
                headers={
                    "Authorization": f"Bearer {request.api_key}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            
            # 获取Trace-ID
            trace_id = (response.headers.get('X-Minimax-Trace-Id') or 
                       response.headers.get('x-minimax-trace-id') or 
                       response.headers.get('Trace-ID') or 
                       response.headers.get('trace-id') or 
                       '未获取到')
            
            # 更新任务中的trace_id
            if task_id in tasks_storage:
                tasks_storage[task_id]["trace_id"] = trace_id
            
            if not response.is_success:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get('base_resp', {}).get('status_msg', f'API错误: {response.status_code}')
                await update_task_status(task_id, "fail", f"生成失败: {error_msg}", session_id, error=error_msg)
                return
            
            data = response.json()
            video_task_id = data.get('task_id')
            
            if not video_task_id:
                await update_task_status(task_id, "fail", "未获取到任务ID", session_id)
                return
        
        # 轮询任务状态
        await update_task_status(task_id, "queueing", f"队列中... (ID: {video_task_id})", session_id)
        
        start_time = time.time()
        
        while True:
            await asyncio.sleep(20)  # 等待20秒后查询
            
            async with httpx.AsyncClient(timeout=30) as client:
                status_response = await client.get(
                    f"{request.api_url}/query/video_generation",
                    headers={"Authorization": f"Bearer {request.api_key}"},
                    params={"task_id": video_task_id}
                )
                
                if not status_response.is_success:
                    await update_task_status(task_id, "fail", "查询状态失败", session_id)
                    return
                
                status_data = status_response.json()
                status = status_data.get('status')
                elapsed_time = int(time.time() - start_time)
                
                if status == 'Queueing':
                    await update_task_status(task_id, "queueing", f"队列中... (用时: {elapsed_time}秒)", session_id)
                elif status == 'Processing':
                    await update_task_status(task_id, "processing", f"生成中... (用时: {elapsed_time}秒)", session_id)
                elif status == 'Success':
                    file_id = status_data.get('file_id')
                    if file_id:
                        video_url = await get_video_download_url(request.api_url, request.api_key, file_id)
                        await update_task_status(task_id, "success", f"生成成功 (用时: {elapsed_time}秒)", session_id, video_url=video_url)
                    else:
                        await update_task_status(task_id, "fail", "获取文件ID失败", session_id)
                    break
                elif status == 'Fail':
                    await update_task_status(task_id, "fail", f"生成失败 (用时: {elapsed_time}秒)", session_id)
                    break
                    
    except Exception as e:
        await update_task_status(task_id, "fail", f"处理错误: {str(e)}", session_id, error=str(e))

async def get_video_download_url(api_url: str, api_key: str, file_id: str) -> Optional[str]:
    """获取视频下载链接"""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{api_url}/files/retrieve",
                headers={"Authorization": f"Bearer {api_key}"},
                params={"file_id": file_id}
            )
            
            if response.is_success:
                data = response.json()
                return data.get('file', {}).get('download_url')
    except:
        pass
    return None

async def update_task_status(task_id: str, status: str, message: str, session_id: str, 
                           video_url: Optional[str] = None, error: Optional[str] = None):
    """更新任务状态并通过WebSocket通知"""
    if task_id in tasks_storage:
        tasks_storage[task_id].update({
            "status": status,
            "message": message,
            "updated_at": time.time()
        })
        
        if video_url:
            tasks_storage[task_id]["video_url"] = video_url
        if error:
            tasks_storage[task_id]["error"] = error
            
        # 更新统计信息
        if session_id in user_statistics:
            user_stat = user_statistics[session_id]
            if status == "success":
                user_stat["success_count"] += 1
                # 更新API Key统计
                api_key_prefix = user_stat["api_key_prefix"]
                if api_key_prefix in api_key_statistics:
                    api_key_statistics[api_key_prefix]["success_count"] += 1
            elif status == "fail":
                user_stat["fail_count"] += 1
                # 更新API Key统计
                api_key_prefix = user_stat["api_key_prefix"]
                if api_key_prefix in api_key_statistics:
                    api_key_statistics[api_key_prefix]["fail_count"] += 1
            
        # 通过WebSocket发送更新
        await manager.send_personal_message({
            "type": "task_update",
            "task_id": task_id,
            "data": tasks_storage[task_id]
        }, session_id)

# 后台清理任务
async def background_cleanup_task():
    """后台定期清理任务"""
    while True:
        try:
            await asyncio.sleep(300)  # 每5分钟清理一次
            cleanup_old_data()
            print(f"🧹 清理完成: 当前用户数 {len(user_statistics)}, 任务数 {len(tasks_storage)}")
        except Exception as e:
            print(f"清理任务错误: {e}")

# FastAPI事件处理
@app.on_event("startup")
async def startup_event():
    """应用启动时的事件"""
    print("🎬 启动 MiniMax Video Generation Tool")
    print("📍 访问地址: http://localhost:5211")
    print("🔧 管理员页面: http://localhost:5211/admin")
    
    # 启动后台清理任务
    asyncio.create_task(background_cleanup_task())
    print("🧹 后台清理任务已启动")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5211)