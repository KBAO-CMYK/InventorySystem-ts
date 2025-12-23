from inventory_management import *
import pandas as pd
from datetime import datetime


def product_lend(data):
    """批量借出功能 - 移除库存扣减计算，保留原始字段结构"""
    try:
        if not data:
            return {"status": "error", "message": "请求数据不能为空"}, 400

        print(f"DEBUG product_lend: 接收到的数据: {data}")

        # 1. 参数验证 - 适配不同字段名
        lend_items = []
        if "lend_items" in data:
            lend_items = data["lend_items"]
        elif "lendItems" in data:
            lend_items = data["lendItems"]
        elif "items" in data and isinstance(data["items"], list):
            lend_items = data["items"]
        elif ("inventory_ids" in data or "inventoryIds" in data) and "quantity" in data:
            inventory_ids = data.get("inventory_ids") or data.get("inventoryIds")
            quantity = data["quantity"]
            if not isinstance(inventory_ids, list) or len(inventory_ids) == 0:
                return {"status": "error", "message": "库存ID列表不能为空"}, 400
            try:
                lend_quantity = float(quantity)
                if lend_quantity <= 0:
                    return {"status": "error", "message": "借出数量必须大于0"}, 400
                lend_items = [{"inventory_id": inv_id, "quantity": lend_quantity}
                              for inv_id in inventory_ids]
            except (ValueError, TypeError):
                return {"status": "error", "message": "借出数量必须是正数"}, 400

        if not isinstance(lend_items, list) or len(lend_items) == 0:
            return {"status": "error", "message": "借出列表不能为空"}, 400

        # 2. 公共字段校验
        operator = None
        if "operator" in data:
            operator = data["operator"]
        elif "Operator" in data:
            operator = data["Operator"]
        if operator is None or not str(operator).strip():
            return {"status": "error", "message": "缺少操作人员字段"}, 400

        remark = ""
        if "remark" in data:
            remark = data["remark"]
        elif "remarkText" in data:
            remark = data["remarkText"]
        elif "Remark" in data:
            remark = data["Remark"]

        out_time = None
        if "out_time" in data:
            out_time = data["out_time"]
        elif "outTime" in data:
            out_time = data["outTime"]
        elif "time" in data:
            out_time = data["time"]
        elif "lend_time" in data:
            out_time = data["lend_time"]

        # 3. 读取CSV数据 + 修复重复字段
        csv_data = read_csv_data()
        inventory_df = csv_data.get("inventory", pd.DataFrame())
        operation_df = csv_data.get("operation_record", pd.DataFrame())

        # 处理重复字段（消除.1后缀，保留原始字段名）
        if not inventory_df.empty:
            # 重命名.1后缀为自定义名称（避免pandas自动生成）
            inventory_df.columns = inventory_df.columns.str.replace('.1', '_duplicate')
            # 可选：删除完全重复的列（保留第一个）
            inventory_df = inventory_df.loc[:, ~inventory_df.columns.duplicated()]

        if inventory_df.empty:
            inventory_df = pd.DataFrame(columns=["库存ID", "库存数量", "商品名称", "货号"])
        if operation_df.empty:
            operation_df = pd.DataFrame(
                columns=["操作ID", "关联库存ID", "操作类型", "操作数量", "操作时间", "操作人员", "备注"])

        # 4. 时间格式处理
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
                    try:
                        datetime.strptime(out_time, "%Y-%m-%dT%H:%M")
                        out_time = out_time.replace("T", " ") + ":00"
                    except ValueError:
                        return {"status": "error", "message": "时间格式不正确"}, 400

        operator = str(operator).strip()
        remark = str(remark).strip()

        # 5. 构建库存索引
        if "库存ID" not in inventory_df.columns:
            return {"status": "error", "message": "库存数据格式错误，缺少库存ID列"}, 500

        inventory_df["库存ID"] = pd.to_numeric(inventory_df["库存ID"], errors="coerce").fillna(-1).astype(int)
        inventory_index = {}
        for idx, row in inventory_df.iterrows():
            inv_id = row["库存ID"]
            if inv_id != -1:
                inventory_index[inv_id] = idx

        print(f"DEBUG product_lend: 库存索引（存在的ID）: {list(inventory_index.keys())}")

        # 6. 验证借出项目 + 强化库存数量空值处理
        valid_items = []
        error_messages = []
        inventory_details = {}

        for idx, item in enumerate(lend_items):
            if not isinstance(item, dict):
                error_messages.append(f"第{idx + 1}项数据格式错误（非字典）")
                continue

            inventory_id = None
            if "inventory_id" in item:
                inventory_id = item["inventory_id"]
            elif "inventoryId" in item:
                inventory_id = item["inventoryId"]
            elif "inventoryID" in item:
                inventory_id = item["inventoryID"]
            elif "id" in item:
                inventory_id = item["id"]

            quantity = None
            if "quantity" in item:
                quantity = item["quantity"]
            elif "lend_quantity" in item:
                quantity = item["lend_quantity"]

            if inventory_id is None or quantity is None:
                error_messages.append(f"第{idx + 1}项缺少inventory_id或quantity字段")
                continue

            try:
                inventory_id = int(inventory_id)
                if inventory_id < 0:
                    error_messages.append(f"第{idx + 1}项: 库存ID {inventory_id} 无效（需大于0）")
                    continue
            except (ValueError, TypeError):
                error_messages.append(f"第{idx + 1}项: 库存ID {inventory_id} 不是有效数字")
                continue

            try:
                quantity = float(quantity)
                if quantity <= 0:
                    error_messages.append(f"库存ID {inventory_id}: 借出数量必须大于0（当前值：{quantity}）")
                    continue
            except (ValueError, TypeError):
                error_messages.append(f"库存ID {inventory_id}: 借出数量 {quantity} 不是有效数字")
                continue

            if inventory_id not in inventory_index:
                error_messages.append(f"库存ID {inventory_id}: 未找到库存记录")
                continue

            idx_pos = inventory_index[inventory_id]
            # 强化库存数量空值处理（核心修复：避免空值）
            current_stock = inventory_df.at[idx_pos, "库存数量"]
            if pd.isna(current_stock) or current_stock == "" or current_stock is None:
                current_stock = 0.0
            else:
                try:
                    current_stock = float(current_stock)
                except (ValueError, TypeError):
                    current_stock = 0.0

            # 移除「库存数量不足」的校验逻辑（允许借出数量大于库存）
            product_name = "未知商品"
            product_code = "未知货号"
            if "商品名称" in inventory_df.columns:
                product_name = inventory_df.at[idx_pos, "商品名称"] if not pd.isna(
                    inventory_df.at[idx_pos, "商品名称"]) else "未知商品"
            if "货号" in inventory_df.columns:
                product_code = inventory_df.at[idx_pos, "货号"] if not pd.isna(
                    inventory_df.at[idx_pos, "货号"]) else "未知货号"

            inventory_details[inventory_id] = {
                "index": idx_pos,
                "product_name": product_name,
                "product_code": product_code,
                "current_stock": current_stock
            }

            valid_items.append({
                "inventory_id": inventory_id,
                "quantity": quantity
            })

        print(f"DEBUG product_lend: 错误详情列表: {error_messages}")
        print(f"DEBUG product_lend: 有效借出项目数: {len(valid_items)}")

        if len(valid_items) == 0:
            return {
                "status": "error",
                "message": "没有有效的借出项目",
                "error_details": error_messages[:20]
            }, 400

        # 7. 生成操作记录ID
        try:
            next_record_id = generate_auto_id_df(operation_df, "操作ID")
            record_ids = [next_record_id + i for i in range(len(valid_items))]
        except Exception as e:
            return {"status": "error", "message": f"生成记录ID失败: {str(e)}"}, 500

        # 8. 批量处理借出（移除库存扣减计算，库存数量保持不变）
        success_count = 0
        new_operation_records = []
        updated_inventory_ids = set()

        for i, item in enumerate(valid_items):
            inventory_id = item["inventory_id"]
            quantity = item["quantity"]

            try:
                inventory_info = inventory_details[inventory_id]
                idx_pos = inventory_info["index"]
                current_stock = inventory_info["current_stock"]

                # 移除库存扣减计算：不再修改库存数量
                # 原逻辑：new_stock = current_stock - quantity
                # 原逻辑：inventory_df.at[idx_pos, "库存数量"] = float(new_stock)

                # 创建借出操作记录
                new_operation_records.append({
                    "操作ID": record_ids[i],
                    "关联库存ID": inventory_id,
                    "操作类型": "借",
                    "操作数量": quantity,
                    "操作时间": out_time,
                    "操作人员": operator,
                    "备注": remark
                })

                updated_inventory_ids.add(inventory_id)
                success_count += 1

                print(
                    f"DEBUG product_lend: 成功借出（无库存计算）- 库存ID: {inventory_id}, 借出数量: {quantity}, 库存保持不变")

            except Exception as e:
                error_msg = f"库存ID {inventory_id}: 处理失败 - {str(e)}"
                print(f"ERROR product_lend: {error_msg}")
                error_messages.append(error_msg)

        # 9. 保存操作记录和库存数据
        if success_count > 0:
            try:
                # 更新操作记录
                if len(new_operation_records) > 0:
                    new_records_df = pd.DataFrame(new_operation_records)
                    operation_df = pd.concat([operation_df, new_records_df], ignore_index=True)
                    csv_data["operation_record"] = operation_df

                # 更新库存数据（字段结构不变，库存数量未修改）
                csv_data["inventory"] = inventory_df

                # 调用校准函数：仅更新状态值，不修改字段
                batch_update_inventory_status(list(updated_inventory_ids), csv_data)

                # 写入CSV
                write_success = write_csv_data(csv_data)
                if not write_success:
                    return {"status": "error", "message": "数据保存失败"}, 500

            except Exception as e:
                error_msg = f"数据保存异常: {str(e)}"
                print(f"ERROR product_lend: {error_msg}")
                return {"status": "error", "message": error_msg}, 500

        # 10. 构建响应（移除after_stock计算，保持原库存值）
        response_data = {
            "status": "success" if success_count == len(lend_items) else "partial_success",
            "message": f"借出完成！成功: {success_count} 个，失败: {len(lend_items) - success_count} 个",
            "data": {
                "success_count": success_count,
                "error_count": len(lend_items) - success_count,
                "total_processed": len(lend_items),
                "operator": operator,
                "out_time": out_time,
                "remark": remark
            }
        }

        if error_messages:
            response_data["data"]["error_details"] = error_messages[:20]

        if success_count > 0:
            success_details = []
            for i, item in enumerate(valid_items[:min(10, len(valid_items))]):
                inventory_id = item["inventory_id"]
                if inventory_id in inventory_details:
                    info = inventory_details[inventory_id]
                    success_details.append({
                        "inventory_id": inventory_id,
                        "product_name": info.get("product_name", ""),
                        "product_code": info.get("product_code", ""),
                        "lend_quantity": item["quantity"],
                        "before_stock": info.get("current_stock", 0),
                        "after_stock": info.get("current_stock", 0),  # 移除扣减计算，保持原库存
                        "record_id": record_ids[i] if i < len(record_ids) else 0
                    })
            response_data["data"]["success_details"] = success_details

        if success_count == 0:
            response_data["status"] = "error"
            return response_data, 400

        return response_data, 200

    except Exception as e:
        print(f"批量借出异常: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"系统异常: {str(e)}"}, 500


def product_return(data):
    """批量归还功能 - 移除库存增加计算，保留原始字段结构"""
    try:
        if not data:
            return {"status": "error", "message": "请求数据不能为空"}, 400

        print(f"DEBUG product_return: 接收到的数据: {data}")

        # 1. 参数验证
        return_items = []
        if "return_items" in data:
            return_items = data["return_items"]
        elif "returnItems" in data:
            return_items = data["returnItems"]
        elif "items" in data and isinstance(data["items"], list):
            return_items = data["items"]
        elif ("inventory_ids" in data or "inventoryIds" in data) and "quantity" in data:
            inventory_ids = data.get("inventory_ids") or data.get("inventoryIds")
            quantity = data["quantity"]
            if not isinstance(inventory_ids, list) or len(inventory_ids) == 0:
                return {"status": "error", "message": "库存ID列表不能为空"}, 400
            try:
                return_quantity = float(quantity)
                if return_quantity <= 0:
                    return {"status": "error", "message": "归还数量必须大于0"}, 400
                return_items = [{"inventory_id": inv_id, "return_quantity": return_quantity}
                                for inv_id in inventory_ids]
            except (ValueError, TypeError):
                return {"status": "error", "message": "归还数量必须是正数"}, 400

        if not isinstance(return_items, list) or len(return_items) == 0:
            return {"status": "error", "message": "归还列表不能为空"}, 400

        # 2. 公共字段校验
        operator = None
        if "operator" in data:
            operator = data["operator"]
        elif "Operator" in data:
            operator = data["Operator"]

        if operator is None or not str(operator).strip():
            return {"status": "error", "message": "缺少操作人员字段"}, 400

        remark = ""
        if "remark" in data:
            remark = data["remark"]
        elif "remarkText" in data:
            remark = data["remarkText"]
        elif "Remark" in data:
            remark = data["Remark"]

        return_time = None
        if "returnTime" in data:
            return_time = data["returnTime"]
        elif "return_time" in data:
            return_time = data["return_time"]
        elif "time" in data:
            return_time = data["time"]
        elif "outTime" in data:
            return_time = data["outTime"]
        elif "lend_time" in data:
            return_time = data["lend_time"]

        # 3. 读取数据 + 修复重复字段
        csv_data = read_csv_data()
        inventory_df = csv_data.get("inventory", pd.DataFrame())
        operation_df = csv_data.get("operation_record", pd.DataFrame())

        # 处理重复字段（消除.1后缀）
        if not inventory_df.empty:
            inventory_df.columns = inventory_df.columns.str.replace('.1', '_duplicate')
            inventory_df = inventory_df.loc[:, ~inventory_df.columns.duplicated()]

        if inventory_df.empty:
            inventory_df = pd.DataFrame(columns=["库存ID", "库存数量"])
        if operation_df.empty:
            operation_df = pd.DataFrame(
                columns=["操作ID", "关联库存ID", "操作类型", "操作数量", "操作时间", "操作人员", "备注"])

        # 4. 处理时间
        if not return_time:
            return_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        else:
            try:
                datetime.strptime(return_time, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                try:
                    datetime.strptime(return_time, "%Y-%m-%d %H")
                    return_time = return_time + ":00:00"
                except ValueError:
                    try:
                        datetime.strptime(return_time, "%Y-%m-%dT%H:%M")
                        return_time = return_time.replace("T", " ") + ":00"
                    except ValueError:
                        return {"status": "error", "message": "时间格式不正确"}, 400

        operator = str(operator).strip()
        remark = str(remark).strip()

        # 5. 构建库存索引
        if "库存ID" not in inventory_df.columns:
            return {"status": "error", "message": "库存数据格式错误，缺少库存ID列"}, 500

        inventory_df["库存ID"] = pd.to_numeric(inventory_df["库存ID"], errors="coerce").fillna(-1).astype(int)
        inventory_index = {}
        for idx, row in inventory_df.iterrows():
            inv_id = row["库存ID"]
            if inv_id != -1:
                inventory_index[inv_id] = idx

        # 6. 分析借出记录（仅校验是否有借出记录）
        print(f"DEBUG: 操作记录表中的操作类型有: {operation_df['操作类型'].unique() if not operation_df.empty else []}")
        lend_operation_types = ["借"]
        lend_type_mask = operation_df["操作类型"].isin(lend_operation_types)
        lend_records = operation_df[lend_type_mask].copy()

        print(f"DEBUG: 找到 {len(lend_records)} 条借出记录")
        if len(lend_records) > 0:
            print(f"DEBUG: 借出记录中的库存ID: {lend_records['关联库存ID'].unique()}")

        # 仅记录有借出记录的库存ID
        inventory_has_lend = set()
        for _, record in lend_records.iterrows():
            try:
                inv_id = int(record["关联库存ID"])
                inventory_has_lend.add(inv_id)
            except (ValueError, TypeError) as e:
                print(f"DEBUG: 解析借出记录失败: {e}")
                continue

        # 7. 验证归还项目 + 强化库存数量空值处理
        valid_items = []
        error_messages = []
        inventory_details = {}

        for idx, item in enumerate(return_items):
            if not isinstance(item, dict):
                error_messages.append(f"第{idx + 1}项数据格式错误")
                continue

            inventory_id = None
            if "inventory_id" in item:
                inventory_id = item["inventory_id"]
            elif "inventoryId" in item:
                inventory_id = item["inventoryId"]
            elif "inventoryID" in item:
                inventory_id = item["inventoryID"]
            elif "id" in item:
                inventory_id = item["id"]

            return_quantity = None
            if "return_quantity" in item:
                return_quantity = item["return_quantity"]
            elif "returnQuantity" in item:
                return_quantity = item["returnQuantity"]
            elif "quantity" in item:
                return_quantity = item["quantity"]
            elif "lend_quantity" in item:
                return_quantity = item["lend_quantity"]

            if inventory_id is None or return_quantity is None:
                error_messages.append(f"第{idx + 1}项缺少inventory_id或quantity字段")
                continue

            try:
                inventory_id = int(inventory_id)
                return_quantity = float(return_quantity)

                if return_quantity <= 0:
                    error_messages.append(f"库存ID {inventory_id}: 归还数量必须大于0")
                    continue

                if inventory_id not in inventory_index:
                    error_messages.append(f"库存ID {inventory_id}: 未找到库存记录")
                    continue

                if inventory_id not in inventory_has_lend:
                    error_messages.append(f"库存ID {inventory_id}: 没有借出记录，无法归还")
                    continue

                # 获取当前库存数量（强化空值处理）
                idx_pos = inventory_index[inventory_id]
                current_stock = inventory_df.at[idx_pos, "库存数量"]
                if pd.isna(current_stock) or current_stock == "" or current_stock is None:
                    current_stock = 0.0
                else:
                    try:
                        current_stock = float(current_stock)
                    except (ValueError, TypeError):
                        current_stock = 0.0

                # 获取商品信息
                product_name = "未知商品"
                product_code = "未知货号"
                if "商品名称" in inventory_df.columns:
                    product_name = inventory_df.at[idx_pos, "商品名称"] if not pd.isna(
                        inventory_df.at[idx_pos, "商品名称"]) else "未知商品"
                if "货号" in inventory_df.columns:
                    product_code = inventory_df.at[idx_pos, "货号"] if not pd.isna(
                        inventory_df.at[idx_pos, "货号"]) else "未知货号"

                inventory_details[inventory_id] = {
                    "index": idx_pos,
                    "product_name": product_name,
                    "product_code": product_code,
                    "current_stock": current_stock
                }

                valid_items.append({
                    "inventory_id": inventory_id,
                    "return_quantity": return_quantity
                })

            except (ValueError, TypeError) as e:
                error_messages.append(f"第{idx + 1}项数据格式错误: {str(e)}")

        if len(valid_items) == 0:
            return {"status": "error", "message": "没有有效的归还项目", "error_details": error_messages}, 400

        # 8. 生成操作记录ID
        try:
            next_record_id = generate_auto_id_df(operation_df, "操作ID")
            record_ids = [next_record_id + i for i in range(len(valid_items))]
        except Exception as e:
            return {"status": "error", "message": f"生成记录ID失败: {str(e)}"}, 500

        # 9. 批量处理归还（移除库存增加计算，库存数量保持不变）
        success_count = 0
        new_operation_records = []
        updated_inventory_ids = set()

        for i, item in enumerate(valid_items):
            inventory_id = item["inventory_id"]
            return_quantity = item["return_quantity"]

            try:
                inventory_info = inventory_details[inventory_id]
                idx_pos = inventory_info["index"]
                current_stock = inventory_info["current_stock"]

                # 移除库存增加计算：不再修改库存数量
                # 原逻辑：new_stock = current_stock + return_quantity
                # 原逻辑：inventory_df.at[idx_pos, "库存数量"] = float(new_stock)

                # 创建归还记录
                new_operation_records.append({
                    "操作ID": record_ids[i],
                    "关联库存ID": inventory_id,
                    "操作类型": "还",
                    "操作数量": return_quantity,
                    "操作时间": return_time,
                    "操作人员": operator,
                    "备注": remark
                })

                updated_inventory_ids.add(inventory_id)
                success_count += 1

                print(
                    f"DEBUG: 成功归还（无库存计算）- 库存ID: {inventory_id}, 归还数量: {return_quantity}, 库存保持不变")

            except Exception as e:
                error_msg = f"库存ID {inventory_id}: 处理失败 - {str(e)}"
                print(f"ERROR: {error_msg}")
                error_messages.append(error_msg)

        # 10. 保存数据
        if success_count > 0:
            try:
                if len(new_operation_records) > 0:
                    new_records_df = pd.DataFrame(new_operation_records)
                    operation_df = pd.concat([operation_df, new_records_df], ignore_index=True)
                    csv_data["operation_record"] = operation_df

                csv_data["inventory"] = inventory_df

                # 调用校准函数：仅更新状态值
                batch_update_inventory_status(list(updated_inventory_ids), csv_data)

                write_success = write_csv_data(csv_data)
                if not write_success:
                    return {"status": "error", "message": "数据保存失败"}, 500

            except Exception as e:
                error_msg = f"数据保存异常: {str(e)}"
                print(f"ERROR: {error_msg}")
                return {"status": "error", "message": error_msg}, 500

        # 11. 构建响应（移除after_stock计算，保持原库存值）
        response_data = {
            "status": "success" if success_count == len(return_items) else "partial_success",
            "message": f"归还完成！成功: {success_count} 个，失败: {len(return_items) - success_count} 个",
            "data": {
                "success_count": success_count,
                "error_count": len(return_items) - success_count,
                "total_processed": len(return_items),
                "operator": operator,
                "return_time": return_time,
                "remark": remark
            }
        }

        if error_messages:
            response_data["data"]["error_details"] = error_messages[:20]

        if success_count > 0:
            success_details = []
            for i, item in enumerate(valid_items[:min(10, len(valid_items))]):
                inventory_id = item["inventory_id"]
                if inventory_id in inventory_details:
                    info = inventory_details[inventory_id]
                    success_details.append({
                        "inventory_id": inventory_id,
                        "product_name": info.get("product_name", ""),
                        "product_code": info.get("product_code", ""),
                        "return_quantity": item["return_quantity"],
                        "before_stock": info.get("current_stock", 0),
                        "after_stock": info.get("current_stock", 0),  # 移除增加计算，保持原库存
                        "record_id": record_ids[i] if i < len(record_ids) else 0
                    })
            response_data["data"]["success_details"] = success_details

        if success_count == 0:
            response_data["status"] = "error"
            return response_data, 400

        return response_data, 200

    except Exception as e:
        print(f"批量归还异常: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"系统异常: {str(e)}"}, 500