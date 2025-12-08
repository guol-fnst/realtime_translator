"""
配置管理模块
管理服务器地址、API密钥和应用设置
"""
import json
import os
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class Config:
    """应用配置"""
    # 服务器设置
    server_url: str = "http://192.168.168.130"
    whisper_api_url: str = "http://192.168.168.130:9000/asr"  # onerahmet/whisper-asr
    ollama_api_url: str = "http://192.168.168.130:11434/api/chat"  # 直接调用Ollama
    
    # 模型设置
    translation_model: str = "qwen2.5:7b"  # 改为 7B 模型以降低延迟
    whisper_model: str = "medium"  # 改为 medium 模型以提高识别速度
    source_language: str = "ja"  # 日语
    target_language: str = "zh"  # 中文
    
    # 音频设置
    sample_rate: int = 16000
    chunk_duration: float = 3.0  # 备用分段长度
    silence_threshold: int = 300  # 静音阈值
    silence_duration: float = 0.6  # 静音持续多久触发发送
    max_buffer_duration: float = 15.0  # 最大缓冲时长
    min_speech_duration: float = 0.5  # 最小语音时长
    vad_enabled: bool = True
    vad_aggressiveness: int = 2
    enable_normalization: bool = True
    normalization_target: int = 30000
    
    # 字幕设置
    subtitle_font_size: int = 24
    subtitle_bg_opacity: float = 0.7
    subtitle_position_x: int = 100
    subtitle_position_y: int = 100
    show_original: bool = True  # 显示原文
    
    # 共享设置
    sharing_enabled: bool = True
    sharing_port: int = 8765
    
    # API密钥（如需要）
    api_key: Optional[str] = "sk-e87cc6015a29456daebefcdc52c7cc57"
    
    @classmethod
    def get_config_path(cls) -> Path:
        """获取配置文件路径"""
        app_data = os.environ.get('APPDATA', os.path.expanduser('~'))
        config_dir = Path(app_data) / 'JapaneseTranslator'
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / 'config.json'
    
    @classmethod
    def load(cls) -> 'Config':
        """加载配置"""
        config_path = cls.get_config_path()
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return cls(**data)
            except Exception as e:
                print(f"加载配置失败: {e}")
        return cls()
    
    def save(self):
        """保存配置"""
        config_path = self.get_config_path()
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(asdict(self), f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存配置失败: {e}")


# 全局配置实例
_config: Optional[Config] = None


def get_config() -> Config:
    """获取全局配置"""
    global _config
    if _config is None:
        _config = Config.load()
    return _config


def save_config():
    """保存全局配置"""
    global _config
    if _config is not None:
        _config.save()
