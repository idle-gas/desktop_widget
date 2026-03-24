"""
桌面小部件主窗口模块
实现无边框、透明、置顶的桌面小部件
"""

import time
from datetime import datetime
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QMenu, QApplication, QPushButton
)
from PyQt6.QtCore import (
    Qt, QPoint, QTimer, QRect, pyqtSignal
)
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QFont, QFontMetrics,
    QMouseEvent, QPaintEvent, QAction
)

from src.config_manager import AppConfig
from src.price_scraper import GoldPriceScraper
from src.alert_monitor import AlertMonitor
from src.settings_dialog import SettingsDialog


class GoldPriceWidget(QWidget):
    """黄金价格桌面小部件主窗口"""

    # 信号：价格更新
    price_updated = pyqtSignal(dict)

    def __init__(
        self,
        config: AppConfig,
        scraper: GoldPriceScraper,
        alert_monitor: AlertMonitor,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)

        # 保存模块引用
        self.config = config
        self.scraper = scraper
        self.alert_monitor = alert_monitor

        # 当前价格数据
        self.current_price_data = None
        self.last_update_time = None
        self.error_message = None

        # 窗口设置
        self.setup_window()
        self.setup_timer()
        self.setup_context_menu()

        # 连接信号
        self.price_updated.connect(self.on_price_updated)

    def setup_window(self):
        """设置窗口属性"""
        # 设置窗口标志
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )

        # 设置透明背景
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # 设置窗口大小（根据设计文档：300x204像素，含工具栏24px）
        self.setFixedSize(300, 204)

        # 设置窗口位置（如果有保存的位置）
        if self.config.window_position:
            self.move(self.config.window_position)

        # 设置窗口标题
        self.setWindowTitle("黄金价格监控")

        # 创建工具栏按钮
        self._setup_toolbar_buttons()

    def _setup_toolbar_buttons(self):
        """创建顶部工具栏按钮"""
        base_style = """
            QPushButton {
                background-color: rgba(60, 60, 60, 200);
                color: #dddddd;
                border: 1px solid rgba(100, 100, 100, 180);
                border-radius: 3px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: rgba(85, 85, 85, 220);
            }
            QPushButton:pressed {
                background-color: rgba(40, 40, 40, 240);
            }
        """
        close_style = base_style.replace(
            "rgba(60, 60, 60, 200)", "rgba(160, 40, 40, 200)"
        ).replace(
            "rgba(85, 85, 85, 220)", "rgba(200, 60, 60, 220)"
        )

        # 数据源切换按钮（当前模式为本地历史）
        self.toggle_btn = QPushButton("本地历史", self)
        self.toggle_btn.setGeometry(4, 2, 186, 20)
        self.toggle_btn.setStyleSheet(base_style)
        self.toggle_btn.clicked.connect(self.toggle_data_source)

        # 设置按钮
        self.settings_btn = QPushButton("⚙", self)
        self.settings_btn.setGeometry(194, 2, 48, 20)
        self.settings_btn.setStyleSheet(base_style)
        self.settings_btn.clicked.connect(self.open_settings)

        # 关闭按钮
        self.close_btn = QPushButton("✕", self)
        self.close_btn.setGeometry(246, 2, 50, 20)
        self.close_btn.setStyleSheet(close_style)
        self.close_btn.clicked.connect(QApplication.instance().quit)

    def toggle_data_source(self):
        """切换历史数据来源（本地历史 / 历史API）"""
        new_mode = not self.scraper.use_history_api
        self.scraper.set_history_mode(new_mode)
        self.toggle_btn.setText("当天走势" if new_mode else "实时走势")
        self.fetch_price()

    def setup_timer(self):
        """设置定时器"""
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.fetch_price)
        # 默认5分钟更新一次（300000毫秒）
        update_interval = self.config.update_interval * 1000
        self.update_timer.start(update_interval)

        # 立即获取一次价格
        QTimer.singleShot(100, self.fetch_price)

    def setup_context_menu(self):
        """设置右键菜单"""
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def fetch_price(self):
        """获取价格数据"""
        try:
            price_data = self.scraper.get_current_gold_price()
            if price_data:
                self.current_price_data = price_data
                self.last_update_time = time.time()
                self.error_message = None

                # 检查阈值提醒
                if self.config.notifications_enabled:
                    current_price = price_data.get('q63')
                    if current_price:
                        self.alert_monitor.check_threshold(
                            current_price,
                            self.config.high_threshold,
                            self.config.low_threshold
                        )

                # 发出价格更新信号
                self.price_updated.emit(price_data)
            else:
                self.error_message = "获取价格数据失败"

        except Exception as e:
            self.error_message = f"网络错误: {str(e)}"
            print(f"获取价格失败: {e}")

        # 触发重绘
        self.update()

    def on_price_updated(self, price_data: dict):
        """价格更新处理"""
        # 这里可以添加额外的处理逻辑
        pass

    def show_context_menu(self, position: QPoint):
        """显示右键菜单"""
        menu = QMenu(self)

        # 添加菜单项
        settings_action = QAction("设置", self)
        settings_action.triggered.connect(self.open_settings)

        refresh_action = QAction("刷新", self)
        refresh_action.triggered.connect(self.fetch_price)

        exit_action = QAction("退出", self)
        exit_action.triggered.connect(QApplication.instance().quit)

        menu.addAction(settings_action)
        menu.addAction(refresh_action)
        menu.addSeparator()
        menu.addAction(exit_action)

        menu.exec(self.mapToGlobal(position))

    def open_settings(self):
        """打开设置对话框"""
        dialog = SettingsDialog(self.config, self)
        if dialog.exec():
            # 保存配置
            from config_manager import ConfigManager
            config_manager = ConfigManager()
            config_manager.save(self.config)

            # 更新定时器间隔
            update_interval = self.config.update_interval * 1000
            self.update_timer.setInterval(update_interval)

            # 重新获取价格
            self.fetch_price()

    # ==================== 鼠标事件处理 ====================

    def mousePressEvent(self, event: QMouseEvent):
        """鼠标按下事件 - 用于窗口拖动"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        """鼠标移动事件 - 用于窗口拖动"""
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            # 保存窗口位置到配置
            self.config.window_position = self.pos()
            event.accept()

    # ==================== 绘制函数 ====================

    def paintEvent(self, event: QPaintEvent):
        """绘制整个窗口内容"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 绘制背景
        self.draw_background(painter)

        # 绘制价格信息
        if self.current_price_data:
            self.draw_price_info(painter)
            self.draw_time_chart(painter)
        elif self.error_message:
            self.draw_error_message(painter)
        else:
            self.draw_loading_message(painter)

        painter.end()

    def draw_background(self, painter: QPainter):
        """绘制半透明背景"""
        # 深灰色半透明背景（RGBA: 30, 30, 30, 220）
        painter.fillRect(self.rect(), QColor(30, 30, 30, 220))

        # 工具栏底部分隔线
        painter.setPen(QPen(QColor(80, 80, 80, 200), 1))
        painter.drawLine(0, 24, 300, 24)

    def draw_price_info(self, painter: QPainter):
        """绘制价格信息区域（顶部50像素）"""
        price_data = self.current_price_data
        if not price_data:
            return

        # 设置字体
        price_font = QFont("Arial", 18, QFont.Weight.Bold)
        change_font = QFont("Arial", 10)
        time_font = QFont("Arial", 8)

        # 获取价格和涨跌信息
        current_price = price_data.get('q63', 0)
        change_amount = price_data.get('q70', 0)
        change_percent = price_data.get('q80', 0)
        unit = price_data.get('unit', '元/克')

        # 确定价格颜色
        if change_amount > 0:
            price_color = QColor(0, 255, 0)  # 绿色
        elif change_amount < 0:
            price_color = QColor(255, 0, 0)  # 红色
        else:
            price_color = QColor(255, 255, 255)  # 白色

        # 绘制当前价格
        painter.setFont(price_font)
        painter.setPen(price_color)
        price_text = f"{current_price:.2f}"
        price_rect = QRect(10, 34, 280, 30)
        painter.drawText(price_rect, Qt.AlignmentFlag.AlignLeft, price_text)

        # 绘制单位
        painter.setFont(time_font)
        painter.setPen(QColor(200, 200, 200))
        unit_rect = QRect(10, 64, 280, 15)
        painter.drawText(unit_rect, Qt.AlignmentFlag.AlignLeft, unit)

        # 绘制涨跌信息
        painter.setFont(change_font)
        change_text = f"{change_amount:+.2f} ({change_percent:+.2f}%)"
        change_rect = QRect(10, 49, 280, 30)
        painter.drawText(change_rect, Qt.AlignmentFlag.AlignRight, change_text)

        # 绘制更新时间
        if self.last_update_time:
            update_time = datetime.fromtimestamp(self.last_update_time).strftime("%H:%M:%S")
            painter.setFont(time_font)
            painter.setPen(QColor(150, 150, 150))
            time_rect = QRect(10, 79, 280, 15)
            painter.drawText(time_rect, Qt.AlignmentFlag.AlignRight, f"更新: {update_time}")

    def draw_time_chart(self, painter: QPainter):
        """绘制分时走势图区域（底部90像素）"""
        # 图表区域：距顶部94像素（24工具栏+70价格区），高度100像素
        chart_rect = QRect(10, 94, 280, 100)

        # 绘制图表背景
        painter.fillRect(chart_rect, QColor(40, 40, 40, 150))

        # 获取历史数据
        history_data = self.scraper.get_time_share_data()
        if not history_data or len(history_data) < 2:
            # 没有足够的历史数据
            painter.setPen(QColor(150, 150, 150))
            painter.drawText(chart_rect, Qt.AlignmentFlag.AlignCenter, "等待历史数据...")
            return

        # 检查是否是降级模式（使用本地历史数据）
        # 本地历史数据最多120个点，历史API通常返回更多数据
        if len(history_data) <= 120:
            # 在图表右上角显示提示
            painter.setFont(QFont("Arial", 7))
            painter.setPen(QColor(255, 165, 0))  # 橙色提示
            painter.drawText(chart_rect.right() - 100, chart_rect.top() + 12,
                            "使用本地缓存数据")
            # 恢复默认字体
            painter.setFont(QFont("Arial", 8))

        # 提取价格和时间数据
        prices = [item[1] for item in history_data]
        if not prices:
            return

        # 计算价格范围
        min_price = min(prices)
        max_price = max(prices)
        price_range = max_price - min_price
        if price_range == 0:
            price_range = 1  # 避免除零

        # 绘制价格线
        painter.setPen(QPen(QColor(0, 180, 255), 2))  # 蓝色价格线

        # 绘制价格线
        for i in range(len(prices) - 1):
            x1 = chart_rect.left() + (i / (len(prices) - 1)) * chart_rect.width()
            y1 = chart_rect.bottom() - ((prices[i] - min_price) / price_range) * chart_rect.height()

            x2 = chart_rect.left() + ((i + 1) / (len(prices) - 1)) * chart_rect.width()
            y2 = chart_rect.bottom() - ((prices[i + 1] - min_price) / price_range) * chart_rect.height()

            painter.drawLine(int(x1), int(y1), int(x2), int(y2))

        # 绘制当前价格点
        current_price = prices[-1]
        current_x = chart_rect.right()
        current_y = chart_rect.bottom() - ((current_price - min_price) / price_range) * chart_rect.height()

        painter.setPen(QPen(QColor(255, 255, 0), 3))  # 黄色点
        painter.drawPoint(int(current_x), int(current_y))

        # 绘制价格标签
        painter.setFont(QFont("Arial", 8))
        painter.setPen(QColor(200, 200, 200))

        # 最高价标签
        high_text = f"{max_price:.1f}"
        painter.drawText(chart_rect.left(), chart_rect.top() + 10, high_text)

        # 最低价标签
        low_text = f"{min_price:.1f}"
        painter.drawText(chart_rect.left(), chart_rect.bottom() - 5, low_text)

    def draw_error_message(self, painter: QPainter):
        """绘制错误信息"""
        painter.setFont(QFont("Arial", 12))
        painter.setPen(QColor(255, 100, 100))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.error_message)

    def draw_loading_message(self, painter: QPainter):
        """绘制加载信息"""
        painter.setFont(QFont("Arial", 12))
        painter.setPen(QColor(200, 200, 200))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "正在加载价格数据...")

    def closeEvent(self, event):
        """窗口关闭事件"""
        # 保存窗口位置
        from config_manager import ConfigManager
        config_manager = ConfigManager()
        self.config.window_position = self.pos()
        config_manager.save(self.config)

        # 停止定时器
        self.update_timer.stop()

        event.accept()