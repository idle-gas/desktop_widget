"""
设置对话框模块
实现应用程序设置界面
"""

from typing import Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QDoubleSpinBox, QSpinBox, QCheckBox,
    QPushButton, QMessageBox, QGridLayout,
    QWidget, QGroupBox
)
from PyQt6.QtCore import Qt, pyqtSignal

from src.config_manager import AppConfig


class SettingsDialog(QDialog):
    """设置对话框"""

    # 信号：设置已保存
    settings_saved = pyqtSignal()

    def __init__(self, config: AppConfig, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.config = config
        self.setup_ui()
        self.load_config()

    def setup_ui(self):
        """设置UI界面"""
        self.setWindowTitle("设置 - 黄金价格监控")
        self.setMinimumWidth(400)

        # 主布局
        main_layout = QVBoxLayout(self)

        # 阈值设置组
        threshold_group = QGroupBox("价格阈值设置")
        threshold_layout = QGridLayout()

        # 高阈值
        threshold_layout.addWidget(QLabel("高阈值:"), 0, 0)
        self.high_threshold_spin = QDoubleSpinBox()
        self.high_threshold_spin.setRange(0, 10000)
        self.high_threshold_spin.setSingleStep(10)
        self.high_threshold_spin.setSuffix(" 元/克")
        self.high_threshold_spin.setDecimals(2)
        threshold_layout.addWidget(self.high_threshold_spin, 0, 1)

        # 低阈值
        threshold_layout.addWidget(QLabel("低阈值:"), 1, 0)
        self.low_threshold_spin = QDoubleSpinBox()
        self.low_threshold_spin.setRange(0, 10000)
        self.low_threshold_spin.setSingleStep(10)
        self.low_threshold_spin.setSuffix(" 元/克")
        self.low_threshold_spin.setDecimals(2)
        threshold_layout.addWidget(self.low_threshold_spin, 1, 1)

        threshold_group.setLayout(threshold_layout)
        main_layout.addWidget(threshold_group)

        # 更新设置组
        update_group = QGroupBox("更新设置")
        update_layout = QGridLayout()

        # 更新频率
        update_layout.addWidget(QLabel("更新频率:"), 0, 0)
        self.update_interval_spin = QSpinBox()
        self.update_interval_spin.setRange(5, 3600)
        self.update_interval_spin.setSingleStep(5)
        self.update_interval_spin.setSuffix(" 秒")
        update_layout.addWidget(self.update_interval_spin, 0, 1)
        update_layout.addWidget(QLabel("(最小5秒)"), 0, 2)

        update_group.setLayout(update_layout)
        main_layout.addWidget(update_group)

        # 提醒设置组
        notification_group = QGroupBox("提醒设置")
        notification_layout = QVBoxLayout()

        # 提醒开关
        self.notification_check = QCheckBox("启用价格阈值提醒")
        notification_layout.addWidget(self.notification_check)

        notification_group.setLayout(notification_layout)
        main_layout.addWidget(notification_group)

        # 按钮布局
        button_layout = QHBoxLayout()

        # 确定按钮
        self.ok_button = QPushButton("确定")
        self.ok_button.clicked.connect(self.save_and_close)
        button_layout.addWidget(self.ok_button)

        # 取消按钮
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        # 应用按钮
        self.apply_button = QPushButton("应用")
        self.apply_button.clicked.connect(self.apply_settings)
        button_layout.addWidget(self.apply_button)

        main_layout.addLayout(button_layout)

        # 设置布局
        self.setLayout(main_layout)

    def load_config(self):
        """加载配置到UI控件"""
        # 阈值设置
        if self.config.high_threshold is not None:
            self.high_threshold_spin.setValue(self.config.high_threshold)
        else:
            self.high_threshold_spin.setValue(1500.0)  # 默认值

        if self.config.low_threshold is not None:
            self.low_threshold_spin.setValue(self.config.low_threshold)
        else:
            self.low_threshold_spin.setValue(900.0)  # 默认值

        # 更新设置
        self.update_interval_spin.setValue(self.config.update_interval)

        # 提醒设置
        self.notification_check.setChecked(self.config.notifications_enabled)

    def get_ui_config(self) -> AppConfig:
        """从UI控件获取配置"""
        config = AppConfig()

        # 阈值设置
        config.high_threshold = self.high_threshold_spin.value()
        config.low_threshold = self.low_threshold_spin.value()

        # 更新设置
        config.update_interval = self.update_interval_spin.value()

        # 提醒设置
        config.notifications_enabled = self.notification_check.isChecked()

        # 保留窗口设置
        config.window_position = self.config.window_position
        config.window_size = self.config.window_size

        return config

    def validate_settings(self, config: AppConfig) -> bool:
        """验证设置有效性"""
        # 检查阈值有效性
        if config.high_threshold is not None and config.low_threshold is not None:
            if config.high_threshold <= config.low_threshold:
                QMessageBox.warning(
                    self,
                    "设置验证失败",
                    f"高阈值({config.high_threshold})必须大于低阈值({config.low_threshold})"
                )
                return False

        # 检查更新间隔
        if config.update_interval < 5:
            QMessageBox.warning(
                self,
                "设置验证失败",
                f"更新间隔({config.update_interval}秒)不能小于5秒"
            )
            return False

        # 检查阈值是否设置
        if config.high_threshold is None and config.low_threshold is None:
            reply = QMessageBox.question(
                self,
                "确认设置",
                "您没有设置任何价格阈值，这将禁用所有价格提醒。\n是否继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return False

        return True

    def apply_settings(self):
        """应用设置（但不关闭对话框）"""
        # 获取UI中的配置
        new_config = self.get_ui_config()

        # 验证设置
        if not self.validate_settings(new_config):
            return

        # 更新配置
        self.config.high_threshold = new_config.high_threshold
        self.config.low_threshold = new_config.low_threshold
        self.config.update_interval = new_config.update_interval
        self.config.notifications_enabled = new_config.notifications_enabled

        # 发出设置已应用信号
        self.settings_saved.emit()

        QMessageBox.information(self, "设置已应用", "设置已成功应用。")

    def save_and_close(self):
        """保存设置并关闭对话框"""
        # 应用设置
        self.apply_settings()

        # 如果设置有效，接受对话框
        if self.validate_settings(self.config):
            self.accept()

    def showEvent(self, event):
        """对话框显示事件"""
        super().showEvent(event)
        # 对话框显示时，将焦点设置到第一个输入框
        self.high_threshold_spin.setFocus()
        self.high_threshold_spin.selectAll()

    def keyPressEvent(self, event):
        """键盘事件处理"""
        # ESC键关闭对话框
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
        # Ctrl+Enter保存并关闭
        elif event.key() == Qt.Key.Key_Return and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.save_and_close()
        else:
            super().keyPressEvent(event)

    @classmethod
    def create_and_exec(cls, config: AppConfig, parent: Optional[QWidget] = None) -> bool:
        """创建并显示设置对话框（便捷方法）"""
        dialog = cls(config, parent)
        return dialog.exec() == QDialog.DialogCode.Accepted