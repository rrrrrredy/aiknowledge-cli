#!/usr/bin/env python3
"""
full_extract_v2.py — 全量增强提取（第二轮）
目标：
  1. 补全 70 篇无 summary/key_points 的文档
  2. 为所有 212 篇补充 tags, date（从标题/正文解析）, raw_text（截取前 1500 字）
  3. 输出更新后的 knowledge_base.json
用法：
  python3 scripts/full_extract_v2.py [--dry-run] [--only-missing] [--start N]
"""

import json
import os
import re
import sys
import time
import argparse
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR  = Path("/tmp/doc_texts")

sys.path.insert(0, str(ROOT / "scripts"))
from catclaw_llm import call_llm

# ── Prompt ────────────────────────────────────────────────────────────────────

EXTRACT_PROMPT = """你是一个专业的 AI 行业研究助手。请分析以下文章，严格按 JSON 格式输出，不要添加任何其他内容。

文章标题：{title}
文章内容：
{content}

请输出以下 JSON（全部字段必须填写，不可省略）：
{{
  "date": "从标题或正文中提取日期，格式 YYYY-MM 或 YYYY-MM-DD，无法确定则为空字符串",
  "summary": "300字以内的精准摘要，涵盖核心观点、数据和结论，使用客观陈述语气",
  "key_points": ["核心论点1（50字以内）", "核心论点2", "核心论点3", "核心论点4（可选）", "核心论点5（可选）"],
  "tags": ["关键词1", "关键词2", "关键词3", "关键词4", "关键词5"],
  "entities": [
    {{"name": "实体名称", "type": "company|product|person|concept|paper"}}
  ]
}}

要求：
- summary：客观、精准、包含核心数据点，不使用"本文"、"作者"等主观表述
- key_points：每条是独立的可检索结论，3-5条，每条含具体名称/数据
- tags：3-8个关键词，优先用英文专有名词（GPT-4o、RAG、RL等），辅以中文概念
- entities：只提取文章中实质性出现的实体，不要凑数，人名用全名
- date：优先从标题提取（如"2025年3月"→"2025-03"），其次从正文第一段

只返回 JSON，不要 markdown 代码块，不要任何解释。"""

# ── Date 解析 ─────────────────────────────────────────────────────────────────

DATE_PATTERNS = [
    (r'(\d{4})年(\d{1,2})月(\d{1,2})日', lambda m: f"{m[1]}-{int(m[2]):02d}-{int(m[3]):02d}"),
    (r'(\d{4})年(\d{1,2})月',             lambda m: f"{m[1]}-{int(m[2]):02d}"),
    (r'(\d{4})-(\d{2})-(\d{2})',          lambda m: f"{m[1]}-{m[2]}-{m[3]}"),
    (r'(\d{4})-(\d{2})',                   lambda m: f"{m[1]}-{m[2]}"),
    (r'(\d{4})\.(\d{1,2})',               lambda m: f"{m[1]}-{int(m[2]):02d}"),
]

def parse_date_from_text(text: str) -> str:
    for pattern, fmt in DATE_PATTERNS:
        m = re.search(pattern, text[:500])
        if m:
            try:
                return fmt(m)
            except Exception:
                continue
    return ""

# ── JSON 解析 ─────────────────────────────────────────────────────────────────

def extract_json(text: str) -> dict:
    """从 LLM 输出中提取 JSON，处理截断情况"""
    # 去掉 markdown 代码块
    text = re.sub(r'```(?:json)?\s*', '', text).strip().rstrip('`').strip()

    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 找到第一个 { 块
    start = text.find('{')
    if start < 0:
        return {}

    snippet = text[start:]

    # 找最后一个完整的 } 块
    depth = 0
    last_valid_end = -1
    for i, ch in enumerate(snippet):
        if ch == '{': depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                last_valid_end = i
                break

    if last_valid_end >= 0:
        try:
            return json.loads(snippet[:last_valid_end + 1])
        except Exception:
            pass

    # JSON 被截断了：尝试智能修复
    # 找到最后一个完整的字段（最后一个 "xxx": ... , 结构）
    # 策略：找最后一个逗号前的内容，尝试闭合
    try:
        # 移除末尾不完整的数组/字符串
        fixed = snippet.rstrip(',').rstrip()
        # 计算未闭合的括号
        open_brackets = fixed.count('[') - fixed.count(']')
        open_braces   = fixed.count('{') - fixed.count('}')
        # 闭合
        fixed += ']' * max(open_brackets, 0)
        fixed += '}' * max(open_braces, 0)
        return json.loads(fixed)
    except Exception:
        pass

    # 最后手段：用正则提取已知字段
    result = {}
    for field in ['date', 'summary']:
        m = re.search(rf'"{field}"\s*:\s*"((?:[^"\\]|\\.)*)"', snippet)
        if m:
            result[field] = m.group(1)
    for field in ['key_points', 'tags']:
        m = re.search(rf'"{field}"\s*:\s*\[([^\]]*)\]', snippet, re.DOTALL)
        if m:
            items = re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(1))
            result[field] = items
    return result

# ── 主逻辑 ────────────────────────────────────────────────────────────────────

def process_doc(doc: dict, raw_text: str, force: bool = False) -> dict:
    """处理单篇文档，返回更新后的 doc"""
    title = doc.get("title", "")

    # 补 raw_text（截取前 1500 字）
    if raw_text and not doc.get("raw_text"):
        doc["raw_text"] = raw_text[:1500]

    # 补 date（先从标题解析，再从正文解析）
    if not doc.get("date"):
        date = parse_date_from_text(title) or parse_date_from_text(raw_text[:500])
        if date:
            doc["date"] = date

    # 如果已有 summary + key_points + tags，且不强制重跑，跳过 LLM
    has_all = (
        doc.get("summary") and
        doc.get("key_points") and
        doc.get("tags")
    )
    if has_all and not force:
        return doc

    # 调用 LLM 提取
    content = raw_text[:4000]  # 限制输入长度
    if not content.strip():
        return doc

    prompt = EXTRACT_PROMPT.format(title=title, content=content)
    try:
        response = call_llm(prompt, max_tokens=2500, temperature=0.1)
        result = extract_json(response)
    except Exception as e:
        print(f"  ⚠️  LLM 调用失败: {e}", flush=True)
        return doc

    if not result:
        print(f"  ⚠️  JSON 解析失败，原始输出前100字: {response[:100]}", flush=True)
        return doc

    # 合并结果（只覆盖缺失或需更新的字段）
    if result.get("date") and not doc.get("date"):
        doc["date"] = result["date"]
    if result.get("summary"):
        doc["summary"] = result["summary"]
    if result.get("key_points"):
        doc["key_points"] = result["key_points"]
    if result.get("tags"):
        doc["tags"] = result["tags"]
    # entities：若原来有且数量较多，保留原版；若原来是空/少，用新版
    orig_entities = doc.get("entities", [])
    new_entities = result.get("entities", [])
    if len(new_entities) > len(orig_entities):
        # 合并去重
        existing_names = {e["name"].lower() for e in orig_entities if isinstance(e, dict)}
        for e in new_entities:
            if isinstance(e, dict) and e.get("name", "").lower() not in existing_names:
                orig_entities.append(e)
                existing_names.add(e["name"].lower())
        doc["entities"] = orig_entities

    return doc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run",      action="store_true", help="不保存，只打印")
    parser.add_argument("--only-missing", action="store_true", help="只处理无 summary 的文档")
    parser.add_argument("--force",        action="store_true", help="强制重跑所有文档的 LLM 提取")
    parser.add_argument("--start",        type=int, default=0, help="从第 N 篇开始（断点续传）")
    args = parser.parse_args()

    # 加载知识库
    kb_path = DATA_DIR / "knowledge_base.json"
    with open(kb_path) as f:
        docs = json.load(f)
    print(f"📚 加载知识库：{len(docs)} 篇文档", flush=True)

    # 筛选要处理的文档
    if args.only_missing:
        targets = [(i, d) for i, d in enumerate(docs) if not d.get("summary")]
        print(f"🎯 仅处理无 summary 的文档：{len(targets)} 篇", flush=True)
    else:
        targets = [(i, d) for i, d in enumerate(docs)]
        print(f"🎯 处理所有文档：{len(targets)} 篇", flush=True)

    if args.start > 0:
        targets = [(i, d) for i, d in targets if i >= args.start]
        print(f"⏩ 从第 {args.start} 篇开始", flush=True)

    ok = 0
    skip = 0
    fail = 0

    for idx, (doc_idx, doc) in enumerate(targets):
        doc_id = doc.get("id", "")
        title  = doc.get("title", "?")[:50]

        # 读取原文
        raw_path = RAW_DIR / f"{doc_id}.txt"
        if not raw_path.exists():
            print(f"[{idx+1}/{len(targets)}] ⏭️  {title} — 无原文文件，跳过", flush=True)
            skip += 1
            continue

        with open(raw_path) as f:
            raw = f.read()

        # 判断是否需要 LLM
        needs_llm = args.force or not (doc.get("summary") and doc.get("key_points") and doc.get("tags"))

        if not needs_llm:
            # 只补 raw_text 和 date
            updated = process_doc(doc, raw, force=False)
            if updated is not doc:
                docs[doc_idx] = updated
            print(f"[{idx+1}/{len(targets)}] ✅ {title} — 跳过LLM（已有summary）", flush=True)
            skip += 1
        else:
            print(f"[{idx+1}/{len(targets)}] 🔄 {title}", flush=True)
            updated = process_doc(doc, raw, force=args.force)
            docs[doc_idx] = updated

            if updated.get("summary"):
                print(f"  ✅ summary: {updated['summary'][:60]}...", flush=True)
                ok += 1
            else:
                print(f"  ❌ 提取失败", flush=True)
                fail += 1

            # 每处理 10 篇保存一次（断点保护）
            if not args.dry_run and (idx + 1) % 10 == 0:
                with open(kb_path, "w") as f:
                    json.dump(docs, f, ensure_ascii=False, indent=2)
                print(f"  💾 已保存（{idx+1}/{len(targets)}）", flush=True)

            time.sleep(0.5)  # 避免触发限速

    # 最终保存
    if not args.dry_run:
        with open(kb_path, "w") as f:
            json.dump(docs, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 已保存到 {kb_path}", flush=True)

    print(f"\n📊 完成：成功 {ok}，跳过 {skip}，失败 {fail}", flush=True)

    # 统计最终质量
    has_summary = sum(1 for d in docs if d.get("summary"))
    has_tags    = sum(1 for d in docs if d.get("tags"))
    has_date    = sum(1 for d in docs if d.get("date"))
    has_raw     = sum(1 for d in docs if d.get("raw_text"))
    print(f"📈 质量统计：summary={has_summary}/212，tags={has_tags}/212，date={has_date}/212，raw_text={has_raw}/212", flush=True)


if __name__ == "__main__":
    main()
