"""
提醒监控模块
实现价格阈值检测和系统声音提醒功能
"""

import time
import logging
from typing import Optional, Dict, Any
from enum import Enum
from dataclasses import dataclass
from src.config_manager import AppConfig

# 尝试导入winsound（Windows系统声音）
try:
    import winsound
    WINSOUND_AVAILABLE = True
except ImportError:
    print("警告: winsound模块不可用，声音提醒功能将禁用")
    WINSOUND_AVAILABLE = False


class AlertType(Enum):
    """提醒类型"""
    HIGH_THRESHOLD = "high"    # 达到高阈值
    LOW_THRESHOLD = "low"      # 达到低阈值


@dataclass
class AlertRecord:
    """提醒记录"""
    alert_type: AlertType
    trigger_time: float
    price: float
    threshold: float


class AlertMonitor:
    """提醒监控器"""

    def __init__(self, config: AppConfig):
        self.config = config

        # 提醒记录
        self.alert_history: Dict[AlertType, Optional[AlertRecord]] = {
            AlertType.HIGH_THRESHOLD: None,
            AlertType.LOW_THRESHOLD: None
        }

        # 提醒冷却时间（秒）
        self.cooldown_period = 60

        # 声音设置
        self.sound_enabled = WINSOUND_AVAILABLE and config.notifications_enabled

        # 日志设置
        self.setup_logging()

    def setup_logging(self):
        """设置日志"""
        # 创建logs目录（如果不存在）
        import os
        logs_dir = "logs"
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir)

        # 配置日志
        log_file = os.path.join(logs_dir, "alerts.log")
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def check_threshold(
        self,
        current_price: float,
        high_threshold: Optional[float] = None,
        low_threshold: Optional[float] = None
    ) -> Optional[AlertType]:
        """
        检查价格是否达到阈值

        Args:
            current_price: 当前价格
            high_threshold: 高阈值（如果为None，则使用配置中的值）
            low_threshold: 低阈值（如果为None，则使用配置中的值）

        Returns:
            触发的提醒类型，如果未触发则返回None
        """
        # 使用配置中的阈值（如果未提供）
        if high_threshold is None:
            high_threshold = self.config.high_threshold
        if low_threshold is None:
            low_threshold = self.config.low_threshold

        # 检查阈值是否设置
        if high_threshold is None and low_threshold is None:
            return None

        alert_type = None
        threshold = None

        # 检查高阈值
        if high_threshold is not None and current_price >= high_threshold:
            alert_type = AlertType.HIGH_THRESHOLD
            threshold = high_threshold

        # 检查低阈值（注意：低阈值提醒优先级高于高阈值）
        elif low_threshold is not None and current_price <= low_threshold:
            alert_type = AlertType.LOW_THRESHOLD
            threshold = low_threshold

        # 如果触发了提醒
        if alert_type and threshold:
            # 检查是否需要提醒（考虑冷却时间）
            if self.should_alert(alert_type):
                # 触发提醒
                self.trigger_alert(alert_type, current_price, threshold)
                return alert_type

        return None

    def should_alert(self, alert_type: AlertType) -> bool:
        """判断是否应该提醒（考虑冷却时间）"""
        current_time = time.time()
        last_alert = self.alert_history.get(alert_type)

        if last_alert is None:
            # 从未提醒过，可以提醒
            return True

        # 检查冷却时间
        time_since_last_alert = current_time - last_alert.trigger_time
        if time_since_last_alert >= self.cooldown_period:
            # 冷却时间已过，可以提醒
            return True

        # 仍在冷却期内
        remaining_time = self.cooldown_period - time_since_last_alert
        self.logger.debug(f"{alert_type.value}阈值提醒仍在冷却期内，剩余{remaining_time:.1f}秒")
        return False

    def trigger_alert(self, alert_type: AlertType, current_price: float, threshold: float):
        """触发提醒"""
        current_time = time.time()

        # 创建提醒记录
        alert_record = AlertRecord(
            alert_type=alert_type,
            trigger_time=current_time,
            price=current_price,
            threshold=threshold
        )

        # 更新提醒历史
        self.alert_history[alert_type] = alert_record

        # 记录提醒
        self.log_alert(alert_record)

        # 播放声音提醒
        if self.sound_enabled:
            self.play_alert_sound(alert_type)

    def log_alert(self, alert_record: AlertRecord):
        """记录提醒到日志"""
        # 格式化时间
        trigger_time_str = time.strftime(
            "%Y-%m-%d %H:%M:%S",
            time.localtime(alert_record.trigger_time)
        )

        # 根据提醒类型设置消息
        if alert_record.alert_type == AlertType.HIGH_THRESHOLD:
            message = (
                f"高阈值提醒: 当前价格 {alert_record.price:.2f} 元/克 "
                f"已达到高阈值 {alert_record.threshold:.2f}"
            )
        else:
            message = (
                f"低阈值提醒: 当前价格 {alert_record.price:.2f} 元/克 "
                f"已达到低阈值 {alert_record.threshold:.2f}"
            )

        # 完整日志消息
        full_message = f"{trigger_time_str} - {message}"

        # 记录日志
        self.logger.info(full_message)
        print(f"提醒: {full_message}")

    def play_alert_sound(self, alert_type: AlertType):
        """播放系统提示音"""
        if not self.sound_enabled:
            return

        try:
            # 根据提醒类型选择不同的声音
            if alert_type == AlertType.HIGH_THRESHOLD:
                # 高阈值提醒 - 使用默认提示音
                winsound.MessageBeep()
            else:
                # 低阈值提醒 - 使用不同的提示音（如果可用）
                try:
                    # 尝试使用不同的系统声音
                    winsound.MessageBeep(winsound.MB_ICONASTERISK)
                except:
                    winsound.MessageBeep()

            self.logger.debug(f"播放{alert_type.value}阈值提醒声音")

        except Exception as e:
            self.logger.error(f"播放声音提醒时出错: {e}")
            # 禁用声音功能，避免重复错误
            self.sound_enabled = False

    def get_last_alert_time(self, alert_type: AlertType) -> Optional[float]:
        """获取上次提醒的时间"""
        last_alert = self.alert_history.get(alert_type)
        if last_alert:
            return last_alert.trigger_time
        return None

    def get_alert_count(self, alert_type: Optional[AlertType] = None) -> int:
        """获取提醒计数"""
        if alert_type:
            return 1 if self.alert_history.get(alert_type) else 0
        else:
            return sum(1 for alert in self.alert_history.values() if alert is not None)

    def reset_alerts(self):
        """重置提醒记录"""
        self.alert_history = {
            AlertType.HIGH_THRESHOLD: None,
            AlertType.LOW_THRESHOLD: None
        }
        self.logger.info("提醒记录已重置")

    def enable_sound(self, enabled: bool = True):
        """启用或禁用声音提醒"""
        if WINSOUND_AVAILABLE:
            self.sound_enabled = enabled
            status = "启用" if enabled else "禁用"
            self.logger.info(f"声音提醒已{status}")
        else:
            self.logger.warning("winsound模块不可用，无法启用声音提醒")
            self.sound_enabled = False

    def set_cooldown_period(self, seconds: int):
        """设置提醒冷却时间"""
        if seconds < 0:
            raise ValueError("冷却时间不能为负数")

        old_cooldown = self.cooldown_period
        self.cooldown_period = seconds
        self.logger.info(f"提醒冷却时间已从{old_cooldown}秒更改为{seconds}秒")

    def get_status(self) -> Dict[str, Any]:
        """获取监控器状态"""
        status = {
            "sound_enabled": self.sound_enabled,
            "cooldown_period": self.cooldown_period,
            "alert_counts": {
                "high": self.get_alert_count(AlertType.HIGH_THRESHOLD),
                "low": self.get_alert_count(AlertType.LOW_THRESHOLD),
                "total": self.get_alert_count()
            },
            "last_alerts": {}
        }

        # 添加上次提醒时间
        for alert_type in AlertType:
            last_time = self.get_last_alert_time(alert_type)
            if last_time:
                status["last_alerts"][alert_type.value] = time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.localtime(last_time)
                )

        return status