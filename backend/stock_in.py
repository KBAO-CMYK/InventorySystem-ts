from flask import jsonify
import pandas as pd
from datetime import datetime
from utils import *
from config import *
import time


def batch_stock_in(data):
    """批量入库功能（优化：同一货号仅生成一个商品ID/商品记录 + 修复厂家ID为空问题 + 图片路径迁移至feature表）"""
    try:
        start_total = time.time()

        if not data:
            return {"status": "error", "message": "请求数据不能为空"}, 400

        # 验证批量入库数据格式
        if "stock_in_items" not in data or not isinstance(data["stock_in_items"], list):
            return {"status": "error", "message": "批量入库数据格式错误，需要 stock_in_items 数组"}, 400

        stock_in_items = data["stock_in_items"]
        if len(stock_in_items) == 0:
            return {"status": "error", "message": "入库商品列表不能为空"}, 400

        # 读取数据
        start_read = time.time()
        csv_data = read_csv_data()
        product_df = csv_data.get("product", pd.DataFrame())
        feature_df = csv_data.get("feature", pd.DataFrame())
        location_df = csv_data.get("location", pd.DataFrame())
        manufacturer_df = csv_data.get("manufacturer", pd.DataFrame())
        inventory_df = csv_data.get("inventory", pd.DataFrame())
        operation_df = csv_data.get("operation_record", pd.DataFrame())
        capacity_df = csv_data.get("capacity", pd.DataFrame())

        # 处理入库时间
        in_time = data.get("入库时间")
        if not in_time:
            in_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        else:
            try:
                # 支持多种时间格式
                if len(in_time) == 10:  # YYYY-MM-DD
                    in_time = in_time + " 00:00:00"
                elif len(in_time) == 13:  # YYYY-MM-DD HH
                    in_time = in_time + ":00:00"
                elif len(in_time) == 16:  # YYYY-MM-DD HH:MM
                    in_time = in_time + ":00"

                datetime.strptime(in_time, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return {"status": "error",
                        "message": "时间格式不正确，请使用 YYYY-MM-DD HH:MM:SS 或 YYYY-MM-DD HH"}, 400

        # 批量处理前的容量检查
        start_cap_check = time.time()
        floor_capacity_check = {}
        if not location_df.empty:
            location_list = location_df.to_dict('records')

        # 先统计各楼层需要的新增框数
        for item in stock_in_items:
            try:
                floor = int(item.get("楼层", 0))
                in_quantity = float(item.get("入库数量", 0))
                address_type = item.get("地址类型", 1)

                # 只有正数入库且地址类型为框时才检查容量
                if in_quantity > 0 and address_type == 1:
                    if floor not in floor_capacity_check:
                        floor_capacity_check[floor] = 0
                    # 检查框号是否已存在，新框号才计数
                    box_no = str(item.get("框号", "")).strip()
                    if box_no and box_no not in get_unique_boxes_by_floor(floor,
                                                                          location_list if location_df.empty else location_list):
                        floor_capacity_check[floor] += 1
            except (ValueError, TypeError):
                continue

        # 检查各楼层容量
        for floor, new_boxes in floor_capacity_check.items():
            if new_boxes > 0:
                floor_capacity, capacity_df = update_capacity(floor,
                                                              location_list if location_df.empty else location_list,
                                                              capacity_df)
                if floor_capacity["楼层剩余容量"] < new_boxes:
                    used_boxes = floor_capacity["楼层容量"] - floor_capacity["楼层剩余容量"]
                    return {
                        "status": "error",
                        "message": f"警告：{floor}楼库存容量不足！需要{new_boxes}框，但只有{floor_capacity['楼层剩余容量']}框可用。当前{floor}楼库存状态：已用{used_boxes}框 / 总容量{floor_capacity['楼层容量']}框"
                    }, 400

        # 批量处理入库
        success_count = 0
        error_count = 0
        error_messages = []

        # 预生成ID范围
        start_id = time.time()
        next_product_id = generate_auto_id_df(product_df, "商品ID")
        next_feature_id = generate_auto_id_df(feature_df, "商品特征ID")
        next_location_id = generate_auto_id_df(location_df, "地址ID")
        next_manufacturer_id = generate_auto_id_df(manufacturer_df, "厂家ID")
        next_inventory_id = generate_auto_id_df(inventory_df, "库存ID")
        next_operation_id = generate_auto_id_df(operation_df, "操作ID")

        # 初始化记录列表
        new_product_records = []
        new_feature_records = []
        new_location_records = []
        new_manufacturer_records = []
        new_inventory_records = []
        new_operation_records = []

        # 创建地址和厂家查找字典（用于批量去重）
        address_lookup = {}
        manufacturer_lookup = {}

        # 先建立现有地址的查找字典（从数据库中已有的记录）
        if not location_df.empty:
            for _, row in location_df.iterrows():
                # 构建唯一的地址键
                address_key = f"{row['地址类型']}|{row['楼层']}|{str(row['架号']).strip() if pd.notna(row['架号']) else ''}|{str(row['框号']).strip() if pd.notna(row['框号']) else ''}|{str(row['包号']).strip() if pd.notna(row['包号']) else ''}"
                address_lookup[address_key] = int(row["地址ID"])

        # 先建立现有厂家的查找字典（从数据库中已有的记录）
        if not manufacturer_df.empty:
            for idx, row in manufacturer_df.iterrows():
                # 统一处理空值和空格，转为字符串后去重
                factory_name = str(row.get("厂家", "")).strip() if pd.notna(row.get("厂家")) else ""
                factory_address = str(row.get("厂家地址", "")).strip() if pd.notna(row.get("厂家地址")) else ""
                factory_phone = str(row.get("电话", "")).strip() if pd.notna(row.get("电话")) else ""

                # 构建唯一的厂家键（兼容空字段，用特殊标记替代）
                manufacturer_key = f"{factory_name if factory_name else '###EMPTY###'}|{factory_address if factory_address else '###EMPTY###'}|{factory_phone if factory_phone else '###EMPTY###'}"
                manufacturer_id = int(row["厂家ID"])
                manufacturer_lookup[manufacturer_key] = manufacturer_id

        # 建立货号到商品ID的映射（实现同一货号一个商品ID）
        # 1. 先加载现有商品表中的货号-商品ID映射
        product_code_to_id = {}
        if not product_df.empty:
            for _, row in product_df.iterrows():
                product_code = str(row["货号"]).strip()
                if product_code and product_code not in product_code_to_id:
                    product_code_to_id[product_code] = int(row["商品ID"])

        # 2. 记录本次批量中新增的货号-商品ID映射（避免重复创建）
        new_product_code_to_id = {}

        # 用于跟踪在本次批量操作中已经分配的新地址ID/厂家ID
        new_addresses_assigned = {}  # 地址键 -> 新地址ID
        new_manufacturers_assigned = {}  # 厂家键 -> 新厂家ID

        # 逐条处理数据
        start_process = time.time()
        for i, item in enumerate(stock_in_items):
            try:
                # 校验必填字段
                required_fields = ["货号", "类型", "地址类型", "楼层", "入库数量"]
                missing_fields = [field for field in required_fields if
                                  field not in item or not str(item[field]).strip()]
                if missing_fields:
                    error_count += 1
                    err_msg = f"第{i + 1}条记录缺少必填字段: {', '.join(missing_fields)}"
                    error_messages.append(err_msg)
                    continue

                # 校验商品类型
                product_type = str(item["类型"]).strip()
                if product_type not in PRODUCT_TYPES:
                    error_count += 1
                    err_msg = f"第{i + 1}条记录商品类型无效: {product_type}"
                    error_messages.append(err_msg)
                    continue

                # 校验楼层
                try:
                    floor = int(item["楼层"])
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
                    in_quantity = float(item["入库数量"])
                    if in_quantity <= 0:
                        error_count += 1
                        err_msg = f"第{i + 1}条记录入库数量必须大于0"
                        error_messages.append(err_msg)
                        continue
                except (ValueError, TypeError):
                    error_count += 1
                    err_msg = f"第{i + 1}条记录数量格式错误"
                    error_messages.append(err_msg)
                    continue

                address_type = item["地址类型"]

                # 校验地址字段
                address_errors = []
                if address_type in [1, 3, 5] and (not item.get("架号") or not str(item["架号"]).strip()):
                    address_errors.append("架号")
                if address_type in [2, 3, 4, 5] and (not item.get("框号") or not str(item["框号"]).strip()):
                    address_errors.append("框号")
                if address_type in [4, 5, 6] and (not item.get("包号") or not str(item["包号"]).strip()):
                    address_errors.append("包号")

                if address_errors:
                    error_count += 1
                    err_msg = f"第{i + 1}条记录地址类型 {address_type} 需要以下字段: {', '.join(address_errors)}"
                    error_messages.append(err_msg)
                    continue

                # 处理货号
                product_code = str(item["货号"]).strip()
                if not product_code:
                    error_count += 1
                    err_msg = f"第{i + 1}条记录货号不能为空"
                    error_messages.append(err_msg)
                    continue

                # 处理其他字段
                unit_price = float(item.get("单价", 0)) if item.get("单价") else 0.0
                weight = float(item.get("重量", 0)) if item.get("重量") else 0.0
                factory_name = str(item.get("厂家", "")).strip() if item.get("厂家") else ""
                factory_address = str(item.get("厂家地址", "")).strip() if item.get("厂家地址") else ""
                factory_phone = str(item.get("电话", "")).strip() if item.get("电话") else ""
                usage = str(item.get("用途", "")).strip() if item.get("用途") else ""
                specification = str(item.get("规格", "")).strip() if item.get("规格") else ""
                note = str(item.get("备注", "")).strip() if item.get("备注") else ""
                # 图片路径仍从item读取，但后续存入feature表
                image_path = str(item.get("图片路径", "")).strip() if item.get("图片路径") else ""
                material = str(item.get("材质", "")).strip() if item.get("材质") else ""
                color = str(item.get("颜色", "")).strip() if item.get("颜色") else ""
                shape = str(item.get("形状", "")).strip() if item.get("形状") else ""
                style = str(item.get("风格", "")).strip() if item.get("风格") else ""
                batch = int(item.get("批次", 1))

                # 计算状态
                if in_quantity > 0:
                    status = "正常"
                elif in_quantity == 0:
                    status = "已出库"
                else:
                    status = "异常"

                # === 地址处理：检查是否已有完全相同的地址 ===
                shelf_no = str(item.get("架号", "")).strip()
                box_no = str(item.get("框号", "")).strip()
                package_no = str(item.get("包号", "")).strip()

                # 构建地址查找键
                address_key = f"{address_type}|{floor}|{shelf_no}|{box_no}|{package_no}"

                # 检查是否在数据库中已有相同地址
                if address_key in address_lookup:
                    # 使用数据库中的已有地址ID
                    location_id = address_lookup[address_key]
                # 检查是否在本次批量操作中已经为相同地址分配了新ID
                elif address_key in new_addresses_assigned:
                    # 使用本次批量操作中已分配的新地址ID
                    location_id = new_addresses_assigned[address_key]
                else:
                    # 需要创建新地址记录
                    location_id = next_location_id + len(new_addresses_assigned)
                    # 添加到查找字典（用于后续记录查找）
                    new_addresses_assigned[address_key] = location_id
                    # 添加到新地址记录列表（只添加一次）
                    new_location_records.append({
                        "地址ID": location_id,
                        "地址类型": address_type,
                        "楼层": floor,
                        "架号": shelf_no,
                        "框号": box_no,
                        "包号": package_no
                    })

                # 厂家匹配逻辑
                manufacturer_id = None  # 默认值：空厂家时赋值为 None
                if factory_name:
                    # 统一处理空值，生成匹配键（和现有厂家字典格式一致）
                    key_name = factory_name if factory_name else "###EMPTY###"
                    key_address = factory_address if factory_address else "###EMPTY###"
                    key_phone = factory_phone if factory_phone else "###EMPTY###"
                    manufacturer_key = f"{key_name}|{key_address}|{key_phone}"

                    # 检查是否在数据库中已有相同厂家
                    if manufacturer_key in manufacturer_lookup:
                        # 使用数据库中的已有厂家ID
                        manufacturer_id = manufacturer_lookup[manufacturer_key]
                    # 检查是否在本次批量操作中已经为相同厂家分配了新ID
                    elif manufacturer_key in new_manufacturers_assigned:
                        # 使用本次批量操作中已分配的新厂家ID
                        manufacturer_id = new_manufacturers_assigned[manufacturer_key]
                    else:
                        # 需要创建新厂家记录
                        manufacturer_id = next_manufacturer_id + len(new_manufacturers_assigned)
                        # 添加到查找字典（用于后续记录查找）
                        new_manufacturers_assigned[manufacturer_key] = manufacturer_id
                        # 添加到新厂家记录列表（只添加一次）
                        new_manufacturer_records.append({
                            "厂家ID": manufacturer_id,
                            "厂家": factory_name,
                            "厂家地址": factory_address,
                            "电话": factory_phone
                        })

                # 获取/分配商品ID（同一货号复用）
                # 1. 先查现有商品表
                if product_code in product_code_to_id:
                    product_id = product_code_to_id[product_code]
                # 2. 再查本次批量新增的
                elif product_code in new_product_code_to_id:
                    product_id = new_product_code_to_id[product_code]
                # 3. 全新货号，分配新ID并记录
                else:
                    product_id = next_product_id + len(new_product_code_to_id)
                    new_product_code_to_id[product_code] = product_id
                    # 仅首次创建商品记录【核心修改：移除图片路径字段】
                    new_product_records.append({
                        "商品ID": product_id,
                        "货号": product_code,
                        "类型": product_type,
                        "备注": note,
                        "用途": usage
                    })

                # 特征/库存/操作ID仍按原有逻辑（每个item一个）
                feature_id = next_feature_id + success_count
                inventory_id = next_inventory_id + success_count
                operation_id = next_operation_id + success_count

                # 商品特征记录 (feature.csv) - 每个特征组合一个【核心修改：添加图片路径字段】
                new_feature_records.append({
                    "商品特征ID": feature_id,
                    "关联商品ID": product_id,  # 关联同一个商品ID
                    "单价": unit_price,
                    "重量": weight,
                    "规格": specification,
                    "材质": material,
                    "颜色": color,
                    "形状": shape,
                    "风格": style,
                    "图片路径": image_path  # 新增：图片路径迁移至feature表
                })

                # 库存记录 (inventory.csv) - 每个特征组合一个
                unit = get_unit_by_addr_type(address_type)
                new_inventory_records.append({
                    "库存ID": inventory_id,
                    "关联商品特征ID": feature_id,
                    "关联位置ID": location_id,
                    "关联厂家ID": manufacturer_id,  # 空厂家时存 None，有厂家时存实际ID
                    "单位": unit,
                    "库存数量": in_quantity,
                    "次品数量": 0,
                    "批次": batch,
                    "状态": status
                })

                # 操作记录 (operation_record.csv) - 每个库存一个
                operator = str(item.get("操作人", "系统")).strip() if item.get("操作人") else "系统"
                new_operation_records.append({
                    "操作ID": operation_id,
                    "关联库存ID": inventory_id,
                    "操作类型": "入库",
                    "操作时间": in_time,
                    "操作数量": in_quantity,
                    "操作人": operator,
                    "备注": f"批量入库: {product_code}"
                })

                success_count += 1

            except Exception as e:
                error_count += 1
                err_msg = f"第{i + 1}条记录处理失败: {str(e)}"
                error_messages.append(err_msg)
                continue

        # 如果所有记录都失败，直接返回
        if success_count == 0:
            return {
                "status": "error",
                "message": "所有入库记录都处理失败",
                "error_details": error_messages
            }, 400

        # 批量合并数据
        start_concat = time.time()
        if new_product_records:
            new_product_df = pd.DataFrame(new_product_records)
            product_df = pd.concat([product_df, new_product_df], ignore_index=True)

        if new_feature_records:
            new_feature_df = pd.DataFrame(new_feature_records)
            feature_df = pd.concat([feature_df, new_feature_df], ignore_index=True)

        if new_location_records:
            new_location_df = pd.DataFrame(new_location_records)
            location_df = pd.concat([location_df, new_location_df], ignore_index=True)

        if new_manufacturer_records:
            new_manufacturer_df = pd.DataFrame(new_manufacturer_records)
            manufacturer_df = pd.concat([manufacturer_df, new_manufacturer_df], ignore_index=True)

        if new_inventory_records:
            new_inventory_df = pd.DataFrame(new_inventory_records)
            inventory_df = pd.concat([inventory_df, new_inventory_df], ignore_index=True)

        if new_operation_records:
            new_operation_df = pd.DataFrame(new_operation_records)
            operation_df = pd.concat([operation_df, new_operation_df], ignore_index=True)

        csv_data["product"] = product_df
        csv_data["feature"] = feature_df
        csv_data["location"] = location_df
        csv_data["manufacturer"] = manufacturer_df
        csv_data["inventory"] = inventory_df
        csv_data["operation_record"] = operation_df
        csv_data["capacity"] = capacity_df

        # 写入文件
        start_write = time.time()
        if not write_csv_data(csv_data):
            return {"status": "error", "message": "数据保存失败"}, 500
        # 保留CSV写入耗时日志
        print(f"[性能] 批量入库：CSV写入耗时 {time.time() - start_write:.4f}秒", flush=True)

        # 构建成功记录的信息
        success_details = []
        for i in range(success_count):
            if i < len(new_inventory_records):
                inventory_record = new_inventory_records[i]
                feature_record = new_feature_records[i]
                # 反向查找商品ID对应的货号
                product_code = None
                for code, pid in {**product_code_to_id, **new_product_code_to_id}.items():
                    if pid == feature_record["关联商品ID"]:
                        product_code = code
                        break

                success_details.append({
                    "商品ID": int(feature_record["关联商品ID"]),
                    "商品特征ID": int(feature_record["商品特征ID"]),
                    "位置ID": int(inventory_record["关联位置ID"]),
                    "厂家ID": int(inventory_record["关联厂家ID"]) if inventory_record["关联厂家ID"] is not None else None,
                    "库存ID": int(inventory_record["库存ID"]),
                    "操作ID": int(new_operation_records[i]["操作ID"]),
                    "货号": product_code or "",
                    "入库数量": float(inventory_record["库存数量"]),
                    "图片路径": feature_record["图片路径"]
                })

        # 总耗时统计
        total_time = time.time() - start_total
        avg_time = total_time / len(stock_in_items) if len(stock_in_items) > 0 else 0
        # 保留批量入库结束日志
        print(
            f"=== 批量入库请求结束 | 总耗时: {total_time:.4f}秒 | 单条平均耗时: {avg_time:.4f}秒 | 成功{success_count}条/失败{error_count}条 ===\n",
            flush=True)

        response_data = {
            "status": "success",
            "message": f"批量入库完成！成功: {success_count} 个，失败: {error_count} 个",
            "data": {
                "success_count": success_count,
                "error_count": error_count,
                "total_count": len(stock_in_items),
                "total_time": f"{total_time:.4f}秒",
                "avg_time_per_item": f"{avg_time:.4f}秒",
                "success_details": success_details,
                "product_mapping": new_product_code_to_id,
                "manufacturer_mapping": new_manufacturers_assigned
            }
        }

        if error_messages:
            response_data["error_details"] = error_messages[:20]

        return response_data, 200

    except Exception as e:
        error_msg = f"批量入库操作异常: {str(e)}"
        return {"status": "error", "message": f"系统异常: {str(e)}"}, 500