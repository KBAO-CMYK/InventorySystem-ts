# read_utils.py
import pandas as pd
import numpy as np
from functools import lru_cache
import shutil
import os
import glob
from datetime import datetime
from config import *

# ------------------- 独立时间测量系统 -------------------
class TimingTracker:
    """独立的时间跟踪器，避免累积时长问题"""

    def __init__(self):
        self.timings = {}
        self.current_operation = None
        self.operation_start = None

    def start_operation(self, operation_name):
        """开始一个新的操作计时"""
        if self.current_operation and self.operation_start:
            # 如果有未结束的操作，先记录它
            elapsed = (datetime.now() - self.operation_start).total_seconds() * 1000
            if self.current_operation not in self.timings:
                self.timings[self.current_operation] = []
            self.timings[self.current_operation].append(elapsed)

        self.current_operation = operation_name
        self.operation_start = datetime.now()

    def end_operation(self):
        """结束当前操作并记录时间"""
        if self.current_operation and self.operation_start:
            elapsed = (datetime.now() - self.operation_start).total_seconds() * 1000
            if self.current_operation not in self.timings:
                self.timings[self.current_operation] = []
            self.timings[self.current_operation].append(elapsed)

            print(f"⏱️  {self.current_operation}: {elapsed:.2f}ms")

        self.current_operation = None
        self.operation_start = None

    def get_summary(self):
        """获取时间统计摘要"""
        summary = {}
        for operation, times in self.timings.items():
            if times:
                summary[operation] = {
                    'count': len(times),
                    'total_ms': sum(times),
                    'avg_ms': sum(times) / len(times),
                    'min_ms': min(times),
                    'max_ms': max(times)
                }
        return summary

    def print_summary(self):
        """打印详细的时间统计"""
        print("\n" + "=" * 50)
        print("📊 操作时间统计摘要")
        print("=" * 50)

        summary = self.get_summary()
        for operation, stats in summary.items():
            print(f"{operation}:")
            print(f"  调用次数: {stats['count']}")
            print(f"  总耗时: {stats['total_ms']:.2f}ms")
            print(f"  平均耗时: {stats['avg_ms']:.2f}ms")
            print(f"  最小耗时: {stats['min_ms']:.2f}ms")
            print(f"  最大耗时: {stats['max_ms']:.2f}ms")
            print()


# 全局时间跟踪器实例
timing_tracker = TimingTracker()


def timing_decorator(func):
    """独立的时间测量装饰器"""

    def wrapper(*args, **kwargs):
        timing_tracker.start_operation(func.__name__)
        result = func(*args, **kwargs)
        timing_tracker.end_operation()
        return result

    return wrapper


# ------------------- CSV文件路径定义 -------------------
CSV_DIR = 'csv'
CSV_FILES = {
    'inventory': os.path.join(CSV_DIR, 'inventory.csv'),
    'manufacturer': os.path.join(CSV_DIR, 'manufacturer.csv'),
    'feature': os.path.join(CSV_DIR, 'feature.csv'),
    'stock_capacity': os.path.join(CSV_DIR, 'stock_capacity.csv'),
    'stock_out_records': os.path.join(CSV_DIR, 'stock_out_records.csv')
}


@timing_decorator
def ensure_csv_directory():
    """确保CSV目录存在"""
    if not os.path.exists(CSV_DIR):
        os.makedirs(CSV_DIR)
        print(f"创建CSV目录: {CSV_DIR}")


@lru_cache(maxsize=1)
def get_cached_csv_data():
    """缓存CSV数据，1分钟自动失效"""
    timing_tracker.start_operation("get_cached_csv_data")
    data = safe_read_csv_files()
    for table in REQUIRED_TABLES:
        if table not in data:
            data[table] = pd.DataFrame()
    timing_tracker.end_operation()
    return data


def invalidate_cache():
    """失效缓存（数据更新时调用）"""
    get_cached_csv_data.cache_clear()


@timing_decorator
def safe_read_csv_files():
    """安全地读取所有CSV文件 - 如果文件不存在返回空DataFrame"""
    data = {}
    try:
        for table, filepath in CSV_FILES.items():
            if os.path.exists(filepath):
                try:
                    # 尝试读取CSV文件
                    df = pd.read_csv(filepath)
                    # 检查是否为空文件
                    if df.empty or (len(df.columns) == 1 and df.columns[0] == 'Unnamed: 0'):
                        data[table] = pd.DataFrame()
                    else:
                        data[table] = df.fillna("")
                    print(f"✅ 成功读取 {table} 数据，行数: {len(data[table])}")
                except Exception as e:
                    print(f"⚠️ 读取 {table} 文件失败: {str(e)}，尝试从备份恢复")
                    # 尝试从备份恢复
                    backup_file = f"{filepath}.backup"
                    if os.path.exists(backup_file):
                        try:
                            shutil.copy2(backup_file, filepath)
                            df = pd.read_csv(filepath)
                            data[table] = df.fillna("")
                            print(f"🔄 从备份恢复 {table} 数据成功")
                        except Exception as backup_error:
                            print(f"❌ 备份恢复也失败: {str(backup_error)}，使用空DataFrame")
                            data[table] = pd.DataFrame()
                    else:
                        print(f"📝 无备份可用，使用空DataFrame")
                        data[table] = pd.DataFrame()
            else:
                print(f"📝 {table} 文件不存在，使用空DataFrame")
                data[table] = pd.DataFrame()
        return data
    except Exception as e:
        print(f"❌ 读取CSV文件失败: {str(e)}")
        return {table: pd.DataFrame() for table in CSV_FILES.keys()}


@timing_decorator
def read_csv_data():
    """读取CSV数据 - 优先从缓存读取"""
    return get_cached_csv_data()


# ------------------- 缓存优化 -------------------
_data_cache = {}
_cache_timestamp = None


@timing_decorator
def read_csv_data_cached():
    """带缓存的数据读取函数"""
    global _data_cache, _cache_timestamp

    current_time = datetime.now()
    if (_cache_timestamp and
            (current_time - _cache_timestamp).total_seconds() < CACHE_TIMEOUT and
            _data_cache):
        return _data_cache.copy()

    data = read_csv_data()
    _data_cache = data.copy()
    _cache_timestamp = current_time

    return data


# ------------------- 兼容性函数 -------------------
def read_excel_data():
    """兼容性函数，保持原有接口"""
    return read_csv_data()


def safe_read_excel_file():
    """兼容性函数，保持原有接口"""
    return safe_read_csv_files()