# other_utils.py
import pandas as pd
import numpy as np
from datetime import datetime
import os
from config import *
from read_utils import timing_decorator, TimingTracker, CSV_FILES, CSV_DIR, ensure_csv_directory, safe_read_csv_files, invalidate_cache
from write_utils import get_required_columns, get_empty_dataframe_template, get_unique_boxes_by_floor, safe_write_csv_files


# ------------------- 数据处理工具函数 -------------------
@timing_decorator
def generate_auto_id_df(df, id_column="ID"):
    """为DataFrame生成自增ID"""
    if df.empty or id_column not in df.columns or df[id_column].empty:
        return 1

    valid_ids = []
    for id_val in df[id_column].tolist():
        if isinstance(id_val, (int, float)) and not pd.isna(id_val):
            valid_ids.append(int(id_val))

    return max(valid_ids) + 1 if valid_ids else 1


@timing_decorator
def convert_to_serializable(value):
    """优化的序列化转换函数"""
    if pd.isna(value) or value == "" or value is None:
        return ""
    elif isinstance(value, (np.integer, np.int64, np.int32)):
        return int(value)
    elif isinstance(value, (np.floating, np.float64, np.float32)):
        return float(value) if not pd.isna(value) else 0.0
    elif isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    elif isinstance(value, np.bool_):
        return bool(value)
    else:
        return str(value) if not isinstance(value, (str, int, float, bool)) else value


@timing_decorator
def df_to_serializable_list(df):
    """批量转换DataFrame为可序列化的字典列表"""
    if df.empty:
        return []
    return df.applymap(convert_to_serializable).to_dict('records')


@timing_decorator
def get_unit_by_addr_type(addr_type):
    if addr_type == 1:
        return "框"
    elif addr_type in [2, 3]:
        return "包"
    elif addr_type in [4, 5, 6]:
        return "个"
    else:
        return "个"


@timing_decorator
def update_stock_capacity(floor, inventory_list, stock_capacity_df):
    """更新指定楼层的剩余容量，无记录则创建"""
    used_boxes = len(get_unique_boxes_by_floor(floor, inventory_list))

    floor_capacity_rows = stock_capacity_df[stock_capacity_df["楼层"] == floor]

    if floor_capacity_rows.empty:
        floor_capacity = {
            "楼层": floor,
            "楼层容量": FLOOR_CAPACITY,
            "楼层剩余容量": max(0, FLOOR_CAPACITY - used_boxes)
        }
        new_row = pd.DataFrame([floor_capacity])
        stock_capacity_df = pd.concat([stock_capacity_df, new_row], ignore_index=True)
        return floor_capacity, stock_capacity_df
    else:
        index = floor_capacity_rows.index[0]
        stock_capacity_df.at[index, "楼层剩余容量"] = max(0, FLOOR_CAPACITY - used_boxes)
        return stock_capacity_df.iloc[index].to_dict(), stock_capacity_df


@timing_decorator
def update_inventory_status(inventory_id, csv_data):
    """更新库存状态"""
    inventory_df = csv_data["inventory"]

    mask = inventory_df["ID"] == inventory_id
    if not inventory_df[mask].any().any():
        return

    current_stock = inventory_df.loc[mask, "入库数量"].iloc[0] - inventory_df.loc[mask, "出库总数量"].iloc[0]
    inventory_df.loc[mask, "库存数量"] = current_stock

    if current_stock > 0:
        status = "已入库"
    elif current_stock == 0:
        status = "已出库"
    else:
        status = "未知库存"

    inventory_df.loc[mask, "状态"] = status


# ------------------- 数据初始化函数 -------------------
@timing_decorator
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


@timing_decorator
def create_new_csv_files():
    """创建新的CSV文件 - 安全的创建流程"""
    try:
        # 确保CSV目录存在
        ensure_csv_directory()

        # 读取现有数据（如果有）
        existing_data = safe_read_csv_files()

        # 创建标准数据结构
        new_data = {
            'inventory': get_empty_dataframe_template('inventory'),
            'manufacturer': get_empty_dataframe_template('manufacturer'),
            'feature': get_empty_dataframe_template('feature'),
            'stock_capacity': get_empty_dataframe_template('stock_capacity'),
            'stock_out_records': get_empty_dataframe_template('stock_out_records')
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
                        if col in ["入库数量", "出库总数量", "库存数量", "地址类型", "楼层"]:
                            existing_df[col] = 0
                        elif col == "状态":
                            existing_df[col] = "已入库"
                        elif col == "单位":
                            existing_df[col] = "框"
                        else:
                            existing_df[col] = ""

                # 移除多余的列
                for col in existing_df.columns:
                    if col not in template_df.columns:
                        existing_df = existing_df.drop(columns=[col])

                merged_data[table] = existing_df
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
@timing_decorator
def repair_csv_structure(data):
    """修复CSV数据结构 - 安全的修复流程"""
    timing_tracker.start_operation("repair_csv_structure")
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

        # 修复各个表的结构
        repair_functions = {
            'inventory': repair_inventory_table,
            'manufacturer': repair_manufacturer_table,
            'feature': repair_feature_table,
            'stock_capacity': repair_stock_capacity_table,
            'stock_out_records': repair_stock_out_records_table
        }

        for table, repair_func in repair_functions.items():
            if table in data:
                data[table] = repair_func(data[table], data)

        # 保存修复后的数据
        result = safe_write_csv_files(data)

        timing_tracker.end_operation()
        if result:
            print("✅ CSV文件修复成功")
        else:
            print("❌ CSV文件修复失败")
        return result

    except Exception as e:
        timing_tracker.end_operation()
        print(f"❌ 修复CSV结构失败: {str(e)}")
        return False


def repair_inventory_table(inventory_df, all_data):
    """修复库存表结构"""
    required_cols = get_required_columns('inventory')

    # 添加缺失的列
    for col in required_cols:
        if col not in inventory_df.columns:
            if col in ["入库数量", "出库总数量", "库存数量", "地址类型", "楼层"]:
                inventory_df[col] = 0
            elif col == "状态":
                inventory_df[col] = "已入库"
            elif col == "单位":
                inventory_df[col] = "框"
            else:
                inventory_df[col] = ""

    # 计算库存数量
    if "入库数量" in inventory_df.columns and "出库总数量" in inventory_df.columns:
        inventory_df["库存数量"] = inventory_df["入库数量"] - inventory_df["出库总数量"]

        # 更新状态
        inventory_df["状态"] = np.where(
            inventory_df["库存数量"] > 0,
            "已入库",
            np.where(inventory_df["库存数量"] == 0, "已出库", "未知库存")
        )

    return inventory_df


def repair_manufacturer_table(manufacturer_df, all_data):
    """修复厂家表结构"""
    required_cols = get_required_columns('manufacturer')
    for col in required_cols:
        if col not in manufacturer_df.columns:
            manufacturer_df[col] = ""
    return manufacturer_df


def repair_feature_table(feature_df, all_data):
    """修复特征表结构"""
    required_cols = get_required_columns('feature')
    for col in required_cols:
        if col not in feature_df.columns:
            if col in ["单价", "重量"]:
                feature_df[col] = 0.0
            else:
                feature_df[col] = ""
    return feature_df


def repair_stock_capacity_table(stock_capacity_df, all_data):
    """修复库存容量表结构"""
    # 获取所有使用的楼层
    inventory_df = all_data.get('inventory', pd.DataFrame())
    inventory_list = inventory_df.to_dict('records') if not inventory_df.empty else []

    existing_floors = set(stock_capacity_df["楼层"].tolist()) if "楼层" in stock_capacity_df.columns else set()

    for floor in FLOORS:
        if floor not in existing_floors:
            used_boxes = len(get_unique_boxes_by_floor(floor, inventory_list))
            new_row = pd.DataFrame([{
                "楼层": floor,
                "楼层容量": FLOOR_CAPACITY,
                "楼层剩余容量": max(0, FLOOR_CAPACITY - used_boxes)
            }])
            stock_capacity_df = pd.concat([stock_capacity_df, new_row], ignore_index=True)

    return stock_capacity_df


def repair_stock_out_records_table(stock_out_records_df, all_data):
    """修复出库记录表结构"""
    required_cols = get_required_columns('stock_out_records')
    for col in required_cols:
        if col not in stock_out_records_df.columns:
            if col == "出库数量":
                stock_out_records_df[col] = 0
            else:
                stock_out_records_df[col] = ""
    return stock_out_records_df


# ------------------- 兼容性函数 -------------------
def init_or_fix_excel_file():
    """兼容性函数，保持原有接口"""
    return init_or_fix_csv_files()


# ------------------- 使用示例和测试函数 -------------------
@timing_decorator
def demo_safe_data_addition():
    """演示安全的数据添加流程"""
    print("\n" + "=" * 50)
    print("演示安全数据添加流程")
    print("=" * 50)

    # 1. 初始化CSV文件
    print("1. 初始化CSV文件...")
    init_or_fix_csv_files()

    # 2. 读取现有数据
    from read_utils import read_csv_data
    print("2. 读取现有数据...")
    data = read_csv_data()

    # 3. 准备新数据
    print("3. 准备新数据...")
    new_inventory_data = {
        "ID": [generate_auto_id_df(data['inventory'])],
        "商品编号": ["TEST001"],
        "入库时间": [datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
        "入库数量": [100],
        "出库总数量": [0],
        "状态": ["已入库"],
        "库存数量": [100],
        "地址类型": [1],
        "楼层": [1],
        "架号": ["A"],
        "框号": ["01"],
        "包号": [""],
        "单位": ["框"]
    }

    new_inventory_df = pd.DataFrame(new_inventory_data)

    # 4. 安全添加数据
    from write_utils import add_data_to_csv
    print("4. 安全添加数据...")
    result = add_data_to_csv({
        'inventory': new_inventory_df
    })

    if result:
        print("✅ 演示完成：数据安全添加成功")
    else:
        print("❌ 演示失败：数据添加失败")

    return result


@timing_decorator
def performance_test():
    """性能测试函数，测试所有读写操作的执行时间"""
    print("🚀 开始性能测试...")

    # 重置时间统计
    global timing_tracker
    timing_tracker = TimingTracker()

    # 测试读取操作
    print("\n📊 读取操作测试:")
    from read_utils import read_csv_data, read_csv_data_cached
    data1 = read_csv_data()
    data2 = read_csv_data_cached()

    # 测试写入操作（创建测试数据）
    print("\n💾 写入操作测试:")
    from write_utils import write_csv_data, write_csv_data_optimized
    test_data = data1.copy()
    write_csv_data(test_data)
    write_csv_data_optimized(test_data)

    # 测试安全数据添加
    print("\n➕ 安全数据添加测试:")
    demo_safe_data_addition()

    # 打印详细统计
    timing_tracker.print_summary()

    print("\n✅ 性能测试完成")


# 如果直接运行此文件，执行演示和测试
if __name__ == "__main__":
    # 执行演示
    demo_safe_data_addition()

    # 执行性能测试
    performance_test()