from typing import Dict, List
from utils import *
from image import *

def batch_delete_images_logic(data: dict, app_logger):
    """
    批量删除图片的业务逻辑
    Args:
        data: 请求数据字典
        app_logger: 应用日志记录器

    Returns:
        tuple: (响应数据字典, HTTP状态码)
    """
    # 1. 解析JSON请求数据
    feature_ids: List[str] = data.get("featureIds", [])
    image_paths: List[str] = data.get("imagePaths", [])
    related_product_ids: List[str] = data.get("relatedProductIds", [])
    clean_csv = data.get("cleanCsv", True)

    # 2. 类型校验（确保是数组）
    if not isinstance(feature_ids, list) or not isinstance(image_paths, list) or not isinstance(related_product_ids,
                                                                                                list):
        app_logger.warning("[批量删除失败] featureIds/imagePaths/relatedProductIds需为数组")
        return {
            "status": "error",
            "message": "featureIds/imagePaths/relatedProductIds必须为数组类型",
            "total": 0,
            "success_count": 0,
            "fail_count": 0,
            "details": []
        }, 400

    # 3. 去重+空值过滤
    feature_ids = [str(fid).strip() for fid in feature_ids if fid and str(fid).strip()]
    image_paths = [path.strip() for path in image_paths if path and str(path).strip()]
    related_product_ids = [code.strip() for code in related_product_ids if code and str(code).strip()]

    # 4. 校验参数非空
    if not feature_ids and not image_paths:
        app_logger.warning("[批量删除失败] 特征ID数组和图片路径数组同时为空")
        return {
            "status": "error",
            "message": "特征ID数组（featureIds）和图片路径数组（imagePaths）不能同时为空",
            "total": 0,
            "success_count": 0,
            "fail_count": 0,
            "details": []
        }, 400

    # 5. 统一整理待处理的图片路径
    target_path_map: Dict[str, str] = {}
    error_details: List[Dict] = []
    fid_to_path = {}

    # 6. 处理featureIds批量转换为图片路径
    if feature_ids:
        try:
            feature_image_mapping = {}
            csv_data = read_csv_data()
            feature_df = csv_data.get("feature", pd.DataFrame())
            if not feature_df.empty:
                for _, row in feature_df.iterrows():
                    fid_val = row["商品特征ID"]
                    if pd.isna(fid_val):
                        continue
                    try:
                        fid_int = int(fid_val)
                    except (ValueError, TypeError):
                        continue

                    path_val = row["图片路径"]
                    if pd.isna(path_val) or not str(path_val).strip():
                        continue
                    feature_image_mapping[fid_int] = str(path_val).strip()

            fid_path_map = batch_get_feature_image_by_ids(feature_ids, feature_image_mapping)

            for fid in feature_ids:
                path = fid_path_map.get(fid, "")
                fid_to_path[fid] = path
                if not path:
                    error_details.append({
                        "type": "featureId",
                        "id": fid,
                        "status": "fail",
                        "message": f"特征ID[{fid}]未关联任何图片",
                        "image_path": "",
                        "image_deleted": False,
                        "csv_cleaned": False,
                        "remaining_references": 0
                    })
                else:
                    target_path_map[f"fid_{fid}"] = path
        except Exception as e:
            app_logger.error(f"[批量删除失败] 批量查询特征ID关联图片失败：{str(e)}")
            return {
                "status": "error",
                "message": f"批量查询特征ID关联图片失败：{str(e)}",
                "total": len(feature_ids) + len(image_paths),
                "success_count": 0,
                "fail_count": len(feature_ids) + len(image_paths),
                "details": error_details
            }, 500

    # 7. 处理imagePaths直接加入待处理列表
    for path in image_paths:
        if feature_ids:
            for fid in feature_ids:
                target_path_map[f"fid_{fid}"] = path
                fid_to_path[fid] = path
        else:
            target_path_map[f"path_{path}"] = path

    # 8. 校验所有图片路径合法性
    valid_path_map: Dict[str, Dict] = {}
    for identifier, path in target_path_map.items():
        full_path = get_image_full_path(path)
        if not full_path:
            error_details.append({
                "type": "imagePath" if identifier.startswith("path_") else "featureId",
                "id": identifier.split("_")[1],
                "status": "fail",
                "message": f"图片路径非法或不存在：{path}",
                "image_path": path,
                "image_deleted": False,
                "csv_cleaned": False,
                "remaining_references": 0
            })
        else:
            valid_path_map[identifier] = {
                "path": path,
                "full_path": full_path,
                "norm_path": os.path.normpath(path) if path else ""
            }

    # 9. 批量处理CSV清理
    csv_clean_success = False
    path_reference_map: Dict[str, int] = {}
    feature_df = pd.DataFrame()

    if clean_csv and valid_path_map:
        try:
            csv_data = read_csv_data()
            feature_df = csv_data.get("feature", pd.DataFrame())
            if not feature_df.empty:
                feature_df["图片路径"] = feature_df["图片路径"].apply(
                    lambda x: os.path.normpath(x) if (pd.notna(x) and x != "") else x
                )

                clear_fids = []
                for identifier, info in valid_path_map.items():
                    if identifier.startswith("fid_"):
                        fid = identifier.split("_")[1]
                        try:
                            clear_fids.append(int(fid))
                        except ValueError:
                            error_details.append({
                                "type": "featureId",
                                "id": fid,
                                "status": "fail",
                                "message": f"特征ID[{fid}]无法转换为整数",
                                "image_path": info["path"],
                                "image_deleted": False,
                                "csv_cleaned": False,
                                "remaining_references": 0
                            })

                if clear_fids:
                    mask_fid = feature_df["商品特征ID"].isin(clear_fids)
                    feature_df.loc[mask_fid, "图片路径"] = ""
                    app_logger.info(f"[批量CSV清理] 按特征ID清空 {mask_fid.sum()} 行")

                all_target_paths = [info["norm_path"] for info in valid_path_map.values()]
                for path in all_target_paths:
                    remaining = len(feature_df[
                                        (feature_df["图片路径"] == path) &
                                        (pd.notna(feature_df["图片路径"])) &
                                        (feature_df["图片路径"] != "")
                                        ])
                    path_reference_map[path] = remaining

                csv_data["feature"] = feature_df
                write_csv_data(csv_data)
                csv_clean_success = True
                app_logger.info(f"[批量CSV同步成功] 处理{len(valid_path_map)}个特征ID，剩余引用数：{path_reference_map}")
            else:
                app_logger.warning("[批量CSV清理] feature.csv为空，无需处理")
                csv_clean_success = True
                for info in valid_path_map.values():
                    path_reference_map[info["norm_path"]] = 0
        except Exception as e:
            app_logger.error(f"[批量CSV清理失败] {str(e)}")
            return {
                "status": "error",
                "message": f"批量清理CSV失败：{str(e)}",
                "total": len(valid_path_map) + len(error_details),
                "success_count": 0,
                "fail_count": len(valid_path_map) + len(error_details),
                "details": error_details
            }, 500

    # 10. 批量处理图片删除
    success_details: List[Dict] = []
    for identifier, info in valid_path_map.items():
        path = info["path"]
        full_path = info["full_path"]
        norm_path = info["norm_path"]
        remaining_ref = path_reference_map.get(norm_path, 0)
        delete_success = False
        item_type = "imagePath" if identifier.startswith("path_") else "featureId"
        item_id = identifier.split("_")[1]

        try:
            if os.path.exists(full_path) and remaining_ref == 0:
                os.remove(full_path)
                delete_success = True
                app_logger.info(f"[批量图片删除成功] 路径：{full_path} | 无剩余引用")
            elif os.path.exists(full_path) and remaining_ref > 0:
                app_logger.warning(f"[批量图片保留] 路径：{full_path} | 仍有{remaining_ref}个引用")
            else:
                app_logger.warning(f"[批量图片警告] 文件不存在：{full_path}")

            success_details.append({
                "type": item_type,
                "id": item_id,
                "status": "success",
                "message": (
                    "特征ID对应的图片路径已清空，且无其他引用，图片文件已删除" if delete_success
                    else f"特征ID对应的图片路径已清空，仍有{remaining_ref}个引用，文件保留" if remaining_ref > 0
                    else "特征ID对应的图片路径已清空，图片文件不存在"
                ),
                "image_path": path,
                "full_image_path": full_path,
                "image_deleted": delete_success,
                "csv_cleaned": clean_csv and csv_clean_success,
                "remaining_references": remaining_ref
            })
        except PermissionError:
            error_details.append({
                "type": item_type,
                "id": item_id,
                "status": "fail",
                "message": f"无文件写入权限：{full_path}",
                "image_path": path,
                "image_deleted": False,
                "csv_cleaned": clean_csv and csv_clean_success,
                "remaining_references": remaining_ref
            })
        except Exception as e:
            error_details.append({
                "type": item_type,
                "id": item_id,
                "status": "fail",
                "message": f"处理失败：{str(e)}",
                "image_path": path,
                "image_deleted": False,
                "csv_cleaned": clean_csv and csv_clean_success,
                "remaining_references": remaining_ref
            })

    # 11. 批量清理缓存
    if related_product_ids:
        clear_image_cache_by_product_code(related_product_ids)

    all_target_paths = [info["path"] for info in valid_path_map.values()]
    for path in all_target_paths:
        if path in image_memory_cache:
            del image_memory_cache[path]

    get_image_full_path.cache_clear()

    # 12. 汇总响应数据
    all_details = success_details + error_details
    total = len(all_details)
    success_count = len(success_details)
    fail_count = len(error_details)

    if fail_count == total:
        overall_status = "error"
    elif fail_count > 0:
        overall_status = "partial_success"
    else:
        overall_status = "success"

    return {
        "status": overall_status,
        "message": (
            "全部处理成功" if overall_status == "success"
            else f"部分处理成功（成功{success_count}个，失败{fail_count}个）" if overall_status == "partial_success"
            else "全部处理失败"
        ),
        "total": total,
        "success_count": success_count,
        "fail_count": fail_count,
        "details": all_details
    }, 200 if overall_status != "error" else 500