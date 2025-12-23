from inventory_management import *
from stock_out import *
from stock_out import *
from get import *
from lend_return import *


def export_operation_records(operation_type=None, inventory_id=None, start_date=None, end_date=None):
    """导出操作记录为CSV"""
    try:
        csv_data = read_csv_data()

        # 创建CSV输出
        output = io.StringIO()
        writer = csv.writer(output)

        # 写入表头
        writer.writerow([
            "操作ID", "操作类型", "关联库存ID", "操作数量", "操作时间", "操作人员", "操作备注",
            "库存ID", "库存数量", "次品数量", "批次", "状态", "单位",
            "商品ID", "货号", "商品名称", "类型", "图片路径", "备注", "用途",
            "特征ID", "单价", "重量", "规格", "材质", "颜色", "形状", "风格",
            "位置ID", "地址类型", "楼层", "架号", "框号", "包号",
            "厂家ID", "厂家", "厂家地址", "电话"
        ])

        # 获取所有需要的表格数据
        operation_df = csv_data.get("operation_record", pd.DataFrame())
        inventory_df = csv_data.get("inventory", pd.DataFrame())
        feature_df = csv_data.get("feature", pd.DataFrame())
        product_df = csv_data.get("product", pd.DataFrame())
        location_df = csv_data.get("location", pd.DataFrame())
        manufacturer_df = csv_data.get("manufacturer", pd.DataFrame())

        # 【关键修改1】检查数据是否为空
        if operation_df.empty:
            print("操作记录表为空")
            output.seek(0)
            return output.getvalue()

        print(f"操作记录总数: {len(operation_df)}")

        # 【关键修改2】确保操作记录中的关联库存ID是数值类型
        operation_df = operation_df.copy()
        operation_df["关联库存ID"] = pd.to_numeric(operation_df["关联库存ID"], errors="coerce").fillna(-1).astype(int)

        # 过滤操作记录
        if operation_type:
            operation_df = operation_df[operation_df["操作类型"] == operation_type]
            print(f"按操作类型过滤后: {len(operation_df)}")

        if inventory_id:
            operation_df = operation_df[operation_df["关联库存ID"] == int(inventory_id)]
            print(f"按库存ID过滤后: {len(operation_df)}")

        if start_date:
            try:
                operation_df["操作时间"] = pd.to_datetime(operation_df["操作时间"], errors="coerce")
                operation_df = operation_df[operation_df["操作时间"] >= pd.to_datetime(start_date)]
                print(f"按开始时间过滤后: {len(operation_df)}")
            except Exception as e:
                print(f"起始时间过滤异常: {str(e)}")

        if end_date:
            try:
                if "操作时间" not in operation_df.columns:
                    operation_df["操作时间"] = pd.to_datetime(operation_df["操作时间"], errors="coerce")
                operation_df = operation_df[operation_df["操作时间"] <= pd.to_datetime(end_date)]
                print(f"按结束时间过滤后: {len(operation_df)}")
            except Exception as e:
                print(f"结束时间过滤异常: {str(e)}")

        # 【关键修改3】确保所有数据表都有正确的数据类型
        # 处理库存表
        if not inventory_df.empty:
            inventory_df = inventory_df.copy()
            inventory_df["库存ID"] = pd.to_numeric(inventory_df["库存ID"], errors="coerce").fillna(-1).astype(int)
            inventory_df["关联商品特征ID"] = pd.to_numeric(inventory_df["关联商品特征ID"], errors="coerce").fillna(
                -1).astype(int)
            inventory_df["关联位置ID"] = pd.to_numeric(inventory_df["关联位置ID"], errors="coerce").fillna(-1).astype(
                int)
            inventory_df["关联厂家ID"] = pd.to_numeric(inventory_df["关联厂家ID"], errors="coerce").fillna(-1).astype(
                int)
            inventory_df["库存数量"] = pd.to_numeric(inventory_df["库存数量"], errors="coerce").fillna(0)
            inventory_df["次品数量"] = pd.to_numeric(inventory_df["次品数量"], errors="coerce").fillna(0)

        # 处理特征表
        if not feature_df.empty:
            feature_df = feature_df.copy()
            feature_df["商品特征ID"] = pd.to_numeric(feature_df["商品特征ID"], errors="coerce").fillna(-1).astype(int)
            feature_df["关联商品ID"] = pd.to_numeric(feature_df["关联商品ID"], errors="coerce").fillna(-1).astype(int)
            feature_df["单价"] = pd.to_numeric(feature_df["单价"], errors="coerce").fillna(0)
            feature_df["重量"] = pd.to_numeric(feature_df["重量"], errors="coerce").fillna(0)

        # 处理商品表
        if not product_df.empty:
            product_df = product_df.copy()
            product_df["商品ID"] = pd.to_numeric(product_df["商品ID"], errors="coerce").fillna(-1).astype(int)

        # 处理位置表
        if not location_df.empty:
            location_df = location_df.copy()
            location_df["地址ID"] = pd.to_numeric(location_df["地址ID"], errors="coerce").fillna(-1).astype(int)
            location_df["地址类型"] = pd.to_numeric(location_df["地址类型"], errors="coerce").fillna(1).astype(int)
            location_df["楼层"] = pd.to_numeric(location_df["楼层"], errors="coerce").fillna(1).astype(int)

        # 处理厂家表
        if not manufacturer_df.empty:
            manufacturer_df = manufacturer_df.copy()
            manufacturer_df["厂家ID"] = pd.to_numeric(manufacturer_df["厂家ID"], errors="coerce").fillna(-1).astype(int)

        # 【关键修改4】优化索引构建方法
        inventory_dict = {}
        if not inventory_df.empty and "库存ID" in inventory_df.columns:
            for _, row in inventory_df.iterrows():
                inv_id = row["库存ID"]
                if inv_id not in inventory_dict:
                    inventory_dict[inv_id] = row.to_dict()
            print(f"库存索引大小: {len(inventory_dict)}")

        feature_dict = {}
        if not feature_df.empty and "商品特征ID" in feature_df.columns:
            for _, row in feature_df.iterrows():
                feature_id = row["商品特征ID"]
                if feature_id not in feature_dict:
                    feature_dict[feature_id] = row.to_dict()
            print(f"特征索引大小: {len(feature_dict)}")

        product_dict = {}
        if not product_df.empty and "商品ID" in product_df.columns:
            for _, row in product_df.iterrows():
                product_id = row["商品ID"]
                if product_id not in product_dict:
                    product_dict[product_id] = row.to_dict()
            print(f"商品索引大小: {len(product_dict)}")

        location_dict = {}
        if not location_df.empty and "地址ID" in location_df.columns:
            for _, row in location_df.iterrows():
                loc_id = row["地址ID"]
                if loc_id not in location_dict:
                    location_dict[loc_id] = row.to_dict()
            print(f"位置索引大小: {len(location_dict)}")

        manufacturer_dict = {}
        if not manufacturer_df.empty and "厂家ID" in manufacturer_df.columns:
            for _, row in manufacturer_df.iterrows():
                mfr_id = row["厂家ID"]
                if mfr_id not in manufacturer_dict:
                    manufacturer_dict[mfr_id] = row.to_dict()
            print(f"厂家索引大小: {len(manufacturer_dict)}")

        # 【关键修改5】处理操作记录，确保每条记录都导出
        operation_list = df_to_serializable_list(operation_df)
        print(f"需要导出的操作记录数量: {len(operation_list)}")

        success_count = 0
        error_count = 0

        for record in operation_list:
            try:
                inv_id = record.get("关联库存ID")

                # 初始化默认值
                inventory_info = {}
                product_info = {}
                feature_info = {}
                location_info = {}
                manufacturer_info = {}

                # 获取库存信息
                if inv_id in inventory_dict:
                    inventory_info = inventory_dict[inv_id]

                    # 获取关联ID
                    feature_id = inventory_info.get("关联商品特征ID")
                    location_id = inventory_info.get("关联位置ID")
                    manufacturer_id = inventory_info.get("关联厂家ID")

                    # 获取特征信息
                    if feature_id is not None and feature_id != 0 and feature_id in feature_dict:
                        feature_info = feature_dict[feature_id]

                        # 获取商品信息
                        product_id = feature_info.get("关联商品ID")
                        if product_id is not None and product_id != 0 and product_id in product_dict:
                            product_info = product_dict[product_id]

                    # 获取位置信息
                    if location_id is not None and location_id != 0 and location_id in location_dict:
                        location_info = location_dict[location_id]

                    # 获取厂家信息
                    if manufacturer_id is not None and manufacturer_id != 0 and manufacturer_id in manufacturer_dict:
                        manufacturer_info = manufacturer_dict[manufacturer_id]

                # 【关键修改6】确保所有字段都有值，防止空值导致格式错误
                writer.writerow([
                    record.get("操作ID", ""),
                    record.get("操作类型", ""),
                    str(record.get("关联库存ID", "")),
                    str(convert_to_serializable(record.get("操作数量", 0))),
                    str(record.get("操作时间", "")),
                    str(record.get("操作人员", "")),
                    str(record.get("备注", "")),
                    str(inventory_info.get("库存ID", "")),
                    str(convert_to_serializable(inventory_info.get("库存数量", 0))),
                    str(convert_to_serializable(inventory_info.get("次品数量", 0))),
                    str(inventory_info.get("批次", "")),
                    str(inventory_info.get("状态", "")),
                    str(inventory_info.get("单位", "")),
                    str(product_info.get("商品ID", "")),
                    str(product_info.get("货号", "")),
                    str(product_info.get("商品名称", "")),
                    str(product_info.get("类型", "")),
                    str(product_info.get("图片路径", "")),
                    str(product_info.get("备注", "")),
                    str(product_info.get("用途", "")),
                    str(feature_info.get("商品特征ID", "")),
                    str(convert_to_serializable(feature_info.get("单价", 0))),
                    str(convert_to_serializable(feature_info.get("重量", 0))),
                    str(feature_info.get("规格", "")),
                    str(feature_info.get("材质", "")),
                    str(feature_info.get("颜色", "")),
                    str(feature_info.get("形状", "")),
                    str(feature_info.get("风格", "")),
                    str(location_info.get("地址ID", "")),
                    str(location_info.get("地址类型", "")),
                    str(location_info.get("楼层", "")),
                    str(location_info.get("架号", "")),
                    str(location_info.get("框号", "")),
                    str(location_info.get("包号", "")),
                    str(manufacturer_info.get("厂家ID", "")),
                    str(manufacturer_info.get("厂家", "")),
                    str(manufacturer_info.get("厂家地址", "")),
                    str(manufacturer_info.get("电话", ""))
                ])

                success_count += 1

            except Exception as e:
                error_count += 1
                print(f"导出操作记录ID {record.get('操作ID', '未知')} 时出错: {str(e)}")
                # 即使出错，也尝试导出基本数据
                try:
                    writer.writerow([
                        record.get("操作ID", ""),
                        record.get("操作类型", ""),
                        record.get("关联库存ID", ""),
                        record.get("操作数量", ""),
                        record.get("操作时间", ""),
                        record.get("操作人员", ""),
                        record.get("备注", ""),
                        "", "", "", "", "", "",  # 库存信息
                        "", "", "", "", "", "", "", "",  # 商品信息
                        "", "", "", "", "", "", "", "",  # 特征信息
                        "", "", "", "", "",  # 位置信息
                        "", "", "", ""  # 厂家信息
                    ])
                except:
                    pass

        print(f"导出完成: 成功 {success_count} 条，失败 {error_count} 条")

        # 返回CSV文件
        output.seek(0)
        csv_content = output.getvalue()
        print(f"生成的CSV内容长度: {len(csv_content)} 字节")

        return csv_content

    except Exception as e:
        print(f"导出操作记录异常: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


# 添加一个简化的导出函数，仅导出操作记录本身（不含关联信息）
def export_operation_records_simple(operation_type=None, inventory_id=None, start_date=None, end_date=None):
    """简化的导出操作记录为CSV（仅操作记录本身）"""
    try:
        csv_data = read_csv_data()

        # 创建CSV输出
        output = io.StringIO()
        writer = csv.writer(output)

        # 写入表头
        writer.writerow([
            "操作ID", "操作类型", "关联库存ID", "操作数量", "操作时间", "操作人员", "备注"
        ])

        # 获取操作记录
        operation_df = csv_data.get("operation_record", pd.DataFrame())

        if operation_df.empty:
            output.seek(0)
            return output.getvalue()

        # 过滤操作记录
        if operation_type:
            operation_df = operation_df[operation_df["操作类型"] == operation_type]

        if inventory_id:
            operation_df["关联库存ID"] = pd.to_numeric(operation_df["关联库存ID"], errors="coerce").fillna(-1).astype(
                int)
            operation_df = operation_df[operation_df["关联库存ID"] == int(inventory_id)]

        if start_date:
            try:
                operation_df["操作时间"] = pd.to_datetime(operation_df["操作时间"], errors="coerce")
                operation_df = operation_df[operation_df["操作时间"] >= pd.to_datetime(start_date)]
            except:
                pass

        if end_date:
            try:
                if "操作时间" not in operation_df.columns:
                    operation_df["操作时间"] = pd.to_datetime(operation_df["操作时间"], errors="coerce")
                operation_df = operation_df[operation_df["操作时间"] <= pd.to_datetime(end_date)]
            except:
                pass

        # 导出所有记录
        for _, row in operation_df.iterrows():
            writer.writerow([
                row.get("操作ID", ""),
                row.get("操作类型", ""),
                row.get("关联库存ID", ""),
                convert_to_serializable(row.get("操作数量", 0)),
                row.get("操作时间", ""),
                row.get("操作人员", ""),
                row.get("备注", "")
            ])

        output.seek(0)
        return output.getvalue()

    except Exception as e:
        print(f"简化导出操作记录异常: {str(e)}")
        return None