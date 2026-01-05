from flask import jsonify, request
import pandas as pd
import time
from utils import *
from config import *
from datetime import datetime
import traceback
import re
# 1、查询详情
# 2、编辑
# 3、删除


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


def get_inventory_detail(inventory_id, page=1, page_size=50):
    """查询库存详情 - 统一计算入库/出库/借/还后的库存数量"""
    try:
        # ========== 【新增】打印请求参数 ==========
        print("=" * 50)
        print(f"【请求参数】库存ID：{inventory_id} | 页码：{page} | 页大小：{page_size}")
        print("=" * 50)

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
            # ========== 【新增】打印库存不存在的提示 ==========
            print(f"【错误】未找到库存ID为 {inventory_id} 的记录")
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

        # ========== 【新增】打印读取到的操作记录基础信息 ==========
        print(f"\n【操作记录】共读取到 {len(target_operations)} 条记录")
        if not target_operations.empty:
            # 打印前5条记录的关键字段（操作类型、操作时间、操作数量）
            print("【操作记录详情（前5条）】：")
            for idx, (_, row) in enumerate(target_operations.head(5).iterrows()):
                op_time = row.get("操作时间", "无")
                # 处理 NaT/空值
                if pd.isna(op_time):
                    op_time = "NaT（空时间）"
                print(
                    f"  第{idx + 1}条：操作类型={row.get('操作类型', '无')} | 操作时间={op_time} | 操作数量={row.get('操作数量', 0)}")

        # 操作记录分页
        page = max(1, int(page))
        page_size = max(10, min(int(page_size), 100))
        total_operations = int(len(target_operations))
        total_pages = int((total_operations + page_size - 1) // page_size)

        # 分页截取 + 处理操作时间（修复核心逻辑）
        paginated_operations = pd.DataFrame()
        if not target_operations.empty:
            # ========== 【新增：详细调试原始数据】 ==========
            print("\n【详细调试】操作时间原始数据：")
            for idx, (_, row) in enumerate(target_operations.iterrows()):
                original_time = row["操作时间"]
                print(f"  第{idx + 1}条：")
                print(f"    类型：{type(original_time)}")
                print(f"    值：{repr(original_time)}")
                print(f"    长度：{len(str(original_time))}")

            # ========== 【修复1：安全时间转换函数】 ==========
            def safe_convert_time(time_str):
                """安全的时间转换函数"""
                if pd.isna(time_str):
                    return pd.NaT

                # 如果是 datetime 类型直接返回
                if isinstance(time_str, (pd.Timestamp, datetime)):
                    return time_str

                # 转换为字符串并清理
                str_time = str(time_str).strip()

                # 清理常见问题字符
                # 1. 替换全角字符
                str_time = str_time.replace('：', ':')  # 全角冒号
                str_time = str_time.replace('－', '-')  # 全角横线

                # 2. 清理不可见字符（控制字符）
                import re
                str_time = re.sub(r'[\x00-\x1f\x7f]', '', str_time)

                # 3. 处理多个空格
                str_time = ' '.join(str_time.split())

                # 4. 统一时间格式（添加秒部分如果缺少）
                if ':' in str_time:
                    parts = str_time.split(':')
                    if len(parts) == 2:  # 只有时:分
                        str_time = f'{str_time}:00'
                    elif len(parts) > 3:  # 如果有多余部分，只取前3部分
                        str_time = ':'.join(parts[:3])

                # 5. 确保日期时间格式完整
                if len(str_time) == 10:  # 只有日期
                    str_time = f'{str_time} 00:00:00'
                elif len(str_time) == 16:  # 日期+时:分
                    str_time = f'{str_time}:00'

                return str_time

            # 应用安全转换
            print("\n【安全转换】开始转换操作时间...")
            target_operations["操作时间"] = target_operations["操作时间"].apply(safe_convert_time)

            # ========== 【新增：调试转换后的字符串】 ==========
            print("\n【调试】转换后的字符串：")
            for idx, (_, row) in enumerate(target_operations.iterrows()):
                conv_time = row["操作时间"]
                print(f"  第{idx + 1}条：{repr(conv_time)}")

            # ========== 【修复2：尝试多种转换方式】 ==========
            # 方式1：尝试标准格式
            target_operations["操作时间_parsed"] = pd.to_datetime(
                target_operations["操作时间"],
                errors='coerce',
                format='%Y-%m-%d %H:%M:%S'
            )

            # 检查哪些转换失败
            failed_mask = target_operations["操作时间_parsed"].isna()
            if failed_mask.any():
                print(f"\n【警告】部分时间转换失败：{failed_mask.sum()}条")

                # 方式2：尝试不指定format，让pandas自动推断
                target_operations.loc[failed_mask, "操作时间_parsed"] = pd.to_datetime(
                    target_operations.loc[failed_mask, "操作时间"],
                    errors='coerce',
                    format=None  # 不指定格式，自动推断
                )

            # 方式3：如果还有失败，尝试更宽松的转换
            still_failed_mask = target_operations["操作时间_parsed"].isna()
            if still_failed_mask.any():
                print(f"\n【警告】仍有{still_failed_mask.sum()}条记录转换失败，尝试最后手段...")

                # 手动解析日期时间
                for idx, row in target_operations[still_failed_mask].iterrows():
                    time_str = row["操作时间"]
                    if isinstance(time_str, str):
                        # 尝试提取日期和时间
                        date_match = re.search(r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})', time_str)
                        time_match = re.search(r'(\d{1,2}:\d{1,2}(:\d{1,2})?)', time_str)

                        if date_match:
                            date_part = date_match.group(1).replace('/', '-')
                            time_part = time_match.group(1) if time_match else "00:00:00"

                            # 补齐时间部分
                            if ':' in time_part:
                                time_parts = time_part.split(':')
                                if len(time_parts) == 2:
                                    time_part = f'{time_part}:00'

                            combined_str = f'{date_part} {time_part}'
                            try:
                                target_operations.at[idx, "操作时间_parsed"] = pd.to_datetime(
                                    combined_str, errors='coerce'
                                )
                            except:
                                target_operations.at[idx, "操作时间_parsed"] = pd.NaT

            # 使用转换后的列
            target_operations["操作时间"] = target_operations["操作时间_parsed"]
            target_operations.drop(columns=["操作时间_parsed"], inplace=True)

            # ========== 【新增：调试转换后的时间】 ==========
            print("\n【时间转换结果】：")
            for idx, (_, row) in enumerate(target_operations.head(10).iterrows()):
                conv_time = row["操作时间"]
                if pd.isna(conv_time):
                    conv_time_str = "NaT"
                else:
                    try:
                        conv_time_str = conv_time.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        conv_time_str = "格式错误"
                print(f"  第{idx + 1}条：转换后时间={conv_time_str}")

            # 检查是否有未转换的记录
            na_count = target_operations["操作时间"].isna().sum()
            if na_count > 0:
                print(f"\n【警告】仍有 {na_count} 条记录的时间转换失败")
                # 填充默认值（使用当前时间或最早的有效时间）
                valid_times = target_operations["操作时间"].dropna()
                if not valid_times.empty:
                    fill_time = valid_times.min()  # 使用最早的有效时间
                else:
                    fill_time = pd.Timestamp.now()

                target_operations["操作时间"] = target_operations["操作时间"].fillna(fill_time)
                print(f"【修复】已用 {fill_time.strftime('%Y-%m-%d %H:%M:%S')} 填充 {na_count} 条失败记录")

            # ========== 【修复3：排序逻辑确认（降序，最新时间在前）】 ==========
            target_operations = target_operations.sort_values(
                "操作时间",
                ascending=False,  # 降序：最新时间排在前面
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
            # ========== 【修复4：正确获取最后操作时间（排除NaT）】 ==========
            valid_times = target_operations["操作时间"].dropna()
            if not valid_times.empty:
                last_op_time = valid_times.max()
                last_operation_time = last_op_time.strftime("%Y-%m-%d %H:%M:%S")

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

        # ========== 【新增】打印最终返回给前端的数据（关键） ==========
        print("\n【最终返回前端数据】")
        print(f"1. 库存基本信息：{inventory_dict}")
        print(f"2. 操作记录总数：{total_operations}")
        print(f"3. 分页后返回的操作记录数：{len(operation_list)}")
        print(f"4. 操作记录示例（前3条）：")
        for idx, op in enumerate(operation_list[:3]):
            print(
                f"   第{idx + 1}条：操作类型={op.get('操作类型', '无')} | 操作时间={op.get('操作时间', '空')} | 操作数量={op.get('操作数量', 0)}")
        print(f"5. 最后操作时间：{last_operation_time}")
        print("=" * 50 + "\n")

        return response_data, 200

    except IndexError as e:
        error_trace = traceback.format_exc()
        print(f"【异常】库存详情查询索引异常：{str(e)}\n完整堆栈：{error_trace}")
        return {"status": "error", "message": "库存数据索引错误，请检查数据完整性"}, 500
    except TypeError as e:
        error_trace = traceback.format_exc()
        print(f"【异常】库存详情查询类型异常：{str(e)}\n完整堆栈：{error_trace}")
        return {"status": "error", "message": "数据类型转换错误，请检查字段格式"}, 500
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"【异常】获取库存详情异常: {str(e)}\n完整堆栈：{error_trace}")
        return {"status": "error", "message": f"系统异常：{str(e)}"}, 500


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

        # 类型校验
        product_type = str(edit_data.get("类型", "")).strip()
        if product_type != "" and product_type not in PRODUCT_TYPES:
            print(f"[错误] 库存编辑：类型无效 - {product_type}", flush=True)
            return {"status": "error", "message": f"类型无效，可选类型：{', '.join(PRODUCT_TYPES)}"}, 400

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