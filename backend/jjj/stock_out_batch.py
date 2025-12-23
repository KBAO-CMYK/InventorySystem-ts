from read_utils import *
from other_utils import *
from write_utils import *

def batch_stock_out(data):
    """优化的批量出库功能"""
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

            # 验证库存ID格式
            try:
                validated_ids = []
                for inv_id in inventory_ids:
                    try:
                        validated_ids.append(int(inv_id))
                    except (ValueError, TypeError):
                        return {
                            "status": "error",
                            "message": f"库存ID格式错误: {inv_id}，必须为整数"
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

            # 批量验证差异化列表
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
                    inventory_id = int(item["inventory_id"])
                    out_quantity = float(item["out_quantity"])
                    validated_items.append({
                        "inventory_id": inventory_id,
                        "out_quantity": out_quantity
                    })
                except (ValueError, TypeError) as e:
                    return {
                        "status": "error",
                        "message": f"第{idx + 1}项数据格式错误: inventory_id必须是整数，out_quantity必须是数字"
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
        stock_out_records_df = csv_data.get("stock_out_records", pd.DataFrame())

        # 如果数据为空，初始化DataFrame
        if inventory_df.empty:
            inventory_df = pd.DataFrame(
                columns=["ID", "商品编号", "入库时间", "入库数量", "出库总数量", "状态", "库存数量"])
        if stock_out_records_df.empty:
            stock_out_records_df = pd.DataFrame(
                columns=["ID", "inventory_id", "出库时间", "出库数量", "操作人员", "备注"])

        # 提前验证时间格式
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
                    return {"status": "error", "message": "时间格式不正确，请使用 YYYY-MM-DD HH:MM:SS 或 YYYY-MM-DD HH"}, 400

        operator = str(data["operator"]).strip()
        remark = str(data.get("remark", "")).strip()

        # 构建库存索引 - 优化性能
        try:
            inventory_df["ID"] = pd.to_numeric(inventory_df["ID"], errors="coerce").fillna(-1).astype(int)
            inventory_index = {row["ID"]: idx for idx, row in inventory_df.iterrows()}
        except Exception as e:
            return {"status": "error", "message": f"库存数据格式错误: {str(e)}"}, 500

        # 过滤无效库存ID并检查数据完整性
        valid_items = []
        invalid_items = []
        inventory_details = {}  # 存储库存详情用于后续处理

        for item in stock_out_items:
            inventory_id = item["inventory_id"]
            if inventory_id in inventory_index:
                idx = inventory_index[inventory_id]
                try:
                    # 获取当前库存信息
                    current_stock = (
                            float(inventory_df.at[idx, "入库数量"]) -
                            float(inventory_df.at[idx, "出库总数量"])
                    )

                    inventory_details[inventory_id] = {
                        "index": idx,
                        "current_stock": current_stock,
                        "product_code": inventory_df.at[idx, "商品编号"]
                    }
                    valid_items.append(item)
                except (ValueError, KeyError) as e:
                    invalid_items.append(f"库存ID {inventory_id}：数据不完整或格式错误")
            else:
                invalid_items.append(f"库存ID {inventory_id}：未找到对应的库存记录")

        if len(valid_items) == 0:
            return {
                "status": "error",
                "message": "所有库存ID均无效",
                "error_details": invalid_items
            }, 400

        # 批量处理出库 - 优化性能
        success_count = 0
        error_count = len(invalid_items)
        error_messages = invalid_items.copy()
        new_stock_out_records = []
        updated_inventory_ids = set()

        # 预生成出库记录ID
        try:
            next_record_id = generate_auto_id_df(stock_out_records_df)
            record_ids = [next_record_id + i for i in range(len(valid_items))]
        except Exception as e:
            return {"status": "error", "message": f"生成记录ID失败: {str(e)}"}, 500

        # 批量更新库存和创建出库记录
        for i, item in enumerate(valid_items):
            inventory_id = item["inventory_id"]
            out_quantity = item["out_quantity"]

            try:
                inventory_info = inventory_details[inventory_id]
                idx = inventory_info["index"]

                # 更新出库总数量
                current_out_total = float(inventory_df.at[idx, "出库总数量"])
                new_out_total = current_out_total + out_quantity
                inventory_df.at[idx, "出库总数量"] = new_out_total

                # 记录需要更新状态的库存ID
                updated_inventory_ids.add(inventory_id)

                # 创建出库记录
                new_stock_out_records.append({
                    "ID": record_ids[i],
                    "inventory_id": inventory_id,
                    "出库时间": out_time,
                    "出库数量": out_quantity,
                    "操作人员": operator,
                    "备注": remark
                })

                success_count += 1

            except Exception as e:
                error_count += 1
                product_info = inventory_details.get(inventory_id, {})
                product_code = product_info.get("product_code", "未知")
                error_messages.append(f"库存ID {inventory_id}({product_code})：处理失败 - {str(e)}")

        # 批量更新库存状态
        try:
            for inventory_id in updated_inventory_ids:
                update_inventory_status(inventory_id, csv_data)
        except Exception as e:
            error_count += len(updated_inventory_ids)
            error_messages.append(f"库存状态更新失败: {str(e)}")
            # 回滚成功的计数
            success_count -= len(updated_inventory_ids)

        # 如果有成功的记录，才进行数据写入
        if success_count > 0 and new_stock_out_records:
            try:
                # 批量添加出库记录
                new_records_df = pd.DataFrame(new_stock_out_records)
                stock_out_records_df = pd.concat([stock_out_records_df, new_records_df], ignore_index=True)

                csv_data["inventory"] = inventory_df
                csv_data["stock_out_records"] = stock_out_records_df

                # 写入文件
                write_success = write_csv_data(csv_data)
                if not write_success:
                    return {"status": "error", "message": "数据保存失败"}, 500
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"数据保存异常: {str(e)}"
                }, 500

        # 构建详细的响应数据
        response_data = {
            "status": "success" if success_count > 0 else "partial_success",
            "message": f"批量出库完成！成功: {success_count} 个，失败: {error_count} 个",
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

        # 添加成功详情
        if success_count > 0:
            success_details = []
            for item in valid_items[:min(10, len(valid_items))]:  # 限制返回数量
                inventory_id = item["inventory_id"]
                if inventory_id in inventory_details:
                    info = inventory_details[inventory_id]
                    success_details.append({
                        "inventory_id": inventory_id,
                        "product_code": info.get("product_code", ""),
                        "out_quantity": item["out_quantity"]
                    })
            response_data["data"]["success_details"] = success_details

        # 添加错误详情
        if error_messages:
            response_data["data"]["error_details"] = error_messages[:20]  # 限制显示数量

        # 如果没有成功记录，返回错误状态
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