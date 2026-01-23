"""
字幕显示模块
透明悬浮窗口显示实时翻译字幕
"""
import tkinter as tk
from tkinter import font as tkfont
from tkinter import filedialog
import threading
import queue
from typing import Optional, Tuple, List
from dataclasses import dataclass
import time
import datetime


@dataclass
class SubtitleContent:
    """字幕内容"""
    original: str = ""  # 原文
    translated: str = ""  # 翻译


class SubtitleOverlay:
    """透明字幕悬浮窗"""
    
    def __init__(self, 
                 font_size: int = 24,
                 bg_opacity: float = 0.7,
                 show_original: bool = True,
                 position: Tuple[int, int] = (100, 100)):
        """
        初始化字幕窗口
        
        Args:
            font_size: 字体大小
            bg_opacity: 背景透明度 (0-1)
            show_original: 是否显示原文
            position: 初始位置 (x, y)
        """
        self.font_size = font_size
        self.bg_opacity = bg_opacity
        self.show_original = show_original
        self.position = position
        
        self._root: Optional[tk.Tk] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._message_queue: queue.Queue = queue.Queue()
        self._subtitle_history: List[Tuple[str, str, str]] = []  # (timestamp, original, translated)
        
        # UI元素
        self._original_label: Optional[tk.Label] = None
        self._translated_label: Optional[tk.Label] = None

        self._status_label: Optional[tk.Label] = None
        
        # 拖拽相关
        self._drag_start_x = 0
        self._drag_start_y = 0
    
    def _create_window(self):
        """创建窗口"""
        self._root = tk.Tk()
        self._root.title("实时字幕")
        
        # 设置窗口属性
        self._root.overrideredirect(True)  # 无边框
        self._root.attributes('-topmost', True)  # 置顶
        self._root.attributes('-alpha', self.bg_opacity)  # 透明度
        
        # 设置背景色
        bg_color = '#1a1a2e'
        self._root.configure(bg=bg_color)
        
        # 创建主框架
        main_frame = tk.Frame(self._root, bg=bg_color, padx=15, pady=10)
        main_frame.pack(fill='both', expand=True)
        
        # 标题栏（用于拖拽）
        title_bar = tk.Frame(main_frame, bg='#16213e', height=25)
        title_bar.pack(fill='x', pady=(0, 5))
        title_bar.pack_propagate(False)
        
        title_text = tk.Label(
            title_bar, 
            text="🎙️ 实时字幕",
            bg='#16213e',
            fg='#e94560',
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
        
        # 保存按钮
        save_btn = tk.Label(
            title_bar,
            text="💾",
            bg='#16213e',
            fg='#ffffff',
            font=('Segoe UI Emoji', 10),
            cursor='hand2'
        )
        save_btn.pack(side='right', padx=5)
        save_btn.bind('<Button-1>', lambda e: self.save_subtitles())
        
        # 绑定提示
        self._create_tooltip(save_btn, "保存字幕记录")
        

        
        # 原文标签
        if self.show_original:
            self._original_label = tk.Label(
                main_frame,
                text="",
                bg=bg_color,
                fg='#a0a0a0',
                font=('Microsoft YaHei UI', self.font_size - 4),
                wraplength=600,
                justify='left',
                anchor='w'
            )
            self._original_label.pack(fill='x', pady=(5, 2))
        
        # 翻译标签
        self._translated_label = tk.Label(
            main_frame,
            text="等待语音输入...",
            bg=bg_color,
            fg='#ffffff',
            font=('Microsoft YaHei UI', self.font_size, 'bold'),
            wraplength=600,
            justify='left',
            anchor='w'
        )
        self._translated_label.pack(fill='x', pady=(2, 5))
        
        # 状态栏
        self._status_label = tk.Label(
            main_frame,
            text="🟢 就绪",
            bg=bg_color,
            fg='#4ecca3',
            font=('Microsoft YaHei UI', 9),
            anchor='w'
        )
        self._status_label.pack(fill='x', pady=(5, 0))
        
        # 绑定拖拽事件
        title_bar.bind('<Button-1>', self._start_drag)
        title_bar.bind('<B1-Motion>', self._on_drag)
        title_text.bind('<Button-1>', self._start_drag)
        title_text.bind('<B1-Motion>', self._on_drag)
        
        # 设置初始位置
        self._root.geometry(f"+{self.position[0]}+{self.position[1]}")
        
        # 设置最小尺寸
        self._root.minsize(400, 100)
    
    def _start_drag(self, event):
        """开始拖拽"""
        self._drag_start_x = event.x
        self._drag_start_y = event.y
    
    def _on_drag(self, event):
        """拖拽中"""
        x = self._root.winfo_x() + event.x - self._drag_start_x
        y = self._root.winfo_y() + event.y - self._drag_start_y
        self._root.geometry(f"+{x}+{y}")
    
    def _process_messages(self):
        """处理消息队列"""
        try:
            while True:
                msg = self._message_queue.get_nowait()
                
                if msg.get('type') == 'subtitle':
                    if self._original_label and msg.get('original'):
                        self._original_label.config(text=msg['original'])
                    if self._translated_label and msg.get('translated'):
                        self._translated_label.config(text=msg['translated'])
                        

                        
                elif msg.get('type') == 'status':
                    if self._status_label:
                        self._status_label.config(text=msg.get('text', ''))
                        
        except queue.Empty:
            pass
        
        if self._running and self._root:
            self._root.after(100, self._process_messages)
    
    def update_subtitle(self, original: str, translated: str):
        """
        更新字幕内容
        
        Args:
            original: 原文
            translated: 翻译
        """
        self._message_queue.put({
            'type': 'subtitle',
            'original': original,
            'translated': translated
        })
    

    
    def update_status(self, text: str):
        """更新状态文本"""
        self._message_queue.put({
            'type': 'status',
            'text': text
        })
    
    def update_translated_streaming(self, text: str):
        """
        流式更新翻译文本（用于逐字显示）
        
        Args:
            text: 当前已生成的完整翻译文本
        """
        self._message_queue.put({
            'type': 'subtitle',
            'translated': text + "▌"  # 添加光标效果
        })
    
    def update_original_streaming(self, text: str):
        self._message_queue.put({
            'type': 'subtitle',
            'original': text + "▌"
        })
    
    def finalize_translated(self, original: str, translated: str):
        """
        完成流式翻译，移除光标
        
        Args:
            original: 原文
            translated: 完整翻译
        """
        # 记录历史
        timestamp = time.strftime("%H:%M:%S")
        self._subtitle_history.append((timestamp, original, translated))
        
        self._message_queue.put({
            'type': 'subtitle',
            'original': original,
            'translated': translated
        })
    
    def save_subtitles(self):
        """保存字幕到文件"""
        if not self._subtitle_history:
            return
            
        filename = f"translations_{time.strftime('%Y%m%d_%H%M%S')}.txt"
        
        filepath = filedialog.asksaveasfilename(
            initialfile=filename,
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        
        if filepath:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(f"翻译记录 - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("-" * 50 + "\n\n")
                    
                    for timestamp, original, translated in self._subtitle_history:
                        f.write(f"[{timestamp}]\n")
                        f.write(f"原文: {original}\n")
                        f.write(f"译文: {translated}\n")
                        f.write("-" * 30 + "\n")
                
                print(f"字幕已保存: {filepath}")
            except Exception as e:
                print(f"保存失败: {e}")

    def _create_tooltip(self, widget, text):
        """创建简单的提示框"""
        def enter(event):
            x, y, _, _ = widget.bbox("insert")
            x += widget.winfo_rootx() + 25
            y += widget.winfo_rooty() + 25
            
            # 创建提示窗口
            tw = tk.Toplevel(widget)
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{x}+{y}")
            
            label = tk.Label(tw, text=text, justify='left',
                           background="#ffffe0", relief='solid', borderwidth=1,
                           font=("tahoma", "8", "normal"))
            label.pack(ipadx=1)
            
            widget.tooltip_window = tw
            
        def leave(event):
            if hasattr(widget, 'tooltip_window'):
                widget.tooltip_window.destroy()
                
        widget.bind('<Enter>', enter)
        widget.bind('<Leave>', leave)

    def _run_mainloop(self):
        """运行主循环"""
        self._create_window()
        self._root.after(100, self._process_messages)
        
        try:
            self._root.mainloop()
        except Exception as e:
            print(f"窗口错误: {e}")
    
    def start(self):
        """启动字幕窗口（在后台线程）"""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run_mainloop, daemon=True)
        self._thread.start()
    
    def start_blocking(self):
        """启动字幕窗口（阻塞主线程）"""
        self._running = True
        self._run_mainloop()
    
    def stop(self):
        """停止字幕窗口"""
        self._running = False
        
        if self._root:
            try:
                self._root.quit()
                self._root.destroy()
            except:
                pass
            self._root = None
        
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None


# 测试代码
if __name__ == "__main__":
    overlay = SubtitleOverlay(
        font_size=22,
        bg_opacity=0.85,
        show_original=True
    )
    
    overlay.start()
    
    # 模拟字幕更新
    test_subtitles = [
        ("こんにちは、皆さん", "大家好"),
        ("今日の会議を始めましょう", "让我们开始今天的会议"),
        ("この問題について話し合いましょう", "让我们讨论一下这个问题"),
        ("ありがとうございます", "谢谢"),
    ]
    
    import time
    time.sleep(1)
    
    for i, (jp, cn) in enumerate(test_subtitles):
        overlay.update_subtitle(jp, cn)

        overlay.update_status(f"🟢 正在翻译... ({i+1}/{len(test_subtitles)})")
        time.sleep(3)
    
    overlay.update_status("🟢 就绪")
    
    print("按 Enter 退出...")
    input()
    overlay.stop()
