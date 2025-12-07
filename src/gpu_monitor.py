"""
GPU监控模块
获取NVIDIA GPU的状态信息（利用率、显存等）
"""
import subprocess
import threading
import time
from typing import Optional, Dict, Callable
from dataclasses import dataclass


@dataclass
class GPUStatus:
    """GPU状态信息"""
    name: str = "Unknown"
    utilization: float = 0.0  # GPU利用率 (%)
    memory_used: int = 0  # 已用显存 (MB)
    memory_total: int = 0  # 总显存 (MB)
    memory_percent: float = 0.0  # 显存使用率 (%)
    temperature: float = 0.0  # 温度 (°C)
    power_draw: float = 0.0  # 功耗 (W)
    available: bool = False  # GPU是否可用
    
    def format_display(self) -> str:
        """格式化显示字符串"""
        if not self.available:
            return "GPU: 不可用"
        return f"GPU: {self.utilization:.0f}% | 显存: {self.memory_used}MB/{self.memory_total}MB ({self.memory_percent:.0f}%)"


class GPUMonitor:
    """NVIDIA GPU监控器"""
    
    def __init__(self, update_interval: float = 2.0):
        """
        初始化GPU监控器
        
        Args:
            update_interval: 更新间隔（秒）
        """
        self.update_interval = update_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._status = GPUStatus()
        self._callback: Optional[Callable[[GPUStatus], None]] = None
        self._use_pynvml = False
        
        # 尝试初始化pynvml
        try:
            import pynvml
            pynvml.nvmlInit()
            self._use_pynvml = True
            self._nvml = pynvml
            print("使用 pynvml 监控GPU")
        except Exception:
            print("pynvml不可用，使用nvidia-smi命令行")
    
    def _get_status_nvidia_smi(self) -> GPUStatus:
        """通过nvidia-smi获取GPU状态"""
        status = GPUStatus()
        
        try:
            # 运行nvidia-smi命令
            result = subprocess.run(
                [
                    'nvidia-smi',
                    '--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw',
                    '--format=csv,noheader,nounits'
                ],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            
            if result.returncode == 0:
                line = result.stdout.strip().split('\n')[0]
                parts = [p.strip() for p in line.split(',')]
                
                if len(parts) >= 4:
                    status.name = parts[0]
                    status.utilization = float(parts[1]) if parts[1] not in ['[N/A]', ''] else 0
                    status.memory_used = int(float(parts[2])) if parts[2] not in ['[N/A]', ''] else 0
                    status.memory_total = int(float(parts[3])) if parts[3] not in ['[N/A]', ''] else 0
                    status.memory_percent = (status.memory_used / status.memory_total * 100) if status.memory_total > 0 else 0
                    
                    if len(parts) >= 5:
                        status.temperature = float(parts[4]) if parts[4] not in ['[N/A]', ''] else 0
                    if len(parts) >= 6:
                        status.power_draw = float(parts[5]) if parts[5] not in ['[N/A]', ''] else 0
                    
                    status.available = True
                    
        except FileNotFoundError:
            pass  # nvidia-smi不存在
        except subprocess.TimeoutExpired:
            pass
        except Exception as e:
            print(f"获取GPU状态出错: {e}")
        
        return status
    
    def _get_status_pynvml(self) -> GPUStatus:
        """通过pynvml获取GPU状态"""
        status = GPUStatus()
        
        try:
            handle = self._nvml.nvmlDeviceGetHandleByIndex(0)
            
            # GPU名称
            status.name = self._nvml.nvmlDeviceGetName(handle)
            if isinstance(status.name, bytes):
                status.name = status.name.decode('utf-8')
            
            # GPU利用率
            util = self._nvml.nvmlDeviceGetUtilizationRates(handle)
            status.utilization = util.gpu
            
            # 显存信息
            mem = self._nvml.nvmlDeviceGetMemoryInfo(handle)
            status.memory_used = mem.used // (1024 * 1024)
            status.memory_total = mem.total // (1024 * 1024)
            status.memory_percent = (mem.used / mem.total * 100) if mem.total > 0 else 0
            
            # 温度
            try:
                status.temperature = self._nvml.nvmlDeviceGetTemperature(handle, self._nvml.NVML_TEMPERATURE_GPU)
            except:
                pass
            
            # 功耗
            try:
                status.power_draw = self._nvml.nvmlDeviceGetPowerUsage(handle) / 1000.0
            except:
                pass
            
            status.available = True
            
        except Exception as e:
            print(f"pynvml获取状态出错: {e}")
            # 回退到nvidia-smi
            return self._get_status_nvidia_smi()
        
        return status
    
    def get_status(self) -> GPUStatus:
        """获取当前GPU状态"""
        if self._use_pynvml:
            return self._get_status_pynvml()
        else:
            return self._get_status_nvidia_smi()
    
    def start(self, callback: Optional[Callable[[GPUStatus], None]] = None):
        """
        开始监控
        
        Args:
            callback: 状态更新回调函数
        """
        if self._running:
            return
        
        self._callback = callback
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
    
    def _monitor_loop(self):
        """监控循环"""
        while self._running:
            self._status = self.get_status()
            
            if self._callback:
                try:
                    self._callback(self._status)
                except Exception as e:
                    print(f"GPU监控回调出错: {e}")
            
            time.sleep(self.update_interval)
    
    def stop(self):
        """停止监控"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        
        if self._use_pynvml:
            try:
                self._nvml.nvmlShutdown()
            except:
                pass
    
    @property
    def current_status(self) -> GPUStatus:
        """获取最近的状态"""
        return self._status


# 测试代码
if __name__ == "__main__":
    def on_status(status: GPUStatus):
        print(f"\r{status.format_display()}", end="", flush=True)
    
    monitor = GPUMonitor(update_interval=1.0)
    
    # 先测试一次
    status = monitor.get_status()
    print(f"GPU名称: {status.name}")
    print(f"可用: {status.available}")
    print(f"利用率: {status.utilization}%")
    print(f"显存: {status.memory_used}MB / {status.memory_total}MB")
    print(f"温度: {status.temperature}°C")
    print(f"功耗: {status.power_draw}W")
    print()
    
    print("开始持续监控...")
    monitor.start(callback=on_status)
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    
    monitor.stop()
    print("\n监控已停止")
