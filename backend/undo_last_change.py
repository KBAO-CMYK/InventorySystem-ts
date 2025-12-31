import os
import shutil
import hashlib
from utils import *  # 导入你的utils所有函数/配置
import logging

# 适配项目日志
logger = logging.getLogger(__name__)


def undo_last_change(confirm=False, table_name=None):
    """
    增强版撤销函数：默认恢复所有有备份的表（回退上一操作修改的所有表）
    :param confirm: 是否确认（API调用固定为False）
    :param table_name: 要恢复的表名（None=恢复所有有备份的表，指定则仅恢复该表）
    :return: dict - 包含success、message、restored、debug_info
    """
    debug_info = {}
    try:
        # ========== 关键1：强制转换为绝对路径（解决相对路径混乱） ==========
        abs_csv_dir = os.path.abspath(CSV_DIR)
        debug_info["csv_dir_abs"] = abs_csv_dir
        ensure_csv_directory()  # 确保CSV目录存在

        backup_exists = False
        # 核心修改：默认遍历所有表（table_name=None时），而非仅单个表
        target_tables = CSV_FILES.keys() if table_name is None else [table_name]
        debug_info["target_tables"] = list(target_tables)

        # 校验表是否存在 + 检查所有目标表的备份文件
        table_backup_map = {}  # 记录每个表的备份文件路径和MD5
        for table in target_tables:
            if table not in CSV_FILES:
                error_msg = f"表 {table} 不存在于配置的CSV_FILES中"
                logger.error(f"❌ {error_msg}")
                return {
                    "success": False,
                    "message": error_msg,
                    "restored": [],
                    "debug_info": debug_info
                }

            # 绝对路径计算
            filepath = os.path.abspath(CSV_FILES[table])
            backup_file = f"{filepath}.backup"
            table_backup_map[table] = {
                "csv_abs": filepath,
                "backup_abs": backup_file,
                "csv_exists": os.path.exists(filepath),
                "backup_exists": os.path.exists(backup_file)
            }

            # 计算MD5（验证内容）
            def get_md5(f):
                if not os.path.exists(f):
                    return "不存在"
                md5 = hashlib.md5()
                with open(f, 'rb') as f_obj:
                    while chunk := f_obj.read(4096):
                        md5.update(chunk)
                return md5.hexdigest()

            table_backup_map[table]["csv_md5_before"] = get_md5(filepath)
            table_backup_map[table]["backup_md5"] = get_md5(backup_file)

            if os.path.exists(backup_file):
                backup_exists = True

        debug_info["table_backup_map"] = table_backup_map

        if not backup_exists:
            error_msg = "无可用的备份文件，无法执行撤销操作"
            logger.error(f"❌ {error_msg}")
            return {
                "success": False,
                "message": error_msg,
                "restored": [],
                "debug_info": debug_info
            }

        # ========== 关键2：遍历所有目标表，恢复所有有备份的表 ==========
        restored = []
        for table in target_tables:
            tb_info = table_backup_map[table]
            filepath = tb_info["csv_abs"]
            backup_file = tb_info["backup_abs"]

            if tb_info["backup_exists"]:
                # 1. 先删除原文件（确保覆盖，避免文件占用）
                if tb_info["csv_exists"]:
                    os.remove(filepath)
                    logger.info(f"删除原CSV文件：{filepath}")

                # 2. 复制备份文件（强制覆盖）
                shutil.copy2(backup_file, filepath)
                # 3. 强制刷新文件系统（解决延迟生效）
                os.sync()

                # 4. 验证恢复结果
                tb_info["csv_md5_after"] = get_md5(filepath)
                if tb_info["csv_md5_after"] == tb_info["backup_md5"]:
                    restored.append(table)
                    logger.info(f"✅ 表 {table} 已从备份恢复（MD5一致）")
                else:
                    logger.error(f"❌ 表 {table} 恢复后MD5不一致")

        # ========== 关键3：彻底清空缓存（适配utils的双层缓存） ==========
        invalidate_cache()  # 清空lru_cache
        # 清空utils里的全局缓存
        global _data_cache, _cache_timestamp
        _data_cache = {}
        _cache_timestamp = None
        logger.info("✅ 所有缓存已彻底清空")

        # ========== 关键4：禁用utils的自动修复（临时） ==========
        # 读取一次数据，确保缓存加载新数据（而非自动修复）
        read_csv_data()

        success_msg = f"成功恢复表：{', '.join(restored)}（共{len(restored)}个表，MD5校验一致）"
        logger.info(f"🎉 {success_msg}")
        return {
            "success": True,
            "message": success_msg,
            "restored": restored,
            "debug_info": debug_info
        }

    except Exception as e:
        error_msg = f"撤销操作失败：{str(e)}"
        logger.error(f"❌ {error_msg}", exc_info=True)
        return {
            "success": False,
            "message": error_msg,
            "restored": [],
            "debug_info": debug_info
        }