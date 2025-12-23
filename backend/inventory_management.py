from flask import jsonify, request
import pandas as pd
import time
from utils import *
from config import *
from datetime import datetime
import traceback

def convert_to_serializable(value):
    """将非JSON序列化类型转换为原生类型"""
    # 处理Numpy数值类型
    if isinstance(value, np.integer):
        return int(value)
    elif isinstance(value, np.floating):
        return float(value)
    # 处理Pandas时间类型
    elif isinstance(value, pd.Timestamp):
        if pd.isna(value):
            return ""
        return value.strftime("%Y-%m-%d %H:%M:%S")
    # 处理Python datetime类型
    elif isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    # 处理NaN/NaT等空值
    elif pd.isna(value) or value is None:
        return ""
    # 其他类型直接返回
    else:
        return value

def get_inventory_detail(inventory_id, page=1, page_size=50):
    """查询库存详情 - 统一计算入库/出库/借/还后的库存数量"""
    try:
        csv_data = read_csv_data()

        # 获取所有相关表
        inventory_df = csv_data.get("inventory", pd.DataFrame())
        feature_df = csv_data.get("feature", pd.DataFrame())
        product_df = csv_data.get("product", pd.DataFrame())
        location_df = csv_data.get("location", pd.DataFrame())
        manufacturer_df = csv_data.get("manufacturer", pd.DataFrame())
        operation_df = csv_data.get("operation_record", pd.DataFrame())

        # 校验库存ID是否存在
        if inventory_df.empty or "库存ID" not in inventory_df.columns:
            return {"status": "error", "message": "库存数据表格结构异常"}, 500

        # 筛选目标库存
        inventory_df["库存ID"] = pd.to_numeric(inventory_df["库存ID"], errors="coerce").fillna(-1).astype(int)
        target_inventory = inventory_df[inventory_df["库存ID"] == inventory_id]

        if target_inventory.empty:
            return {"status": "error", "message": f"未找到ID为{inventory_id}的库存记录"}, 404

        # 获取关联ID
        inventory_record = target_inventory.iloc[0]
        feature_id = inventory_record.get("关联商品特征ID")
        location_id = inventory_record.get("关联位置ID")
        manufacturer_id = inventory_record.get("关联厂家ID")

        # 获取商品特征信息
        target_features = pd.DataFrame()
        if feature_id is not None and not feature_df.empty and "商品特征ID" in feature_df.columns:
            feature_df["商品特征ID"] = pd.to_numeric(feature_df["商品特征ID"], errors="coerce").fillna(
                -1).astype(int)
            target_features = feature_df[feature_df["商品特征ID"] == feature_id].copy()

        # 获取商品信息
        target_products = pd.DataFrame()
        if feature_id is not None and not target_features.empty and not product_df.empty and "商品ID" in product_df.columns:
            product_id = target_features.iloc[0].get("关联商品ID")
            if product_id is not None:
                product_df["商品ID"] = pd.to_numeric(product_df["商品ID"], errors="coerce").fillna(-1).astype(int)
                target_products = product_df[product_df["商品ID"] == product_id].copy()

        # 获取位置信息
        target_locations = pd.DataFrame()
        if location_id is not None and not location_df.empty and "地址ID" in location_df.columns:
            location_df["地址ID"] = pd.to_numeric(location_df["地址ID"], errors="coerce").fillna(-1).astype(int)
            target_locations = location_df[location_df["地址ID"] == location_id].copy()

        # 获取厂家信息
        target_manufacturers = pd.DataFrame()
        if manufacturer_id is not None and not manufacturer_df.empty and "厂家ID" in manufacturer_df.columns:
            manufacturer_df["厂家ID"] = pd.to_numeric(manufacturer_df["厂家ID"], errors="coerce").fillna(-1).astype(int)
            target_manufacturers = manufacturer_df[manufacturer_df["厂家ID"] == manufacturer_id].copy()

        # 获取操作记录
        target_operations = pd.DataFrame()
        if inventory_id is not None and not operation_df.empty and "关联库存ID" in operation_df.columns:
            operation_df["关联库存ID"] = pd.to_numeric(operation_df["关联库存ID"], errors="coerce").fillna(-1).astype(
                int)
            target_operations = operation_df[operation_df["关联库存ID"] == inventory_id].copy()

        # 操作记录分页
        page = max(1, int(page))  # 确保是Python原生int
        page_size = max(10, min(int(page_size), 100))  # 确保是Python原生int
        total_operations = int(len(target_operations))  # 转换为Python原生int
        total_pages = int((total_operations + page_size - 1) // page_size)  # 转换为Python原生int

        # 分页截取
        paginated_operations = pd.DataFrame()
        if not target_operations.empty:
            target_operations["操作时间"] = pd.to_datetime(target_operations["操作时间"], errors="coerce")
            target_operations = target_operations.sort_values("操作时间", ascending=False)
            start = (page - 1) * page_size
            end = start + page_size
            paginated_operations = target_operations.iloc[start:end]

        def serialize_df(df):
            """DataFrame序列化（确保所有值为JSON可序列化类型）"""
            if df.empty:
                return []
            # 逐元素转换为可序列化类型
            df_serializable = df.apply(lambda col: col.map(convert_to_serializable))
            return df_serializable.to_dict('records')

        # 数据序列化
        inventory_dict = serialize_df(target_inventory)[0] if serialize_df(target_inventory) else {}
        product_list = serialize_df(target_products)
        feature_list = serialize_df(target_features)
        location_list = serialize_df(target_locations)
        manufacturer_list = serialize_df(target_manufacturers)
        operation_list = serialize_df(paginated_operations)

        # 计算操作统计（包含借/还）
        total_in_quantity = 0.0
        total_out_quantity = 0.0
        total_lend_quantity = 0.0
        total_return_quantity = 0.0
        other_stats = {}

        if not target_operations.empty:
            # 确保操作数量为数值类型
            target_operations["操作数量"] = pd.to_numeric(target_operations["操作数量"], errors="coerce").fillna(0)

            # 入库/出库统计（转换为Python原生float）
            in_operations = target_operations[target_operations["操作类型"] == "入库"]
            total_in_quantity = float(in_operations["操作数量"].sum()) if not in_operations.empty else 0.0

            out_operations = target_operations[target_operations["操作类型"] == "出库"]
            total_out_quantity = float(out_operations["操作数量"].sum()) if not out_operations.empty else 0.0

            # 借/还统计（转换为Python原生float）
            lend_operations = target_operations[target_operations["操作类型"] == "借"]
            total_lend_quantity = float(lend_operations["操作数量"].sum()) if not lend_operations.empty else 0.0

            return_operations = target_operations[target_operations["操作类型"] == "还"]
            total_return_quantity = float(return_operations["操作数量"].sum()) if not return_operations.empty else 0.0

            # 其他操作类型（确保数值为Python原生类型）
            other_operations = target_operations[~target_operations["操作类型"].isin(["入库", "出库", "借", "还"])]
            if not other_operations.empty:
                for op_type in other_operations["操作类型"].unique():
                    op_type_str = str(op_type)  # 确保操作类型是字符串
                    type_ops = other_operations[other_operations["操作类型"] == op_type]
                    other_stats[op_type_str] = {
                        "次数": int(len(type_ops)),  # 转换为Python原生int
                        "总数量": float(type_ops["操作数量"].sum())  # 转换为Python原生float
                    }

        # 统一计算当前库存（转换为Python原生float）
        current_stock = float(total_in_quantity - total_out_quantity - total_lend_quantity + total_return_quantity)
        inventory_dict["库存数量"] = round(current_stock, 2)
        inventory_dict["累计入库数量"] = total_in_quantity
        inventory_dict["累计出库数量"] = total_out_quantity
        inventory_dict["累计借出数量"] = total_lend_quantity
        inventory_dict["累计归还数量"] = total_return_quantity

        # 操作统计信息（确保所有值为JSON可序列化类型）
        last_operation_time = ""
        if not target_operations.empty:
            last_op_time = target_operations["操作时间"].max()
            last_operation_time = convert_to_serializable(last_op_time)

        operation_stats = {
            "total_in_quantity": float(total_in_quantity),
            "total_out_quantity": float(total_out_quantity),
            "total_lend_quantity": float(total_lend_quantity),
            "total_return_quantity": float(total_return_quantity),
            "current_stock": float(current_stock),
            "total_operations": int(total_operations),
            "other_operations": other_stats,
            "last_operation_time": last_operation_time
        }

        # 处理多记录警告提示
        warnings = []
        if len(product_list) > 1:
            warnings.append(f"该库存关联{len(product_list)}个商品记录，请确认数据是否正常")
        if len(feature_list) > 1:
            warnings.append(f"该库存关联{len(feature_list)}个特征记录，请确认数据是否正常")
        if len(location_list) > 1:
            warnings.append(f"该库存关联{len(location_list)}个位置记录，请确认数据是否正常")
        if len(manufacturer_list) > 1:
            warnings.append(f"该库存关联{len(manufacturer_list)}个厂家记录，请确认数据是否正常")

        # 组装响应数据（确保所有数值为Python原生类型）
        response_data = {
            "status": "success",
            "data": {
                "inventory": inventory_dict,
                "product": product_list[0] if product_list else {},
                "feature": feature_list[0] if feature_list else {},
                "location": location_list[0] if location_list else {},
                "manufacturer": manufacturer_list[0] if manufacturer_list else {},
                "operations": operation_list,
                "operation_stats": operation_stats
            },
            "pagination": {
                "total": int(total_operations),
                "page": int(page),
                "page_size": int(page_size),
                "total_pages": int(total_pages)
            }
        }

        if warnings:
            response_data["warnings"] = warnings

        return response_data, 200

    except IndexError as e:
        print(f"库存详情查询索引异常：{str(e)}")
        return {"status": "error", "message": "库存数据索引错误，请检查数据完整性"}, 500
    except TypeError as e:
        print(f"库存详情查询类型异常：{str(e)}")
        return {"status": "error", "message": "数据类型转换错误，请检查字段格式"}, 500
    except Exception as e:
        print(f"获取库存详情异常: {str(e)}")
        return {"status": "error", "message": f"系统异常：{str(e)}"}, 500


def serialize_df(df):
    """
    重写序列化函数：强制逐单元格处理，避免 datetime 列的 map 特殊行为
    """
    if df.empty:
        return []

    # 先将所有 datetime 列转为字符串（主动处理 NaT）
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            # 直接将 datetime 列转为字符串，NaT → 空字符串
            df[col] = df[col].dt.strftime("%Y-%m-%d %H:%M:%S").fillna("")

    # 再逐元素序列化（此时已无 datetime 类型，只有字符串/数值）
    df_serializable = df.apply(lambda col: col.map(convert_to_serializable))
    return df_serializable.to_dict('records')


# ===================== 核心业务函数 =====================
def get_inventory_detail(inventory_id, page=1, page_size=50):
    """查询库存详情 - 统一计算入库/出库/借/还后的库存数量"""
    try:
        csv_data = read_csv_data()

        # 获取所有相关表（加 copy 避免原数据被修改）
        inventory_df = csv_data.get("inventory", pd.DataFrame()).copy()
        feature_df = csv_data.get("feature", pd.DataFrame()).copy()
        product_df = csv_data.get("product", pd.DataFrame()).copy()
        location_df = csv_data.get("location", pd.DataFrame()).copy()
        manufacturer_df = csv_data.get("manufacturer", pd.DataFrame()).copy()
        operation_df = csv_data.get("operation_record", pd.DataFrame()).copy()

        # 校验库存ID是否存在
        if inventory_df.empty or "库存ID" not in inventory_df.columns:
            return {"status": "error", "message": "库存数据表格结构异常"}, 500

        # 筛选目标库存
        inventory_df["库存ID"] = pd.to_numeric(inventory_df["库存ID"], errors="coerce").fillna(-1).astype(int)
        target_inventory = inventory_df[inventory_df["库存ID"] == inventory_id].copy()

        if target_inventory.empty:
            return {"status": "error", "message": f"未找到ID为{inventory_id}的库存记录"}, 404

        # 获取关联ID
        inventory_record = target_inventory.iloc[0]
        feature_id = inventory_record.get("关联商品特征ID")
        location_id = inventory_record.get("关联位置ID")
        manufacturer_id = inventory_record.get("关联厂家ID")

        # 获取商品特征信息
        target_features = pd.DataFrame()
        if feature_id is not None and not feature_df.empty and "商品特征ID" in feature_df.columns:
            feature_df["商品特征ID"] = pd.to_numeric(feature_df["商品特征ID"], errors="coerce").fillna(-1).astype(int)
            target_features = feature_df[feature_df["商品特征ID"] == feature_id].copy()

        # 获取商品信息
        target_products = pd.DataFrame()
        if feature_id is not None and not target_features.empty and not product_df.empty and "商品ID" in product_df.columns:
            product_id = target_features.iloc[0].get("关联商品ID")
            if product_id is not None and product_id != "":
                product_df["商品ID"] = pd.to_numeric(product_df["商品ID"], errors="coerce").fillna(-1).astype(int)
                target_products = product_df[product_df["商品ID"] == int(product_id)].copy()

        # 获取位置信息
        target_locations = pd.DataFrame()
        if location_id is not None and not location_df.empty and "地址ID" in location_df.columns:
            location_df["地址ID"] = pd.to_numeric(location_df["地址ID"], errors="coerce").fillna(-1).astype(int)
            target_locations = location_df[location_df["地址ID"] == location_id].copy()

        # 获取厂家信息
        target_manufacturers = pd.DataFrame()
        if manufacturer_id is not None and not manufacturer_df.empty and "厂家ID" in manufacturer_df.columns:
            manufacturer_df["厂家ID"] = pd.to_numeric(manufacturer_df["厂家ID"], errors="coerce").fillna(-1).astype(int)
            target_manufacturers = manufacturer_df[manufacturer_df["厂家ID"] == manufacturer_id].copy()

        # 获取操作记录
        target_operations = pd.DataFrame()
        if inventory_id is not None and not operation_df.empty and "关联库存ID" in operation_df.columns:
            operation_df["关联库存ID"] = pd.to_numeric(operation_df["关联库存ID"], errors="coerce").fillna(-1).astype(
                int)
            target_operations = operation_df[operation_df["关联库存ID"] == inventory_id].copy()

        # 操作记录分页
        page = max(1, int(page))
        page_size = max(10, min(int(page_size), 100))
        total_operations = int(len(target_operations))
        total_pages = int((total_operations + page_size - 1) // page_size)

        # 分页截取 + 处理操作时间（提前处理 NaT）
        paginated_operations = pd.DataFrame()
        if not target_operations.empty:
            # 转换操作时间（兼容 NaT），但先不排序
            target_operations["操作时间"] = pd.to_datetime(target_operations["操作时间"], errors="coerce")
            # 排序：用 fillna 把 NaT 排到最后
            target_operations = target_operations.sort_values(
                "操作时间",
                ascending=False,
                na_position='last'  # NaT 放到最后
            )
            # 分页
            start = (page - 1) * page_size
            end = start + page_size
            paginated_operations = target_operations.iloc[start:end].copy()

        # 数据序列化（使用修复后的 serialize_df）
        inventory_serial = serialize_df(target_inventory)
        inventory_dict = inventory_serial[0] if inventory_serial else {}
        product_list = serialize_df(target_products)
        feature_list = serialize_df(target_features)
        location_list = serialize_df(target_locations)
        manufacturer_list = serialize_df(target_manufacturers)
        operation_list = serialize_df(paginated_operations)

        # 计算操作统计（包含借/还）
        total_in_quantity = 0.0
        total_out_quantity = 0.0
        total_lend_quantity = 0.0
        total_return_quantity = 0.0
        other_stats = {}

        if not target_operations.empty:
            # 确保操作数量为数值类型
            target_operations["操作数量"] = pd.to_numeric(target_operations["操作数量"], errors="coerce").fillna(0.0)

            # 入库/出库统计
            in_operations = target_operations[target_operations["操作类型"] == "入库"]
            total_in_quantity = float(in_operations["操作数量"].sum()) if not in_operations.empty else 0.0

            out_operations = target_operations[target_operations["操作类型"] == "出库"]
            total_out_quantity = float(out_operations["操作数量"].sum()) if not out_operations.empty else 0.0

            # 借/还统计
            lend_operations = target_operations[target_operations["操作类型"] == "借"]
            total_lend_quantity = float(lend_operations["操作数量"].sum()) if not lend_operations.empty else 0.0

            return_operations = target_operations[target_operations["操作类型"] == "还"]
            total_return_quantity = float(return_operations["操作数量"].sum()) if not return_operations.empty else 0.0

            # 其他操作类型
            other_operations = target_operations[~target_operations["操作类型"].isin(["入库", "出库", "借", "还"])]
            if not other_operations.empty:
                for op_type in other_operations["操作类型"].unique():
                    op_type_str = str(op_type).strip()
                    if not op_type_str:
                        continue
                    type_ops = other_operations[other_operations["操作类型"] == op_type]
                    other_stats[op_type_str] = {
                        "次数": int(len(type_ops)),
                        "总数量": float(type_ops["操作数量"].sum())
                    }

        # 统一计算当前库存
        current_stock = round(
            float(total_in_quantity - total_out_quantity - total_lend_quantity + total_return_quantity),
            2
        )
        inventory_dict["库存数量"] = current_stock
        inventory_dict["累计入库数量"] = round(total_in_quantity, 2)
        inventory_dict["累计出库数量"] = round(total_out_quantity, 2)
        inventory_dict["累计借出数量"] = round(total_lend_quantity, 2)
        inventory_dict["累计归还数量"] = round(total_return_quantity, 2)

        # 操作统计信息（处理最后操作时间）
        last_operation_time = ""
        if not target_operations.empty:
            last_op_time = target_operations["操作时间"].max()
            # 直接处理 NaT，不依赖序列化函数
            last_operation_time = last_op_time.strftime("%Y-%m-%d %H:%M:%S") if not pd.isna(last_op_time) else ""

        operation_stats = {
            "total_in_quantity": round(total_in_quantity, 2),
            "total_out_quantity": round(total_out_quantity, 2),
            "total_lend_quantity": round(total_lend_quantity, 2),
            "total_return_quantity": round(total_return_quantity, 2),
            "current_stock": current_stock,
            "total_operations": int(total_operations),
            "other_operations": other_stats,
            "last_operation_time": last_operation_time
        }

        # 处理多记录警告提示
        warnings = []
        if len(product_list) > 1:
            warnings.append(f"该库存关联{len(product_list)}个商品记录，请确认数据是否正常")
        if len(feature_list) > 1:
            warnings.append(f"该库存关联{len(feature_list)}个特征记录，请确认数据是否正常")
        if len(location_list) > 1:
            warnings.append(f"该库存关联{len(location_list)}个位置记录，请确认数据是否正常")
        if len(manufacturer_list) > 1:
            warnings.append(f"该库存关联{len(manufacturer_list)}个厂家记录，请确认数据是否正常")

        # 组装响应数据
        response_data = {
            "status": "success",
            "data": {
                "inventory": inventory_dict,
                "product": product_list[0] if product_list else {},
                "feature": feature_list[0] if feature_list else {},
                "location": location_list[0] if location_list else {},
                "manufacturer": manufacturer_list[0] if manufacturer_list else {},
                "operations": operation_list,
                "operation_stats": operation_stats
            },
            "pagination": {
                "total": int(total_operations),
                "page": int(page),
                "page_size": int(page_size),
                "total_pages": int(total_pages)
            }
        }

        if warnings:
            response_data["warnings"] = warnings

        return response_data, 200

    except IndexError as e:
        error_trace = traceback.format_exc()
        print(f"库存详情查询索引异常：{str(e)}\n完整堆栈：{error_trace}")
        return {"status": "error", "message": "库存数据索引错误，请检查数据完整性"}, 500
    except TypeError as e:
        error_trace = traceback.format_exc()
        print(f"库存详情查询类型异常：{str(e)}\n完整堆栈：{error_trace}")
        return {"status": "error", "message": "数据类型转换错误，请检查字段格式"}, 500
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"获取库存详情异常: {str(e)}\n完整堆栈：{error_trace}")
        return {"status": "error", "message": f"系统异常：{str(e)}"}, 500


def batch_update_inventory_status(inventory_ids, csv_data):
    """批量更新库存状态 - 仅更新状态值，不新增/重命名任何原始字段"""
    try:
        inventory_df = csv_data.get("inventory", pd.DataFrame())
        operation_df = csv_data.get("operation_record", pd.DataFrame())

        if inventory_df.empty:
            print("警告：库存数据表为空")
            return

        # 确保状态字段存在（仅值初始化，不新增其他字段）
        if "状态" not in inventory_df.columns:
            inventory_df["状态"] = ""

        # 批量处理库存状态更新
        for inventory_id in inventory_ids:
            try:
                # 强化库存ID匹配（兼容空值/字符串ID）
                inventory_df["库存ID"] = pd.to_numeric(inventory_df["库存ID"], errors="coerce").fillna(-1).astype(int)
                target_id = int(inventory_id) if str(inventory_id).isdigit() else -1
                mask = inventory_df["库存ID"] == target_id

                if not mask.any():
                    print(f"警告：库存ID {inventory_id} 未找到匹配记录")
                    continue

                # 初始化统计变量
                qty_stats = {"入库": 0.0, "出库": 0.0, "借": 0.0, "还": 0.0}
                count_stats = {"入库": 0, "出库": 0, "借": 0, "还": 0}

                if not operation_df.empty:
                    # 过滤该库存ID的操作记录
                    operation_df["关联库存ID"] = pd.to_numeric(operation_df["关联库存ID"], errors="coerce").fillna(-1).astype(int)
                    inventory_mask = operation_df["关联库存ID"] == target_id

                    if inventory_mask.any():
                        inventory_operations = operation_df[inventory_mask].copy()
                        inventory_operations["操作数量"] = pd.to_numeric(inventory_operations["操作数量"], errors="coerce").fillna(0.0)

                        # 统计数量和次数
                        for op_type in ["入库", "出库", "借", "还"]:
                            op_mask = inventory_operations["操作类型"] == op_type
                            if op_mask.any():
                                qty_stats[op_type] = inventory_operations[op_mask]["操作数量"].sum()
                                count_stats[op_type] = int(op_mask.sum())

                        # 构建状态字符串（仅更新状态值，不碰其他字段）
                        status_parts = []
                        if count_stats["入库"] > 0:
                            status_parts.append(f"入:{count_stats['入库']}次({qty_stats['入库']}个)")
                        if count_stats["出库"] > 0:
                            status_parts.append(f"出:{count_stats['出库']}次({qty_stats['出库']}个)")
                        if count_stats["借"] > 0:
                            status_parts.append(f"借:{count_stats['借']}次({qty_stats['借']}个)")
                        if count_stats["还"] > 0:
                            status_parts.append(f"还:{count_stats['还']}次({qty_stats['还']}个)")
                        unreturned = round(qty_stats['借'] - qty_stats['还'], 2)
                        if unreturned > 0:
                            status_parts.append(f"({unreturned}个未还)")
                        status = " ".join(status_parts)
                    else:
                        status = "无操作记录"
                else:
                    status = "无操作记录"

                # 仅更新状态列的值，不修改任何字段名
                inventory_df.loc[mask, "状态"] = status

            except Exception as e:
                print(f"更新库存ID {inventory_id} 失败: {str(e)}")
                continue

        # 写回数据（仅更新状态值，字段结构不变）
        csv_data["inventory"] = inventory_df
        print(f"批量更新完成，共处理 {len(inventory_ids)} 个库存ID")

    except Exception as e:
        print(f"批量更新库存状态异常: {str(e)}")
        import traceback
        traceback.print_exc()


def edit_inventory(inventory_id, edit_data):
    """
    编辑库存功能（最终修复版：编辑后不再写入操作记录表）
    核心修复：
    1. ID=0合法校验（仅拦截None/空字符串）
    2. feature_id=0时正常更新feature表
    3. 特征字段对比兼容original_feature为空的场景
    4. 移除操作记录表的写入逻辑，仅保留变更日志用于接口响应
    """
    try:
        start_time = time.time()
        current_time = datetime.now()
        print(f"\n=== 库存编辑请求开始 | 时间: {current_time} | 库存ID: {inventory_id} ===", flush=True)

        # 打印接收到的编辑数据（排查日志）
        print(f"[库存ID:{inventory_id}] 接收到的编辑参数：{edit_data}", flush=True)

        # 1. 基础参数校验（核心修复：ID=0合法，仅拦截None/空字符串）
        if inventory_id is None or (isinstance(inventory_id, str) and inventory_id.strip() == ""):
            print(f"[错误] 库存编辑：库存ID无效 - 为空或None", flush=True)
            return {"status": "error", "message": "库存ID不能为空"}, 400

        if not isinstance(inventory_id, (int, str)):
            print(f"[错误] 库存编辑：库存ID类型错误 - 类型：{type(inventory_id)}，值：{inventory_id}", flush=True)
            return {"status": "error", "message": "库存ID必须为数字或字符串类型"}, 400

        # 强制转换为int（支持"0"转0，保留0的合法性）
        try:
            inventory_id = int(inventory_id)
        except (ValueError, TypeError):
            print(f"[错误] 库存编辑：库存ID无法转换为数字 - {inventory_id}", flush=True)
            return {"status": "error", "message": "库存ID必须为数字"}, 400

        # 校验edit_data
        if not edit_data or not isinstance(edit_data, dict):
            print(f"[错误] 库存编辑：编辑数据为空或格式错误 - 类型：{type(edit_data)}", flush=True)
            return {"status": "error", "message": "编辑数据不能为空且必须为JSON格式"}, 400

        # 2. 读取CSV数据
        csv_data = read_csv_data()
        inventory_df = csv_data.get("inventory", pd.DataFrame())
        feature_df = csv_data.get("feature", pd.DataFrame())
        product_df = csv_data.get("product", pd.DataFrame())
        location_df = csv_data.get("location", pd.DataFrame())
        manufacturer_df = csv_data.get("manufacturer", pd.DataFrame())
        # 不再处理operation_df，仅读取不修改

        # 确保feature表有图片路径字段（无则初始化）
        if "图片路径" not in feature_df.columns:
            feature_df["图片路径"] = ""

        # 3. 校验库存记录是否存在（支持ID=0）
        if inventory_df.empty or "库存ID" not in inventory_df.columns:
            print(f"[错误] 库存编辑：库存数据表结构异常", flush=True)
            return {"status": "error", "message": "库存数据表格结构异常"}, 500

        inventory_df["库存ID"] = pd.to_numeric(inventory_df["库存ID"], errors="coerce").fillna(-1).astype(int)
        target_inventory_idx = inventory_df[inventory_df["库存ID"] == inventory_id].index
        if target_inventory_idx.empty:
            print(f"[错误] 库存编辑：未找到ID为{inventory_id}的库存记录", flush=True)
            return {"status": "error", "message": f"未找到ID为{inventory_id}的库存记录"}, 404
        target_inventory_idx = target_inventory_idx[0]

        # 4. 提取原始记录
        original_inventory = inventory_df.iloc[target_inventory_idx].copy()
        original_feature = {}
        original_product = {}
        original_location = {}
        original_manufacturer = {}

        # 5. 提取关联ID（兼容0值）
        feature_id = original_inventory.get("关联商品特征ID")
        location_id = original_inventory.get("关联位置ID")
        manufacturer_id = original_inventory.get("关联厂家ID")
        product_id = None

        # 6. 数据校验
        # 楼层校验
        if "楼层" in edit_data and edit_data["楼层"] is not None and str(edit_data["楼层"]).strip() != "":
            floor_val = edit_data["楼层"]
            if not isinstance(floor_val, (int, str)):
                print(f"[错误] 库存编辑：楼层类型错误 - 类型：{type(floor_val)}，值：{floor_val}", flush=True)
                return {"status": "error", "message": "楼层必须为数字或数字字符串"}, 400
            try:
                floor = int(floor_val)
            except ValueError:
                print(f"[错误] 库存编辑：楼层格式错误 - {floor_val}", flush=True)
                return {"status": "error", "message": "楼层必须为数字"}, 400
            if floor not in FLOORS:
                print(f"[错误] 库存编辑：楼层无效 - {floor}", flush=True)
                return {"status": "error", "message": f"楼层无效，可选楼层：{', '.join(map(str, FLOORS))}"}, 400

        # 商品类型校验
        product_type = str(edit_data.get("类型", "")).strip()
        if product_type != "" and product_type not in PRODUCT_TYPES:
            print(f"[错误] 库存编辑：商品类型无效 - {product_type}", flush=True)
            return {"status": "error", "message": f"商品类型无效，可选类型：{', '.join(PRODUCT_TYPES)}"}, 400

        # 7. 更新商品信息（核心修复：feature_id=0时正常处理）
        product_code = str(edit_data.get("货号", "")).strip()

        # 兼容feature_id=0的场景
        if feature_id is not None and feature_id != "":
            feature_df["商品特征ID"] = pd.to_numeric(feature_df["商品特征ID"], errors="coerce").fillna(-1).astype(int)
            target_feature = feature_df[feature_df["商品特征ID"] == feature_id]

            # 无对应feature记录时自动创建（适配首次上传图片）
            if target_feature.empty:
                print(f"[特征ID:{feature_id}] 无现有记录，自动创建新特征记录", flush=True)
                new_feature = {
                    "商品特征ID": feature_id,
                    "关联商品ID": "",
                    "单价": "",
                    "重量": "",
                    "规格": "",
                    "材质": "",
                    "颜色": "",
                    "形状": "",
                    "风格": "",
                    "图片路径": ""
                }
                feature_df = pd.concat([feature_df, pd.DataFrame([new_feature])], ignore_index=True)
                target_feature = feature_df[feature_df["商品特征ID"] == feature_id]

            # 提取原始特征记录
            original_feature = target_feature.iloc[0].to_dict()
            product_id = target_feature.iloc[0].get("关联商品ID")

            # 更新feature表字段（包含图片路径）
            feature_update_fields = ["单价", "重量", "规格", "材质", "颜色", "形状", "风格", "图片路径"]
            for field in feature_update_fields:
                if field in edit_data and edit_data[field] is not None:
                    feature_df.loc[feature_df["商品特征ID"] == feature_id, field] = str(edit_data[field]).strip()
                    print(f"[特征ID:{feature_id}] 更新{field}：{original_feature.get(field, '')} → {edit_data[field]}",
                          flush=True)

        # 更新商品基础信息
        if product_id:
            product_df["商品ID"] = pd.to_numeric(product_df["商品ID"], errors="coerce").fillna(-1).astype(int)
            target_product = product_df[product_df["商品ID"] == product_id]
            if not target_product.empty:
                original_product = target_product.iloc[0].to_dict()
                product_update_fields = ["货号", "类型", "用途", "备注"]
                for field in product_update_fields:
                    if field in edit_data and edit_data[field] is not None:
                        product_df.loc[product_df["商品ID"] == product_id, field] = str(edit_data[field]).strip()
        else:
            # 货号为空时创建新商品
            product_code_to_id = {}
            if not product_df.empty:
                for _, row in product_df.iterrows():
                    code = str(row["货号"]).strip()
                    if code and code not in product_code_to_id:
                        product_code_to_id[code] = int(row["商品ID"])

            if product_code in product_code_to_id:
                product_id = product_code_to_id[product_code]
            else:
                product_id = generate_auto_id_df(product_df, "商品ID")
                new_product = {
                    "商品ID": product_id,
                    "货号": product_code,
                    "类型": product_type,
                    "备注": edit_data.get("备注", ""),
                    "用途": edit_data.get("用途", "")
                }
                product_df = pd.concat([product_df, pd.DataFrame([new_product])], ignore_index=True)

            # 关联商品ID到feature表（兼容feature_id=0）
            if feature_id is not None and feature_id != "":
                feature_df.loc[feature_df["商品特征ID"] == feature_id, "关联商品ID"] = product_id

        # 8. 更新地址信息（兼容0值）
        if location_id is not None and location_id != "":
            location_df["地址ID"] = pd.to_numeric(location_df["地址ID"], errors="coerce").fillna(-1).astype(int)
            target_location = location_df[location_df["地址ID"] == location_id]
            if not target_location.empty:
                original_location = target_location.iloc[0].to_dict()
                location_update_fields = ["地址类型", "楼层", "架号", "框号", "包号"]
                for field in location_update_fields:
                    if field in edit_data and edit_data[field] is not None:
                        val = edit_data[field]
                        if field in ["地址类型", "楼层"]:
                            val = int(val) if val and str(val).strip() != "" else ""
                        else:
                            val = str(val).strip()
                        location_df.loc[location_df["地址ID"] == location_id, field] = val

        # 9. 更新厂家信息（兼容0值）
        if manufacturer_id is not None and manufacturer_id != "":
            manufacturer_df["厂家ID"] = pd.to_numeric(manufacturer_df["厂家ID"], errors="coerce").fillna(-1).astype(int)
            target_manufacturer = manufacturer_df[manufacturer_df["厂家ID"] == manufacturer_id]
            if not target_manufacturer.empty:
                original_manufacturer = target_manufacturer.iloc[0].to_dict()
                manufacturer_update_fields = ["厂家", "厂家地址", "电话"]
                for field in manufacturer_update_fields:
                    if field in edit_data and edit_data[field] is not None:
                        manufacturer_df.loc[manufacturer_df["厂家ID"] == manufacturer_id, field] = str(
                            edit_data[field]).strip()
        elif "厂家" in edit_data and edit_data["厂家"]:
            factory_name = str(edit_data.get("厂家", "")).strip()
            factory_address = str(edit_data.get("厂家地址", "")).strip()
            factory_phone = str(edit_data.get("电话", "")).strip()

            manufacturer_key = f"{factory_name if factory_name else '###EMPTY###'}|{factory_address if factory_address else '###EMPTY###'}|{factory_phone if factory_phone else '###EMPTY###'}"
            manufacturer_lookup = {}
            if not manufacturer_df.empty:
                for _, row in manufacturer_df.iterrows():
                    key = f"{str(row.get('厂家', '')).strip() if pd.notna(row.get('厂家')) else '###EMPTY###'}|{str(row.get('厂家地址', '')).strip() if pd.notna(row.get('厂家地址')) else '###EMPTY###'}|{str(row.get('电话', '')).strip() if pd.notna(row.get('电话')) else '###EMPTY###'}"
                    manufacturer_lookup[key] = int(row["厂家ID"])

            if manufacturer_key in manufacturer_lookup:
                manufacturer_id = manufacturer_lookup[manufacturer_key]
            else:
                manufacturer_id = generate_auto_id_df(manufacturer_df, "厂家ID")
                new_manufacturer = {
                    "厂家ID": manufacturer_id,
                    "厂家": factory_name,
                    "厂家地址": factory_address,
                    "电话": factory_phone
                }
                manufacturer_df = pd.concat([manufacturer_df, pd.DataFrame([new_manufacturer])], ignore_index=True)

            inventory_df.loc[target_inventory_idx, "关联厂家ID"] = manufacturer_id

        # 10. 更新库存基础信息
        inventory_update_fields = ["批次", "状态", "次品数量"]
        for field in inventory_update_fields:
            if field in edit_data and edit_data[field] is not None:
                try:
                    if field == "批次":
                        val = int(edit_data[field])
                    elif field == "次品数量":
                        val = float(edit_data[field])
                    else:
                        val = str(edit_data[field]).strip()
                    inventory_df.loc[target_inventory_idx, field] = val
                except (ValueError, TypeError) as e:
                    print(f"[错误] 库存编辑：{field}格式错误 - {edit_data[field]} | 异常：{e}", flush=True)
                    return {"status": "error", "message": f"{field}格式错误，请检查"}, 400

        # 11. 生成修改日志（仅用于接口响应，不再写入操作记录表）
        edit_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        operator = str(edit_data.get("操作人", "系统")).strip()

        change_log = []
        # 库存字段对比
        for col in ["批次", "状态", "次品数量"]:
            if col in edit_data:
                old_val = original_inventory.get(col, "")
                new_val = edit_data.get(col, "")
                if str(old_val).strip() != str(new_val).strip():
                    change_log.append(f"{col}：{old_val} → {new_val}")

        # 商品字段对比
        for col in ["货号", "类型", "用途", "备注"]:
            if col in edit_data:
                old_val = original_product.get(col, "") if original_product else ""
                new_val = edit_data.get(col, "")
                if str(old_val).strip() != str(new_val).strip():
                    change_log.append(f"商品{col}：{old_val} → {new_val}")

        # 特征字段对比
        for col in ["单价", "重量", "规格", "材质", "图片路径"]:
            if col in edit_data:
                old_val = original_feature.get(col, "") if original_feature else ""
                new_val = edit_data.get(col, "")
                if str(old_val).strip() != str(new_val).strip():
                    change_log.append(f"特征{col}：{old_val} → {new_val}")

        # 地址字段对比
        for col in ["地址类型", "楼层", "架号", "框号", "包号"]:
            if col in edit_data:
                old_val = original_location.get(col, "") if original_location else ""
                new_val = edit_data.get(col, "")
                if str(old_val).strip() != str(new_val).strip():
                    change_log.append(f"地址{col}：{old_val} → {new_val}")

        # 厂家字段对比
        for col in ["厂家", "厂家地址", "电话"]:
            if col in edit_data:
                old_val = original_manufacturer.get(col, "") if original_manufacturer else ""
                new_val = edit_data.get(col, "")
                if str(old_val).strip() != str(new_val).strip():
                    change_log.append(f"厂家{col}：{old_val} → {new_val}")

        change_note = "；".join(change_log) if change_log else "未修改具体字段"
        print(f"[库存ID:{inventory_id}] 生成的变更日志：{change_log}", flush=True)

        # 12. 保存数据（不再更新操作记录表）
        csv_data.update({
            "inventory": inventory_df,
            "feature": feature_df,
            "product": product_df,
            "location": location_df,
            "manufacturer": manufacturer_df
            # 移除操作记录的更新，编辑操作不再写入操作记录表
        })

        if not write_csv_data(csv_data):
            print(f"[错误] 库存编辑：数据保存失败", flush=True)
            return {"status": "error", "message": "数据保存失败"}, 500

        # 13. 组装响应
        updated_inventory = inventory_df.iloc[target_inventory_idx].to_dict()
        response_data = {
            "status": "success",
            "message": f"库存ID {inventory_id} 编辑成功",
            "data": {
                "inventory_id": inventory_id,
                "updated_fields": change_log,
                "edit_time": edit_time,
                "operator": operator,
                "inventory": convert_to_serializable(updated_inventory)
            },
            "performance": {
                "total_time": f"{time.time() - start_time:.4f}秒"
            }
        }

        print(f"=== 库存编辑请求结束 | 耗时: {time.time() - start_time:.4f}秒 | 库存ID: {inventory_id} ===", flush=True)
        return response_data, 200

    except IndexError as e:
        print(f"库存编辑索引异常：{str(e)}", flush=True)
        return {"status": "error", "message": "库存数据索引错误，请检查数据完整性"}, 500
    except TypeError as e:
        if "isinstance" in str(e):
            print(f"库存编辑类型异常（isinstance参数错误）：{str(e)}", flush=True)
            return {"status": "error", "message": "数据类型校验参数错误，请检查字段格式"}, 500
        print(f"库存编辑类型异常：{str(e)}", flush=True)
        return {"status": "error", "message": "数据类型转换错误，请检查字段格式"}, 500
    except Exception as e:
        print(f"库存编辑系统异常: {str(e)}", flush=True)
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"系统异常：{str(e)}"}, 500

def delete_inventory(inventory_id):
    """删除库存记录（支持删除：无操作记录 / 仅入库记录的库存）"""
    try:
        # 强制清除缓存，确保读取最新数据
        invalidate_cache()
        csv_data = read_csv_data()

        # ------------------- 1. 标准化输入ID -------------------
        try:
            inventory_id = int(inventory_id)
            if inventory_id < 0:  # 过滤无效ID（负数/0）
                return {"status": "error", "message": "无效的库存ID（需为正整数）"}, 400
        except (ValueError, TypeError):
            return {"status": "error", "message": "库存ID必须为数字"}, 400

        # ------------------- 2. 校验库存表结构 & 筛选目标库存 -------------------
        inventory_df = csv_data.get("inventory", pd.DataFrame()).copy()
        if inventory_df.empty or "库存ID" not in inventory_df.columns:
            return {"status": "error", "message": "库存数据表格结构异常"}, 500

        # 清理库存表无效数据
        inventory_df = inventory_df.dropna(how='all')  # 删除全空行
        inventory_df = inventory_df.loc[:, ~inventory_df.columns.str.contains('^Unnamed')]  # 删除索引列
        inventory_df["库存ID"] = pd.to_numeric(inventory_df["库存ID"], errors="coerce")
        # 过滤有效库存行（正整数ID）
        valid_inventory_df = inventory_df[
            inventory_df["库存ID"].notna() & (inventory_df["库存ID"] >= 0)
            ].astype({"库存ID": int})

        # 检查目标库存是否存在
        mask = valid_inventory_df["库存ID"] == inventory_id
        if not mask.any():
            return {"status": "error", "message": f"未找到库存ID为 {inventory_id} 的记录"}, 404

        # ------------------- 3. 核心逻辑：判断操作记录是否允许删除 -------------------
        operation_df = csv_data.get("operation_record", pd.DataFrame()).copy()
        # 初始化：默认允许删除（无操作记录/仅入库记录）
        allow_delete = True
        error_msg = ""

        if not operation_df.empty and "关联库存ID" in operation_df.columns:
            # 清理操作记录无效数据
            operation_df = operation_df.dropna(how='all')
            operation_df = operation_df.loc[:, ~operation_df.columns.str.contains('^Unnamed')]
            # 标准化关联库存ID
            operation_df["关联库存ID"] = pd.to_numeric(operation_df["关联库存ID"], errors="coerce")
            # 筛选关联当前库存的有效操作记录（正整数ID）
            valid_operation_df = operation_df[
                (operation_df["关联库存ID"].notna()) &
                (operation_df["关联库存ID"] > 0) &
                (operation_df["关联库存ID"] == inventory_id)
                ].astype({"关联库存ID": int})

            if not valid_operation_df.empty:
                # 标准化操作类型（去空格、转中文，避免格式问题）
                valid_operation_df["操作类型"] = valid_operation_df["操作类型"].astype(str).str.strip()
                # 获取所有唯一的操作类型
                operation_types = valid_operation_df["操作类型"].unique().tolist()
                # 定义允许删除的操作类型（仅入库）
                allowed_op_types = ["入库"]

                # 检查是否包含非入库记录
                has_non_inbound = any(op_type not in allowed_op_types for op_type in operation_types)
                if has_non_inbound:
                    allow_delete = False
                    error_msg = f"该库存（ID:{inventory_id}）包含非入库操作记录（{operation_types}），无法删除。请先删除相关操作记录。"
                else:
                    # 仅入库记录 → 允许删除，打印日志
                    print(f"✅ 库存ID {inventory_id} 仅包含入库记录（共{len(valid_operation_df)}条），允许删除")

        # 若不允许删除，返回错误
        if not allow_delete:
            return {"status": "error", "message": error_msg}, 400

        # ------------------- 4. 处理关联ID & 删除库存记录 -------------------
        # 获取原库存记录的关联ID
        original_inventory = csv_data.get("inventory", pd.DataFrame())
        original_inventory["库存ID"] = pd.to_numeric(original_inventory["库存ID"], errors="coerce").fillna(-1).astype(
            int)
        original_record = original_inventory[original_inventory["库存ID"] == inventory_id]

        feature_id = location_id = manufacturer_id = None
        if not original_record.empty:
            original_record = original_record.iloc[0]
            # 标准化关联ID（仅保留有效正整数）
            feature_id = original_record.get("关联商品特征ID")
            feature_id = int(feature_id) if (
                        pd.notna(feature_id) and str(feature_id).strip() and int(feature_id) > 0) else None

            location_id = original_record.get("关联位置ID")
            location_id = int(location_id) if (
                        pd.notna(location_id) and str(location_id).strip() and int(location_id) > 0) else None

            manufacturer_id = original_record.get("关联厂家ID")
            manufacturer_id = int(manufacturer_id) if (
                        pd.notna(manufacturer_id) and str(manufacturer_id).strip() and int(
                    manufacturer_id) > 0) else None

        # 核心：删除目标库存记录并清理
        valid_inventory_df = valid_inventory_df[~mask].copy().reset_index(drop=True)
        # 最终清理空行
        inventory_df = valid_inventory_df.dropna(how='all').reset_index(drop=True)

        # ------------------- 5. 清理关联的特征/位置/厂家记录（无其他库存使用时） -------------------
        # 5.1 清理商品特征
        feature_df = csv_data.get("feature", pd.DataFrame()).copy()
        if feature_id is not None and not feature_df.empty and "商品特征ID" in feature_df.columns:
            feature_df = feature_df.dropna(how='all')
            feature_df["商品特征ID"] = pd.to_numeric(feature_df["商品特征ID"], errors="coerce")
            feature_df = feature_df[feature_df["商品特征ID"].notna() & (feature_df["商品特征ID"] >= 0)].astype(
                {"商品特征ID": int})

            # 检查是否有其他库存使用该特征
            inventory_df["关联商品特征ID"] = pd.to_numeric(inventory_df["关联商品特征ID"], errors="coerce").fillna(
                -1).astype(int)
            other_usage = inventory_df[inventory_df["关联商品特征ID"] == feature_id].empty
            if other_usage:
                feature_df = feature_df[feature_df["商品特征ID"] != feature_id].reset_index(drop=True)

        # 5.2 清理位置
        location_df = csv_data.get("location", pd.DataFrame()).copy()
        if location_id is not None and not location_df.empty and "地址ID" in location_df.columns:
            location_df = location_df.dropna(how='all')
            location_df["地址ID"] = pd.to_numeric(location_df["地址ID"], errors="coerce")
            location_df = location_df[location_df["地址ID"].notna() & (location_df["地址ID"] >= 0)].astype(
                {"地址ID": int})

            inventory_df["关联位置ID"] = pd.to_numeric(inventory_df["关联位置ID"], errors="coerce").fillna(-1).astype(
                int)
            other_usage = inventory_df[inventory_df["关联位置ID"] == location_id].empty
            if other_usage:
                location_df = location_df[location_df["地址ID"] != location_id].reset_index(drop=True)

        # 5.3 清理厂家
        manufacturer_df = csv_data.get("manufacturer", pd.DataFrame()).copy()
        if manufacturer_id is not None and not manufacturer_df.empty and "厂家ID" in manufacturer_df.columns:
            manufacturer_df = manufacturer_df.dropna(how='all')
            manufacturer_df["厂家ID"] = pd.to_numeric(manufacturer_df["厂家ID"], errors="coerce")
            manufacturer_df = manufacturer_df[
                manufacturer_df["厂家ID"].notna() & (manufacturer_df["厂家ID"] >= 0)].astype({"厂家ID": int})

            inventory_df["关联厂家ID"] = pd.to_numeric(inventory_df["关联厂家ID"], errors="coerce").fillna(-1).astype(
                int)
            other_usage = inventory_df[inventory_df["关联厂家ID"] == manufacturer_id].empty
            if other_usage:
                manufacturer_df = manufacturer_df[manufacturer_df["厂家ID"] != manufacturer_id].reset_index(drop=True)

        # ------------------- 6. 强制覆盖写入（避免数据残留） -------------------
        # 更新数据字典
        csv_data["inventory"] = inventory_df
        csv_data["feature"] = feature_df
        csv_data["location"] = location_df
        csv_data["manufacturer"] = manufacturer_df

        # 自定义强制写入函数（彻底覆盖，无合并）
        def force_write_csv(data_dict):
            try:
                ensure_csv_directory()
                create_single_backup()  # 写入前备份
                for table, filepath in CSV_FILES.items():
                    df = data_dict.get(table, pd.DataFrame())
                    # 最终清理：空行 + 无效列
                    df = df.dropna(how='all')
                    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
                    # 原子写入（临时文件→替换）
                    with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8-sig') as temp_f:
                        df.to_csv(temp_f, index=False, encoding='utf-8-sig')
                        temp_path = temp_f.name
                    if os.path.exists(filepath):
                        os.remove(filepath)
                    shutil.move(temp_path, filepath)
                invalidate_cache()
                return True
            except Exception as e:
                print(f"强制写入失败: {e}")
                restore_from_backup()

                return False

        # 执行写入
        if not force_write_csv(csv_data):
            return {"status": "error", "message": "数据保存失败"}, 500

        # ------------------- 7. 最终校验：确认删除成功 -------------------
        verify_data = read_csv_data()
        verify_inventory = verify_data.get("inventory", pd.DataFrame())
        verify_inventory["库存ID"] = pd.to_numeric(verify_inventory["库存ID"], errors="coerce").fillna(-1).astype(int)
        if inventory_id in verify_inventory["库存ID"].values:
            return {"status": "error", "message": "删除后校验失败（ID仍存在）"}, 500

        return {
            "status": "success",
            "message": f"库存ID {inventory_id} 记录删除成功！"
        }, 200

    except Exception as e:
        print(f"删除库存记录异常: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"系统异常: {str(e)}"}, 500