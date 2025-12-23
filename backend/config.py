# config.py
import os

# Excel文件路径
EXCEL_FILE = "inventory_system.xlsx"
BACKUP_FILE = "inventory_system.xlsx.backup"

# 定义商品类型选项
PRODUCT_TYPES = ["样品", "原材料", "HB"]

# 定义楼层选项和容量
FLOORS = [1, 2, 3, 4, 5]
FLOOR_CAPACITY = 100  # 每层楼100框容量

# 必需的工作表名称
REQUIRED_TABLES = ['capacity', 'feature', 'inventory', 'location', 'manufacturer','operation_record','product']
# 缓存配置
CACHE_TTL = 60  # 1分钟
MAX_CACHE_SIZE = 100
CACHE_TIMEOUT = 30  # 缓存30秒

# 分页配置
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100

