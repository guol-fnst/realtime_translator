"""
翻译模块
通过 OpenWebUI/Ollama API 将日语翻译为中文
"""
import requests
import json
from typing import Optional, List
from config import get_config


class Translator:
    """翻译器 - 使用 Ollama LLM 进行翻译"""
    
    def __init__(self):
        self.config = get_config()
        self._session = requests.Session()
        self._context_history: List[str] = []  # 上下文历史
        self._max_context = 5  # 保留最近5句用于上下文
        
    def translate(self, text: str, use_context: bool = True) -> Optional[str]:
        """
        将日语文本翻译为中文
        
        Args:
            text: 要翻译的日语文本
            use_context: 是否使用上下文提高翻译质量
            
        Returns:
            中文翻译结果，失败返回 None
        """
        if not text or not text.strip():
            return None
        
        try:
            # 构建翻译提示
            context_prompt = ""
            if use_context and self._context_history:
                context_prompt = "之前的对话内容（用于上下文参考）：\n"
                for prev in self._context_history[-self._max_context:]:
                    context_prompt += f"- {prev}\n"
                context_prompt += "\n"
            
            system_prompt = """你是一个专业的日语到中文实时翻译器。请将用户提供的日语内容准确翻译成简体中文。

翻译要求：
1. 保持原文的语气和风格
2. 翻译要自然流畅
3. 只输出翻译结果，不要添加解释
4. 如果输入不是日语或无法翻译，直接返回原文"""

            user_message = f"{context_prompt}请翻译以下日语：\n{text}"
            
            # 准备请求体
            payload = {
                "model": self.config.translation_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                "stream": False,
                "options": {
                    "temperature": 0.3,  # 低温度以获得更稳定的翻译
                    "num_predict": 500
                }
            }
            
            # 添加 API 密钥
            headers = {
                'Content-Type': 'application/json'
            }
            if self.config.api_key:
                headers['Authorization'] = f'Bearer {self.config.api_key}'
            
            # 发送请求
            response = self._session.post(
                self.config.ollama_api_url,
                json=payload,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # 提取翻译结果
                if 'message' in result:
                    translated = result['message'].get('content', '').strip()
                elif 'response' in result:
                    translated = result['response'].strip()
                else:
                    translated = None
                
                if translated:
                    # 更新上下文
                    self._context_history.append(f"{text} -> {translated}")
                    if len(self._context_history) > self._max_context * 2:
                        self._context_history = self._context_history[-self._max_context:]
                    
                    return translated
                
            else:
                print(f"翻译失败: HTTP {response.status_code}")
                print(f"响应: {response.text[:200]}")
                
            return None
            
        except requests.exceptions.Timeout:
            print("翻译请求超时")
            return None
        except requests.exceptions.ConnectionError:
            print("无法连接到翻译服务器")
            return None
        except Exception as e:
            print(f"翻译出错: {e}")
            return None
    
    def translate_stream(self, text: str, on_token=None, use_context: bool = True) -> Optional[str]:
        """
        流式翻译 - 逐字生成翻译结果
        
        Args:
            text: 要翻译的日语文本
            on_token: 每生成一个token时调用的回调函数，参数为(当前token, 完整文本)
            use_context: 是否使用上下文
            
        Returns:
            完整的翻译结果
        """
        if not text or not text.strip():
            return None
        
        try:
            # 构建翻译提示
            context_prompt = ""
            if use_context and self._context_history:
                context_prompt = "之前的对话内容（用于上下文参考）：\n"
                for prev in self._context_history[-self._max_context:]:
                    context_prompt += f"- {prev}\n"
                context_prompt += "\n"
            
            system_prompt = """你是一个专业的日语到中文实时翻译器。请将用户提供的日语内容准确翻译成简体中文。
翻译要求：
1. 保持原文的语气和风格
2. 翻译要自然流畅
3. 只输出翻译结果，不要添加解释
4. 如果输入不是日语或无法翻译，直接返回原文"""

            user_message = f"{context_prompt}请翻译以下日语：\n{text}"
            
            # 准备请求体 - 流式模式
            payload = {
                "model": self.config.translation_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                "stream": True,  # 启用流式
                "options": {
                    "temperature": 0.3,
                    "num_predict": 500
                }
            }
            
            headers = {'Content-Type': 'application/json'}
            if self.config.api_key:
                headers['Authorization'] = f'Bearer {self.config.api_key}'
            
            # 流式请求
            response = self._session.post(
                self.config.ollama_api_url,
                json=payload,
                headers=headers,
                timeout=60,
                stream=True
            )
            
            if response.status_code != 200:
                print(f"翻译失败: HTTP {response.status_code}")
                return None
            
            full_text = ""
            
            # 逐行读取流式响应
            for line in response.iter_lines():
                if not line:
                    continue
                
                try:
                    data = json.loads(line)
                    
                    # Ollama 格式
                    if 'message' in data:
                        token = data['message'].get('content', '')
                    elif 'response' in data:
                        token = data.get('response', '')
                    else:
                        continue
                    
                    if token:
                        full_text += token
                        
                        # 调用回调函数
                        if on_token:
                            on_token(token, full_text)
                    
                    # 检查是否完成
                    if data.get('done', False):
                        break
                        
                except json.JSONDecodeError:
                    continue
            
            full_text = full_text.strip()
            
            if full_text:
                # 更新上下文
                self._context_history.append(f"{text} -> {full_text}")
                if len(self._context_history) > self._max_context * 2:
                    self._context_history = self._context_history[-self._max_context:]
                
                return full_text
            
            return None
            
        except Exception as e:
            print(f"流式翻译出错: {e}")
            return None
    
    def translate_batch(self, texts: List[str]) -> List[Optional[str]]:
        """批量翻译"""
        return [self.translate(text) for text in texts]
    
    def clear_context(self):
        """清除上下文历史"""
        self._context_history.clear()
    
    def test_connection(self) -> bool:
        """测试与翻译服务器的连接"""
        try:
            payload = {
                "model": self.config.translation_model,
                "messages": [
                    {"role": "user", "content": "你好"}
                ],
                "stream": False,
                "options": {
                    "num_predict": 10
                }
            }
            
            headers = {'Content-Type': 'application/json'}
            if self.config.api_key:
                headers['Authorization'] = f'Bearer {self.config.api_key}'
            
            response = self._session.post(
                self.config.ollama_api_url,
                json=payload,
                headers=headers,
                timeout=15
            )
            
            return response.status_code == 200
            
        except Exception as e:
            print(f"连接测试失败: {e}")
            return False


# 测试代码
if __name__ == "__main__":
    translator = Translator()
    
    print("测试与翻译服务器的连接...")
    if translator.test_connection():
        print("✓ 连接成功!")
        
        # 测试翻译
        test_texts = [
            "こんにちは、お元気ですか？",
            "今日の会議は午後3時からです。",
            "この問題について話し合いましょう。"
        ]
        
        print("\n测试翻译:")
        for text in test_texts:
            result = translator.translate(text)
            print(f"  日语: {text}")
            print(f"  中文: {result}")
            print()
    else:
        print("✗ 连接失败!")
