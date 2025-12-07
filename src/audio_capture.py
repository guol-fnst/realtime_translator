"""
音频捕获模块
使用 PyAudioWPatch 捕获 Windows 系统音频 (WASAPI Loopback)
"""
import threading
import queue
import wave
import io
import numpy as np
from typing import Optional, Callable
import time


class AudioCapture:
    """Windows系统音频捕获器 - 支持智能断句"""
    
    def __init__(self, sample_rate: int = 16000, chunk_duration: float = 3.0,
                 silence_threshold: int = 300, silence_duration: float = 0.6,
                 max_buffer_duration: float = 15.0, min_speech_duration: float = 0.5):
        """
        初始化音频捕获器
        
        Args:
            sample_rate: 目标采样率 (Hz)
            chunk_duration: 固定分段时长（备用，用于智能断句失败时）
            silence_threshold: 静音阈值（音频振幅低于此值视为静音）
            silence_duration: 静音持续多久后触发发送（秒）
            max_buffer_duration: 最大缓冲时长（超过后强制发送）
            min_speech_duration: 最小语音时长（太短的不发送）
        """
        self.sample_rate = sample_rate
        self.chunk_duration = chunk_duration
        self.chunk_size = int(sample_rate * chunk_duration)
        
        # 智能断句参数
        self.silence_threshold = silence_threshold
        self.silence_duration = silence_duration
        self.max_buffer_duration = max_buffer_duration
        self.min_speech_duration = min_speech_duration
        
        self._audio = None
        self._stream = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._audio_queue: queue.Queue = queue.Queue()
        self._callback: Optional[Callable[[bytes], None]] = None
        
        # 音频缓冲区
        self._buffer = []
        self._buffer_samples = 0
        
        # 静音检测状态
        self._silence_samples = 0  # 连续静音采样数
        self._speech_started = False  # 是否检测到语音开始
        self._speech_samples = 0  # 语音采样数
        
    def _init_audio(self):
        """初始化 PyAudioWPatch"""
        try:
            import pyaudiowpatch as pyaudio
            self._audio = pyaudio.PyAudio()
            return True
        except ImportError:
            print("错误: 请安装 PyAudioWPatch: pip install PyAudioWPatch")
            return False
        except Exception as e:
            print(f"初始化音频失败: {e}")
            return False
    
    def get_loopback_device(self):
        """获取默认的 WASAPI Loopback 设备"""
        if self._audio is None:
            return None
        
        try:
            # 方法1: 尝试获取默认的 WASAPI loopback 设备
            device = self._audio.get_default_wasapi_loopback()
            if device:
                print(f"找到默认 Loopback 设备: {device.get('name', 'Unknown')}")
                return device
        except Exception as e:
            print(f"获取默认 Loopback 设备失败: {e}")
        
        # 方法2: 手动搜索 loopback 设备
        print("尝试手动搜索 Loopback 设备...")
        try:
            for i in range(self._audio.get_device_count()):
                try:
                    info = self._audio.get_device_info_by_index(i)
                    if info.get('isLoopbackDevice', False):
                        print(f"找到 Loopback 设备: {info.get('name', 'Unknown')}")
                        return info
                except Exception:
                    pass
        except Exception as e:
            print(f"搜索设备失败: {e}")
        
        # 方法3: 搜索名称包含 Loopback 或 Stereo Mix 的设备
        print("尝试通过名称搜索...")
        try:
            for i in range(self._audio.get_device_count()):
                try:
                    info = self._audio.get_device_info_by_index(i)
                    name = info.get('name', '').lower()
                    if info.get('maxInputChannels', 0) > 0:
                        if 'loopback' in name or 'stereo mix' in name or 'what u hear' in name:
                            print(f"找到设备: {info.get('name', 'Unknown')}")
                            return info
                except Exception:
                    pass
        except Exception as e:
            print(f"名称搜索失败: {e}")
        
        print("错误: 无法找到任何 Loopback 设备")
        print("提示: 请确保已安装 PyAudioWPatch 而不是 PyAudio")
        print("运行: pip uninstall pyaudio && pip install pyaudiowpatch")
        return None
    
    def list_devices(self) -> list:
        """列出所有可用的音频设备"""
        if not self._init_audio():
            return []
        
        devices = []
        print(f"发现 {self._audio.get_device_count()} 个音频设备:")
        for i in range(self._audio.get_device_count()):
            try:
                info = self._audio.get_device_info_by_index(i)
                is_loopback = info.get('isLoopbackDevice', False)
                devices.append({
                    'index': i,
                    'name': info.get('name', 'Unknown'),
                    'channels': info.get('maxInputChannels', 0),
                    'sample_rate': info.get('defaultSampleRate', 0),
                    'is_loopback': is_loopback
                })
                if is_loopback:
                    print(f"  [Loopback] {i}: {info.get('name', 'Unknown')}")
            except Exception as e:
                print(f"  设备 {i}: 读取失败 - {e}")
        
        self._audio.terminate()
        self._audio = None
        return devices
    
    def start(self, callback: Optional[Callable[[bytes], None]] = None):
        """
        开始捕获音频
        
        Args:
            callback: 音频数据回调函数，接收 WAV 格式的音频数据
        """
        if self._running:
            return
        
        if not self._init_audio():
            return
        
        loopback = self.get_loopback_device()
        if loopback is None:
            print("错误: 找不到 Loopback 设备")
            return
        
        self._callback = callback
        self._running = True
        
        # 获取设备参数
        device_sample_rate = int(loopback['defaultSampleRate'])
        channels = loopback['maxInputChannels']
        
        print(f"使用设备: {loopback['name']}")
        print(f"采样率: {device_sample_rate} Hz, 声道: {channels}")
        
        import pyaudiowpatch as pyaudio
        
        # 打开音频流
        self._stream = self._audio.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=device_sample_rate,
            input=True,
            input_device_index=loopback['index'],
            frames_per_buffer=1024,
            stream_callback=self._audio_callback
        )
        
        self._device_sample_rate = device_sample_rate
        self._device_channels = channels
        
        # 启动处理线程
        self._thread = threading.Thread(target=self._process_audio, daemon=True)
        self._thread.start()
        
        print("音频捕获已启动")
    
    def _audio_callback(self, in_data, frame_count, time_info, status):
        """音频流回调"""
        import pyaudiowpatch as pyaudio
        if self._running:
            self._audio_queue.put(in_data)
        return (None, pyaudio.paContinue)
    
    def _process_audio(self):
        """处理音频数据的后台线程 - 智能断句版本"""
        silence_samples_threshold = int(self.sample_rate * self.silence_duration)
        max_buffer_samples = int(self.sample_rate * self.max_buffer_duration)
        min_speech_samples = int(self.sample_rate * self.min_speech_duration)
        
        while self._running:
            try:
                # 获取音频数据
                data = self._audio_queue.get(timeout=0.1)
                
                # 转换为 numpy 数组
                audio_data = np.frombuffer(data, dtype=np.int16)
                
                # 如果是多声道，转换为单声道
                if self._device_channels > 1:
                    audio_data = audio_data.reshape(-1, self._device_channels)
                    audio_data = audio_data.mean(axis=1).astype(np.int16)
                
                # 重采样到目标采样率（如果需要）
                if self._device_sample_rate != self.sample_rate:
                    audio_data = self._resample(audio_data, self._device_sample_rate, self.sample_rate)
                
                # 计算当前块的音量
                current_volume = np.abs(audio_data).mean()
                is_silence = current_volume < self.silence_threshold
                
                # 添加到缓冲区
                self._buffer.append(audio_data)
                self._buffer_samples += len(audio_data)
                
                if is_silence:
                    # 静音中
                    self._silence_samples += len(audio_data)
                    
                    # 如果已经开始说话，且静音持续足够长，发送
                    if self._speech_started and self._silence_samples >= silence_samples_threshold:
                        if self._speech_samples >= min_speech_samples:
                            self._flush_buffer_smart()
                        else:
                            # 语音太短，清空缓冲区
                            self._clear_buffer()
                else:
                    # 有声音
                    self._silence_samples = 0
                    self._speech_started = True
                    self._speech_samples += len(audio_data)
                
                # 超过最大缓冲时间，强制发送
                if self._buffer_samples >= max_buffer_samples:
                    if self._speech_samples >= min_speech_samples:
                        self._flush_buffer_smart()
                    else:
                        self._clear_buffer()
                    
            except queue.Empty:
                continue
            except Exception as e:
                print(f"处理音频出错: {e}")
    
    def _resample(self, audio: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
        """简单的重采样（线性插值）"""
        if src_rate == dst_rate:
            return audio
        
        duration = len(audio) / src_rate
        target_length = int(duration * dst_rate)
        indices = np.linspace(0, len(audio) - 1, target_length)
        return np.interp(indices, np.arange(len(audio)), audio).astype(np.int16)
    
    def _clear_buffer(self):
        """清空缓冲区"""
        self._buffer = []
        self._buffer_samples = 0
        self._silence_samples = 0
        self._speech_started = False
        self._speech_samples = 0
    
    def _flush_buffer_smart(self):
        """智能刷新缓冲区 - 去除尾部静音"""
        if not self._buffer:
            return
        
        # 合并缓冲区
        audio_data = np.concatenate(self._buffer)
        
        # 去除尾部静音
        audio_data = self._trim_silence(audio_data)
        
        # 重置状态
        self._clear_buffer()
        
        if len(audio_data) < int(self.sample_rate * self.min_speech_duration):
            return
        
        # 转换为 WAV 格式
        wav_data = self._to_wav(audio_data)
        
        # 调用回调
        if self._callback:
            try:
                self._callback(wav_data)
            except Exception as e:
                print(f"回调出错: {e}")
    
    def _trim_silence(self, audio_data: np.ndarray, threshold: int = None) -> np.ndarray:
        """去除音频尾部的静音"""
        if threshold is None:
            threshold = self.silence_threshold
        
        # 从尾部开始找到第一个非静音位置
        window_size = int(self.sample_rate * 0.05)  # 50ms 窗口
        end_idx = len(audio_data)
        
        for i in range(len(audio_data) - window_size, 0, -window_size):
            window = audio_data[i:i + window_size]
            if np.abs(window).mean() >= threshold:
                end_idx = min(i + window_size * 2, len(audio_data))  # 保留一点尾音
                break
        
        return audio_data[:end_idx]
    
    def _flush_buffer(self):
        """刷新缓冲区并发送音频（保留用于兼容）"""
        self._flush_buffer_smart()
    
    def _to_wav(self, audio_data: np.ndarray) -> bytes:
        """将音频数据转换为 WAV 格式"""
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)  # 16-bit
            wav.setframerate(self.sample_rate)
            wav.writeframes(audio_data.tobytes())
        return buffer.getvalue()
    
    def stop(self):
        """停止捕获音频"""
        self._running = False
        
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None
        
        if self._audio:
            self._audio.terminate()
            self._audio = None
        
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        
        print("音频捕获已停止")


# 测试代码
if __name__ == "__main__":
    def on_audio(wav_data: bytes):
        print(f"收到音频数据: {len(wav_data)} 字节")
    
    capture = AudioCapture()
    
    print("可用设备:")
    for device in capture.list_devices():
        print(f"  {device['index']}: {device['name']} (Loopback: {device['is_loopback']})")
    
    print("\n开始捕获系统音频...")
    capture.start(callback=on_audio)
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    
    capture.stop()
