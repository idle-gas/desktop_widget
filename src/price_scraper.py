"""
价格数据获取模块
实现从金价API获取实时价格数据，解析JSONP格式，维护本地历史记录
"""

import json
import time
import requests
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

    def parse_jsonp_response(self, jsonp_text: str) -> Optional[Dict]:
        """解析JSONP格式响应
        var quote_json = {"flag":true,"JO_92233":{"code":"JO_92233","time":1774269057000,"q64":4642.304,"q193":1.0,"q1":995.83997,"q2":996.72107,"q3":1005.7867,"q4":908.88727,"q5":971.7576,"q6":972.1125,"q70":-24.96344,"q7":0.0,"q8":0.0,"q9":0.0,"q10":0.0,"q11":0.0,"q12":0.0,"q13":0.0,"q14":0.0,"q15":0.0,"q16":0.0,"q80":-2.5045562,"q17":0.0,"q18":0.0,"q19":0.0,"q20":0.0,"q21":0.0,"q22":0.0,"q23":0.0,"q24":0.0,"q60":69746.0,"q61":0.0,"q62":0.0,"q63":971.7576,"unit":"元/克","showName":"现货黄金","showCode":"XAU","digits":2,"status":100},"errorCode":[]}
        """
        try:
            # JSONP格式通常是: var quote_json = {...};
            # 或者直接是 {...}
            if 'var quote_json = ' in jsonp_text:
                # 提取JSON部分
                start = jsonp_text.find('var quote_json = ') + len('var quote_json = ')
                # end = jsonp_text.rfind(';')
                json_text = jsonp_text[start:].strip()
            elif jsonp_text.strip().startswith('{'):
                # 直接是JSON格式
                json_text = jsonp_text.strip()
                if json_text.endswith(';'):
                    json_text = json_text[:-1]
            else:
                print(f"未知的响应格式: {jsonp_text[:100]}...")
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

    def get_time_share_data(self) -> List[Tuple[int, float]]:
        """获取分时数据（用于图表绘制）"""
        # 返回历史数据，按时间戳升序排列
        return sorted(self.price_history, key=lambda x: x[0])

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
