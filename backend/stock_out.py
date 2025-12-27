# stock_out.py
from flask import jsonify, Response
import pandas as pd
import io
import csv
from datetime import datetime
from utils import *
from config import *
from inventory_management import *
from get import *



def batch_stock_out(data):
    """优化的批量出库功能（修复ID生成+库存ID=0兼容）"""
    try:
        if not data:
            return {"status": "error", "message": "请求数据不能为空"}, 400

        # 参数模式识别与验证
        is_unified_mode = False
        stock_out_items = []

        # 验证模式1：统一数量模式
        if "inventory_ids" in data and "out_quantity" in data:
            inventory_ids = data["inventory_ids"]
            if not isinstance(inventory_ids, list) or len(inventory_ids) == 0:
                return {"status": "error", "message": "库存ID列表不能为空"}, 400

            # 验证库存ID格式（强制兼容0：明确允许0作为合法值）
            try:
                validated_ids = []
                for inv_id in inventory_ids:
                    try:
                        inv_id_int = int(inv_id)  # 0会被正确转为int(0)
                        validated_ids.append(inv_id_int)
                    except (ValueError, TypeError):
                        return {
                            "status": "error",
                            "message": f"库存ID格式错误: {inv_id}，必须为整数（支持0）"
                        }, 400
                inventory_ids = validated_ids
            except Exception as e:
                return {"status": "error", "message": f"库存ID验证失败: {str(e)}"}, 400

            try:
                out_quantity = float(data["out_quantity"])
            except (ValueError, TypeError):
                return {"status": "error", "message": "出库数量必须是数字"}, 400

            stock_out_items = [{"inventory_id": id, "out_quantity": out_quantity} for id in inventory_ids]
            is_unified_mode = True

        # 验证模式2：差异化数量模式
        elif "stock_out_items" in data:
            stock_out_items = data["stock_out_items"]
            if not isinstance(stock_out_items, list) or len(stock_out_items) == 0:
                return {"status": "error", "message": "差异化出库列表不能为空"}, 400

            # 批量验证差异化列表（强化0值兼容）
            validated_items = []
            for idx, item in enumerate(stock_out_items):
                if not isinstance(item, dict):
                    return {
                        "status": "error",
                        "message": f"第{idx + 1}项数据格式错误，必须为对象"
                    }, 400

                if "inventory_id" not in item or "out_quantity" not in item:
                    return {
                        "status": "error",
                        "message": f"第{idx + 1}项缺少inventory_id或out_quantity字段"
                    }, 400

                try:
                    # 明确允许inventory_id=0
                    inventory_id = int(item["inventory_id"])
                    out_quantity = float(item["out_quantity"])
                    validated_items.append({
                        "inventory_id": inventory_id,
                        "out_quantity": out_quantity
                    })
                except (ValueError, TypeError) as e:
                    return {
                        "status": "error",
                        "message": f"第{idx + 1}项数据格式错误: inventory_id必须是整数（支持0），out_quantity必须是数字"
                    }, 400

            stock_out_items = validated_items

        else:
            return {
                "status": "error",
                "message": "请选择一种出库模式：1. 传递inventory_ids+out_quantity（统一数量） 2. 传递stock_out_items（差异化数量）"
            }, 400

        # 验证公共必填字段
        if "operator" not in data or not str(data["operator"]).strip():
            return {"status": "error", "message": "缺少必填字段：operator"}, 400

        # 预读取所有数据
        csv_data = read_csv_data()
        inventory_df = csv_data.get("inventory", pd.DataFrame())
        operation_df = csv_data.get("operation_record", pd.DataFrame())

        # 初始化空DataFrame（确保库存ID列类型为int，兼容0）
        if inventory_df.empty:
            inventory_df = pd.DataFrame(
                columns=["库存ID", "关联商品特征ID", "关联位置ID", "关联厂家ID", "库存数量", "次品数量", "批次", "状态",
                         "单位"],
                dtype=int  # 强制列类型为int，避免0被转为其他类型
            )
        if operation_df.empty:
            operation_df = pd.DataFrame(
                columns=["操作ID", "关联库存ID", "操作类型", "操作数量", "操作时间", "操作人", "备注"]
            )

        # 时间格式验证
        out_time = data.get("out_time")
        if not out_time:
            out_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        else:
            try:
                datetime.strptime(out_time, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                try:
                    datetime.strptime(out_time, "%Y-%m-%d %H")
                    out_time = out_time + ":00:00"
                except ValueError:
                    return {"status": "error",
                            "message": "时间格式不正确，请使用 YYYY-MM-DD HH:MM:SS 或 YYYY-MM-DD HH"}, 400

        operator = str(data["operator"]).strip()
        remark = str(data.get("remark", "")).strip()

        # 构建库存索引 - 核心修复：强制保留0作为有效ID
        try:
            # 关键修改1：库存ID转换时，仅将NaN设为-1，0保留为int(0)
            inventory_df["库存ID"] = pd.to_numeric(inventory_df["库存ID"], errors="coerce")  # 非数字转NaN
            inventory_df["库存ID"] = inventory_df["库存ID"].fillna(-1)  # NaN→-1（无效ID）
            inventory_df["库存ID"] = inventory_df["库存ID"].astype(int)  # 0会被保留为int(0)

            # 关键修改2：构建索引时明确包含0
            inventory_index = {}
            for idx, row in inventory_df.iterrows():
                inv_id = row["库存ID"]
                # 仅排除-1（无效ID），0被视为有效ID
                if inv_id != -1:
                    inventory_index[inv_id] = idx
        except Exception as e:
            return {"status": "error", "message": f"库存数据格式错误: {str(e)}"}, 500

        # 过滤无效库存ID并检查数据完整性（核心修复：0被视为有效）
        valid_items = []
        invalid_items = []
        inventory_details = {}  # 存储库存详情

        for item in stock_out_items:
            inventory_id = item["inventory_id"]
            # 关键修改3：存在性判断仅排除-1和不在索引中的值，0会被正常匹配
            if inventory_id in inventory_index:
                idx = inventory_index[inventory_id]
                try:
                    # 获取商品信息（强化0值兼容）
                    product_name = "未知商品"
                    product_code = "未知货号"

                    # 获取关联特征ID（允许0）
                    feature_id = inventory_df.at[idx, "关联商品特征ID"]
                    feature_id = pd.to_numeric(feature_id, errors="coerce") if feature_id is not None else -1

                    # 特征ID不为-1时（兼容0），读取商品信息
                    if feature_id != -1:
                        feature_df = csv_data.get("feature", pd.DataFrame())
                        if not feature_df.empty and "商品特征ID" in feature_df.columns:
                            feature_df["商品特征ID"] = pd.to_numeric(feature_df["商品特征ID"], errors="coerce").fillna(
                                -1).astype(int)
                            feature_mask = feature_df["商品特征ID"] == feature_id
                            if feature_mask.any():
                                # 获取商品ID（允许0）
                                product_id = feature_df[feature_mask].iloc[0].get("关联商品ID")
                                product_id = pd.to_numeric(product_id,
                                                           errors="coerce") if product_id is not None else -1

                                # 商品ID不为-1时（兼容0），读取商品名称/货号
                                if product_id != -1:
                                    product_df = csv_data.get("product", pd.DataFrame())
                                    if not product_df.empty and "商品ID" in product_df.columns:
                                        product_df["商品ID"] = pd.to_numeric(product_df["商品ID"],
                                                                             errors="coerce").fillna(-1).astype(int)
                                        product_mask = product_df["商品ID"] == product_id
                                        if product_mask.any():
                                            product_name = product_df[product_mask].iloc[0].get("商品名称", "未知商品")
                                            product_code = product_df[product_mask].iloc[0].get("货号", "未知货号")

                    # 存储库存详情（明确包含0的情况）
                    inventory_details[inventory_id] = {
                        "index": idx,
                        "product_name": product_name,
                        "product_code": product_code
                    }
                    valid_items.append(item)
                except (ValueError, KeyError) as e:
                    invalid_items.append(f"库存ID {inventory_id}（支持0）：数据不完整或格式错误 - {str(e)}")
            else:
                # 明确提示0是合法值，仅当0不在库存中时才报错
                invalid_items.append(f"库存ID {inventory_id}（支持0）：未找到对应的库存记录")

        if len(valid_items) == 0:
            return {
                "status": "error",
                "message": "所有库存ID均无效（含0）",
                "error_details": invalid_items
            }, 400

        # 批量处理出库
        success_count = 0
        error_count = len(invalid_items)
        error_messages = invalid_items.copy()
        new_operation_records = []
        updated_inventory_ids = set()

        # 预生成操作记录ID（修复后的函数：兼容0值ID）
        try:
            next_record_id = generate_auto_id_df(operation_df, "操作ID")
            record_ids = [next_record_id + i for i in range(len(valid_items))]
        except Exception as e:
            return {"status": "error", "message": f"生成记录ID失败: {str(e)}"}, 500

        # 批量创建出库操作记录
        # 临时存储出库数量（用于库存扣减）
        csv_data["temp_out_items"] = valid_items
        for i, item in enumerate(valid_items):
            inventory_id = item["inventory_id"]
            out_quantity = item["out_quantity"]

            try:
                inventory_info = inventory_details[inventory_id]

                # 创建操作记录（明确兼容库存ID=0）
                new_operation_records.append({
                    "操作ID": record_ids[i],
                    "关联库存ID": inventory_id,  # 0会被正常写入
                    "操作类型": "出库",
                    "操作数量": out_quantity,
                    "操作时间": out_time,
                    "操作人": operator,
                    "备注": remark
                })

                updated_inventory_ids.add(inventory_id)
                success_count += 1

            except Exception as e:
                error_count += 1
                product_info = inventory_details.get(inventory_id, {})
                product_code = product_info.get("product_code", "未知")
                error_messages.append(f"库存ID {inventory_id}({product_code})（支持0）：处理失败 - {str(e)}")

        # 批量添加操作记录
        if success_count > 0 and new_operation_records:
            try:
                new_records_df = pd.DataFrame(new_operation_records)
                operation_df = pd.concat([operation_df, new_records_df], ignore_index=True)
                csv_data["operation_record"] = operation_df

                # 批量更新库存状态（兼容0）
                batch_update_inventory_status(list(updated_inventory_ids), csv_data)

            except Exception as e:
                error_count += len(updated_inventory_ids)
                error_messages.append(f"创建操作记录失败: {str(e)}")
                success_count -= len(updated_inventory_ids)

        # 写入数据
        if success_count > 0:
            try:
                write_success = write_csv_data(csv_data)
                if not write_success:
                    return {"status": "error", "message": "数据保存失败"}, 500
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"数据保存异常: {str(e)}"
                }, 500

        # 构建响应
        response_data = {
            "status": "success" if success_count > 0 else "partial_success",
            "message": f"批量出库完成！成功: {success_count} 个，失败: {error_count} 个（兼容库存ID=0）",
            "data": {
                "success_count": success_count,
                "error_count": error_count,
                "total_processed": len(stock_out_items),
                "batch_size": len(stock_out_items),
                "mode": "统一数量" if is_unified_mode else "差异化数量",
                "operator": operator,
                "out_time": out_time
            }
        }

        # 成功详情（明确包含0的情况）
        if success_count > 0:
            success_details = []
            for item in valid_items[:min(10, len(valid_items))]:
                inventory_id = item["inventory_id"]
                if inventory_id in inventory_details:
                    info = inventory_details[inventory_id]
                    success_details.append({
                        "inventory_id": inventory_id,  # 0会被正常展示
                        "product_name": info.get("product_name", ""),
                        "product_code": info.get("product_code", ""),
                        "out_quantity": item["out_quantity"]
                    })
            response_data["data"]["success_details"] = success_details

        # 错误详情
        if error_messages:
            response_data["data"]["error_details"] = error_messages[:20]

        # 无成功记录返回错误
        if success_count == 0:
            response_data["status"] = "error"
            return response_data, 400

        return response_data, 200

    except Exception as e:
        print(f"批量出库操作异常: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "message": f"系统异常: {str(e)}"
        }, 500





