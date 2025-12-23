logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def get_inventory_list():
    """查询库存列表 - 修复fillna报错+商品/特征关联问题"""
    try:
        start_time = time.perf_counter()

        # 1. 读取数据
        csv_data = read_csv_data()
        load_time = time.perf_counter()
        logger.info(f"数据加载耗时: {(load_time - start_time) * 1000:.2f}ms")

        # 2. 提取各表
        inventory_df = csv_data.get("inventory", pd.DataFrame())
        feature_df = csv_data.get("feature", pd.DataFrame())
        product_df = csv_data.get("product", pd.DataFrame())
        location_df = csv_data.get("location", pd.DataFrame())
        manufacturer_df = csv_data.get("manufacturer", pd.DataFrame())
        operation_df = csv_data.get("operation_record", pd.DataFrame())

        # ===================== 修复：特征表索引构建 =====================
        feature_dict = {}
        if not feature_df.empty:
            for idx, row in feature_df.iterrows():
                feature_id = row.get("商品特征ID")
                if pd.isna(feature_id):
                    logger.warning(f"特征表第{idx}行：商品特征ID为空，跳过")
                    continue

                product_id = row.get("关联商品ID")
                product_id = None if pd.isna(product_id) else product_id

                feature_info = row.to_dict()
                feature_info = {k: v for k, v in feature_info.items() if not pd.isna(v)}
                feature_info["商品特征ID"] = feature_id
                feature_info["关联商品ID"] = product_id

                feature_dict[feature_id] = feature_info

        # ===================== 修复：商品表索引构建 =====================
        product_dict = {}
        if not product_df.empty:
            for idx, row in product_df.iterrows():
                product_id = row.get("商品ID")
                if pd.isna(product_id):
                    logger.warning(f"商品表第{idx}行：商品ID为空，跳过")
                    continue

                product_info = row.to_dict()
                product_info = {k: v for k, v in product_info.items() if not pd.isna(v)}
                product_info["商品ID"] = product_id

                product_dict[product_id] = product_info

        # ===================== 修复：位置/厂家索引构建 =====================
        location_dict = {}
        if not location_df.empty:
            for idx, row in location_df.iterrows():
                loc_id = row.get("地址ID")
                if pd.isna(loc_id):
                    logger.warning(f"位置表第{idx}行：地址ID为空，跳过")
                    continue
                loc_info = row.to_dict()
                loc_info = {k: v for k, v in loc_info.items() if not pd.isna(v)}
                location_dict[loc_id] = loc_info

        manufacturer_dict = {}
        if not manufacturer_df.empty:
            for idx, row in manufacturer_df.iterrows():
                mfr_id = row.get("厂家ID")
                if pd.isna(mfr_id):
                    logger.warning(f"厂家表第{idx}行：厂家ID为空，跳过")
                    continue
                mfr_info = row.to_dict()
                mfr_info = {k: v for k, v in mfr_info.items() if not pd.isna(v)}
                manufacturer_dict[mfr_id] = mfr_info

        # ===================== 修复：操作记录处理（核心报错点）=====================
        operation_stats = defaultdict(lambda: defaultdict(int))
        operation_records = defaultdict(list)

        if not operation_df.empty:
            # 修复1：显式指定value参数，ID字段用-1填充（兼容数值类型），避免None导致的报错
            # 若关联库存ID是字符串类型，改为 fillna(value="")
            operation_df["关联库存ID"] = operation_df["关联库存ID"].fillna(value=-1)
            # 修复2：操作数量填充0（数值类型）
            operation_df["操作数量"] = operation_df["操作数量"].fillna(value=0)
            # 修复3：操作类型填充空字符串（字符串类型）
            operation_df["操作类型"] = operation_df["操作类型"].fillna(value="")

            for _, row in operation_df.iterrows():
                inv_id = row["关联库存ID"]
                # 跳过填充的无效ID（-1）
                if inv_id == -1:
                    continue

                op_type = str(row["操作类型"])
                op_qty = int(row["操作数量"])

                operation_stats[inv_id][op_type] += op_qty
                operation_records[inv_id].append({
                    "操作记录ID": row.get("操作记录ID", None),
                    "操作类型": op_type,
                    "操作数量": op_qty,
                    "操作时间": row.get("操作时间", ""),
                    "操作人员": row.get("操作人员", ""),
                    "关联库存ID": inv_id
                })

        op_time = time.perf_counter()
        logger.info(f"操作记录处理耗时: {(op_time - load_time) * 1000:.2f}ms")

        # ===================== 库存数据组装 =====================
        inventory_with_details = []
        OP_IN = "入库"
        OP_OUT = "出库"
        OP_LEND = "借"
        OP_RETURN = "还"

        if not inventory_df.empty:
            for idx, inv_row in inventory_df.iterrows():
                inv_id = inv_row.get("库存ID")
                if pd.isna(inv_id):
                    logger.warning(f"库存表第{idx}行：库存ID为空，跳过")
                    continue

                feature_id = inv_row.get("关联商品特征ID")
                feature_id = None if pd.isna(feature_id) else feature_id

                location_id = inv_row.get("关联位置ID")
                location_id = None if pd.isna(location_id) else location_id

                manufacturer_id = inv_row.get("关联厂家ID")
                manufacturer_id = None if pd.isna(manufacturer_id) else manufacturer_id

                inventory_record = {
                    "库存ID": inv_id,
                    "关联商品特征ID": feature_id,
                    "关联位置ID": location_id,
                    "关联厂家ID": manufacturer_id,
                    "创建时间": inv_row.get("创建时间", ""),
                    "备注": inv_row.get("备注", "")
                }

                # 关联特征+商品
                feature_info = {}
                product_info = {}
                if feature_id is not None and feature_id in feature_dict:
                    feature_info = feature_dict[feature_id]
                    inventory_record["特征信息"] = feature_info

                    product_id = feature_info.get("关联商品ID")
                    if product_id is not None and product_id in product_dict:
                        product_info = product_dict[product_id]
                        inventory_record["商品信息"] = product_info
                        logger.info(f"库存ID[{inv_id}]：成功关联特征ID[{feature_id}]→商品ID[{product_id}]")
                    else:
                        logger.warning(f"库存ID[{inv_id}]：特征ID[{feature_id}]的关联商品ID[{product_id}]未找到")
                        inventory_record["商品信息"] = {}
                else:
                    logger.warning(f"库存ID[{inv_id}]：关联特征ID[{feature_id}]未找到")
                    inventory_record["特征信息"] = {}
                    inventory_record["商品信息"] = {}

                # 关联位置/厂家
                if location_id is not None and location_id in location_dict:
                    inventory_record["位置信息"] = location_dict[location_id]
                else:
                    inventory_record["位置信息"] = {}

                if manufacturer_id is not None and manufacturer_id in manufacturer_dict:
                    inventory_record["厂家信息"] = manufacturer_dict[manufacturer_id]
                else:
                    inventory_record["厂家信息"] = {}

                # 操作统计
                stats = operation_stats.get(inv_id, {})
                inventory_record["累计入库数量"] = stats.get(OP_IN, 0)
                inventory_record["累计出库数量"] = stats.get(OP_OUT, 0)
                inventory_record["累计借出数量"] = stats.get(OP_LEND, 0)
                inventory_record["累计归还数量"] = stats.get(OP_RETURN, 0)
                inventory_record["库存数量"] = (
                    inventory_record["累计入库数量"] -
                    inventory_record["累计出库数量"] -
                    inventory_record["累计借出数量"] +
                    inventory_record["累计归还数量"]
                )
                inventory_record["操作记录"] = operation_records.get(inv_id, [])

                inventory_with_details.append(inventory_record)

        assemble_time = time.perf_counter()
        logger.info(f"数据组装耗时: {(assemble_time - op_time) * 1000:.2f}ms")
        logger.info(f"最终关联到{len(inventory_with_details)}条库存记录")

        return {
            "status": "success",
            "data": inventory_with_details,
            "stats": {
                "inventory_count": len(inventory_with_details),
                "feature_count": len(feature_dict),
                "product_count": len(product_dict),
                "total_time_ms": round((assemble_time - start_time) * 1000, 2)
            }
        }, 200

    except Exception as e:
        logger.error(f"查询库存异常: {str(e)}", exc_info=True)
        return {"status": "error", "message": f"系统异常: {str(e)}"}, 500


# 如果需要分页，可以添加这个函数
def get_inventory_list_paginated(page=1, page_size=20):
    """分页查询库存列表"""
    try:
        result = get_inventory_list()

        if result[1] != 200:
            return result

        data = result[0]["data"]
        total = len(data)

        # 计算分页
        start_idx = (page - 1) * page_size
        end_idx = min(start_idx + page_size, total)

        paginated_data = data[start_idx:end_idx]

        return {
            "status": "success",
            "data": paginated_data,
            "pagination": {
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size
            }
        }, 200

    except Exception as e:
        print(f"分页查询异常: {str(e)}")
        return {"status": "error", "message": f"系统异常: {str(e)}"}, 500


# 如果需要缓存支持，可以添加这个装饰器版本
import functools
from datetime import datetime, timedelta

inventory_cache = {}
cache_expiry = {}


def cached_inventory_list(expire_minutes=5):
    """库存查询缓存装饰器"""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = "inventory_list_full"

            # 检查缓存
            now = datetime.now()
            if cache_key in inventory_cache:
                if cache_key in cache_expiry and now < cache_expiry[cache_key]:
                    print(f"【缓存命中】库存列表")
                    return inventory_cache[cache_key]

            # 执行查询
            result = func(*args, **kwargs)

            # 缓存结果
            if result[1] == 200:  # 只缓存成功结果
                inventory_cache[cache_key] = result
                cache_expiry[cache_key] = now + timedelta(minutes=expire_minutes)
                print(f"【缓存更新】库存列表，有效期{expire_minutes}分钟")

            return result

        return wrapper

    return decorator


# 使用缓存版本
@cached_inventory_list(expire_minutes=5)
def get_inventory_list_cached():
    """带缓存的库存查询"""
    return get_inventory_list()