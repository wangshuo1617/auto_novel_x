"""短故事生成管线：大纲生成、逐章生成+质检。"""
from __future__ import annotations
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from workflows.short_story.agents import (
    ContentGenerationAgent,
    OutlineConceptAgent,
    ReviewAlignmentAgent,
)

SHORT_STORY_DIR_PREFIX = "short_"
MAX_RETRIES = 3


def _story_dir(output_dir: Path | str, timestamp: str | None = None) -> Path:
    ts = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path(output_dir) / f"{SHORT_STORY_DIR_PREFIX}{ts}"


def generate_outline(
    output_dir: str | Path,
    track: str,
    target_words: int,
    inspiration: str,
) -> dict[str, Any]:
    """生成短故事大纲，创建故事目录，返回 story_dir 和大纲数据。"""
    story_dir = _story_dir(output_dir)
    story_dir.mkdir(parents=True, exist_ok=True)

    print(f"[大纲策划] 轨道{track} / 目标{target_words}字 / 灵感: {inspiration[:40]}...")
    agent = OutlineConceptAgent(track=track, target_words=target_words, inspiration=inspiration)
    outline = agent.run()

    # 保存大纲
    (story_dir / "outline.json").write_text(json.dumps(outline, ensure_ascii=False, indent=2), encoding="utf-8")

    # 保存元信息
    meta = {
        "track": track,
        "target_words": target_words,
        "inspiration": inspiration,
        "title": outline.get("title", ""),
        "logline": outline.get("logline", ""),
        "total_chapters": outline.get("total_chapters", len(outline.get("chapters", []))),
        "completed_chapters": 0,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    (story_dir / "story_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✓ 大纲已生成: 《{meta['title']}》共{meta['total_chapters']}章 → {story_dir}")
    return {"story_dir": str(story_dir), "outline": outline, "meta": meta}


def generate_chapter(story_dir: str | Path, chapter_num: int) -> dict[str, Any]:
    """生成指定章节正文，经质检后保存。"""
    story_dir = Path(story_dir)
    outline = json.loads((story_dir / "outline.json").read_text(encoding="utf-8"))
    meta = json.loads((story_dir / "story_meta.json").read_text(encoding="utf-8"))
    track = meta["track"]

    chapters = outline.get("chapters", [])
    chapter_data = next((c for c in chapters if c.get("chapter_num") == chapter_num), None)
    if not chapter_data:
        raise ValueError(f"大纲中未找到第{chapter_num}章")

    chapter_outline_text = (
        f"第{chapter_data['chapter_num']}章《{chapter_data['title']}》\n"
        f"情节梗概：{chapter_data['outline']}\n"
        f"情绪爆发点/悬念钩子：{chapter_data['hook']}\n"
        f"目标字数：约{chapter_data.get('estimated_words', 3000)}字"
    )

    # 读取上一章结尾
    prev_ending = ""
    if chapter_num > 1:
        prev_path = story_dir / f"chapter_{chapter_num - 1:03d}.md"
        if prev_path.exists():
            prev_text = prev_path.read_text(encoding="utf-8")
            prev_ending = prev_text[-200:] if len(prev_text) > 200 else prev_text

    last_review: dict = {}
    content = ""
    title = chapter_data["title"]
    for attempt in range(1, MAX_RETRIES + 1):
        rewrite_hint = ""
        if last_review and not last_review.get("pass_gate"):
            rewrite_hint = f"\n上一次生成未通过质检，修改建议：{last_review.get('feedback_for_rewrite', '')}"
        outline_input = chapter_outline_text + rewrite_hint

        print(f"\n[E] 正在生成第{chapter_num}章正文...（尝试 {attempt}/{MAX_RETRIES}）")
        result = ContentGenerationAgent(
            track=track,
            chapter_outline=outline_input,
            previous_chapter_ending=prev_ending,
        ).run()
        content = result.get("content", "").strip()
        title = result.get("title", title)
        if not content:
            print("⚠ 正文为空，重试...")
            continue

        print(f"[I] 正在质检第{chapter_num}章...")
        last_review = ReviewAlignmentAgent(track=track, chapter_text=content).run()
        if last_review.get("pass_gate"):
            scores = last_review.get("metrics_scores", {})
            print(f"✓ 质检通过 节奏={scores.get('pacing')} 情感={scores.get('emotional_tension')}")
            break
        print(f"⚠ 质检未通过：{last_review.get('feedback_for_rewrite', '')[:80]}")
    else:
        print(f"⚠ 第{chapter_num}章经{MAX_RETRIES}次重试仍未通过质检，保存最后一次结果")

    # 保存正文
    chapter_path = story_dir / f"chapter_{chapter_num:03d}.md"
    chapter_path.write_text(f"# {title}\n\n{content}", encoding="utf-8")

    # 保存质检报告
    (story_dir / f"review_{chapter_num:03d}.json").write_text(
        json.dumps(last_review, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 更新进度
    meta["completed_chapters"] = max(meta.get("completed_chapters", 0), chapter_num)
    meta["updated_at"] = datetime.now().isoformat()
    (story_dir / "story_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    word_count = sum(1 for c in content if not c.isspace())
    print(f"✓ 第{chapter_num}章已保存（约{word_count}字）: {chapter_path.name}")
    return {"chapter_num": chapter_num, "title": title, "word_count": word_count, "review": last_review}


def list_short_stories(output_dir: str | Path) -> list[dict[str, Any]]:
    """列出所有短故事目录及元信息摘要。"""
    output_dir = Path(output_dir)
    if not output_dir.exists():
        return []
    stories = []
    for d in sorted(output_dir.iterdir()):
        if not d.is_dir() or not d.name.startswith(SHORT_STORY_DIR_PREFIX):
            continue
        meta_path = d / "story_meta.json"
        if not meta_path.exists():
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        stories.append({
            "path": str(d),
            "title": meta.get("title", d.name),
            "track": meta.get("track", "?"),
            "total_chapters": meta.get("total_chapters", 0),
            "completed_chapters": meta.get("completed_chapters", 0),
            "updated_at": meta.get("updated_at", ""),
        })
    return sorted(stories, key=lambda x: x["updated_at"], reverse=True)


def get_short_story_view(story_dir: str | Path) -> dict[str, Any]:
    """读取短故事的完整视图（元信息、大纲、章节列表）。"""
    d = Path(story_dir)
    meta = json.loads((d / "story_meta.json").read_text(encoding="utf-8"))
    outline = json.loads((d / "outline.json").read_text(encoding="utf-8")) if (d / "outline.json").exists() else {}
    chapters = sorted(d.glob("chapter_*.md"), key=lambda p: p.name)
    reviews = sorted(d.glob("review_*.json"), key=lambda p: p.name)
    return {
        "meta": meta,
        "outline": outline,
        "chapters": [{"path": str(c), "name": c.name} for c in chapters],
        "reviews": [{"path": str(r), "name": r.name} for r in reviews],
    }
