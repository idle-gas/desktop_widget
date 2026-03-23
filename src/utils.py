"""
通用工具模块
提供JSONP解析、时间处理、颜色转换等通用功能
"""

import json
import time
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple
from PyQt6.QtGui import QColor


def parse_jsonp_response(jsonp_text: str) -> Optional[Dict[str, Any]]:
    """
    解析JSONP格式响应

    Args:
        jsonp_text: JSONP格式的文本

    Returns:
        解析后的字典，如果解析失败则返回None
    """
    if not jsonp_text:
        return None

    try:
        # 常见JSONP格式:
        # 1. var variable_name = {...};
        # 2. callback_name({...});
        # 3. 直接是JSON {...}

        # 去除前后空白
        text = jsonp_text.strip()

        # 如果是直接JSON格式
        if text.startswith('{') and text.endswith('}'):
            json_text = text
        elif text.startswith('[') and text.endswith(']'):
            json_text = text
        else:
            # 尝试提取JSON部分
            # 查找第一个 '{' 或 '['
            start_bracket = text.find('{')
            start_square = text.find('[')

            if start_bracket == -1 and start_square == -1:
                return None

            # 使用第一个出现的括号
            if start_bracket != -1 and (start_square == -1 or start_bracket < start_square):
                start = start_bracket
                # 找到匹配的 '}'
                bracket_count = 0
                end = -1
                for i in range(start, len(text)):
                    if text[i] == '{':
                        bracket_count += 1
                    elif text[i] == '}':
                        bracket_count -= 1
                        if bracket_count == 0:
                            end = i + 1
                            break
            else:
                start = start_square
                # 找到匹配的 ']'
                bracket_count = 0
                end = -1
                for i in range(start, len(text)):
                    if text[i] == '[':
                        bracket_count += 1
                    elif text[i] == ']':
                        bracket_count -= 1
                        if bracket_count == 0:
                            end = i + 1
                            break

            if end == -1:
                return None

            json_text = text[start:end]

        # 解析JSON
        return json.loads(json_text)

    except json.JSONDecodeError as e:
        print(f"JSON解析错误: {e}")
        print(f"原始文本片段: {jsonp_text[:200]}...")
        return None
    except Exception as e:
        print(f"解析JSONP响应时出错: {e}")
        return None


def format_timestamp(timestamp: int, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    格式化时间戳

    Args:
        timestamp: Unix时间戳（秒或毫秒）
        format_str: 时间格式字符串

    Returns:
        格式化后的时间字符串
    """
    # 判断是秒还是毫秒
    if timestamp > 100000000000:  # 大于 100000000000 的可能是毫秒
        timestamp = timestamp / 1000

    try:
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime(format_str)
    except (ValueError, OSError) as e:
        print(f"格式化时间戳时出错: {e}")
        return "时间格式错误"


def format_time_delta(seconds: int) -> str:
    """
    格式化时间间隔

    Args:
        seconds: 秒数

    Returns:
        格式化的时间间隔字符串
    """
    if seconds < 60:
        return f"{seconds}秒"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}分{secs}秒"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}小时{minutes}分"


def get_color_for_change(change_amount: float) -> QColor:
    """
    根据涨跌额获取颜色

    Args:
        change_amount: 涨跌额

    Returns:
        QColor对象
    """
    if change_amount > 0:
        return QColor(0, 255, 0)  # 绿色 - 上涨
    elif change_amount < 0:
        return QColor(255, 0, 0)  # 红色 - 下跌
    else:
        return QColor(255, 255, 255)  # 白色 - 不变


def hex_to_qcolor(hex_color: str, default: QColor = None) -> QColor:
    """
    将十六进制颜色代码转换为QColor

    Args:
        hex_color: 十六进制颜色代码（如 "#RRGGBB" 或 "#RRGGBBAA"）
        default: 转换失败时返回的默认颜色

    Returns:
        QColor对象
    """
    if default is None:
        default = QColor(255, 255, 255)  # 默认白色

    if not hex_color or not hex_color.startswith('#'):
        return default

    hex_color = hex_color.lstrip('#')

    try:
        if len(hex_color) == 6:  # RRGGBB
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            return QColor(r, g, b)
        elif len(hex_color) == 8:  # RRGGBBAA
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            a = int(hex_color[6:8], 16)
            return QColor(r, g, b, a)
        else:
            return default
    except ValueError:
        return default


def qcolor_to_hex(color: QColor, include_alpha: bool = False) -> str:
    """
    将QColor转换为十六进制颜色代码

    Args:
        color: QColor对象
        include_alpha: 是否包含透明度

    Returns:
        十六进制颜色代码字符串
    """
    if include_alpha:
        return f"#{color.red():02x}{color.green():02x}{color.blue():02x}{color.alpha():02x}"
    else:
        return f"#{color.red():02x}{color.green():02x}{color.blue():02x}"


def safe_float(value: Any, default: float = 0.0) -> float:
    """
    安全地将值转换为浮点数

    Args:
        value: 要转换的值
        default: 转换失败时返回的默认值

    Returns:
        浮点数
    """
    if value is None:
        return default

    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    """
    安全地将值转换为整数

    Args:
        value: 要转换的值
        default: 转换失败时返回的默认值

    Returns:
        整数
    """
    if value is None:
        return default

    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def truncate_text(text: str, max_length: int, ellipsis: str = "...") -> str:
    """
    截断文本并在末尾添加省略号

    Args:
        text: 原始文本
        max_length: 最大长度
        ellipsis: 省略号字符串

    Returns:
        截断后的文本
    """
    if len(text) <= max_length:
        return text

    if max_length <= len(ellipsis):
        return ellipsis[:max_length]

    return text[:max_length - len(ellipsis)] + ellipsis


def format_price(price: float, decimals: int = 2) -> str:
    """
    格式化价格数字

    Args:
        price: 价格
        decimals: 小数位数

    Returns:
        格式化后的价格字符串
    """
    if price is None:
        return "N/A"

    try:
        format_str = f"{{:.{decimals}f}}"
        return format_str.format(float(price))
    except (ValueError, TypeError):
        return "N/A"


def format_percentage(value: float, decimals: int = 2) -> str:
    """
    格式化百分比

    Args:
        value: 百分比值（如 0.05 表示 5%）
        decimals: 小数位数

    Returns:
        格式化后的百分比字符串
    """
    if value is None:
        return "N/A"

    try:
        percentage = float(value) * 100
        format_str = f"{{:.{decimals}f}}%"
        return format_str.format(percentage)
    except (ValueError, TypeError):
        return "N/A"


def calculate_change_percentage(current: float, previous: float) -> float:
    """
    计算涨跌幅百分比

    Args:
        current: 当前价格
        previous: 之前价格

    Returns:
        涨跌幅百分比（小数形式，如 0.05 表示 5%）
    """
    if previous == 0:
        return 0.0

    return (current - previous) / previous


def get_file_size_str(size_bytes: int) -> str:
    """
    获取文件大小字符串表示

    Args:
        size_bytes: 字节数

    Returns:
        格式化后的文件大小字符串
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f}{unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f}TB"


def validate_email(email: str) -> bool:
    """
    验证邮箱格式

    Args:
        email: 邮箱地址

    Returns:
        是否有效
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


class Timer:
    """简单的计时器类"""

    def __init__(self):
        self.start_time = None
        self.end_time = None

    def start(self):
        """开始计时"""
        self.start_time = time.time()
        self.end_time = None

    def stop(self) -> float:
        """停止计时并返回经过的时间（秒）"""
        if self.start_time is None:
            return 0.0

        self.end_time = time.time()
        return self.end_time - self.start_time

    def elapsed(self) -> float:
        """获取经过的时间（秒）"""
        if self.start_time is None:
            return 0.0

        current_time = time.time()
        if self.end_time is not None:
            return self.end_time - self.start_time
        else:
            return current_time - self.start_time

    def reset(self):
        """重置计时器"""
        self.start_time = None
        self.end_time = None


if __name__ == "__main__":
    # 简单的测试
    print("utils.py 测试:")

    # 测试JSONP解析
    jsonp_text = 'var quote_json = {"flag": true, "data": {"price": 4255.0}};'
    result = parse_jsonp_response(jsonp_text)
    print(f"JSONP解析结果: {result}")

    # 测试颜色转换
    color = get_color_for_change(10.5)
    print(f"上涨颜色: {color.red()}, {color.green()}, {color.blue()}")

    color = get_color_for_change(-5.2)
    print(f"下跌颜色: {color.red()}, {color.green()}, {color.blue()}")

    # 测试价格格式化
    print(f"价格格式化: {format_price(4255.1234, 2)}")

    # 测试百分比格式化
    print(f"百分比格式化: {format_percentage(0.051234, 2)}")