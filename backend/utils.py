import os
import tempfile
import shutil
import pandas as pd
import numpy as np
from datetime import datetime
from functools import lru_cache
import glob

# 注意：确保config.py中定义了 REQUIRED_TABLES、CACHE_TIMEOUT、FLOOR_CAPACITY
# 示例config.py配置（可根据实际调整）：
# REQUIRED_TABLES = ['product', 'feature', 'inventory', 'location', 'operation_record', 'manufacturer', 'capacity']
# CACHE_TIMEOUT = 60  # 缓存超时时间（秒）
# FLOOR_CAPACITY = 100  # 楼层容量
from config import *


# ------------------- CSV文件路径定义 -------------------
CSV_DIR = 'csv'
CSV_FILES = {
    'product': os.path.join(CSV_DIR, 'product.csv'),  # 商品表
    'feature': os.path.join(CSV_DIR, 'feature.csv'),  # 商品特征表
    'inventory': os.path.join(CSV_DIR, 'inventory.csv'),  # 库存表
    'location': os.path.join(CSV_DIR, 'location.csv'),  # 位置表
    'operation_record': os.path.join(CSV_DIR, 'operation_record.csv'),  # 操作记录表
    'manufacturer': os.path.join(CSV_DIR, 'manufacturer.csv'),  # 厂家表
    'capacity': os.path.join(CSV_DIR, 'capacity.csv')  # 容量表
}


# ------------------- 目录操作函数 -------------------
def ensure_csv_directory():
    """确保CSV目录存在"""
    if not os.path.exists(CSV_DIR):
        os.makedirs(CSV_DIR)
        print(f"创建CSV目录: {CSV_DIR}")


# ------------------- 备份管理函数 -------------------
def cleanup_old_backups():
    """清理旧的备份文件，只保留最新的备份"""
    try:
        backup_pattern = os.path.join(CSV_DIR, "*.backup_*")
        backup_files = glob.glob(backup_pattern)

        # 按修改时间排序，最新的在前面
        backup_files.sort(key=os.path.getmtime, reverse=True)

        # 为每个表保留最新的一个备份
        table_backups = {}
        for backup_file in backup_files:
            # 提取表名（文件名前缀）
            filename = os.path.basename(backup_file)
            table_name = filename.split('.backup_')[0]

            if table_name not in table_backups:
                table_backups[table_name] = backup_file
            else:
                # 删除多余的备份文件
                try:
                    os.remove(backup_file)
                    print(f"🗑️  删除旧备份: {backup_file}")
                except Exception as e:
                    print(f"⚠️ 删除备份文件 {backup_file} 失败: {str(e)}")

        print(f"✅ 备份清理完成，保留 {len(table_backups)} 个最新备份")

    except Exception as e:
        print(f"⚠️ 清理备份文件时出错: {str(e)}")


def create_single_backup():
    """为所有表创建单一备份（覆盖旧备份）"""
    try:
        ensure_csv_directory()
        backup_created = False

        for table, filepath in CSV_FILES.items():
            if os.path.exists(filepath):
                # 使用固定备份文件名，覆盖旧的备份
                backup_file = f"{filepath}.backup"
                try:
                    # 复制文件时保留元数据，确保备份完整
                    shutil.copy2(filepath, backup_file)
                    backup_created = True
                    print(f"📦 创建备份: {backup_file}")
                except Exception as e:
                    print(f"⚠️ 创建备份文件 {backup_file} 失败: {str(e)}")

        # 清理可能存在的带时间戳的旧备份
        cleanup_old_backups()

        return backup_created

    except Exception as e:
        print(f"❌ 创建备份失败: {str(e)}")
        return False


def restore_from_backup():
    """从备份恢复数据"""
    try:
        ensure_csv_directory()
        restored_tables = []

        for table, filepath in CSV_FILES.items():
            backup_file = f"{filepath}.backup"
            if os.path.exists(backup_file):
                try:
                    # 先删除损坏的文件，再恢复备份
                    if os.path.exists(filepath):
                        os.remove(filepath)
                    shutil.copy2(backup_file, filepath)
                    restored_tables.append(table)
                    print(f"🔄 从备份恢复: {table}")
                except Exception as e:
                    print(f"⚠️ 恢复 {table} 失败: {str(e)}")

        if restored_tables:
            print(f"✅ 成功恢复 {len(restored_tables)} 个表的数据")
            invalidate_cache()
            return True
        else:
            print("ℹ️  没有找到可用的备份文件")
            return False

    except Exception as e:
        print(f"❌ 恢复备份失败: {str(e)}")
        return False


# ------------------- 核心优化：缓存机制 -------------------
@lru_cache(maxsize=1)
def get_cached_csv_data():
    """缓存CSV数据，1分钟自动失效"""
    data = safe_read_csv_files()
    for table in REQUIRED_TABLES:
        if table not in data:
            data[table] = pd.DataFrame()
        # 修复：确保ID列类型统一为整数，避免匹配错误
        data[table] = normalize_id_columns(data[table], table)
    return data


def invalidate_cache():
    """失效缓存（数据更新时调用）"""
    get_cached_csv_data.cache_clear()
    # 额外清理自定义缓存
    global _data_cache, _cache_timestamp
    _data_cache = {}
    _cache_timestamp = None


def normalize_id_columns(df, table_name):
    """标准化ID列类型为整数，避免字符串/数值混用导致的匹配错误"""
    if df.empty:
        return df

    id_column = get_id_column(table_name)
    if id_column and id_column in df.columns:
        # 清理空值/非数值，转为整数
        df[id_column] = pd.to_numeric(df[id_column], errors='coerce').fillna(-1).astype(int)
        # 过滤无效ID（-1）
        df = df[df[id_column] != -1].reset_index(drop=True)

    # 处理关联ID列
    related_id_cols = {
        'inventory': ['关联商品特征ID', '关联位置ID', '关联厂家ID'],
        'feature': ['关联商品ID'],
        'operation_record': ['关联库存ID']
    }
    for col in related_id_cols.get(table_name, []):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(-1).astype(int)

    return df


# ------------------- 安全的文件操作函数 -------------------
def safe_read_csv_files():
    """安全地读取所有CSV文件 - 如果文件不存在返回空DataFrame"""
    data = {}
    try:
        for table, filepath in CSV_FILES.items():
            if os.path.exists(filepath):
                try:
                    # 修复1：指定header=0确保表头正确，避免读取时索引列混入数据
                    df = pd.read_csv(filepath, header=0, encoding='utf-8-sig')
                    # 检查是否为空文件或只有索引列
                    if df.empty or (len(df.columns) == 1 and 'Unnamed: 0' in df.columns):
                        data[table] = get_empty_dataframe_template(table)
                    else:
                        # 修复：标准化ID列类型
                        data[table] = normalize_id_columns(df.fillna(""), table)
                    print(f"✅ 成功读取 {table} 数据，行数: {len(data[table])}")
                except Exception as e:
                    print(f"⚠️ 读取 {table} 文件失败: {str(e)}，尝试从备份恢复")
                    # 尝试从备份恢复
                    backup_file = f"{filepath}.backup"
                    if os.path.exists(backup_file):
                        try:
                            shutil.copy2(backup_file, filepath)
                            df = pd.read_csv(filepath, header=0, encoding='utf-8-sig')
                            data[table] = normalize_id_columns(df.fillna(""), table)
                            print(f"🔄 从备份恢复 {table} 数据成功")
                        except Exception as backup_error:
                            print(f"❌ 备份恢复也失败: {str(backup_error)}，使用空DataFrame")
                            data[table] = get_empty_dataframe_template(table)
                    else:
                        print(f"📝 无备份可用，使用空DataFrame")
                        data[table] = get_empty_dataframe_template(table)
            else:
                print(f"📝 {table} 文件不存在，使用空DataFrame")
                data[table] = get_empty_dataframe_template(table)
        return data
    except Exception as e:
        print(f"❌ 读取CSV文件失败: {str(e)}")
        return {table: get_empty_dataframe_template(table) for table in CSV_FILES.keys()}


def safe_write_csv_files(data, force_override=False):
    """安全写入CSV（支持强制覆盖，不合并）"""
    try:
        ensure_csv_directory()
        create_single_backup()  # 先备份

        write_success = True
        for table, filepath in CSV_FILES.items():
            df = data.get(table, pd.DataFrame())
            # 终极清理：删除全空行、Unnamed列
            df = df.dropna(how='all')
            df = df.loc[:, ~df.columns.str.contains('^Unnamed')]

            if force_override:
                # 强制覆盖：直接写入，不合并
                with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8-sig') as temp_f:
                    df.to_csv(temp_f, index=False, encoding='utf-8-sig')
                    temp_path = temp_f.name
                if os.path.exists(filepath):
                    os.remove(filepath)
                shutil.move(temp_path, filepath)
            else:
                # 原有合并逻辑（保留）
                existing_df = safe_read_csv_files().get(table, pd.DataFrame())
                existing_df = existing_df.dropna(how='all')
                existing_df = existing_df.loc[:, ~existing_df.columns.str.contains('^Unnamed')]

                id_col = get_id_column(table)
                if id_col and id_col in df.columns and id_col in existing_df.columns:
                    existing_df = existing_df[~existing_df[id_col].isin(df[id_col])]
                    df = pd.concat([existing_df, df], ignore_index=True).dropna(how='all')

                df.to_csv(filepath, index=False, encoding='utf-8-sig')

            print(f"💾 写入 {table}：{len(df)} 行")

        invalidate_cache()
        return write_success
    except Exception as e:
        print(f"写入失败: {e}")
        restore_from_backup()
        return False


def get_id_column(table_name):
    """获取表的主键列名"""
    id_columns = {
        'product': '商品ID',
        'feature': '商品特征ID',
        'inventory': '库存ID',
        'location': '地址ID',
        'operation_record': '操作ID',
        'manufacturer': '厂家ID',
        'capacity': '楼层'  # 容量表使用楼层作为主键
    }
    return id_columns.get(table_name, None)


def get_empty_dataframe_template(table_name):
    """获取指定表的空DataFrame模板"""
    templates = {
        'product': pd.DataFrame(columns=[
            "商品ID", "货号", "类型", "备注", "用途"
        ]),
        'feature': pd.DataFrame(columns=[
            "商品特征ID", "关联商品ID", "单价", "重量", "规格", "材质",
            "颜色", "形状", "风格","图片路径"
        ]),
        'inventory': pd.DataFrame(columns=[
            "库存ID", "关联商品特征ID", "关联位置ID", "关联厂家ID",
            "单位", "库存数量", "次品数量", "批次", "状态"
        ]),
        'location': pd.DataFrame(columns=[
            "地址ID", "地址类型", "楼层", "架号", "框号", "包号"
        ]),
        'operation_record': pd.DataFrame(columns=[
            "操作ID", "关联库存ID", "操作类型", "操作时间",
            "操作数量", "操作人", "备注"
        ]),
        'manufacturer': pd.DataFrame(columns=[
            "厂家ID", "厂家", "厂家地址", "电话"
        ]),
        'capacity': pd.DataFrame(columns=[
            "楼层", "楼层容量", "楼层剩余容量"
        ])
    }
    # 修复：空模板的ID列默认类型为整数
    template_df = templates.get(table_name, pd.DataFrame())
    if not template_df.empty:
        id_col = get_id_column(table_name)
        if id_col in template_df.columns:
            template_df[id_col] = template_df[id_col].astype('Int64')  # 可空整数类型
    return template_df


# ------------------- 数据初始化函数 -------------------
def init_or_fix_csv_files():
    """初始化或修复CSV文件 - 安全的初始化流程"""
    # 确保CSV目录存在
    ensure_csv_directory()

    # 首先尝试读取现有数据
    data = safe_read_csv_files()

    # 检查是否需要创建或修复文件
    needs_creation = False
    needs_repair = False

    for table in REQUIRED_TABLES:
        filepath = CSV_FILES[table]
        if not os.path.exists(filepath):
            print(f"📝 {table} 文件不存在，需要创建")
            needs_creation = True
        elif table not in data or data[table] is None or data[table].empty:
            print(f"⚠️ {table} 数据为空或损坏，需要修复")
            needs_repair = True
        else:
            # 检查必要的列是否存在
            required_cols = get_required_columns(table)
            if required_cols:
                existing_cols = set(data[table].columns)
                missing_cols = set(required_cols) - existing_cols
                if missing_cols:
                    print(f"⚠️ {table} 缺少列: {missing_cols}，需要修复")
                    needs_repair = True

    if needs_creation:
        print("🆕 创建新的CSV文件")
        result = create_new_csv_files()
        invalidate_cache()
        return result
    elif needs_repair:
        print("🔧 修复CSV文件结构")
        try:
            result = repair_csv_structure(data)
            invalidate_cache()
            return result
        except Exception as e:
            print(f"❌ 修复失败: {str(e)}，尝试重新创建")
            result = create_new_csv_files()
            invalidate_cache()
            return result
    else:
        print("✅ CSV文件状态正常")
        return True


def get_required_columns(table_name):
    """获取指定表必需的列"""
    required_columns = {
        'product': ["商品ID", "货号", "类型", "备注", "用途"],
        'feature': ["商品特征ID", "关联商品ID", "单价", "重量", "规格", "材质", "颜色", "形状", "风格", "图片路径"],
        'inventory': ["库存ID", "关联商品特征ID", "关联位置ID", "关联厂家ID", "单位", "库存数量", "次品数量", "批次",
                      "状态"],
        'location': ["地址ID", "地址类型", "楼层", "架号", "框号", "包号"],
        'operation_record': ["操作ID", "关联库存ID", "操作类型", "操作时间", "操作数量", "操作人", "备注"],
        'manufacturer': ["厂家ID", "厂家", "厂家地址", "电话"],
        'capacity': ["楼层", "楼层容量", "楼层剩余容量"]
    }
    return required_columns.get(table_name, [])


def create_new_csv_files():
    """创建新的CSV文件 - 安全的创建流程"""
    try:
        # 确保CSV目录存在
        ensure_csv_directory()

        # 读取现有数据（如果有）
        existing_data = safe_read_csv_files()

        # 创建标准数据结构
        new_data = {
            'product': get_empty_dataframe_template('product'),
            'feature': get_empty_dataframe_template('feature'),
            'inventory': get_empty_dataframe_template('inventory'),
            'location': get_empty_dataframe_template('location'),
            'operation_record': get_empty_dataframe_template('operation_record'),
            'manufacturer': get_empty_dataframe_template('manufacturer'),
            'capacity': get_empty_dataframe_template('capacity')
        }

        # 合并现有数据和新数据结构
        merged_data = {}
        for table in REQUIRED_TABLES:
            if table in existing_data and not existing_data[table].empty:
                # 保留现有数据，但确保列结构正确
                existing_df = existing_data[table]
                template_df = new_data[table]

                # 添加缺失的列
                for col in template_df.columns:
                    if col not in existing_df.columns:
                        if col in ["库存数量", "次品数量", "楼层"]:
                            existing_df[col] = 0
                        elif col == "状态":
                            existing_df[col] = "正常"
                        elif col == "地址类型":
                            existing_df[col] = 1
                        elif col == "操作类型":
                            existing_df[col] = "入库"
                        else:
                            existing_df[col] = ""

                # 移除多余的列
                for col in existing_df.columns:
                    if col not in template_df.columns:
                        existing_df = existing_df.drop(columns=[col])

                # 修复：重置索引
                merged_data[table] = existing_df.reset_index(drop=True)
            else:
                merged_data[table] = new_data[table]

        # 写入文件
        result = safe_write_csv_files(merged_data)
        if result:
            print("✅ CSV文件创建/初始化成功")
        else:
            print("❌ CSV文件创建失败")
        return result

    except Exception as e:
        print(f"❌ 创建CSV文件失败: {str(e)}")
        return False


# ------------------- 数据修复函数 -------------------
def repair_csv_structure(data):
    """修复CSV数据结构 - 安全的修复流程"""
    try:
        # 首先读取现有数据作为基准
        existing_data = safe_read_csv_files()

        # 用现有数据填补缺失的表
        for table in REQUIRED_TABLES:
            if table not in data or data[table] is None or data[table].empty:
                if table in existing_data and not existing_data[table].empty:
                    data[table] = existing_data[table]
                else:
                    data[table] = get_empty_dataframe_template(table)
            # 修复：标准化ID列
            data[table] = normalize_id_columns(data[table], table)

        # 修复各个表的结构
        repair_functions = {
            'product': repair_product_table,
            'feature': repair_feature_table,
            'inventory': repair_inventory_table,
            'location': repair_location_table,
            'operation_record': repair_operation_record_table,
            'manufacturer': repair_manufacturer_table,
            'capacity': repair_capacity_table
        }

        for table, repair_func in repair_functions.items():
            if table in data:
                data[table] = repair_func(data[table], data)
                # 修复：重置索引
                data[table] = data[table].reset_index(drop=True)

        # 保存修复后的数据
        result = safe_write_csv_files(data)

        if result:
            print("✅ CSV文件修复成功")
        else:
            print("❌ CSV文件修复失败")
        return result

    except Exception as e:
        print(f"❌ 修复CSV结构失败: {str(e)}")
        return False


def repair_product_table(product_df, all_data):
    """修复商品表结构"""
    required_cols = get_required_columns('product')

    # 添加缺失的列
    for col in required_cols:
        if col not in product_df.columns:
            product_df[col] = ""

    # 修复：重置索引
    return product_df.reset_index(drop=True)


def repair_feature_table(feature_df, all_data):
    """修复商品特征表结构"""
    required_cols = get_required_columns('feature')

    # 添加缺失的列
    for col in required_cols:
        if col not in feature_df.columns:
            if col in ["单价", "重量"]:
                feature_df[col] = 0.0
            else:
                feature_df[col] = ""

    # 确保关联商品ID存在
    if "关联商品ID" in feature_df.columns and "商品ID" in all_data.get('product', pd.DataFrame()).columns:
        product_ids = set(all_data['product']["商品ID"].tolist())
        feature_df["关联商品ID"] = feature_df["关联商品ID"].apply(
            lambda x: x if x in product_ids else -1
        )

    # 修复：重置索引
    return feature_df.reset_index(drop=True)


def repair_inventory_table(inventory_df, all_data):
    """修复库存表结构"""
    required_cols = get_required_columns('inventory')

    # 添加缺失的列
    for col in required_cols:
        if col not in inventory_df.columns:
            if col in ["库存数量", "次品数量", "批次"]:
                inventory_df[col] = 0
            elif col == "状态":
                inventory_df[col] = "正常"
            elif col == "单位":
                inventory_df[col] = "个"
            else:
                inventory_df[col] = -1  # 关联ID默认-1（无效）

    # 验证外键关联
    if "关联商品特征ID" in inventory_df.columns and "商品特征ID" in all_data.get('feature', pd.DataFrame()).columns:
        feature_ids = set(all_data['feature']["商品特征ID"].tolist())
        inventory_df["关联商品特征ID"] = inventory_df["关联商品特征ID"].apply(
            lambda x: x if x in feature_ids else -1
        )

    if "关联位置ID" in inventory_df.columns and "地址ID" in all_data.get('location', pd.DataFrame()).columns:
        location_ids = set(all_data['location']["地址ID"].tolist())
        inventory_df["关联位置ID"] = inventory_df["关联位置ID"].apply(
            lambda x: x if x in location_ids else -1
        )

    if "关联厂家ID" in inventory_df.columns and "厂家ID" in all_data.get('manufacturer', pd.DataFrame()).columns:
        manufacturer_ids = set(all_data['manufacturer']["厂家ID"].tolist())
        inventory_df["关联厂家ID"] = inventory_df["关联厂家ID"].apply(
            lambda x: x if x in manufacturer_ids else -1
        )

    # 修复：重置索引
    return inventory_df.reset_index(drop=True)


def repair_location_table(location_df, all_data):
    """修复位置表结构"""
    required_cols = get_required_columns('location')

    # 添加缺失的列
    for col in required_cols:
        if col not in location_df.columns:
            if col in ["地址类型", "楼层"]:
                location_df[col] = 1
            else:
                location_df[col] = ""

    # 修复：重置索引
    return location_df.reset_index(drop=True)


def repair_operation_record_table(record_df, all_data):
    """修复操作记录表结构"""
    required_cols = get_required_columns('operation_record')

    # 添加缺失的列
    for col in required_cols:
        if col not in record_df.columns:
            if col == "操作数量":
                record_df[col] = 0
            elif col == "操作类型":
                record_df[col] = "入库"
            elif col == "操作时间":
                record_df[col] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            else:
                record_df[col] = ""

    # 验证外键关联
    if "关联库存ID" in record_df.columns and "库存ID" in all_data.get('inventory', pd.DataFrame()).columns:
        inventory_ids = set(all_data['inventory']["库存ID"].tolist())
        record_df["关联库存ID"] = record_df["关联库存ID"].apply(
            lambda x: x if x in inventory_ids else -1
        )

    # 修复：重置索引
    return record_df.reset_index(drop=True)


def repair_manufacturer_table(manufacturer_df, all_data):
    """修复厂家表结构"""
    required_cols = get_required_columns('manufacturer')

    # 添加缺失的列
    for col in required_cols:
        if col not in manufacturer_df.columns:
            manufacturer_df[col] = ""

    # 修复：重置索引
    return manufacturer_df.reset_index(drop=True)


def repair_capacity_table(capacity_df, all_data):
    """修复容量表结构"""
    # 修复：确保楼层列是整数类型
    if "楼层" in capacity_df.columns:
        capacity_df["楼层"] = pd.to_numeric(capacity_df["楼层"], errors='coerce').fillna(0).astype(int)

    # 获取所有使用的楼层
    inventory_df = all_data.get('inventory', pd.DataFrame())
    location_df = all_data.get('location', pd.DataFrame())

    # 获取所有已使用的楼层
    used_floors = set()
    if not inventory_df.empty and "关联位置ID" in inventory_df.columns and not location_df.empty:
        # 获取库存表中的位置ID
        location_ids = inventory_df["关联位置ID"].dropna().tolist()
        # 从位置表获取对应的楼层
        if "地址ID" in location_df.columns and "楼层" in location_df.columns:
            location_df["地址ID"] = pd.to_numeric(location_df["地址ID"], errors='coerce').fillna(-1).astype(int)
            location_df["楼层"] = pd.to_numeric(location_df["楼层"], errors='coerce').fillna(0).astype(int)
            location_dict = location_df.set_index("地址ID")["楼层"].to_dict()
            for loc_id in location_ids:
                if loc_id in location_dict:
                    used_floors.add(int(location_dict[loc_id]))

    # 确保楼层1-5都存在
    for floor in range(1, 6):
        if floor not in capacity_df["楼层"].values:
            used_boxes = 1 if floor in used_floors else 0
            new_row = pd.DataFrame([{
                "楼层": floor,
                "楼层容量": FLOOR_CAPACITY if hasattr(globals(), 'FLOOR_CAPACITY') else 100,
                "楼层剩余容量": max(0, (FLOOR_CAPACITY if hasattr(globals(), 'FLOOR_CAPACITY') else 100) - used_boxes)
            }])
            capacity_df = pd.concat([capacity_df, new_row], ignore_index=True)

    # 修复：重置索引
    return capacity_df.reset_index(drop=True)


# ------------------- 核心数据操作函数 -------------------
def read_csv_data():
    """读取CSV数据 - 优先从缓存读取"""
    return get_cached_csv_data()


def write_csv_data(data):
    """写入CSV数据 - 安全的写入流程"""
    return safe_write_csv_files(data)


def add_data_to_csv(new_data_dict):
    """
    安全地添加数据到CSV文件
    new_data_dict: {'table_name': DataFrame或字典列表, ...}
    """
    try:
        # 1. 首先读取现有数据
        existing_data = read_csv_data()

        # 2. 合并新数据到现有数据
        for table_name, new_data in new_data_dict.items():
            if table_name in existing_data:
                if isinstance(new_data, pd.DataFrame):
                    new_df = new_data
                else:
                    # 如果是字典列表，转换为DataFrame
                    new_df = pd.DataFrame(new_data)

                if not new_df.empty:
                    # 生成自增ID（如果需要）
                    id_column = get_id_column(table_name)
                    if id_column and id_column not in new_df.columns:
                        # 获取下一个ID
                        next_id = generate_auto_id_df(existing_data[table_name], id_column)
                        new_df[id_column] = range(next_id, next_id + len(new_df))

                    # 合并数据
                    if not existing_data[table_name].empty:
                        existing_data[table_name] = pd.concat(
                            [existing_data[table_name], new_df],
                            ignore_index=True
                        )
                    else:
                        existing_data[table_name] = new_df

                    # 修复：重置索引
                    existing_data[table_name] = existing_data[table_name].reset_index(drop=True)
                    print(f"✅ 成功添加 {len(new_df)} 行数据到 {table_name}")

        # 3. 写入合并后的数据
        result = write_csv_data(existing_data)
        if result:
            print("🎉 数据添加成功")
        else:
            print("❌ 数据添加失败")
        return result

    except Exception as e:
        print(f"❌ 添加数据失败: {str(e)}")
        return False


# ------------------- 数据处理工具函数 -------------------
def generate_auto_id_df(df, id_column="ID"):
    """为DataFrame生成自增ID"""
    if df.empty or id_column not in df.columns or df[id_column].empty:
        return 1

    valid_ids = []
    for id_val in df[id_column].tolist():
        if isinstance(id_val, (int, float)) and not pd.isna(id_val):
            valid_ids.append(int(id_val))

    return max(valid_ids) + 1 if valid_ids else 1


def convert_to_serializable(value):
    """
    核心修改：优先用 pd.isna 拦截所有缺失值（包括 NaT），再处理其他类型
    彻底避免 NaT 走到 strftime 行
    """
    # ========== 第一步：优先拦截 ALL 缺失值（NaT/NaN/None/空字符串） ==========
    # pd.isna 能识别 NaT/NaN/None，是最可靠的判断方式
    if pd.isna(value) or value == "" or value is None:
        return ""

    # ========== 第二步：处理时间类型（此时已无 NaT） ==========
    # 兼容 pandas Timestamp + Python 原生 datetime
    if isinstance(value, (pd.Timestamp, datetime)):
        try:
            return value.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            return ""

    # ========== 第三步：处理数值类型（numpy → Python 原生） ==========
    if isinstance(value, (np.integer, np.int64, np.int32, int)):
        return int(value)
    if isinstance(value, (np.floating, np.float64, np.float32, float)):
        return float(value)

    # ========== 第四步：处理布尔类型 ==========
    if isinstance(value, (np.bool_, bool)):
        return bool(value)

    # ========== 第五步：兜底（确保为字符串） ==========
    try:
        return str(value) if not isinstance(value, (str, int, float, bool)) else value
    except:
        return ""


def df_to_serializable_list(df):
    """批量转换DataFrame为可序列化的字典列表"""
    if df.empty:
        return []
    # 替换 applymap：逐列（Series）调用 map，等价原 applymap 逻辑
    df_serialized = df.reset_index(drop=True).apply(
        lambda col: col.map(convert_to_serializable)  # 每一列（Series）用 map 处理每个元素
    )
    return df_serialized.to_dict('records')

def get_unit_by_addr_type(addr_type):
    """根据地址类型获取单位"""
    if addr_type == 1:
        return "框"
    elif addr_type in [2, 3]:
        return "包"
    elif addr_type in [4, 5, 6]:
        return "个"
    else:
        return "个"


def get_unique_boxes_by_floor(floor, location_list):
    """获取指定楼层使用的唯一框号集合"""
    used_boxes = set()
    for item in location_list:
        item_floor = item.get("楼层", 0)
        if item_floor == floor and "框号" in item and item["框号"] and not pd.isna(item["框号"]):
            box_no = str(item["框号"]).strip()
            if box_no:
                used_boxes.add(box_no)
    return used_boxes


def update_capacity(floor, location_list, capacity_df):
    """更新指定楼层的剩余容量，无记录则创建"""
    # 修复：确保floor是整数
    floor = int(floor) if isinstance(floor, (int, float)) else 0
    used_boxes = len(get_unique_boxes_by_floor(floor, location_list))

    # 修复：确保楼层列是整数
    capacity_df["楼层"] = pd.to_numeric(capacity_df["楼层"], errors='coerce').fillna(0).astype(int)
    floor_capacity_rows = capacity_df[capacity_df["楼层"] == floor]

    floor_capacity_val = FLOOR_CAPACITY if hasattr(globals(), 'FLOOR_CAPACITY') else 100
    if floor_capacity_rows.empty:
        floor_capacity = {
            "楼层": floor,
            "楼层容量": floor_capacity_val,
            "楼层剩余容量": max(0, floor_capacity_val - used_boxes)
        }
        new_row = pd.DataFrame([floor_capacity])
        capacity_df = pd.concat([capacity_df, new_row], ignore_index=True)
        # 修复：重置索引
        capacity_df = capacity_df.reset_index(drop=True)
        return floor_capacity, capacity_df
    else:
        index = floor_capacity_rows.index[0]
        capacity_df.at[index, "楼层剩余容量"] = max(0, floor_capacity_val - used_boxes)
        return capacity_df.iloc[index].to_dict(), capacity_df


def update_inventory_status(inventory_id, csv_data):
    """更新库存状态（基于操作记录）"""
    # 修复：确保inventory_id是整数
    inventory_id = int(inventory_id) if isinstance(inventory_id, (int, float)) else -1

    inventory_df = csv_data.get("inventory", pd.DataFrame())
    operation_df = csv_data.get("operation_record", pd.DataFrame())

    if inventory_df.empty or "库存ID" not in inventory_df.columns:
        return

    # 修复：标准化库存ID列
    inventory_df["库存ID"] = pd.to_numeric(inventory_df["库存ID"], errors='coerce').fillna(-1).astype(int)
    mask = inventory_df["库存ID"] == inventory_id

    if not mask.any():
        return

    # 计算总入库和总出库数量
    if not operation_df.empty and "关联库存ID" in operation_df.columns and "操作类型" in operation_df.columns and "操作数量" in operation_df.columns:
        # 标准化操作记录的关联库存ID和操作数量
        operation_df["关联库存ID"] = pd.to_numeric(operation_df["关联库存ID"], errors='coerce').fillna(-1).astype(int)
        operation_df["操作数量"] = pd.to_numeric(operation_df["操作数量"], errors='coerce').fillna(0).astype(int)

        # 入库操作
        stock_in = operation_df[
            (operation_df["关联库存ID"] == inventory_id) &
            (operation_df["操作类型"] == "入库")
            ]["操作数量"].sum()

        # 出库操作
        stock_out = operation_df[
            (operation_df["关联库存ID"] == inventory_id) &
            (operation_df["操作类型"] == "出库")
            ]["操作数量"].sum()

        current_stock = stock_in - stock_out

        # 更新库存数量
        inventory_df.loc[mask, "库存数量"] = current_stock

        # 更新状态
        if current_stock > 0:
            status = "正常"
        elif current_stock == 0:
            status = "已出库"
        else:
            status = "异常"

        inventory_df.loc[mask, "状态"] = status

    # 修复：重置索引
    csv_data["inventory"] = inventory_df.reset_index(drop=True)


# ------------------- 缓存优化 -------------------
_data_cache = {}
_cache_timestamp = None


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


def write_csv_data_optimized(csv_data):
    """优化的数据写入函数"""
    try:
        global _data_cache, _cache_timestamp
        _data_cache = {}
        _cache_timestamp = None
        return write_csv_data(csv_data)
    except Exception as e:
        print(f"❌ 数据写入失败: {str(e)}")
        return False


# ------------------- 兼容性函数（保持原有接口） -------------------
def init_or_fix_excel_file():
    """兼容性函数，保持原有接口"""
    return init_or_fix_csv_files()


def read_excel_data():
    """兼容性函数，保持原有接口"""
    return read_csv_data()


def write_excel_data(data):
    """兼容性函数，保持原有接口"""
    return write_csv_data(data)


def safe_read_excel_file():
    """兼容性函数，保持原有接口"""
    return safe_read_csv_files()


def safe_write_excel_file(data):
    """兼容性函数，保持原有接口"""
    return safe_write_csv_files(data)


# ------------------- 备份管理功能 -------------------
def list_backups():
    """列出所有备份文件"""
    try:
        backup_pattern = os.path.join(CSV_DIR, "*.backup*")
        backup_files = glob.glob(backup_pattern)

        if backup_files:
            print("📋 现有备份文件:")
            for backup_file in backup_files:
                file_size = os.path.getsize(backup_file)
                mod_time = datetime.fromtimestamp(os.path.getmtime(backup_file))
                print(f"  {os.path.basename(backup_file)}")
                print(f"    大小: {file_size} 字节, 修改时间: {mod_time}")
        else:
            print("ℹ️  没有找到备份文件")

        return backup_files
    except Exception as e:
        print(f"❌ 列出备份文件失败: {str(e)}")
        return []


def cleanup_all_backups():
    """清理所有备份文件"""
    try:
        backup_files = list_backups()
        if not backup_files:
            print("ℹ️  没有备份文件需要清理")
            return True

        confirm = input("⚠️  确定要删除所有备份文件吗？(y/N): ")
        if confirm.lower() == 'y':
            deleted_count = 0
            for backup_file in backup_files:
                try:
                    os.remove(backup_file)
                    deleted_count += 1
                    print(f"🗑️  删除: {backup_file}")
                except Exception as e:
                    print(f"⚠️ 删除 {backup_file} 失败: {str(e)}")

            print(f"✅ 已删除 {deleted_count} 个备份文件")
            return deleted_count == len(backup_files)
        else:
            print("❌ 操作已取消")
            return False

    except Exception as e:
        print(f"❌ 清理备份失败: {str(e)}")
        return False