#!/usr/bin/env python3
"""
增强提取脚本：从原始文档文本中提取结构化知识
- 每篇文档提取：标题/日期/类型/摘要/核心论点/关键实体
- 输出 knowledge_base.json（问答用）和更新的 nodes/edges（图谱用）
"""

import os
import json
import re
import sys
import time
from pathlib import Path

# 添加脚本目录到路径
sys.path.insert(0, str(Path(__file__).parent))
from catclaw_llm import call_llm

# ── 配置 ──────────────────────────────────────────────────────────────────────
DOC_DIRS = [
    "/tmp/doc_texts",      # 原有 203 篇
    "/tmp/doc_texts_new",  # 新增文档
]
OUTPUT_DIR = Path(__file__).parent.parent / "data"
OUTPUT_DIR.mkdir(exist_ok=True)

# 文档类型映射（根据标题关键词判断）
def infer_doc_type(title: str) -> str:
    title_lower = title.lower()
    if any(k in title for k in ["周报", "周刊", "一周"]):
        return "weekly_report"
    if any(k in title for k in ["论文", "paper", "研究"]):
        return "paper_digest"
    if any(k in title for k in ["月度", "月报"]):
        return "monthly_report"
    if any(k in title for k in ["龙虾", "Skill", "OpenClaw", "Agent"]):
        return "agent_methodology"
    if any(k in title for k in ["学习资源", "资源", "推荐"]):
        return "learning_resources"
    return "topic_research"

# 节点类型（与图谱一致）
NODE_TYPES = {
    "company": "公司/院校",
    "product": "产品",
    "person": "人物",
    "concept": "技术概念",
    "paper": "论文",
    "resource": "资源",
}

EXTRACT_PROMPT = """你是一个 AI 知识库结构化提取助手。请分析以下文档，提取结构化信息。

要求：
1. 摘要：150-300字，精准概括文档核心内容，不废话
2. 核心论点：3-5条，每条一句话，提炼文档中最有价值的洞察
3. 关键实体：提取所有明确提及的实体，按类型分类
   - company: 公司名、机构名、大学名（如 OpenAI、Meta、清华大学）
   - product: 产品名、模型名、工具名（如 GPT-4、Claude、Cursor）
   - person: 人名（如 Sam Altman、Yann LeCun）
   - concept: 技术概念、方法论（如 RAG、Agent、RLHF）
   - paper: 论文名称（如 Attention Is All You Need）
4. 实体关系：从文档中提取实体间的明确关系（最多10条）
   - 关系类型：made_by/develops（制造/开发）、competes_with（竞争）、researches（研究）、 
     focuses_on（专注于）、founded_by（由...创立）、acquired_by（被收购）、cooperates_with（合作）

文档标题：{title}
文档内容（前3000字）：
{content}

请输出 JSON 格式（不要有其他文字）：
{{
  "summary": "...",
  "key_points": ["...", "...", "..."],
  "entities": {{
    "company": ["...", "..."],
    "product": ["...", "..."],
    "person": ["...", "..."],
    "concept": ["...", "..."],
    "paper": []
  }},
  "relations": [
    {{"source": "实体A", "target": "实体B", "type": "关系类型", "source_type": "product", "target_type": "company"}}
  ]
}}"""


def extract_title_from_content(content: str) -> str:
    """从文档内容中提取标题"""
    m = re.search(r'《([^》]+)》', content[:200])
    if m:
        return m.group(1)
    m = re.search(r':::title\n(.+)', content[:500])
    if m:
        return m.group(1).strip()
    m = re.search(r'#\s+(.+)', content[:500])
    if m:
        return m.group(1).strip()
    return "未知标题"


def extract_date_from_content(content: str) -> str:
    """从文档内容中提取日期"""
    patterns = [
        r'(\d{4})[年\-/](\d{1,2})[月\-/](\d{1,2})',
        r'(\d{4})年(\d{1,2})月',
    ]
    for p in patterns:
        m = re.search(p, content[:1000])
        if m:
            groups = m.groups()
            if len(groups) >= 2:
                return f"{groups[0]}-{groups[1].zfill(2)}{('-' + groups[2].zfill(2)) if len(groups) > 2 else ''}"
    return ""


def clean_content(content: str) -> str:
    """清理文档内容，去除 KM 格式噪音"""
    # 去除 JSON 结构（表格数据）
    content = re.sub(r'\{["\w]+:[^{}]{0,200}\}', '', content)
    # 去除图片链接
    content = re.sub(r'!\[.*?\]\(https?://[^\)]+\)', '', content)
    # 去除 KM 特殊标记
    content = re.sub(r':::\w+[\{[^\]]*\]?', '', content)
    content = re.sub(r':::', '', content)
    content = re.sub(r':\[link\][^\[]*\[/link\]', '', content)
    # 去除多余空行
    content = re.sub(r'\n{3,}', '\n\n', content)
    return content.strip()


def extract_with_llm(title: str, content: str) -> dict:
    """调用 LLM 提取结构化信息（使用 CatClaw 接口）"""
    clean = clean_content(content)[:3000]
    prompt = EXTRACT_PROMPT.format(title=title, content=clean)
    
    try:
        text = call_llm(prompt, max_tokens=2000, temperature=0.1)
        # 提取 JSON 部分
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except Exception as e:
        print(f"  LLM error: {e}", file=sys.stderr)
    
    return {
        "summary": "",
        "key_points": [],
        "entities": {"company": [], "product": [], "person": [], "concept": [], "paper": []},
        "relations": [],
    }


def process_all_docs():
    """处理所有文档"""
    # 收集所有文档
    doc_files = []
    for doc_dir in DOC_DIRS:
        p = Path(doc_dir)
        if p.exists():
            doc_files.extend(p.glob("*.txt"))
    
    print(f"找到 {len(doc_files)} 个文档文件")
    
    knowledge_base = []
    all_entities = {}   # name -> {type, count, doc_ids}
    all_relations = []  # [{source, target, type, ...}]
    
    for i, doc_file in enumerate(sorted(doc_files)):
        doc_id = doc_file.stem
        print(f"[{i+1}/{len(doc_files)}] 处理 {doc_id}...", end=" ", flush=True)
        
        try:
            content = doc_file.read_text(errors='replace')
        except Exception as e:
            print(f"读取失败: {e}")
            continue
        
        title = extract_title_from_content(content)
        date  = extract_date_from_content(content)
        doc_type = infer_doc_type(title)
        
        # 调用 LLM 提取
        extracted = extract_with_llm(title, content)
        
        doc_record = {
            "id": doc_id,
            "title": title,
            "date": date,
            "type": doc_type,
            "summary": extracted.get("summary", ""),
            "key_points": extracted.get("key_points", []),
            "entities": extracted.get("entities", {}),
            "km_url": f"https://km.sankuai.com/collabpage/{doc_id}" if doc_id.isdigit() else "",
        }
        knowledge_base.append(doc_record)
        
        # 汇总实体
        for etype, names in extracted.get("entities", {}).items():
            for name in names:
                name = name.strip()
                if not name or len(name) < 2:
                    continue
                key = f"{etype}::{name}"
                if key not in all_entities:
                    all_entities[key] = {"name": name, "type": etype, "count": 0, "doc_ids": []}
                all_entities[key]["count"] += 1
                all_entities[key]["doc_ids"].append(doc_id)
        
        # 汇总关系
        for rel in extracted.get("relations", []):
            rel["doc_id"] = doc_id
            all_relations.append(rel)
        
        print(f"OK (实体:{sum(len(v) for v in extracted.get('entities',{}).values())}, 关系:{len(extracted.get('relations',[]))})")
        time.sleep(0.3)  # rate limit
    
    # ── 生成知识库 JSON ───────────────────────────────────────────────────────
    kb_path = OUTPUT_DIR / "knowledge_base.json"
    with open(kb_path, "w") as f:
        json.dump(knowledge_base, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 知识库写入: {kb_path} ({len(knowledge_base)} 篇)")
    
    # ── 生成图谱 nodes ────────────────────────────────────────────────────────
    nodes = []
    entity_id_map = {}  # key -> node_id
    for idx, (key, ent) in enumerate(sorted(all_entities.items(), key=lambda x: -x[1]["count"])):
        node = {
            "id": str(idx),
            "name": ent["name"],
            "type": ent["type"],
            "count": ent["count"],
            "doc_ids": ent["doc_ids"][:10],  # 最多保留10个来源
        }
        nodes.append(node)
        entity_id_map[key] = str(idx)
        entity_id_map[ent["name"]] = str(idx)  # 也按名称索引
    
    nodes_path = OUTPUT_DIR / "nodes.json"
    with open(nodes_path, "w") as f:
        json.dump(nodes, f, ensure_ascii=False, indent=2)
    print(f"✅ 节点写入: {nodes_path} ({len(nodes)} 个节点)")
    
    # ── 生成图谱 edges ────────────────────────────────────────────────────────
    seen_edges = set()
    edges = []
    for rel in all_relations:
        src_name = rel.get("source", "").strip()
        tgt_name = rel.get("target", "").strip()
        rel_type = rel.get("type", "relates_to")
        
        src_id = entity_id_map.get(src_name)
        tgt_id = entity_id_map.get(tgt_name)
        if not src_id or not tgt_id or src_id == tgt_id:
            continue
        
        edge_key = f"{min(src_id,tgt_id)}-{max(src_id,tgt_id)}-{rel_type}"
        if edge_key in seen_edges:
            continue
        seen_edges.add(edge_key)
        
        edges.append({
            "source": src_id,
            "target": tgt_id,
            "type": rel_type,
            "doc_id": rel.get("doc_id", ""),
        })
    
    edges_path = OUTPUT_DIR / "edges.json"
    with open(edges_path, "w") as f:
        json.dump(edges, f, ensure_ascii=False, indent=2)
    print(f"✅ 关系写入: {edges_path} ({len(edges)} 条关系)")
    
    # ── 生成摘要统计 ──────────────────────────────────────────────────────────
    stats = {
        "total_docs": len(knowledge_base),
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "doc_types": {},
        "entity_types": {},
    }
    for doc in knowledge_base:
        stats["doc_types"][doc["type"]] = stats["doc_types"].get(doc["type"], 0) + 1
    for ent in nodes:
        stats["entity_types"][ent["type"]] = stats["entity_types"].get(ent["type"], 0) + 1
    
    stats_path = OUTPUT_DIR / "stats.json"
    with open(stats_path, "w") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"✅ 统计写入: {stats_path}")
    print(f"\n📊 统计：{stats}")


if __name__ == "__main__":
    process_all_docs()
