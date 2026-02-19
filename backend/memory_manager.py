"""记忆管理器 — VibeWorker 记忆系统的中枢。

管理长期记忆（MEMORY.md）和每日日志（memory/logs/YYYY-MM-DD.md）。
提供结构化条目管理、每日日志操作和统计功能。
"""
import hashlib
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)

# 分类定义
VALID_CATEGORIES = ["preferences", "facts", "tasks", "reflections", "general"]

CATEGORY_LABELS = {
    "preferences": "用户偏好",
    "facts": "重要事实",
    "tasks": "任务备忘",
    "reflections": "反思日志",
    "general": "通用记忆",
}

CATEGORY_HEADERS = {
    "preferences": "## 用户偏好",
    "facts": "## 重要事实",
    "tasks": "## 任务备忘",
    "reflections": "## 反思日志",
    "general": "## 通用记忆",
}


class MemoryEntry:
    """单条记忆条目。"""

    def __init__(self, content: str, category: str, timestamp: str, entry_id: str = ""):
        self.content = content
        self.category = category
        self.timestamp = timestamp
        self.entry_id = entry_id or self._generate_id(timestamp, content)

    @staticmethod
    def _generate_id(timestamp: str, content: str) -> str:
        raw = f"{timestamp}:{content}"
        return hashlib.md5(raw.encode("utf-8")).hexdigest()[:8]

    def to_dict(self) -> dict:
        return {
            "entry_id": self.entry_id,
            "content": self.content,
            "category": self.category,
            "timestamp": self.timestamp,
        }


class MemoryManager:
    """记忆管理核心类。"""

    def __init__(self):
        self.memory_dir = settings.memory_dir
        self.logs_dir = settings.memory_dir / "logs"
        self.memory_file = settings.memory_dir / "MEMORY.md"
        # 确保目录存在
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    # ============================================
    # MEMORY.md 操作
    # ============================================

    def read_memory(self) -> str:
        """读取整个 MEMORY.md 文件。"""
        if not self.memory_file.exists():
            return ""
        return self.memory_file.read_text(encoding="utf-8")

    def get_entries(self, category: Optional[str] = None) -> list[dict]:
        """解析 MEMORY.md 并返回结构化条目。

        每条记录为一行列表项：`- [YYYY-MM-DD] content` 或 `- [YYYY-MM-DD][id] content`
        """
        content = self.read_memory()
        if not content:
            return []

        entries = []
        current_category = "general"

        for line in content.split("\n"):
            stripped = line.strip()

            # 检测分类标题
            for cat, header in CATEGORY_HEADERS.items():
                if stripped.startswith(header):
                    current_category = cat
                    break

            # 解析条目行：`- [YYYY-MM-DD] content` 或 `- [YYYY-MM-DD][id] content`
            match = re.match(
                r"^-\s+\[(\d{4}-\d{2}-\d{2})\](?:\[([a-f0-9]+)\])?\s*(.+)$",
                stripped,
            )
            if match:
                timestamp = match.group(1)
                entry_id = match.group(2) or ""
                entry_content = match.group(3)

                entry = MemoryEntry(
                    content=entry_content,
                    category=current_category,
                    timestamp=timestamp,
                    entry_id=entry_id,
                )
                # 若 ID 缺失则自动生成
                if not entry.entry_id:
                    entry.entry_id = entry._generate_id(timestamp, entry_content)

                if category is None or current_category == category:
                    entries.append(entry.to_dict())

        return entries

    def add_entry(self, content: str, category: str = "general") -> dict:
        """向 MEMORY.md 对应分类下添加新条目。

        返回创建的 MemoryEntry dict。按内容相似度去重。
        """
        if category not in VALID_CATEGORIES:
            category = "general"

        today = datetime.now().strftime("%Y-%m-%d")
        entry = MemoryEntry(content=content, category=category, timestamp=today)

        # 检查重复
        existing = self.get_entries(category)
        for e in existing:
            if e["content"].strip() == content.strip():
                return e  # 已存在

        # 读取当前内容
        memory_content = self.read_memory()

        header = CATEGORY_HEADERS[category]
        new_line = f"- [{today}][{entry.entry_id}] {content}"

        if header in memory_content:
            # 找到对应分类，在占位符或最后一条之后插入
            lines = memory_content.split("\n")
            new_lines = []
            found_section = False
            inserted = False

            for i, line in enumerate(lines):
                new_lines.append(line)
                if line.strip().startswith(header):
                    found_section = True
                    continue
                if found_section and not inserted:
                    # 存在占位符时替换
                    if line.strip() == "_（暂无记录）_":
                        new_lines[-1] = new_line
                        inserted = True
                    elif not line.strip().startswith("- [") and not line.strip() == "":
                        # 已越过分类条目区域，在此行前插入
                        new_lines.insert(len(new_lines) - 1, new_line)
                        inserted = True
                    elif line.strip() == "" and i + 1 < len(lines) and lines[i + 1].strip().startswith("##"):
                        # 分类结束（空行后是下一个标题）
                        new_lines.insert(len(new_lines) - 1, new_line)
                        inserted = True

            if found_section and not inserted:
                new_lines.append(new_line)

            memory_content = "\n".join(new_lines)
        else:
            # 分类不存在，追加新分类
            memory_content = memory_content.rstrip() + f"\n\n{header}\n{new_line}\n"

        self.memory_file.write_text(memory_content, encoding="utf-8")
        logger.info(f"已添加记忆条目 [{entry.entry_id}] 到 {category}")
        return entry.to_dict()

    def delete_entry(self, entry_id: str) -> bool:
        """按 ID 删除记忆条目。"""
        content = self.read_memory()
        if not content:
            return False

        lines = content.split("\n")
        new_lines = []
        deleted = False

        for line in lines:
            # 检查行是否包含该条目 ID
            if f"[{entry_id}]" in line and line.strip().startswith("- ["):
                deleted = True
                continue
            # 同时尝试按生成 ID 匹配
            match = re.match(
                r"^-\s+\[(\d{4}-\d{2}-\d{2})\](?:\[([a-f0-9]+)\])?\s*(.+)$",
                line.strip(),
            )
            if match and not match.group(2):
                ts = match.group(1)
                cnt = match.group(3)
                gen_id = MemoryEntry._generate_id(ts, cnt)
                if gen_id == entry_id:
                    deleted = True
                    continue
            new_lines.append(line)

        if deleted:
            self.memory_file.write_text("\n".join(new_lines), encoding="utf-8")
            logger.info(f"已删除记忆条目 [{entry_id}]")

        return deleted

    # ============================================
    # 每日日志操作
    # ============================================

    def _daily_log_path(self, day: Optional[str] = None) -> Path:
        """获取每日日志文件路径。"""
        if day is None:
            day = datetime.now().strftime("%Y-%m-%d")
        return self.logs_dir / f"{day}.md"

    def append_daily_log(self, content: str, day: Optional[str] = None) -> None:
        """向今天（或指定日期）的每日日志追加内容。"""
        path = self._daily_log_path(day)
        timestamp = datetime.now().strftime("%H:%M")

        if not path.exists():
            day_str = day or datetime.now().strftime("%Y-%m-%d")
            path.write_text(
                f"# Daily Log - {day_str}\n\n", encoding="utf-8"
            )

        existing = path.read_text(encoding="utf-8")
        existing += f"- [{timestamp}] {content}\n"
        path.write_text(existing, encoding="utf-8")
        logger.info(f"已追加到每日日志: {path.name}")

    def read_daily_log(self, day: Optional[str] = None) -> str:
        """读取每日日志文件。"""
        path = self._daily_log_path(day)
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def delete_daily_log(self, day: str) -> bool:
        """删除每日日志文件。"""
        path = self._daily_log_path(day)
        if not path.exists():
            return False
        path.unlink()
        logger.info(f"已删除每日日志: {path.name}")
        return True

    def list_daily_logs(self) -> list[dict]:
        """列出所有每日日志文件及元数据。"""
        logs = []
        if not self.logs_dir.exists():
            return logs

        for f in sorted(self.logs_dir.glob("*.md"), reverse=True):
            name = f.stem  # 如 "2026-02-15"
            # 校验格式
            if not re.match(r"\d{4}-\d{2}-\d{2}", name):
                continue
            stat = f.stat()
            logs.append({
                "date": name,
                "path": f"memory/logs/{f.name}",
                "size": stat.st_size,
            })

        return logs

    def get_daily_context(self, num_days: Optional[int] = None) -> str:
        """获取近期每日日志，用于注入 System Prompt。

        返回今天 + 昨天（或可配置天数）的日志内容。
        """
        if num_days is None:
            num_days = settings.memory_daily_log_days

        parts = []
        today = datetime.now()

        for i in range(num_days):
            day = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            content = self.read_daily_log(day)
            if content:
                label = "今天" if i == 0 else f"{i}天前" if i > 1 else "昨天"
                parts.append(f"### {label} ({day})\n{content}")

        return "\n\n".join(parts)

    # ============================================
    # 统计
    # ============================================

    def get_stats(self) -> dict:
        """获取记忆统计信息。"""
        entries = self.get_entries()
        logs = self.list_daily_logs()

        # 按分类计数
        category_counts = {}
        for cat in VALID_CATEGORIES:
            category_counts[cat] = sum(1 for e in entries if e["category"] == cat)

        memory_size = self.memory_file.stat().st_size if self.memory_file.exists() else 0

        return {
            "total_entries": len(entries),
            "category_counts": category_counts,
            "daily_logs_count": len(logs),
            "memory_file_size": memory_size,
            "daily_log_days": settings.memory_daily_log_days,
            "auto_extract_enabled": settings.memory_auto_extract,
        }

    # ============================================
    # 自动提取（Phase 6）
    # ============================================

    async def auto_extract(self, messages: list[dict]) -> None:
        """从近期消息中自动提取关键信息。

        取最近 3 轮（6 条消息），使用轻量 LLM 提取偏好/事实/任务，
        以 [auto] 前缀写入每日日志。
        """
        if not settings.memory_auto_extract:
            return

        try:
            # 取最近 6 条消息
            recent = messages[-6:] if len(messages) > 6 else messages
            if not recent:
                return

            # 构建对话文本
            conversation = ""
            for msg in recent:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                if content:
                    conversation += f"{role}: {content[:500]}\n"

            if not conversation.strip():
                return

            from engine.llm_factory import create_llm
            llm = create_llm()

            prompt = f"""分析以下对话，提取值得记住的关键信息。只提取确定性的事实和偏好，不要猜测。

如果没有值得记录的信息，返回"无"。

如果有，每条一行，格式：`类别|内容`
可用类别：preferences（偏好）、facts（事实）、tasks（任务）

对话内容：
{conversation}

提取结果："""

            response = await llm.ainvoke(prompt)
            result = response.content.strip()

            if result == "无" or not result:
                return

            for line in result.split("\n"):
                line = line.strip()
                if "|" not in line:
                    continue
                parts = line.split("|", 1)
                if len(parts) != 2:
                    continue
                cat = parts[0].strip().lower()
                content = parts[1].strip()
                if not content:
                    continue

                # 以 [auto] 前缀写入每日日志
                self.append_daily_log(f"[auto] [{cat}] {content}")
                logger.info(f"自动提取: [{cat}] {content[:50]}...")

        except Exception as e:
            logger.error(f"自动提取失败: {e}")


# 单例实例
memory_manager = MemoryManager()
