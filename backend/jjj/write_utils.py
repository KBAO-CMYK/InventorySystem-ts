# write_utils.py
import pandas as pd
import numpy as np
import shutil
import os
import glob
from datetime import datetime
from config import *
from read_utils import safe_read_csv_files, invalidate_cache, CSV_FILES, CSV_DIR, ensure_csv_directory, \
    timing_decorator, timing_tracker


def get_required_columns(table_name):
    """获取指定表必需的列"""
    required_columns = {
        'inventory': [
            "ID", "商品编号", "入库时间", "入库数量", "出库总数量", "状态",
            "库存数量", "地址类型", "楼层", "架号", "框号", "包号", "单位"
        ],
        'manufacturer': ["ID", "inventory_id", "厂家货号", "厂家", "厂家地址", "电话"],
        'feature': [
            "ID", "inventory_id", "商品类型", "单价", "重量", "用途",
            "规格", "备注", "材质", "颜色", "形状", "风格"
        ],
        'stock_capacity': ["楼层", "楼层容量", "楼层剩余容量"],
        'stock_out_records': ["ID", "inventory_id", "出库时间", "出库数量", "操作人员", "备注"]
    }
    return required_columns.get(table_name, [])


def get_empty_dataframe_template(table_name):
    """获取指定表的空DataFrame模板"""
    templates = {
        'inventory': pd.DataFrame(columns=[
            "ID", "商品编号", "入库时间", "入库数量", "出库总数量", "状态",
            "库存数量", "地址类型", "楼层", "架号", "框号", "包号", "单位"
        ]),
        'manufacturer': pd.DataFrame(columns=[
            "ID", "inventory_id", "厂家货号", "厂家", "厂家地址", "电话"
        ]),
        'feature': pd.DataFrame(columns=[
            "ID", "inventory_id", "商品类型", "单价", "重量", "用途",
            "规格", "备注", "材质", "颜色", "形状", "风格"
        ]),
        'stock_capacity': pd.DataFrame(columns=[
            "楼层", "楼层容量", "楼层剩余容量"
        ]),
        'stock_out_records': pd.DataFrame(columns=[
            "ID", "inventory_id", "出库时间", "出库数量", "操作人员", "备注"
        ])
    }
    return templates.get(table_name, pd.DataFrame())


def get_unique_boxes_by_floor(floor, inventory_list):
    """获取指定楼层使用的唯一框号集合"""
    used_boxes = set()
    for item in inventory_list:
        item_floor = item.get("楼层", 0)
        if item_floor == floor and "框号" in item and item["框号"] and not pd.isna(item["框号"]):
            box_no = str(item["框号"]).strip()
            if box_no:
                used_boxes.add(box_no)
    return used_boxes


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


@timing_decorator
def safe_write_csv_files(data):
    """安全地写入所有CSV文件 - 使用单一备份策略"""
    try:
        # 确保CSV目录存在
        ensure_csv_directory()

        # 首先读取现有数据，确保不会覆盖
        existing_data = safe_read_csv_files()

        # 合并现有数据和新数据（以新数据为准，但保留现有数据的其他行）
        merged_data = {}
        for table in REQUIRED_TABLES:
            if table in data and not data[table].empty:
                if table in existing_data and not existing_data[table].empty:
                    # 如果有ID列，基于ID合并，否则直接使用新数据
                    if 'ID' in data[table].columns and 'ID' in existing_data[table].columns:
                        # 获取新数据的ID集合
                        new_ids = set(data[table]['ID'].astype(str))
                        # 保留现有数据中不在新数据ID中的行
                        existing_filtered = existing_data[table][
                            ~existing_data[table]['ID'].astype(str).isin(new_ids)
                        ]
                        # 合并数据
                        merged_data[table] = pd.concat([existing_filtered, data[table]], ignore_index=True)
                    else:
                        # 没有ID列，直接使用新数据
                        merged_data[table] = data[table]
                else:
                    # 没有现有数据，直接使用新数据
                    merged_data[table] = data[table]
            else:
                # 新数据为空，使用现有数据
                merged_data[table] = existing_data.get(table, pd.DataFrame())

        # 创建单一备份（覆盖旧备份）
        timing_tracker.start_operation("create_backup")
        backup_created = create_single_backup()
        timing_tracker.end_operation()

        if not backup_created:
            print("⚠️ 备份创建失败，但继续执行写入操作")

        # 写入CSV文件
        timing_tracker.start_operation("write_csv_files")
        write_success = True
        for table, filepath in CSV_FILES.items():
            try:
                df = merged_data.get(table, pd.DataFrame())
                if not df.empty:
                    # 确保目录存在
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    df.to_csv(filepath, index=False, encoding='utf-8-sig')
                    print(f"💾 成功写入 {table}，行数: {len(df)}")
                else:
                    # 如果数据为空，创建空的CSV文件（只有表头）
                    df_template = get_empty_dataframe_template(table)
                    df_template.to_csv(filepath, index=False, encoding='utf-8-sig')
                    print(f"📄 创建空文件: {table}")
            except Exception as e:
                print(f"❌ 写入 {table} 文件失败: {str(e)}")
                write_success = False

        timing_tracker.end_operation()

        if write_success:
            print("✅ 所有CSV文件写入成功")
            invalidate_cache()
            return True
        else:
            print("❌ 部分文件写入失败，尝试从备份恢复")
            # 写入失败时尝试恢复备份
            restore_from_backup()
            return False

    except Exception as e:
        print(f"❌ 写入CSV文件失败: {str(e)}")
        # 发生异常时尝试恢复备份
        restore_from_backup()
        return False


@timing_decorator
def write_csv_data(data):
    """写入CSV数据 - 安全的写入流程"""
    return safe_write_csv_files(data)


@timing_decorator
def add_data_to_csv(new_data_dict):
    """
    安全地添加数据到CSV文件
    new_data_dict: {'table_name': DataFrame或字典列表, ...}
    """
    try:
        from read_utils import read_csv_data

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
                    # 合并数据
                    if not existing_data[table_name].empty:
                        existing_data[table_name] = pd.concat(
                            [existing_data[table_name], new_df],
                            ignore_index=True
                        )
                    else:
                        existing_data[table_name] = new_df

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


@timing_decorator
def write_csv_data_optimized(csv_data):
    """优化的数据写入函数"""
    try:
        from read_utils import _data_cache, _cache_timestamp
        _data_cache = {}
        _cache_timestamp = None
        return write_csv_data(csv_data)
    except Exception as e:
        print(f"❌ 数据写入失败: {str(e)}")
        return False


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


# ------------------- 兼容性函数 -------------------
def write_excel_data(data):
    """兼容性函数，保持原有接口"""
    return write_csv_data(data)


def safe_write_excel_file(data):
    """兼容性函数，保持原有接口"""
    return safe_write_csv_files(data)