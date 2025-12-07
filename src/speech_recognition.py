"""
语音识别模块
调用服务端 faster-whisper API 进行日语语音识别
支持多种后端: OpenAI兼容API, onerahmet/whisper-asr
"""
import requests
import io
from typing import Optional, Tuple
from config import get_config


class SpeechRecognizer:
    """语音识别器 - 调用服务端 Whisper API"""
    
    def __init__(self):
        self.config = get_config()
        self._session = requests.Session()
        
    def transcribe(self, audio_data: bytes) -> Tuple[Optional[str], Optional[str]]:
        """
        将音频转录为文本
        
        Args:
            audio_data: WAV 格式的音频数据
            
        Returns:
            (转录文本, 检测到的语言) 或 (None, None) 如果失败
        """
        # 尝试 onerahmet/whisper-asr 格式 (/asr 端点)
        result = self._transcribe_asr_format(audio_data)
        if result[0] is not None:
            return result
        
        # 回退到 OpenAI 兼容格式
        return self._transcribe_openai_format(audio_data)
    
    def _transcribe_asr_format(self, audio_data: bytes) -> Tuple[Optional[str], Optional[str]]:
        """onerahmet/whisper-asr 格式"""
        try:
            # 直接使用配置的 URL
            asr_url = self.config.whisper_api_url
            
            # 确保 URL 指向 /asr 端点
            if not asr_url.endswith('/asr'):
                asr_url = asr_url.rstrip('/') + '/asr'
            
            files = {
                'audio_file': ('audio.wav', io.BytesIO(audio_data), 'audio/wav')
            }
            
            params = {
                'language': self.config.source_language,
                'output': 'json',
                'task': 'transcribe'
            }
            
            print(f"[Whisper] 请求: {asr_url}")
            
            response = self._session.post(
                asr_url,
                files=files,
                params=params,
                timeout=30
            )
            
            print(f"[Whisper] 响应: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                # onerahmet 格式返回 {"text": "..."} 
                text = result.get('text', '').strip()
                if text:
                    return text, self.config.source_language
            else:
                print(f"[Whisper] 错误: {response.text[:200]}")
            
            return None, None
            
        except Exception as e:
            print(f"[Whisper] 异常: {e}")
            return None, None
    
    def _transcribe_openai_format(self, audio_data: bytes) -> Tuple[Optional[str], Optional[str]]:
        """OpenAI 兼容格式"""
        try:
            files = {
                'file': ('audio.wav', io.BytesIO(audio_data), 'audio/wav')
            }
            
            data = {
                'model': self.config.whisper_model,
                'language': self.config.source_language,
                'response_format': 'json'
            }
            
            headers = {}
            if self.config.api_key:
                headers['Authorization'] = f'Bearer {self.config.api_key}'
            
            response = self._session.post(
                self.config.whisper_api_url,
                files=files,
                data=data,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                text = result.get('text', '').strip()
                language = result.get('language', self.config.source_language)
                
                if text:
                    return text, language
                return None, None
            else:
                print(f"语音识别失败: HTTP {response.status_code}")
                print(f"响应: {response.text[:200]}")
                return None, None
                
        except requests.exceptions.Timeout:
            print("语音识别超时")
            return None, None
        except requests.exceptions.ConnectionError:
            print("无法连接到语音识别服务器")
            return None, None
        except Exception as e:
            print(f"语音识别出错: {e}")
            return None, None
    
    def transcribe_with_timestamps(self, audio_data: bytes) -> Optional[list]:
        """
        带时间戳的转录
        
        Returns:
            [{'start': float, 'end': float, 'text': str}, ...]
        """
        try:
            files = {
                'file': ('audio.wav', io.BytesIO(audio_data), 'audio/wav')
            }
            
            data = {
                'model': self.config.whisper_model,
                'language': self.config.source_language,
                'response_format': 'verbose_json',
                'timestamp_granularities': ['segment']
            }
            
            headers = {}
            if self.config.api_key:
                headers['Authorization'] = f'Bearer {self.config.api_key}'
            
            response = self._session.post(
                self.config.whisper_api_url,
                files=files,
                data=data,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                segments = result.get('segments', [])
                return [{
                    'start': seg.get('start', 0),
                    'end': seg.get('end', 0),
                    'text': seg.get('text', '').strip()
                } for seg in segments if seg.get('text', '').strip()]
            
            return None
            
        except Exception as e:
            print(f"带时间戳的转录出错: {e}")
            return None
    
    def test_connection(self) -> bool:
        """测试与服务器的连接"""
        try:
            # 创建一个简短的静音音频用于测试
            import wave
            buffer = io.BytesIO()
            with wave.open(buffer, 'wb') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                wav.writeframes(b'\x00' * 16000)  # 1秒静音
            
            # 使用 onerahmet 格式
            asr_url = self.config.whisper_api_url
            if not asr_url.endswith('/asr'):
                asr_url = asr_url.rstrip('/') + '/asr'
            
            files = {
                'audio_file': ('test.wav', io.BytesIO(buffer.getvalue()), 'audio/wav')
            }
            
            params = {
                'language': self.config.source_language,
                'output': 'json'
            }
            
            response = self._session.post(
                asr_url,
                files=files,
                params=params,
                timeout=15
            )
            
            print(f"[Whisper Test] URL: {asr_url}, Status: {response.status_code}")
            
            # 200 成功，422 参数问题也算连接正常
            return response.status_code in [200, 422]
            
        except Exception as e:
            print(f"连接测试失败: {e}")
            return False


# 测试代码
if __name__ == "__main__":
    recognizer = SpeechRecognizer()
    
    print("测试与语音识别服务器的连接...")
    if recognizer.test_connection():
        print("✓ 连接成功!")
    else:
        print("✗ 连接失败!")
