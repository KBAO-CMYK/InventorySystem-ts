# stock_in.py
from flask import jsonify
import pandas as pd
from datetime import datetime
from read_utils import *
from other_utils import *
from write_utils import *
from stock_in import *
from config import *
import time


def batch_stock_in(data):
    """批量入库功能"""
    try:
        start_total = time.time()
        print(f"\n=== 批量入库请求开始 | 时间: {datetime.now()} | 数据量: {len(data.get('stock_in_items', []))}条 ===", flush=True)

        if not data:
            print(f"[错误] 批量入库：请求数据为空", flush=True)
            return {"status": "error", "message": "请求数据不能为空"}, 400

        # 验证批量入库数据格式
        if "stock_in_items" not in data or not isinstance(data["stock_in_items"], list):
            print(f"[错误] 批量入库：数据格式错误（缺少stock_in_items数组）", flush=True)
            return {"status": "error", "message": "批量入库数据格式错误，需要 stock_in_items 数组"}, 400

        stock_in_items = data["stock_in_items"]
        if len(stock_in_items) == 0:
            print(f"[错误] 批量入库：入库商品列表为空", flush=True)
            return {"status": "error", "message": "入库商品列表不能为空"}, 400

        # 读取数据
        start_read = time.time()
        csv_data = read_csv_data()
        inventory_df = csv_data.get("inventory", pd.DataFrame())
        manufacturer_df = csv_data.get("manufacturer", pd.DataFrame())
        feature_df = csv_data.get("feature", pd.DataFrame())
        stock_capacity_df = csv_data.get("stock_capacity", pd.DataFrame())
        print(f"[性能] 批量入库：CSV读取耗时 {time.time() - start_read:.4f}秒", flush=True)

        # 处理入库时间
        in_time = data.get("in_time")
        if not in_time:
            in_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        else:
            try:
                datetime.strptime(in_time, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                try:
                    datetime.strptime(in_time, "%Y-%m-%d %H")
                    in_time = in_time + ":00:00"
                except ValueError:
                    print(f"[错误] 批量入库：时间格式错误 - {in_time}", flush=True)
                    return {"status": "error", "message": "时间格式不正确，请使用 YYYY-MM-DD HH:MM:SS 或 YYYY-MM-DD HH"}, 400

        # 批量处理前的容量检查
        start_cap_check = time.time()
        floor_capacity_check = {}
        inventory_list = inventory_df.to_dict('records')

        # 先统计各楼层需要的新增框数
        for item in stock_in_items:
            try:
                floor = int(item.get("floor", 0))
                quantity = float(item.get("quantity", 0))
                address_type = item.get("address_type", 1)

                # 只有正数入库且地址类型为框时才检查容量
                if quantity > 0 and address_type == 1:
                    if floor not in floor_capacity_check:
                        floor_capacity_check[floor] = 0
                    # 检查框号是否已存在，新框号才计数
                    box_no = str(item.get("box_no", "")).strip()
                    if box_no and box_no not in get_unique_boxes_by_floor(floor, inventory_list):
                        floor_capacity_check[floor] += 1
            except (ValueError, TypeError):
                continue

        # 检查各楼层容量
        for floor, new_boxes in floor_capacity_check.items():
            if new_boxes > 0:
                floor_capacity, stock_capacity_df = update_stock_capacity(floor, inventory_list, stock_capacity_df)
                if floor_capacity["楼层剩余容量"] < new_boxes:
                    used_boxes = floor_capacity["楼层容量"] - floor_capacity["楼层剩余容量"]
                    print(f"[错误] 批量入库：{floor}楼容量不足（需{new_boxes}框/剩{floor_capacity['楼层剩余容量']}框）", flush=True)
                    return {
                        "status": "error",
                        "message": f"警告：{floor}楼库存容量不足！需要{new_boxes}框，但只有{floor_capacity['楼层剩余容量']}框可用。当前{floor}楼库存状态：已用{used_boxes}框 / 总容量{floor_capacity['楼层容量']}框"
                    }, 400
        print(f"[性能] 批量入库：楼层容量检查耗时 {time.time() - start_cap_check:.4f}秒", flush=True)

        # 批量处理入库
        success_count = 0
        error_count = 0
        error_messages = []
        new_inventory_records = []
        new_manufacturer_records = []
        new_feature_records = []

        # 预生成ID范围
        start_id = time.time()
        next_inventory_id = generate_auto_id_df(inventory_df)
        next_manufacturer_id = generate_auto_id_df(manufacturer_df)
        next_feature_id = generate_auto_id_df(feature_df)

        inventory_ids = [next_inventory_id + i for i in range(len(stock_in_items))]
        manufacturer_ids = [next_manufacturer_id + i for i in range(len(stock_in_items))]
        feature_ids = [next_feature_id + i for i in range(len(stock_in_items))]
        print(f"[性能] 批量入库：ID预生成耗时 {time.time() - start_id:.4f}秒", flush=True)

        # 逐条处理数据
        start_process = time.time()
        for i, item in enumerate(stock_in_items):
            try:
                # 校验必填字段
                required_fields = ["product_code", "product_type", "address_type", "floor", "quantity"]
                missing_fields = [field for field in required_fields if
                                  field not in item or not str(item[field]).strip()]
                if missing_fields:
                    error_count += 1
                    err_msg = f"第{i + 1}条记录缺少必填字段: {', '.join(missing_fields)}"
                    error_messages.append(err_msg)
                    continue

                # 校验商品类型
                product_type = str(item["product_type"]).strip()
                if product_type not in PRODUCT_TYPES:
                    error_count += 1
                    err_msg = f"第{i + 1}条记录商品类型无效: {product_type}"
                    error_messages.append(err_msg)
                    continue

                # 校验楼层
                try:
                    floor = int(item["floor"])
                    if floor not in FLOORS:
                        error_count += 1
                        err_msg = f"第{i + 1}条记录楼层无效: {floor}"
                        error_messages.append(err_msg)
                        continue
                except (ValueError, TypeError):
                    error_count += 1
                    err_msg = f"第{i + 1}条记录楼层格式错误"
                    error_messages.append(err_msg)
                    continue

                # 校验数量
                try:
                    quantity = float(item["quantity"])
                except (ValueError, TypeError):
                    error_count += 1
                    err_msg = f"第{i + 1}条记录数量格式错误"
                    error_messages.append(err_msg)
                    continue

                address_type = item["address_type"]

                # 校验地址字段
                address_errors = []
                if address_type in [1, 3, 5] and (not item.get("shelf_no") or not str(item["shelf_no"]).strip()):
                    address_errors.append("架号")
                if address_type in [2, 3, 4, 5] and (not item.get("box_no") or not str(item["box_no"]).strip()):
                    address_errors.append("框号")
                if address_type in [4, 5, 6] and (not item.get("package_no") or not str(item["package_no"]).strip()):
                    address_errors.append("包号")

                if address_errors:
                    error_count += 1
                    err_msg = f"第{i + 1}条记录地址类型 {address_type} 需要以下字段: {', '.join(address_errors)}"
                    error_messages.append(err_msg)
                    continue

                # 处理商品编号
                product_code = str(item["product_code"]).strip()
                if not product_code:
                    error_count += 1
                    err_msg = f"第{i + 1}条记录商品编号不能为空"
                    error_messages.append(err_msg)
                    continue

                unit = get_unit_by_addr_type(address_type)

                # 处理其他字段
                unit_price = float(item.get("unit_price", 0)) if item.get("unit_price") else 0.0
                weight = float(item.get("weight", 0)) if item.get("weight") else 0.0
                factory_sku = item.get("factory_sku", "")
                factory_name = item.get("factory_name", "")
                factory_address = item.get("factory_address", "")
                factory_phone = item.get("factory_phone", "")
                usage = item.get("usage", "")
                specification = item.get("specification", "")
                note = item.get("note", "")

                # 计算状态和库存数量
                current_stock = quantity
                if current_stock > 0:
                    status = "已入库"
                elif current_stock == 0:
                    status = "已出库"
                else:
                    status = "未知库存"

                inventory_id = inventory_ids[i]

                # 构建库存记录 (inventory.csv)
                new_inventory_records.append({
                    "ID": inventory_id,
                    "商品编号": product_code,
                    "入库时间": in_time,
                    "入库数量": quantity,
                    "出库总数量": 0,
                    "状态": status,
                    "库存数量": current_stock,
                    "地址类型": address_type,
                    "楼层": floor,
                    "架号": str(item.get("shelf_no", "")).strip(),
                    "框号": str(item.get("box_no", "")).strip(),
                    "包号": str(item.get("package_no", "")).strip(),
                    "单位": unit
                })

                # 构建厂家记录 (manufacturer.csv)
                new_manufacturer_records.append({
                    "ID": manufacturer_ids[i],
                    "inventory_id": inventory_id,
                    "厂家货号": factory_sku,
                    "厂家": factory_name,
                    "厂家地址": factory_address,
                    "电话": factory_phone
                })

                # 构建特征记录 (feature.csv)
                new_feature_records.append({
                    "ID": feature_ids[i],
                    "inventory_id": inventory_id,
                    "商品类型": product_type,
                    "单价": unit_price,
                    "重量": weight,
                    "用途": usage,
                    "规格": specification,
                    "备注": note,
                    "材质": item.get("material", ""),
                    "颜色": item.get("color", ""),
                    "形状": item.get("shape", ""),
                    "风格": item.get("style", "")
                })

                success_count += 1

            except Exception as e:
                error_count += 1
                err_msg = f"第{i + 1}条记录处理失败: {str(e)}"
                error_messages.append(err_msg)
                continue
        print(f"[性能] 批量入库：逐条数据处理耗时 {time.time() - start_process:.4f}秒", flush=True)

        # 如果所有记录都失败，直接返回
        if success_count == 0:
            print(f"[错误] 批量入库：所有记录处理失败", flush=True)
            return {
                "status": "error",
                "message": "所有入库记录都处理失败",
                "error_details": error_messages
            }, 400

        # 批量合并数据
        start_concat = time.time()
        if new_inventory_records:
            new_inventory_df = pd.DataFrame(new_inventory_records)
            inventory_df = pd.concat([inventory_df, new_inventory_df], ignore_index=True)

        if new_manufacturer_records:
            new_manufacturer_df = pd.DataFrame(new_manufacturer_records)
            manufacturer_df = pd.concat([manufacturer_df, new_manufacturer_df], ignore_index=True)

        if new_feature_records:
            new_feature_df = pd.DataFrame(new_feature_records)
            feature_df = pd.concat([feature_df, new_feature_df], ignore_index=True)
        print(f"[性能] 批量入库：DataFrame合并耗时 {time.time() - start_concat:.4f}秒", flush=True)

        csv_data["inventory"] = inventory_df
        csv_data["manufacturer"] = manufacturer_df
        csv_data["feature"] = feature_df
        csv_data["stock_capacity"] = stock_capacity_df

        # 写入文件
        start_write = time.time()
        if not write_csv_data(csv_data):
            print(f"[错误] 批量入库：数据保存失败", flush=True)
            return {"status": "error", "message": "数据保存失败"}, 500
        print(f"[性能] 批量入库：CSV写入耗时 {time.time() - start_write:.4f}秒", flush=True)

        # 构建成功记录的信息
        success_details = []
        for i in range(success_count):
            if i < len(new_inventory_records):
                record = new_inventory_records[i]
                manufacturer = new_manufacturer_records[i]
                feature = new_feature_records[i]

                success_details.append({
                    "inventory_id": int(record["ID"]),
                    "product_code": record["商品编号"],
                    "quantity": float(record["入库数量"]),
                    "manufacturer_id": int(manufacturer["ID"]),
                    "feature_id": int(feature["ID"])
                })

        # 总耗时统计
        total_time = time.time() - start_total
        avg_time = total_time / len(stock_in_items) if len(stock_in_items) > 0 else 0
        print(f"=== 批量入库请求结束 | 总耗时: {total_time:.4f}秒 | 单条平均耗时: {avg_time:.4f}秒 | 成功{success_count}条/失败{error_count}条 ===\n", flush=True)

        response_data = {
            "status": "success",
            "message": f"批量入库完成！成功: {success_count} 个，失败: {error_count} 个",
            "data": {
                "success_count": success_count,
                "error_count": error_count,
                "total_count": len(stock_in_items),
                "total_time": f"{total_time:.4f}秒",
                "avg_time_per_item": f"{avg_time:.4f}秒",
                "success_details": success_details
            }
        }

        if error_messages:
            response_data["error_details"] = error_messages[:20]  # 限制显示20条错误

        return response_data, 200

    except Exception as e:
        error_msg = f"批量入库操作异常: {str(e)}"
        print(f"[异常] {error_msg}", flush=True)
        return {"status": "error", "message": f"系统异常: {str(e)}"}, 500


def get_last_address_info(data):
    """获取最后地址信息（架号、框号、包号）- 仅按地址类型区分"""
    try:
        print(f"\n=== 获取最后地址信息请求开始 | 时间: {datetime.now()} ===", flush=True)

        if not data:
            print("[错误] 获取最后地址信息：请求数据为空", flush=True)
            return {"status": "error", "message": "请求数据不能为空"}, 400

        # 校验必填字段 - 现在只需要地址类型
        required_fields = ["address_type"]
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            print(f"[错误] 获取最后地址信息：缺少必填字段 - {', '.join(missing_fields)}", flush=True)
            return {
                "status": "error",
                "message": f"缺少必填字段: {', '.join(missing_fields)}"
            }, 400

        # 校验地址类型
        try:
            address_type = int(data["address_type"])
            if address_type not in [1, 2, 3, 4, 5, 6]:
                print(f"[错误] 获取最后地址信息：无效地址类型 - {address_type}", flush=True)
                return {
                    "status": "error",
                    "message": "无效的地址类型，请选择1-6之间的数字"
                }, 400
        except (ValueError, TypeError):
            print(f"[错误] 获取最后地址信息：地址类型格式错误 - {data.get('address_type')}", flush=True)
            return {
                "status": "error",
                "message": "地址类型必须是整数"
            }, 400

        # 读取库存数据
        csv_data = read_csv_data()
        inventory_df = csv_data.get("inventory", pd.DataFrame())

        if inventory_df.empty:
            print(f"[信息] 获取最后地址信息：库存数据为空，返回默认值", flush=True)
            return {
                "status": "success",
                "data": {
                    "shelf_no": "",
                    "box_no": "",
                    "package_no": ""
                }
            }, 200

        # 过滤指定地址类型的记录（不按楼层过滤）
        filtered_df = inventory_df[inventory_df["地址类型"] == address_type]

        if filtered_df.empty:
            print(f"[信息] 获取最后地址信息：地址类型{address_type}无记录，返回默认值", flush=True)
            return {
                "status": "success",
                "data": {
                    "shelf_no": "",
                    "box_no": "",
                    "package_no": ""
                }
            }, 200

        # 按ID倒序排列，获取最后的记录（ID最大的记录）
        latest_record = filtered_df.sort_values("ID", ascending=False).iloc[0]

        # 提取地址信息
        shelf_no = str(latest_record.get("架号", "")).strip() if pd.notna(latest_record.get("架号")) else ""
        box_no = str(latest_record.get("框号", "")).strip() if pd.notna(latest_record.get("框号")) else ""
        package_no = str(latest_record.get("包号", "")).strip() if pd.notna(latest_record.get("包号")) else ""

        print(f"[成功] 获取最后地址信息：地址类型{address_type} - ID:{latest_record['ID']} - 架号:{shelf_no}, 框号:{box_no}, 包号:{package_no}", flush=True)

        return {
            "status": "success",
            "data": {
                "shelf_no": shelf_no,
                "box_no": box_no,
                "package_no": package_no
            }
        }, 200

    except Exception as e:
        error_msg = f"获取最后地址信息异常: {str(e)}"
        print(f"[异常] {error_msg}", flush=True)
        return {"status": "error", "message": f"系统异常: {str(e)}"}, 500