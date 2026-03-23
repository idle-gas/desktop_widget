"""
配置管理模块
实现应用程序配置的加载、保存和验证
"""

import json
import os
import sys
from dataclasses import dataclass, asdict, field
from typing import Optional
from pathlib import Path

from PyQt6.QtCore import QPoint


@dataclass
class AppConfig:
    """应用程序配置类"""
    # 阈值设置（元/克）
    high_threshold: Optional[float] = None  # 高阈值
    low_threshold: Optional[float] = None   # 低阈值

    # 窗口设置
    window_position: Optional[QPoint] = None  # 窗口位置
    window_size: tuple = (300, 180)          # 窗口大小（包含分时图）

    # 更新设置
    update_interval: int = 5  # 更新间隔（秒，默认5秒）

    # 提醒设置
    notifications_enabled: bool = True


class ConfigManager:
    """配置管理器"""

    def __init__(self, config_dir: str = None, config_file: str = "config.json"):
        # 确定配置目录
        if config_dir is None:
            config_dir = self._get_default_config_dir()

        # 配置目录和文件路径
        self.config_dir = Path(config_dir)
        self.config_file = self.config_dir / config_file

        # 确保配置目录存在
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # 默认配置
        self.default_config = AppConfig()

    def _get_default_config_dir(self) -> str:
        """获取默认配置目录路径"""
        # 检查是否在PyInstaller打包环境中
        if getattr(sys, 'frozen', False):
            # 打包环境：使用可执行文件所在目录下的config目录
            base_dir = Path(sys.executable).parent
        else:
            # 开发环境：使用当前目录下的config目录
            base_dir = Path.cwd()

        # 创建config目录路径
        config_dir = base_dir / "config"
        return str(config_dir)

    def qpoint_to_dict(self, qpoint: Optional[QPoint]) -> Optional[dict]:
        """将QPoint对象转换为字典"""
        if qpoint is None:
            return None
        return {"x": qpoint.x(), "y": qpoint.y()}

    def dict_to_qpoint(self, point_dict: Optional[dict]) -> Optional[QPoint]:
        """将字典转换为QPoint对象"""
        if point_dict is None:
            return None
        return QPoint(point_dict.get("x", 100), point_dict.get("y", 100))

    def serialize_config(self, config: AppConfig) -> dict:
        """序列化配置对象为字典"""
        config_dict = asdict(config)

        # 特殊处理QPoint对象
        config_dict['window_position'] = self.qpoint_to_dict(config.window_position)

        # 移除None值（使JSON更简洁）
        config_dict = {k: v for k, v in config_dict.items() if v is not None}

        return config_dict

    def deserialize_config(self, config_dict: dict) -> AppConfig:
        """从字典反序列化为配置对象"""
        # 创建配置对象
        config = AppConfig()

        # 设置阈值
        config.high_threshold = config_dict.get('high_threshold')
        config.low_threshold = config_dict.get('low_threshold')

        # 设置窗口位置
        window_pos_dict = config_dict.get('window_position')
        if window_pos_dict:
            config.window_position = self.dict_to_qpoint(window_pos_dict)

        # 设置窗口大小
        window_size = config_dict.get('window_size')
        if window_size and len(window_size) == 2:
            config.window_size = tuple(window_size)

        # 设置更新间隔
        update_interval = config_dict.get('update_interval')
        if update_interval is not None:
            config.update_interval = int(update_interval)

        # 设置提醒开关
        notifications_enabled = config_dict.get('notifications_enabled')
        if notifications_enabled is not None:
            config.notifications_enabled = bool(notifications_enabled)

        return config

    def validate_config(self, config: AppConfig) -> bool:
        """验证配置有效性"""
        # 检查阈值设置
        if config.high_threshold is not None and config.low_threshold is not None:
            if config.high_threshold <= config.low_threshold:
                print(f"配置验证失败: 高阈值({config.high_threshold})必须大于低阈值({config.low_threshold})")
                return False

        # 检查更新间隔
        if config.update_interval < 5:
            print(f"配置验证失败: 更新间隔({config.update_interval}秒)不能小于5秒")
            return False

        # 检查窗口大小
        if len(config.window_size) != 2:
            print(f"配置验证失败: 窗口大小格式错误: {config.window_size}")
            return False

        width, height = config.window_size
        if width <= 0 or height <= 0:
            print(f"配置验证失败: 窗口大小必须为正数: {width}x{height}")
            return False

        return True

    def load(self) -> AppConfig:
        """加载配置文件"""
        try:
            # 检查配置文件是否存在
            if not self.config_file.exists():
                print(f"配置文件不存在，使用默认配置: {self.config_file}")
                return self.default_config

            # 读取配置文件
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config_dict = json.load(f)

            print(f"配置文件加载成功: {self.config_file}")

            # 反序列化配置
            config = self.deserialize_config(config_dict)

            # 验证配置
            if not self.validate_config(config):
                print("配置验证失败，使用默认配置")
                return self.default_config

            return config

        except json.JSONDecodeError as e:
            print(f"配置文件JSON格式错误: {e}")
            print("使用默认配置")
            return self.default_config
        except Exception as e:
            print(f"加载配置文件时出错: {e}")
            print("使用默认配置")
            return self.default_config

    def save(self, config: AppConfig) -> bool:
        """保存配置文件"""
        try:
            # 验证配置
            if not self.validate_config(config):
                print("配置验证失败，未保存")
                return False

            # 序列化配置
            config_dict = self.serialize_config(config)

            # 写入配置文件
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=2, ensure_ascii=False)

            print(f"配置文件保存成功: {self.config_file}")
            return True

        except Exception as e:
            print(f"保存配置文件时出错: {e}")
            return False

    def create_default_config(self) -> bool:
        """创建默认配置文件"""
        try:
            # 设置一些合理的默认值
            default_config = AppConfig()
            default_config.high_threshold = 4300.0  # 默认高阈值
            default_config.low_threshold = 4200.0   # 默认低阈值
            default_config.window_position = QPoint(100, 100)  # 默认窗口位置

            # 保存默认配置
            return self.save(default_config)

        except Exception as e:
            print(f"创建默认配置文件时出错: {e}")
            return False

    def get_config_path(self) -> str:
        """获取配置文件路径"""
        return str(self.config_file.absolute())

    def backup_config(self) -> bool:
        """备份配置文件"""
        try:
            if not self.config_file.exists():
                print("配置文件不存在，无需备份")
                return False

            backup_file = self.config_file.with_suffix('.json.backup')
            import shutil
            shutil.copy2(self.config_file, backup_file)
            print(f"配置文件备份成功: {backup_file}")
            return True

        except Exception as e:
            print(f"备份配置文件时出错: {e}")
            return False