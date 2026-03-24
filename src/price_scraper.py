"""
价格数据获取模块
实现从金价API获取实时价格数据，解析JSONP格式，维护本地历史记录
"""

import json
import time
import requests
from datetime import datetime, time as dt_time
from typing import Optional, List, Tuple, Dict
from dataclasses import dataclass

from PyQt6.QtWidgets import QApplication

from src.config_manager import AppConfig


@dataclass
class PriceData:
    """价格数据结构"""
    current_price: float  # q63: 最新价
    open_price: float    # q1: 开盘价
    previous_close: float # q2: 昨收价
    high_price: float    # q3: 最高价
    low_price: float     # q4: 最低价
    buy_price: float     # q5: 买价
    sell_price: float    # q6: 卖价
    change_amount: float # q70: 涨跌额
    change_percent: float # q80: 涨跌幅（百分比）
    volume: float        # q60: 成交量
    timestamp: int       # time: 时间戳（毫秒）
    unit: str            # unit: 价格单位
    status: int          # status: 交易状态


class GoldPriceScraper:
    """黄金价格数据获取器"""

    def __init__(self, config: AppConfig):
        self.config = config
        self.price_history: List[Tuple[int, float]] = []  # (timestamp, price) 列表
        self.max_history_length = 120  # 最大历史记录长度（2小时，每分钟一个点）
        self.last_fetch_time = 0
        self.retry_count = 0
        self.max_retries = 3
        self.retry_delay = 30  # 秒

        # API配置
        self.api_url = "https://api.jijinhao.com/quoteCenter/realTime.htm?codes=JO_92233&isCalc=true&_="
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://quote.cngold.org/',
            'Accept': 'application/javascript, */*; q=0.01',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        }

        # 历史API配置
        self.history_api_url = "https://api.jijinhao.com/sQuoteCenter/history.htm?code=JO_92233&isCalc=true&style=1&pageSize=300&_="
        self.history_cache: Dict[str, List[Tuple[int, float]]] = {}  # 日期 -> 历史数据
        self.history_last_fetch_time = 0
        self.history_cache_duration = 60
        # self.use_history_api = True  # 是否使用历史API的开关
        self.use_history_api = False  # 是否使用历史API的开关

    def parse_jsonp_response(self, jsonp_text: str) -> Optional[Dict]:
        """解析JSONP格式响应
        var quote_json = {"flag":true,"JO_92233":{"code":"JO_92233","time":1774269057000,"q64":4642.304,"q193":1.0,"q1":995.83997,"q2":996.72107,"q3":1005.7867,"q4":908.88727,"q5":971.7576,"q6":972.1125,"q70":-24.96344,"q7":0.0,"q8":0.0,"q9":0.0,"q10":0.0,"q11":0.0,"q12":0.0,"q13":0.0,"q14":0.0,"q15":0.0,"q16":0.0,"q80":-2.5045562,"q17":0.0,"q18":0.0,"q19":0.0,"q20":0.0,"q21":0.0,"q22":0.0,"q23":0.0,"q24":0.0,"q60":69746.0,"q61":0.0,"q62":0.0,"q63":971.7576,"unit":"元/克","showName":"现货黄金","showCode":"XAU","digits":2,"status":100},"errorCode":[]}
        """
        try:
            # JSONP格式可能是:
            # 1. var variable_name = {...};
            # 2. callback_name({...});
            # 3. 直接是JSON {...}

            text = jsonp_text.strip()

            # 如果是直接JSON格式
            if text.startswith('{') and text.endswith('}'):
                json_text = text
                if json_text.endswith(';'):
                    json_text = json_text[:-1]
            # 检查是否是 var something = 格式
            elif text.startswith('var '):
                # 查找第一个 '=' 符号
                equals_pos = text.find('=')
                if equals_pos > 0:
                    # 提取等号后的部分
                    json_text = text[equals_pos + 1:].strip()
                    # 移除末尾的分号（如果有）
                    if json_text.endswith(';'):
                        json_text = json_text[:-1].strip()
                else:
                    print(f"无效的var格式，未找到'=': {text[:100]}...")
                    return None
            # 检查是否是 callback({...}) 格式
            elif '(' in text and ')' in text:
                # 查找第一个 '(' 和最后一个 ')'
                start = text.find('(') + 1
                end = text.rfind(')')
                if start < end:
                    json_text = text[start:end].strip()
                else:
                    print(f"无效的回调格式: {text[:100]}...")
                    return None
            else:
                print(f"未知的响应格式: {text[:100]}...")
                return None

            # 解析JSON
            data = json.loads(json_text)
            return data

        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {e}")
            print(f"原始文本: {jsonp_text[:200]}...")
            return None
        except Exception as e:
            print(f"解析JSONP响应时出错: {e}")
            return None

    def extract_price_data(self, api_data: Dict) -> Optional[PriceData]:
        """从API数据中提取价格信息"""
        try:
            # 获取黄金数据
            gold_data = api_data.get('JO_92233')
            if not gold_data:
                print(f"API响应中未找到JO_92233数据: {api_data}")
                return None

            # 检查交易状态
            status = gold_data.get('status')
            if status != 100:  # 100表示交易中
                print(f"交易状态异常: {status}")
                return None

            # 提取字段
            price_data = PriceData(
                current_price=gold_data.get('q63', 0),
                open_price=gold_data.get('q1', 0),
                previous_close=gold_data.get('q2', 0),
                high_price=gold_data.get('q3', 0),
                low_price=gold_data.get('q4', 0),
                buy_price=gold_data.get('q5', 0),
                sell_price=gold_data.get('q6', 0),
                change_amount=gold_data.get('q70', 0),
                change_percent=gold_data.get('q80', 0),
                volume=gold_data.get('q60', 0),
                timestamp=gold_data.get('time', 0),
                # unit=gold_data.get('unit', '元/克'),
                unit='元/克',
                status=status
            )

            # 验证数据完整性
            if price_data.current_price <= 0:
                print(f"价格数据异常: current_price={price_data.current_price}")
                return None

            return price_data

        except Exception as e:
            print(f"提取价格数据时出错: {e}")
            return None

    def get_current_gold_price(self) -> Optional[Dict]:
        """获取当前黄金价格信息"""
        # 检查API缓存（设计文档中提到API缓存15秒）
        current_time = int(time.time()*1000)
        if current_time - self.last_fetch_time < 15:
            print("跳过API调用：仍在缓存期内")
            return None

        try:
            print(f"调用API: {self.api_url}{current_time}")
            response = requests.get(
                self.api_url+str(current_time),
                # self.api_url,
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()

            # 解析JSONP响应
            api_data = self.parse_jsonp_response(response.text)
            if not api_data:
                self.retry_count += 1
                print(f"解析API响应失败，重试 {self.retry_count}/{self.max_retries}")
                return None

            # 检查API响应标志
            if not api_data.get('flag', False):
                print(f"API返回失败标志: {api_data.get('errorCode', '未知错误')}")
                self.retry_count += 1
                return None

            # 提取价格数据
            price_data = self.extract_price_data(api_data)
            if not price_data:
                self.retry_count += 1
                print(f"提取价格数据失败，重试 {self.retry_count}/{self.max_retries}")
                return None

            # 重置重试计数
            self.retry_count = 0
            self.last_fetch_time = current_time

            # 更新本地历史记录
            self.update_price_history(price_data.timestamp, price_data.current_price)

            # 转换为字典格式返回（兼容widget.py的期望格式）
            return {
                'q63': price_data.current_price,
                'q1': price_data.open_price,
                'q2': price_data.previous_close,
                'q3': price_data.high_price,
                'q4': price_data.low_price,
                'q5': price_data.buy_price,
                'q6': price_data.sell_price,
                'q70': price_data.change_amount,
                'q80': price_data.change_percent,
                'q60': price_data.volume,
                'time': price_data.timestamp,
                'unit': price_data.unit,
                'status': price_data.status,
                'showName': '现货黄金',
                'showCode': 'XAU'
            }

        except requests.exceptions.Timeout:
            print("API请求超时")
            self.retry_count += 1
            return None
        except requests.exceptions.ConnectionError:
            print("网络连接错误")
            self.retry_count += 1
            return None
        except requests.exceptions.HTTPError as e:
            print(f"HTTP错误: {e}")
            self.retry_count += 1
            return None
        except Exception as e:
            print(f"获取价格数据时发生未知错误: {e}")
            self.retry_count += 1
            return None

    def update_price_history(self, timestamp: int, price: float):
        """更新本地价格历史记录"""
        # 添加新数据点
        self.price_history.append((timestamp, price))

        # 保持历史记录长度不超过最大值
        if len(self.price_history) > self.max_history_length:
            self.price_history = self.price_history[-self.max_history_length:]

        print(f"历史记录更新: 当前有 {len(self.price_history)} 个数据点，最新价格: {price}")

    def _call_history_api(self) -> Optional[List[Tuple[int, float]]]:
        """调用历史API并解析响应"""
        try:
            current_time = int(time.time() * 1000)
            url = f"{self.history_api_url}{current_time}"

            print(f"调用历史API: {url}")
            response = requests.get(
                url,
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()

            # 解析历史API响应
            return self._parse_history_response(response.text)

        except Exception as e:
            print(f"调用历史API失败: {e}")
            return None

    def _parse_history_response(self, jsonp_text: str) -> Optional[List[Tuple[int, float]]]:
        """解析历史API响应

        注意：需要先测试API的实际响应格式
        假设格式可能是: {"data": [[timestamp, price, volume], ...]}
        实际格式需要根据测试结果调整
        """
        try:
            # 使用现有的JSONP解析方法
            data = self.parse_jsonp_response(jsonp_text)
            if not data:
                print("历史API响应解析失败：JSONP解析返回None")
                return None

            # 调试：打印数据结构的键，帮助了解实际格式
            print(f"历史API响应键: {list(data.keys())}")

            # 根据测试结果，历史API返回格式: {"data":[{"date":..., "open":..., "high":..., "low":..., "close":...}, ...]}
            # 或者可能是其他格式，我们需要灵活处理

            history_list = None
            result = []

            # 尝试不同的数据提取逻辑
            # 情况1: 数据在"data"键中，且是对象列表
            if 'data' in data and isinstance(data['data'], list):
                history_list = data['data']
                print(f"从'data'键提取历史数据，共{len(history_list)}条")

                # 处理对象列表格式: [{"date":..., "open":..., "close":...}, ...]
                for item in history_list:
                    if isinstance(item, dict):
                        # 尝试不同的字段名
                        timestamp = item.get('date') or item.get('time') or item.get('timestamp')
                        # 尝试不同的价格字段：收盘价、开盘价、最新价等
                        price = item.get('close') or item.get('price') or item.get('last') or item.get('current_price')

                        if timestamp is not None and price is not None:
                            try:
                                ts = int(timestamp)
                                pr = float(price)
                                result.append((ts, pr))
                            except (ValueError, TypeError) as e:
                                print(f"数据转换错误: timestamp={timestamp}, price={price}, error={e}")
                        else:
                            # 如果找不到标准字段，尝试其他可能的结构
                            print(f"对象缺少必要字段: {item}")
                    elif isinstance(item, list) and len(item) >= 2:
                        # 处理二维列表格式: [[timestamp, price], ...]
                        timestamp = item[0]
                        price = item[1]
                        try:
                            ts = int(timestamp)
                            pr = float(price)
                            result.append((ts, pr))
                        except (ValueError, TypeError) as e:
                            print(f"列表数据转换错误: {item}, error={e}")
                    else:
                        print(f"未知的数据格式: {type(item)} - {item}")

            # 情况2: 数据在根级别是列表
            elif isinstance(data, list):
                history_list = data
                print(f"根级别是历史数据列表，共{len(history_list)}条")

                for item in history_list:
                    if isinstance(item, dict):
                        timestamp = item.get('date') or item.get('time') or item.get('timestamp')
                        price = item.get('close') or item.get('price') or item.get('last')
                        if timestamp is not None and price is not None:
                            try:
                                result.append((int(timestamp), float(price)))
                            except (ValueError, TypeError):
                                pass
                    elif isinstance(item, list) and len(item) >= 2:
                        try:
                            result.append((int(item[0]), float(item[1])))
                        except (ValueError, TypeError):
                            pass

            # 情况3: 数据在其他键中
            else:
                # 尝试查找包含历史数据的列表
                for key, value in data.items():
                    if isinstance(value, list) and len(value) > 0:
                        history_list = value
                        print(f"从'{key}'键提取历史数据，共{len(history_list)}条")

                        # 处理列表中的元素
                        for item in history_list:
                            if isinstance(item, dict):
                                timestamp = item.get('date') or item.get('time')
                                price = item.get('close') or item.get('price')
                                if timestamp is not None and price is not None:
                                    try:
                                        result.append((int(timestamp), float(price)))
                                    except (ValueError, TypeError):
                                        pass
                            elif isinstance(item, list) and len(item) >= 2:
                                try:
                                    result.append((int(item[0]), float(item[1])))
                                except (ValueError, TypeError):
                                    pass
                        break
                else:
                    print(f"未找到历史数据列表，可用键: {list(data.keys())}")
                    print(f"数据样本: {str(data)[:200]}...")
                    return None

            print(f"成功解析历史数据: {len(result)} 个数据点")
            return result

        except Exception as e:
            print(f"解析历史API响应时出错: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _filter_today_data(self, historical_data: List[Tuple[int, float]]) -> List[Tuple[int, float]]:
        """过滤出当天数据"""
        if not historical_data:
            return []

        today = datetime.now().date()
        # 当天开始时间戳（毫秒）
        today_start = int(datetime.combine(today, dt_time.min).timestamp() * 1000)
        # 当天结束时间戳（毫秒）
        today_end = int(datetime.combine(today, dt_time.max).timestamp() * 1000)

        filtered_data = [(ts, price) for ts, price in historical_data
                        if today_start <= ts <= today_end]

        print(f"当天数据过滤: 原始{len(historical_data)}条 -> 当天{len(filtered_data)}条")
        return filtered_data

    def _is_history_cache_valid(self) -> bool:
        """检查历史缓存是否有效"""
        current_time = time.time()
        if current_time - self.history_last_fetch_time < self.history_cache_duration:
            return True
        return False

    def _get_cached_history_data(self) -> Optional[List[Tuple[int, float]]]:
        """获取缓存的当天历史数据"""
        today_str = datetime.now().strftime("%Y-%m-%d")
        return self.history_cache.get(today_str)

    def _update_history_cache(self, data: List[Tuple[int, float]]):
        """更新历史缓存"""
        today_str = datetime.now().strftime("%Y-%m-%d")
        self.history_cache[today_str] = data
        self.history_last_fetch_time = time.time()

        # 清理旧缓存（只保留最近3天的数据）
        if len(self.history_cache) > 3:
            oldest_key = min(self.history_cache.keys())
            del self.history_cache[oldest_key]
            print(f"清理历史缓存: 移除{oldest_key}")

        print(f"历史缓存更新: {today_str} - {len(data)} 个数据点")

    def fetch_historical_data(self) -> Optional[List[Tuple[int, float]]]:
        """获取历史API数据，过滤当天数据"""
        if not self.use_history_api:
            print("历史API功能已禁用")
            return None

        # 检查缓存有效性
        if self._is_history_cache_valid():
            cached_data = self._get_cached_history_data()
            if cached_data:
                print(f"使用缓存的历史数据: {len(cached_data)} 个数据点")
                return cached_data

        # 调用历史API
        print("缓存无效或过期，调用历史API...")
        historical_data = self._call_history_api()
        if not historical_data:
            print("历史API调用失败")
            return None

        # 过滤当天数据
        today_data = self._filter_today_data(historical_data)
        if today_data:
            self._update_history_cache(today_data)
        else:
            print("过滤后当天数据为空")

        return today_data

    def get_time_share_data(self) -> List[Tuple[int, float]]:
        """获取分时数据（优先使用历史API数据）"""
        # 尝试获取历史API数据
        historical_data = self.fetch_historical_data()
        if historical_data:
            print(f"使用历史API数据: {len(historical_data)} 个数据点")
            return sorted(historical_data, key=lambda x: x[0])

        # 降级：使用本地历史数据
        print("历史API数据不可用，使用本地历史数据")
        if self.price_history:
            # 在图表区域显示提示信息（通过widget.py处理）
            pass
        return sorted(self.price_history, key=lambda x: x[0])

    def set_history_mode(self, use_api: bool):
        """切换历史数据模式，并清除缓存以立即生效"""
        self.use_history_api = use_api
        self.history_cache.clear()
        self.history_last_fetch_time = 0
        print(f"历史数据模式切换为: {'历史API' if use_api else '本地历史'}")

    def get_last_known_price(self) -> Optional[float]:
        """获取最后已知的价格（用于网络异常时）"""
        if self.price_history:
            return self.price_history[-1][1]
        return None

    def should_retry(self) -> bool:
        """判断是否应该重试"""
        if self.retry_count >= self.max_retries:
            print(f"已达到最大重试次数: {self.retry_count}")
            return False

        # 检查是否需要等待重试延迟
        if time.time() - self.last_fetch_time < self.retry_delay:
            return False

        return True
