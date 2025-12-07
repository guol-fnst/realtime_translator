"""
字幕客户端
连接到共享服务器接收实时字幕
"""
import asyncio
import json
import sys
import threading
import tkinter as tk
from typing import Optional
import time


class SubtitleClient:
    """字幕客户端 - 连接WebSocket服务器接收字幕"""
    
    def __init__(self, server_url: str = "ws://localhost:8765"):
        self.server_url = server_url
        self._running = False
        self._ws = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        
        # GUI
        self._root: Optional[tk.Tk] = None
        self._original_label: Optional[tk.Label] = None
        self._translated_label: Optional[tk.Label] = None
        self._status_label: Optional[tk.Label] = None
        self._gpu_label: Optional[tk.Label] = None
        
        # 拖拽
        self._drag_start_x = 0
        self._drag_start_y = 0
    
    def _create_window(self):
        """创建窗口"""
        self._root = tk.Tk()
        self._root.title("实时字幕 - 客户端")
        
        # 窗口属性
        self._root.overrideredirect(True)
        self._root.attributes('-topmost', True)
        self._root.attributes('-alpha', 0.85)
        
        bg_color = '#1a1a2e'
        self._root.configure(bg=bg_color)
        
        # 主框架
        main_frame = tk.Frame(self._root, bg=bg_color, padx=15, pady=10)
        main_frame.pack(fill='both', expand=True)
        
        # 标题栏
        title_bar = tk.Frame(main_frame, bg='#16213e', height=25)
        title_bar.pack(fill='x', pady=(0, 5))
        title_bar.pack_propagate(False)
        
        title_text = tk.Label(
            title_bar,
            text="📺 字幕接收",
            bg='#16213e',
            fg='#4ecca3',
            font=('Microsoft YaHei UI', 10, 'bold')
        )
        title_text.pack(side='left', padx=5)
        
        # 关闭按钮
        close_btn = tk.Label(
            title_bar,
            text="✕",
            bg='#16213e',
            fg='#ffffff',
            font=('Arial', 12),
            cursor='hand2'
        )
        close_btn.pack(side='right', padx=5)
        close_btn.bind('<Button-1>', lambda e: self.stop())
        
        # GPU状态
        self._gpu_label = tk.Label(
            main_frame,
            text="服务器GPU: --",
            bg=bg_color,
            fg='#0f3460',
            font=('Consolas', 9),
            anchor='w'
        )
        self._gpu_label.pack(fill='x', pady=(0, 5))
        
        # 原文
        self._original_label = tk.Label(
            main_frame,
            text="",
            bg=bg_color,
            fg='#a0a0a0',
            font=('Microsoft YaHei UI', 18),
            wraplength=600,
            justify='left',
            anchor='w'
        )
        self._original_label.pack(fill='x', pady=(5, 2))
        
        # 翻译
        self._translated_label = tk.Label(
            main_frame,
            text="等待字幕...",
            bg=bg_color,
            fg='#ffffff',
            font=('Microsoft YaHei UI', 22, 'bold'),
            wraplength=600,
            justify='left',
            anchor='w'
        )
        self._translated_label.pack(fill='x', pady=(2, 5))
        
        # 状态
        self._status_label = tk.Label(
            main_frame,
            text="🔴 未连接",
            bg=bg_color,
            fg='#e94560',
            font=('Microsoft YaHei UI', 9),
            anchor='w'
        )
        self._status_label.pack(fill='x', pady=(5, 0))
        
        # 拖拽绑定
        title_bar.bind('<Button-1>', self._start_drag)
        title_bar.bind('<B1-Motion>', self._on_drag)
        title_text.bind('<Button-1>', self._start_drag)
        title_text.bind('<B1-Motion>', self._on_drag)
        
        self._root.geometry("+200+200")
        self._root.minsize(400, 100)
    
    def _start_drag(self, event):
        self._drag_start_x = event.x
        self._drag_start_y = event.y
    
    def _on_drag(self, event):
        x = self._root.winfo_x() + event.x - self._drag_start_x
        y = self._root.winfo_y() + event.y - self._drag_start_y
        self._root.geometry(f"+{x}+{y}")
    
    def _update_gui(self, msg_type: str, **kwargs):
        """更新GUI（线程安全）"""
        if not self._root:
            return
        
        def update():
            if msg_type == 'subtitle':
                if self._original_label:
                    self._original_label.config(text=kwargs.get('original', ''))
                if self._translated_label:
                    self._translated_label.config(text=kwargs.get('translated', ''))
            elif msg_type == 'status':
                if self._status_label:
                    self._status_label.config(
                        text=kwargs.get('text', ''),
                        fg=kwargs.get('color', '#4ecca3')
                    )
            elif msg_type == 'gpu':
                if self._gpu_label:
                    util = kwargs.get('utilization', 0)
                    mem_used = kwargs.get('memory_used', 0)
                    mem_total = kwargs.get('memory_total', 0)
                    self._gpu_label.config(
                        text=f"服务器GPU: {util:.0f}% | 显存: {mem_used}MB/{mem_total}MB"
                    )
        
        try:
            self._root.after(0, update)
        except:
            pass
    
    async def _connect(self):
        """连接到服务器"""
        import websockets
        
        while self._running:
            try:
                self._update_gui('status', text='🟡 正在连接...', color='#ffd700')
                
                async with websockets.connect(
                    self.server_url,
                    ping_interval=30,
                    ping_timeout=10
                ) as ws:
                    self._ws = ws
                    self._update_gui('status', text='🟢 已连接', color='#4ecca3')
                    print(f"已连接到 {self.server_url}")
                    
                    async for message in ws:
                        try:
                            data = json.loads(message)
                            msg_type = data.get('type', '')
                            
                            if msg_type == 'subtitle':
                                self._update_gui(
                                    'subtitle',
                                    original=data.get('original', ''),
                                    translated=data.get('translated', '')
                                )
                            elif msg_type == 'status':
                                if 'gpu_utilization' in data:
                                    self._update_gui(
                                        'gpu',
                                        utilization=data.get('gpu_utilization', 0),
                                        memory_used=data.get('gpu_memory_used', 0),
                                        memory_total=data.get('gpu_memory_total', 0)
                                    )
                            elif msg_type == 'welcome':
                                print(f"服务器: {data.get('message', '')}")
                                
                        except json.JSONDecodeError:
                            pass
                            
            except Exception as e:
                print(f"连接错误: {e}")
                self._update_gui('status', text='🔴 连接失败', color='#e94560')
                
                if self._running:
                    await asyncio.sleep(3)  # 3秒后重试
    
    def _run_loop(self):
        """运行事件循环"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        
        try:
            self._loop.run_until_complete(self._connect())
        finally:
            self._loop.close()
    
    def run(self):
        """运行客户端"""
        print(f"连接到: {self.server_url}")
        
        self._running = True
        
        # 启动连接线程
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        
        # 创建并运行GUI
        self._create_window()
        
        try:
            self._root.mainloop()
        except KeyboardInterrupt:
            pass
        
        self.stop()
    
    def stop(self):
        """停止客户端"""
        self._running = False
        
        if self._root:
            try:
                self._root.quit()
                self._root.destroy()
            except:
                pass
        
        print("客户端已退出")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='字幕客户端')
    parser.add_argument('--server', type=str, default='ws://localhost:8765',
                       help='服务器地址 (例如: ws://192.168.1.100:8765)')
    
    args = parser.parse_args()
    
    client = SubtitleClient(server_url=args.server)
    client.run()


if __name__ == "__main__":
    main()
