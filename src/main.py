#!/usr/bin/env python3
"""
黄金价格监控小部件 - 主程序入口
基于详细设计文档实现
"""

import sys
import traceback
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from src.config_manager import ConfigManager
from src.widget import GoldPriceWidget
from src.alert_monitor import AlertMonitor
from src.price_scraper import GoldPriceScraper


def setup_application():
    """设置应用程序"""
    app = QApplication(sys.argv)
    app.setApplicationName("GoldPriceWidget")
    app.setApplicationDisplayName("黄金价格监控小部件")

    return app


def initialize_modules(config):
    """初始化所有模块"""
    # 初始化价格获取器
    scraper = GoldPriceScraper(config)

    # 初始化提醒监控器
    alert_monitor = AlertMonitor(config)

    # 初始化主窗口
    widget = GoldPriceWidget(config, scraper, alert_monitor)

    return scraper, alert_monitor, widget


def main():
    """主函数"""
    try:
        print("启动黄金价格监控小部件...")

        # 加载配置
        config_manager = ConfigManager()
        config = config_manager.load()
        print(f"配置加载完成: 高阈值={config.high_threshold}, 低阈值={config.low_threshold}")

        # 设置应用程序
        app = setup_application()

        # 初始化模块
        scraper, alert_monitor, widget = initialize_modules(config)

        # 显示窗口
        widget.show()
        print("主窗口已显示")

        # 启动应用事件循环
        sys.exit(app.exec())

    except Exception as e:
        print(f"应用程序启动失败: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()