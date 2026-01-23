"""
实时日语转中文字幕翻译系统
主程序入口
"""
import sys
import os
import threading
import time
import argparse
from typing import Optional

# 添加src目录到路径（支持从不同目录运行）
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# 也添加父目录（如果从src目录运行）
parent_dir = os.path.dirname(current_dir)
src_dir = os.path.join(parent_dir, 'src')
if os.path.exists(src_dir) and src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from config import get_config, save_config
from audio_capture import AudioCapture
from speech_recognition import SpeechRecognizer
from translator import Translator
from subtitle_overlay import SubtitleOverlay
from sharing_server import SharingServer



class TranslatorApp:
    """主应用程序"""
    
    def __init__(self):
        self.config = get_config()
        
        # 组件
        self.audio_capture: Optional[AudioCapture] = None
        self.speech_recognizer: Optional[SpeechRecognizer] = None
        self.translator: Optional[Translator] = None
        self.subtitle_overlay: Optional[SubtitleOverlay] = None
        self.sharing_server: Optional[SharingServer] = None

        
        # 状态
        self._running = False
        self._processing = False
        self._metrics = {
            'rec_times': [],
            'fail_count': 0,
            'success_count': 0,
            'durations': []
        }
        
    def _init_components(self):
        """初始化组件"""
        print("正在初始化组件...")
        
        # 语音识别器
        self.speech_recognizer = SpeechRecognizer()
        
        # 翻译器
        self.translator = Translator()
        
        # 音频捕获
        self.audio_capture = AudioCapture(
            sample_rate=self.config.sample_rate,
            chunk_duration=self.config.chunk_duration,
            silence_threshold=self.config.silence_threshold,
            silence_duration=self.config.silence_duration,
            max_buffer_duration=self.config.max_buffer_duration,
            min_speech_duration=self.config.min_speech_duration,
            use_vad=self.config.vad_enabled,
            vad_aggressiveness=self.config.vad_aggressiveness,
            enable_normalization=self.config.enable_normalization,
            normalization_target=self.config.normalization_target
        )
        
        # 字幕窗口
        self.subtitle_overlay = SubtitleOverlay(
            font_size=self.config.subtitle_font_size,
            bg_opacity=self.config.subtitle_bg_opacity,
            show_original=self.config.show_original,
            position=(self.config.subtitle_position_x, self.config.subtitle_position_y)
        )
        
        # 共享服务器
        if self.config.sharing_enabled:
            self.sharing_server = SharingServer(port=self.config.sharing_port)
        

    
    def _on_audio(self, audio_data: bytes):
        """音频数据回调"""
        if not self._running or self._processing:
            return
        
        self._processing = True
        
        try:
            # 更新状态
            self.subtitle_overlay.update_status("🔄 正在识别...")
            import io, wave
            try:
                b = io.BytesIO(audio_data)
                with wave.open(b, 'rb') as w:
                    frames = w.getnframes()
                    rate = w.getframerate()
                    duration = frames / max(rate, 1)
                self._metrics['durations'].append(duration)
                if len(self._metrics['durations']) > 100:
                    self._metrics['durations'] = self._metrics['durations'][-100:]
            except Exception:
                pass
            t0 = time.time()
            
            # 语音识别
            text, language = self.speech_recognizer.transcribe(audio_data)
            t1 = time.time()
            self._metrics['rec_times'].append(int((t1 - t0) * 1000))
            if len(self._metrics['rec_times']) > 100:
                self._metrics['rec_times'] = self._metrics['rec_times'][-100:]
            
            if text:
                print(f"[识别] {text}")
                self._metrics['success_count'] += 1
                
                # 显示原文
                if self.subtitle_overlay:
                    self.subtitle_overlay.update_subtitle(text, "翻译中...")
                
                # 更新状态
                self.subtitle_overlay.update_status("🔄 正在翻译...")
                
                # 流式翻译回调
                def on_token(token, full_text):
                    if self.subtitle_overlay:
                        self.subtitle_overlay.update_translated_streaming(full_text)
                
                # 使用流式翻译
                translated = self.translator.translate_stream(text, on_token=on_token)
                
                if translated:
                    print(f"[翻译] {translated}")
                    
                    # 完成翻译，移除光标
                    self.subtitle_overlay.finalize_translated(text, translated)
                    
                    # 广播给其他客户端
                    if self.sharing_server:
                        self.sharing_server.broadcast_subtitle(text, translated)
                    
                    self.subtitle_overlay.update_status("🟢 就绪")
                else:
                    self.subtitle_overlay.update_status("⚠️ 翻译失败")
            else:
                self._metrics['fail_count'] += 1
                self.subtitle_overlay.update_status("🟢 就绪")
                
        except Exception as e:
            print(f"处理错误: {e}")
            self.subtitle_overlay.update_status(f"❌ 错误: {str(e)[:30]}")
        finally:
            try:
                self._adapt_params()
            except Exception:
                pass
            self._processing = False
    

    
    def test_connections(self) -> bool:
        """测试与服务器的连接"""
        print("\n=== 测试服务器连接 ===")
        print(f"服务器地址: {self.config.server_url}")
        
        all_ok = True
        
        # 测试语音识别
        print("\n1. 测试语音识别服务...")
        if self.speech_recognizer.test_connection():
            print("   ✓ 语音识别服务正常")
        else:
            print("   ✗ 语音识别服务不可用")
            all_ok = False
        
        # 测试翻译服务
        print("\n2. 测试翻译服务...")
        if self.translator.test_connection():
            print("   ✓ 翻译服务正常")
            
            # 测试翻译
            result = self.translator.translate("こんにちは")
            if result:
                print(f"   测试翻译: こんにちは -> {result}")
        else:
            print("   ✗ 翻译服务不可用")
            all_ok = False
        

        
        print("\n" + "=" * 30)
        
        return all_ok
    
    def _adapt_params(self):
        rec_list = self._metrics['rec_times']
        if rec_list:
            avg = sum(rec_list) / len(rec_list)
        else:
            avg = 0
        fail = self._metrics['fail_count']
        succ = self._metrics['success_count']
        total = fail + succ if (fail + succ) > 0 else 1
        fr = fail / total
        force_interval = self.config.silence_duration
        max_buf = self.config.max_buffer_duration
        if avg > 1500:
            max_buf = max(5.0, max_buf - 2.0)
            force_interval = max(0.4, self.config.silence_duration - 0.1)
        else:
            max_buf = min(12.0, max_buf + 1.0)
            force_interval = min(0.8, self.config.silence_duration + 0.05)
        if fr > 0.1:
            force_interval = min(0.9, force_interval + 0.1)
        self.config.max_buffer_duration = max_buf
        self.config.silence_duration = force_interval
        if self.audio_capture:
            self.audio_capture.update_dynamic_params(
                silence_duration=self.config.silence_duration,
                max_buffer_duration=self.config.max_buffer_duration,
                force_flush_interval=max(1.0, self.config.silence_duration)
            )
    def run(self):
        """运行应用程序"""
        print("=" * 50)
        print("  实时日语转中文字幕翻译系统")
        print("=" * 50)
        
        # 初始化组件
        self._init_components()
        
        # 测试连接
        if not self.test_connections():
            print("\n⚠️ 部分服务不可用，将继续运行...")
        
        self._running = True
        
        # 启动共享服务器
        if self.sharing_server:
            self.sharing_server.start()
            print(f"\n共享地址: {self.sharing_server.get_connection_info()}")
        

        
        # 启动音频捕获
        print("\n开始捕获系统音频...")
        self.audio_capture.start(callback=self._on_audio)
        
        # 启动字幕窗口（阻塞主线程）
        print("\n字幕窗口已启动，关闭窗口退出程序")
        print("提示: 拖拽标题栏可移动窗口位置")
        
        try:
            self.subtitle_overlay.start_blocking()
        except KeyboardInterrupt:
            pass
        
        self.stop()
    
    def stop(self):
        """停止应用程序"""
        print("\n正在停止...")
        self._running = False
        
        if self.audio_capture:
            self.audio_capture.stop()
        

        
        if self.sharing_server:
            self.sharing_server.stop()
        
        if self.subtitle_overlay:
            self.subtitle_overlay.stop()
        
        print("程序已退出")


def main():
    """程序入口"""
    parser = argparse.ArgumentParser(description='实时日语转中文字幕翻译系统')
    parser.add_argument('--test-api', action='store_true', help='测试API连接')
    parser.add_argument('--test-audio', action='store_true', help='测试音频捕获')
    parser.add_argument('--server', type=str, help='服务器地址')
    parser.add_argument('--model', type=str, help='翻译模型')
    
    args = parser.parse_args()
    
    # 更新配置
    config = get_config()
    if args.server:
        config.server_url = args.server
        config.whisper_api_url = f"{args.server}/api/v1/audio/transcriptions"
        config.ollama_api_url = f"{args.server}/ollama/api/chat"
    if args.model:
        config.translation_model = args.model
    save_config()
    
    # 测试API
    if args.test_api:
        app = TranslatorApp()
        app._init_components()
        app.test_connections()
        return
    
    # 测试音频
    if args.test_audio:
        print("测试音频捕获...")
        capture = AudioCapture()
        
        print("\n可用设备:")
        for device in capture.list_devices():
            marker = "* " if device.get('is_loopback') else "  "
            print(f"{marker}{device['index']}: {device['name']}")
        
        def on_audio(data):
            print(f"捕获到音频: {len(data)} 字节")
        
        print("\n开始捕获 (按 Ctrl+C 停止)...")
        capture.start(callback=on_audio)
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        
        capture.stop()
        return
    
    # 运行主程序
    app = TranslatorApp()
    app.run()


if __name__ == "__main__":
    main()
