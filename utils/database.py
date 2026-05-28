"""
数据库模块 - 使用 SQLite 存储小说世界数据

管理角色、物品、地图等数据
"""

import sqlite3
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime


class Database:
    """
    使用 SQLite 数据库存储小说世界数据
    管理角色、物品、地图等数据
    """

    def __init__(self, db_path: str):
        """
        初始化数据库
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # 使查询结果可以通过列名访问
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._init_tables()

    def _init_tables(self):
        """初始化数据库表结构"""
        cursor = self.conn.cursor()
        
        # 角色表（统一存储所有角色）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS characters (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,  -- 'protagonist', 'supporting', 'villain'
                data TEXT NOT NULL,  -- JSON 格式的完整角色数据
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 角色状态表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS character_status (
                character_id TEXT PRIMARY KEY,
                location_id TEXT,
                state TEXT DEFAULT 'active',  -- 'active', 'injured', 'dead', etc.
                stats TEXT,  -- JSON 格式的统计数据
                FOREIGN KEY (character_id) REFERENCES characters(id)
            )
        """)
        
        # 角色背包表（多对多关系）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS character_inventory (
                character_id TEXT,
                item_id TEXT,
                quantity INTEGER DEFAULT 1,
                PRIMARY KEY (character_id, item_id),
                FOREIGN KEY (character_id) REFERENCES characters(id),
                FOREIGN KEY (item_id) REFERENCES items(id)
            )
        """)
        
        # 角色关系表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS character_relations (
                character_id TEXT,
                target_id TEXT,
                relation TEXT,  -- 'ally', 'enemy', 'neutral', etc.
                trust_level INTEGER DEFAULT 50,  -- 0-100
                PRIMARY KEY (character_id, target_id),
                FOREIGN KEY (character_id) REFERENCES characters(id),
                FOREIGN KEY (target_id) REFERENCES characters(id)
            )
        """)
        
        # 地点表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS locations (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT,  -- 'Village', 'City', 'Sect', etc.
                description TEXT,
                data TEXT,  -- JSON 格式的完整地点数据
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 物品表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT,  -- 'Weapon', 'Consumable', 'Material', etc.
                rarity TEXT,
                effect_description TEXT,
                data TEXT,  -- JSON 格式的完整物品数据
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 物品放置表（物品在场景中或角色身上）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS item_placement (
                item_id TEXT PRIMARY KEY,
                placement_type TEXT,  -- 'world_object', 'inventory_item'
                location_id TEXT,
                owner_id TEXT,
                FOREIGN KEY (item_id) REFERENCES items(id),
                FOREIGN KEY (location_id) REFERENCES locations(id),
                FOREIGN KEY (owner_id) REFERENCES characters(id)
            )
        """)
        
        self.conn.commit()

    def save(self):
        """保存数据到数据库"""
        self.conn.commit()

    def _json_dumps(self, obj: Any) -> str:
        """将对象转换为 JSON 字符串"""
        return json.dumps(obj, ensure_ascii=False)

    def _json_loads(self, s: str) -> Any:
        """将 JSON 字符串转换为对象"""
        if not s:
            return {}
        return json.loads(s)

    def get_state(self) -> Dict[str, Any]:
        """
        获取当前数据库状态
        
        Returns:
            包含 protagonist, supporting_characters, villains, locations, items 的字典
        """
        cursor = self.conn.cursor()
        
        result = {
            "protagonist": {},
            "supporting_characters": [],
            "villains": [],
            "locations": [],
            "items": [],
        }
        
        # 获取主角
        cursor.execute("SELECT data FROM characters WHERE type = 'protagonist' LIMIT 1")
        row = cursor.fetchone()
        if row:
            result["protagonist"] = self._json_loads(row["data"])
            # 添加状态信息
            char_id = result["protagonist"].get("id", "")
            if char_id:
                result["protagonist"]["current_status"] = self._get_character_status(char_id)
        
        # 获取配角
        cursor.execute("SELECT data FROM characters WHERE type = 'supporting'")
        for row in cursor.fetchall():
            char_data = self._json_loads(row["data"])
            char_id = char_data.get("id", "")
            if char_id:
                char_data["current_status"] = self._get_character_status(char_id)
            result["supporting_characters"].append(char_data)
        
        # 获取反派
        cursor.execute("SELECT data FROM characters WHERE type = 'villain'")
        for row in cursor.fetchall():
            char_data = self._json_loads(row["data"])
            char_id = char_data.get("id", "")
            if char_id:
                char_data["current_status"] = self._get_character_status(char_id)
            result["villains"].append(char_data)
        
        # 获取地点
        cursor.execute("SELECT data FROM locations")
        for row in cursor.fetchall():
            result["locations"].append(self._json_loads(row["data"]))
        
        # 获取物品
        cursor.execute("SELECT data FROM items")
        for row in cursor.fetchall():
            item_data = self._json_loads(row["data"])
            item_id = item_data.get("id", "")
            if item_id:
                placement = self._get_item_placement(item_id)
                if placement:
                    item_data["placement"] = placement
            result["items"].append(item_data)
        
        return result

    def _get_character_status(self, character_id: str) -> Dict[str, Any]:
        """获取角色状态信息"""
        cursor = self.conn.cursor()
        
        # 获取状态
        cursor.execute("""
            SELECT location_id, state, stats 
            FROM character_status 
            WHERE character_id = ?
        """, (character_id,))
        row = cursor.fetchone()
        
        status = {"stats": {}}
        if row and row["location_id"]:
            status["location_id"] = row["location_id"]
        if row and row["state"]:
            status["state"] = row["state"]
        if row and row["stats"]:
            status["stats"] = self._json_loads(row["stats"])
        
        # 获取背包物品
        cursor.execute("""
            SELECT item_id FROM character_inventory 
            WHERE character_id = ?
        """, (character_id,))
        inventory_ids = [row["item_id"] for row in cursor.fetchall()]
        status["inventory_ids"] = inventory_ids
        
        return status

    def _get_item_placement(self, item_id: str) -> Dict[str, Any]:
        """获取物品当前位置或持有人。"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT placement_type, location_id, owner_id
            FROM item_placement
            WHERE item_id = ?
        """, (item_id,))
        row = cursor.fetchone()
        if not row:
            return {}
        placement = {"type": row["placement_type"] or ""}
        if row["location_id"]:
            placement["location_id"] = row["location_id"]
        if row["owner_id"]:
            placement["owner_id"] = row["owner_id"]
        return placement

    def update(self, updates: Dict[str, Any]):
        """
        更新数据库
        
        Args:
            updates: 更新数据
        """
        with self.conn:
            cursor = self.conn.cursor()
            
            # 更新主角状态
            if "protagonist" in updates:
                prot_updates = updates["protagonist"] or {}
                if not isinstance(prot_updates, dict):
                    raise ValueError("database_updates.protagonist 必须是对象")
                # 获取主角ID
                cursor.execute("SELECT id FROM characters WHERE type = 'protagonist' LIMIT 1")
                row = cursor.fetchone()
                if row:
                    self._apply_character_delta(row["id"], prot_updates, "database_updates.protagonist")
            
            # 更新其他角色状态
            if "characters_updates" in updates:
                char_updates = updates["characters_updates"] or []
                if not isinstance(char_updates, list):
                    raise ValueError("database_updates.characters_updates 必须是数组")
                for char_update in char_updates:
                    if not isinstance(char_update, dict):
                        raise ValueError("database_updates.characters_updates 的每一项都必须是对象")
                    char_id = char_update["id"]

                    self._apply_character_delta(char_id, char_update, "database_updates.characters_updates")

            # 更新物品位置或完整数据补丁
            if "items_updates" in updates:
                item_updates = updates["items_updates"] or []
                if not isinstance(item_updates, list):
                    raise ValueError("database_updates.items_updates 必须是数组")
                for item_update in item_updates:
                    if not isinstance(item_update, dict):
                        raise ValueError("database_updates.items_updates 的每一项都必须是对象")
                    self._apply_item_delta(item_update)

    def _apply_character_delta(self, character_id: str, updates: Dict[str, Any], path: str):
        if "new_status" in updates:
            self._update_character_state(character_id, updates["new_status"])

        if "new_location_id" in updates:
            self._update_character_location(character_id, updates["new_location_id"])

        if "inventory_changes" in updates:
            changes = updates["inventory_changes"] or {}
            if not isinstance(changes, dict):
                raise ValueError(f"{path}.inventory_changes 必须是对象")
            for item_id in changes.get("add", []):
                self._add_item_to_inventory(character_id, item_id)
            for item_id in changes.get("remove", []):
                self._remove_item_from_inventory(character_id, item_id)

        if "stat_changes" in updates:
            stat_changes = updates["stat_changes"] or {}
            if not isinstance(stat_changes, dict):
                raise ValueError(f"{path}.stat_changes 必须是对象")
            self._update_character_stats(character_id, stat_changes)

    def _apply_item_delta(self, item_update: Dict[str, Any]):
        item_id = item_update.get("id", "")
        if not item_id:
            raise ValueError("database_updates.items_updates 的每一项都必须包含 id")

        placement_type = item_update.get("placement_type") or None
        owner_id = item_update.get("new_owner_id") or None
        location_id = item_update.get("new_location_id") or None
        if placement_type or owner_id is not None or location_id is not None:
            self._update_item_placement(
                item_id,
                placement_type=placement_type,
                owner_id=owner_id,
                location_id=location_id,
            )

        data_updates = item_update.get("data_updates")
        if data_updates is not None:
            if not isinstance(data_updates, dict):
                raise ValueError("database_updates.items_updates.data_updates 必须是对象")
            self._update_item_data(item_id, data_updates)

    def _update_character_location(self, character_id: str, location_id: str):
        """更新角色位置"""
        cursor = self.conn.cursor()
        
        # 检查记录是否存在
        cursor.execute("SELECT state, stats FROM character_status WHERE character_id = ?", (character_id,))
        row = cursor.fetchone()
        
        if row:
            # 更新现有记录
            state = row["state"] or "active"
            stats = row["stats"] or "{}"
            cursor.execute("""
                UPDATE character_status 
                SET location_id = ?, state = ?, stats = ?
                WHERE character_id = ?
            """, (location_id, state, stats, character_id))
        else:
            # 创建新记录
            cursor.execute("""
                INSERT INTO character_status (character_id, location_id, state, stats)
                VALUES (?, ?, 'active', '{}')
            """, (character_id, location_id))

    def _update_character_state(self, character_id: str, state: str):
        """更新角色状态（如 alive, dead, injured）"""
        cursor = self.conn.cursor()
        
        # 检查记录是否存在
        cursor.execute("SELECT location_id, stats FROM character_status WHERE character_id = ?", (character_id,))
        row = cursor.fetchone()
        
        if row:
            # 更新现有记录
            location_id = row["location_id"]
            stats = row["stats"] or "{}"
            cursor.execute("""
                UPDATE character_status 
                SET state = ?, stats = ?
                WHERE character_id = ?
            """, (state, stats, character_id))
        else:
            # 创建新记录
            cursor.execute("""
                INSERT INTO character_status (character_id, state, stats)
                VALUES (?, ?, '{}')
            """, (character_id, state))

    def _update_character_stats(self, character_id: str, stats: Dict[str, Any]):
        """更新角色属性"""
        cursor = self.conn.cursor()
        
        # 获取现有stats
        cursor.execute("SELECT location_id, state, stats FROM character_status WHERE character_id = ?", (character_id,))
        row = cursor.fetchone()
        existing_stats = {}
        location_id = None
        state = "active"
        
        if row:
            if row["stats"]:
                existing_stats = self._json_loads(row["stats"])
            location_id = row["location_id"]
            state = row["state"] or "active"
        
        # 合并更新
        existing_stats.update(stats)
        
        if row:
            # 更新现有记录
            cursor.execute("""
                UPDATE character_status 
                SET stats = ?
                WHERE character_id = ?
            """, (self._json_dumps(existing_stats), character_id))
        else:
            # 创建新记录
            cursor.execute("""
                INSERT INTO character_status (character_id, location_id, state, stats)
                VALUES (?, ?, ?, ?)
            """, (character_id, location_id, state, self._json_dumps(existing_stats)))

    def _add_item_to_inventory(self, character_id: str, item_id: str):
        """添加物品到角色背包"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO character_inventory (character_id, item_id, quantity)
            VALUES (?, ?, COALESCE((SELECT quantity FROM character_inventory WHERE character_id = ? AND item_id = ?), 0) + 1)
        """, (character_id, item_id, character_id, item_id))
        cursor.execute("""
            INSERT OR REPLACE INTO item_placement (item_id, placement_type, location_id, owner_id)
            VALUES (?, 'inventory_item', NULL, ?)
        """, (item_id, character_id))

    def _remove_item_from_inventory(self, character_id: str, item_id: str):
        """从角色背包移除物品"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM character_inventory WHERE character_id = ? AND item_id = ?", (character_id, item_id))
        cursor.execute("DELETE FROM item_placement WHERE item_id = ? AND owner_id = ?", (item_id, character_id))

    def _update_item_placement(
        self,
        item_id: str,
        *,
        placement_type: str | None = None,
        owner_id: str | None = None,
        location_id: str | None = None,
    ):
        """更新物品位置或持有人。"""
        cursor = self.conn.cursor()
        resolved_type = placement_type or ("inventory_item" if owner_id else "world_object")
        cursor.execute("DELETE FROM character_inventory WHERE item_id = ?", (item_id,))
        cursor.execute("""
            INSERT OR REPLACE INTO item_placement (item_id, placement_type, location_id, owner_id)
            VALUES (?, ?, ?, ?)
        """, (item_id, resolved_type, location_id, owner_id))
        if owner_id:
            cursor.execute("""
                INSERT OR IGNORE INTO character_inventory (character_id, item_id, quantity)
                VALUES (?, ?, 1)
            """, (owner_id, item_id))

    def _update_item_data(self, item_id: str, data_updates: Dict[str, Any]):
        """合并更新物品完整 JSON 数据。"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT data FROM items WHERE id = ?", (item_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"物品不存在，无法更新: {item_id}")
        data = self._json_loads(row["data"])
        data.update(data_updates)
        cursor.execute("""
            UPDATE items
            SET data = ?
            WHERE id = ?
        """, (self._json_dumps(data), item_id))

    def merge_element_data(self, element_data: Dict[str, Any]):
        """事务性合并元素设计师生成的数据。"""
        with self.conn:
            self._merge_element_data_uncommitted(element_data)

    def _merge_element_data_uncommitted(self, element_data: Dict[str, Any]):
        """
        合并元素设计师生成的数据
        
        Args:
            element_data: 包含 protagonist, supporting_characters, villains, locations, items 的字典
        """
        cursor = self.conn.cursor()
        pending_statuses: list[tuple[str, Dict[str, Any]]] = []
        
        # 合并主角
        if "protagonist" in element_data:
            prot = element_data["protagonist"]
            char_id = prot.get("id", "")
            if char_id:
                cursor.execute("""
                    INSERT INTO characters (id, name, type, data, updated_at)
                    VALUES (?, ?, 'protagonist', ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        type = excluded.type,
                        data = excluded.data,
                        updated_at = CURRENT_TIMESTAMP
                """, (char_id, prot.get("name", ""), self._json_dumps(prot)))
                
                # 更新状态
                if "current_status" in prot:
                    pending_statuses.append((char_id, prot["current_status"]))
        
        # 合并配角
        if "supporting_characters" in element_data:
            for char in element_data["supporting_characters"]:
                char_id = char.get("id", "")
                if char_id:
                    cursor.execute("""
                        INSERT INTO characters (id, name, type, data, updated_at)
                        VALUES (?, ?, 'supporting', ?, CURRENT_TIMESTAMP)
                        ON CONFLICT(id) DO UPDATE SET
                            name = excluded.name,
                            type = excluded.type,
                            data = excluded.data,
                            updated_at = CURRENT_TIMESTAMP
                    """, (char_id, char.get("name", ""), self._json_dumps(char)))
                    
                    if "current_status" in char:
                        pending_statuses.append((char_id, char["current_status"]))
        
        # 合并反派
        if "villains" in element_data:
            for char in element_data["villains"]:
                char_id = char.get("id", "")
                if char_id:
                    cursor.execute("""
                        INSERT INTO characters (id, name, type, data, updated_at)
                        VALUES (?, ?, 'villain', ?, CURRENT_TIMESTAMP)
                        ON CONFLICT(id) DO UPDATE SET
                            name = excluded.name,
                            type = excluded.type,
                            data = excluded.data,
                            updated_at = CURRENT_TIMESTAMP
                    """, (char_id, char.get("name", ""), self._json_dumps(char)))
                    
                    if "current_status" in char:
                        pending_statuses.append((char_id, char["current_status"]))
        
        # 合并地点
        if "locations" in element_data:
            for loc in element_data["locations"]:
                loc_id = loc.get("id", "")
                if loc_id:
                    cursor.execute("""
                        INSERT INTO locations (id, name, type, description, data)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                            name = excluded.name,
                            type = excluded.type,
                            description = excluded.description,
                            data = excluded.data
                    """, (
                        loc_id,
                        loc.get("name", ""),
                        loc.get("type", ""),
                        loc.get("description", ""),
                        self._json_dumps(loc)
                    ))
        
        # 合并物品
        if "items" in element_data:
            for item in element_data["items"]:
                item_id = item.get("id", "")
                if item_id:
                    cursor.execute("""
                        INSERT INTO items (id, name, type, rarity, effect_description, data)
                        VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                            name = excluded.name,
                            type = excluded.type,
                            rarity = excluded.rarity,
                            effect_description = excluded.effect_description,
                            data = excluded.data
                    """, (
                        item_id,
                        item.get("name", ""),
                        item.get("type", ""),
                        item.get("rarity", ""),
                        item.get("effect_description", ""),
                        self._json_dumps(item)
                    ))
                    
                    # 处理物品放置
                    if "placement" in item:
                        placement = item["placement"]
                        self._update_item_placement(
                            item_id,
                            placement_type=placement.get("type"),
                            location_id=placement.get("location_id"),
                            owner_id=placement.get("owner_id"),
                        )

        for char_id, status in pending_statuses:
            self._update_character_from_status(char_id, status)

    def _update_character_from_status(self, character_id: str, status: Dict[str, Any]):
        """从状态字典更新角色状态"""
        cursor = self.conn.cursor()
        
        location_id = status.get("location_id")
        state = status.get("state", "active")
        stats = status.get("stats", {})
        inventory_ids = status.get("inventory_ids", [])
        
        # 更新状态表
        cursor.execute("""
            INSERT OR REPLACE INTO character_status (character_id, location_id, state, stats)
            VALUES (?, ?, ?, ?)
        """, (character_id, location_id, state, self._json_dumps(stats)))
        
        # 更新背包
        cursor.execute("DELETE FROM character_inventory WHERE character_id = ?", (character_id,))
        for item_id in inventory_ids:
            cursor.execute("""
                INSERT INTO character_inventory (character_id, item_id, quantity)
                VALUES (?, ?, 1)
            """, (character_id, item_id))
        
        # 更新关系
        if "social_relations" in status:
            cursor.execute("DELETE FROM character_relations WHERE character_id = ?", (character_id,))
            for rel in status["social_relations"]:
                cursor.execute("""
                    INSERT INTO character_relations (character_id, target_id, relation, trust_level)
                    VALUES (?, ?, ?, ?)
                """, (
                    character_id,
                    rel.get("target_id", ""),
                    rel.get("relation", ""),
                    rel.get("trust_level", 50)
                ))

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()

    def clear_all(self, drop_file: bool = False) -> Dict[str, Any]:
        """
        清空数据库中的所有信息。

        Args:
            drop_file: 如果为 True，则会关闭连接、删除数据库文件并重新创建空数据库；
                       否则仅删除所有表中的数据并执行 VACUUM。

        Returns:
            一个字典，包含被清空的表名以及操作结果。
        """
        results: Dict[str, Any] = {}

        # 如果用户希望删除文件，则需要先关闭连接
        if drop_file:
            try:
                self.close()
            except Exception:
                pass

            try:
                if self.db_path.exists():
                    self.db_path.unlink()
                # 重新创建空数据库文件并初始化表
                self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
                self.conn.row_factory = sqlite3.Row
                self._init_tables()
                results["dropped_file"] = True
            except Exception as e:
                results["dropped_file"] = False
                results["error"] = str(e)

            return results

        tables = [
            "character_inventory",
            "character_relations",
            "character_status",
            "item_placement",
            "items",
            "locations",
            "characters",
        ]

        try:
            with self.conn:
                cursor = self.conn.cursor()
                for t in tables:
                    cursor.execute(f"DELETE FROM {t}")
                    results[t] = "cleared"
        except Exception as e:
            results["error"] = str(e)
            raise RuntimeError(f"清空数据库失败，已回滚: {e}") from e

        try:
            self.conn.execute("VACUUM")
            results["vacuum"] = "ok"
        except Exception as e:
            results["vacuum"] = f"error: {e}"

        return results

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()


# 模块级缓存：为每本书维护一个 Database 实例，避免不同模块无意间使用同一个文件或创建多个连接
_DB_INSTANCES = {}


def get_database_for_book(book_dir: str | Path) -> Database:
    """
    返回指定书籍目录对应的 Database 实例（单例/缓存）。

    Args:
        book_dir: 书籍目录路径或字符串

    Returns:
        Database 实例（对应 book_dir/database.db）
    """
    book_path = Path(book_dir)
    db_path = str((book_path / "database.db").resolve())
    inst = _DB_INSTANCES.get(db_path)
    if inst:
        return inst

    inst = Database(db_path)
    _DB_INSTANCES[db_path] = inst
    return inst


def close_database_for_book(book_dir: str | Path) -> bool:
    """
    关闭并移除缓存中指定书籍的 Database 实例（如果存在）。

    Returns True if an instance was closed/removed.
    """
    book_path = Path(book_dir)
    db_path = str((book_path / "database.db").resolve())
    inst = _DB_INSTANCES.pop(db_path, None)
    if inst:
        try:
            inst.close()
        except Exception:
            pass
        return True
    return False