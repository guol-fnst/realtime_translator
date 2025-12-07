"""
共享服务器模块
WebSocket服务器，允许其他用户连接查看实时字幕
"""
import asyncio
import json
import threading
from typing import Set, Optional, Callable
from dataclasses import dataclass, asdict
import time


@dataclass
class SubtitleMessage:
    """字幕消息"""
    type: str = "subtitle"
    original: str = ""  # 原文（日语）
    translated: str = ""  # 翻译（中文）
    timestamp: float = 0  # 时间戳


class SharingServer:
    """WebSocket共享服务器"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8765):
        """
        初始化共享服务器
        
        Args:
            host: 监听地址
            port: 监听端口
        """
        self.host = host
        self.port = port
        self._clients: Set = set()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._server = None
        
    async def _handler(self, websocket):
        """处理WebSocket连接"""
        self._clients.add(websocket)
        client_ip = websocket.remote_address[0] if websocket.remote_address else "unknown"
        print(f"客户端连接: {client_ip} (当前连接数: {len(self._clients)})")
        
        try:
            # 发送欢迎消息
            welcome = {
                "type": "welcome",
                "message": "已连接到实时字幕服务器",
                "client_count": len(self._clients)
            }
            await websocket.send(json.dumps(welcome, ensure_ascii=False))
            
            # 保持连接并处理心跳
            async for message in websocket:
                try:
                    data = json.loads(message)
                    if data.get("type") == "ping":
                        await websocket.send(json.dumps({"type": "pong"}))
                except json.JSONDecodeError:
                    pass
                    
        except Exception as e:
            print(f"客户端异常: {e}")
        finally:
            self._clients.discard(websocket)
            print(f"客户端断开: {client_ip} (当前连接数: {len(self._clients)})")
    
    async def _broadcast(self, message: str):
        """广播消息给所有客户端"""
        if not self._clients:
            return
        
        # 复制客户端列表以避免并发修改
        clients = list(self._clients)
        for client in clients:
            try:
                await client.send(message)
            except Exception:
                self._clients.discard(client)
    
    def broadcast_subtitle(self, original: str, translated: str):
        """
        广播字幕消息
        
        Args:
            original: 原文（日语）
            translated: 翻译（中文）
        """
        if not self._running or not self._loop:
            return
        
        msg = SubtitleMessage(
            original=original,
            translated=translated,
            timestamp=time.time()
        )
        
        message = json.dumps(asdict(msg), ensure_ascii=False)
        
        # 在事件循环中调度广播
        asyncio.run_coroutine_threadsafe(
            self._broadcast(message),
            self._loop
        )
    
    def broadcast_status(self, status: dict):
        """广播状态消息"""
        if not self._running or not self._loop:
            return
        
        message = json.dumps({
            "type": "status",
            **status
        }, ensure_ascii=False)
        
        asyncio.run_coroutine_threadsafe(
            self._broadcast(message),
            self._loop
        )
    
    async def _run_server(self):
        """运行服务器"""
        try:
            import websockets
            
            async with websockets.serve(
                self._handler,
                self.host,
                self.port,
                ping_interval=30,
                ping_timeout=10
            ) as server:
                self._server = server
                print(f"WebSocket共享服务器启动: ws://{self.host}:{self.port}")
                
                # 等待直到停止
                while self._running:
                    await asyncio.sleep(1)
                    
        except ImportError:
            print("错误: 请安装 websockets: pip install websockets")
        except Exception as e:
            print(f"服务器错误: {e}")
    
    def _run_loop(self):
        """在独立线程中运行事件循环"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        
        try:
            self._loop.run_until_complete(self._run_server())
        finally:
            self._loop.close()
    
    def start(self):
        """启动服务器"""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
    
    def stop(self):
        """停止服务器"""
        self._running = False
        
        if self._thread:
            self._thread.join(timeout=3)
            self._thread = None
        
        print("共享服务器已停止")
    
    @property
    def client_count(self) -> int:
        """当前连接的客户端数量"""
        return len(self._clients)
    
    def get_connection_info(self) -> str:
        """获取连接信息"""
        import socket
        try:
            # 获取本机IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except:
            local_ip = "localhost"
        
        return f"ws://{local_ip}:{self.port}"


# 测试代码
if __name__ == "__main__":
    import time
    
    server = SharingServer(port=8765)
    server.start()
    
    print(f"连接地址: {server.get_connection_info()}")
    print("等待客户端连接...")
    
    try:
        count = 0
        while True:
            time.sleep(3)
            count += 1
            # 模拟发送字幕
            server.broadcast_subtitle(
                f"テスト {count}",
                f"测试 {count}"
            )
            print(f"发送测试字幕 {count}, 客户端数: {server.client_count}")
    except KeyboardInterrupt:
        pass
    
    server.stop()
