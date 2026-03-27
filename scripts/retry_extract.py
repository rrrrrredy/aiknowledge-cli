#!/usr/bin/env python3
"""
补跑脚本：对实体数量 <= 10 的文档，用更严格的 prompt 重新提取
"""
import json
import os
import re
import sys
import time

# 确保能 import catclaw_llm
sys.path.insert(0, os.path.dirname(__file__))
from catclaw_llm import call_llm

DOC_DIR = "/tmp/doc_texts"
KB_PATH = "data/knowledge_base.json"
NODES_PATH = "data/nodes.json"
EDGES_PATH = "data/edges.json"
STATS_PATH = "data/stats.json"
LOG_PATH = "/tmp/retry_extract.log"

ENTITY_TYPES = ["company", "product", "person", "concept", "paper"]

EXTRACT_PROMPT = """从以下AI/ML领域文章中提取实体和关系，严格按JSON格式输出，不要有任何其他文字。

文章内容：
{text}

输出格式（纯JSON）：
{{
  "entities": [
    {{"name": "实体名称", "type": "company|product|person|concept|paper"}}
  ],
  "relations": [
    {{"source": "实体A", "relation": "关系类型", "target": "实体B"}}
  ]
}}

关系类型：made_by, works_at, competes_with, researches, focuses_on, enhances, enables, uses, is_variant_of, is_method_of, powered_by, extends, improves, part_of, is_type_of, related_to, same_as, describes, technique_of

要求：
1. 实体名称标准化（如 GPT-4, Claude 3, Gemini Pro）
2. 只提取AI/ML领域相关实体
3. 提取20-50个实体
4. 输出必须是合法 JSON，不能有注释或多余文字"""


def extract_json(text: str) -> dict:
    """从 LLM 输出中提取 JSON"""
    # 去掉 markdown code fence
    text = re.sub(r'```(?:json)?\s*', '', text).strip()
    text = text.rstrip('`').strip()
    
    # 找最大的 {} 块
    m = re.search(r'\{[\s\S]*\}', text)
    if m:
        try:
            return json.loads(m.group())
        except:
            pass
    return json.loads(text)


def main():
    with open(KB_PATH) as f:
        kb = json.load(f)

    to_retry = [d for d in kb if len(d.get("entities", [])) <= 10]
    print(f"需要补跑: {len(to_retry)} 篇（实体数 <=10）")

    log = open(LOG_PATH, "w")
    improved = 0

    for i, doc in enumerate(to_retry):
        doc_id = doc["id"]
        txt_path = os.path.join(DOC_DIR, f"{doc_id}.txt")

        if not os.path.exists(txt_path):
            msg = f"[{i+1}/{len(to_retry)}] {doc_id}: 无文档文件，跳过"
            print(msg); log.write(msg + "\n"); log.flush()
            continue

        with open(txt_path, encoding="utf-8", errors="ignore") as f:
            text = f.read()[:3500]

        print(f"[{i+1}/{len(to_retry)}] 处理 {doc_id}... ", end="", flush=True)
        log.write(f"[{i+1}/{len(to_retry)}] 处理 {doc_id}... ")

        try:
            response = call_llm(EXTRACT_PROMPT.format(text=text), max_tokens=2000)
            result = extract_json(response)
            entities = result.get("entities", [])
            relations = result.get("relations", [])

            old_count = len(doc.get("entities", []))
            doc["entities"] = entities
            doc["relations"] = relations
            doc["entities_count"] = len(entities)

            msg = f"OK (实体:{len(entities)}, 关系:{len(relations)}) [之前:{old_count}]"
            if len(entities) > old_count:
                improved += 1
        except Exception as e:
            msg = f"  FAILED: {e}"

        print(msg); log.write(msg + "\n"); log.flush()
        time.sleep(1.0)

    log.close()

    # 写回 KB
    with open(KB_PATH, "w") as f:
        json.dump(kb, f, ensure_ascii=False)
    print(f"\n✅ 补跑完成，改善 {improved}/{len(to_retry)} 篇")

    # 重建 nodes/edges
    rebuild_graph(kb)


def rebuild_graph(kb):
    node_map = {}
    edge_list = []
    node_counter = [0]

    def get_or_create_node(name, ntype):
        key = name.lower().strip()
        if key not in node_map:
            node_map[key] = {
                "id": str(node_counter[0]),
                "name": name,
                "type": ntype,
                "count": 0,
                "doc_ids": []
            }
            node_counter[0] += 1
        return node_map[key]

    for doc in kb:
        doc_id = doc["id"]
        entities = doc.get("entities", [])
        relations = doc.get("relations", [])

        for ent in entities:
            name = ent.get("name", "").strip()
            ntype = ent.get("type", "concept")
            if not name or ntype not in ENTITY_TYPES:
                continue
            node = get_or_create_node(name, ntype)
            node["count"] += 1
            if doc_id not in node["doc_ids"]:
                node["doc_ids"].append(doc_id)

        name_to_id = {}
        for ent in entities:
            name = ent.get("name", "").strip()
            if name:
                key = name.lower().strip()
                if key in node_map:
                    name_to_id[name.lower()] = node_map[key]["id"]

        for rel in relations[:10]:
            src = rel.get("source", "").strip()
            tgt = rel.get("target", "").strip()
            rtype = rel.get("relation", "related_to")
            if not src or not tgt:
                continue
            src_id = name_to_id.get(src.lower())
            tgt_id = name_to_id.get(tgt.lower())
            if src_id and tgt_id and src_id != tgt_id:
                edge_list.append({
                    "source": src_id,
                    "target": tgt_id,
                    "type": rtype,
                    "doc_id": doc_id
                })

    nodes = list(node_map.values())

    with open(NODES_PATH, "w") as f:
        json.dump(nodes, f, ensure_ascii=False)
    with open(EDGES_PATH, "w") as f:
        json.dump(edge_list, f, ensure_ascii=False)

    stats = {
        "total_docs": len(kb),
        "total_nodes": len(nodes),
        "total_edges": len(edge_list),
        "doc_types": {},
        "entity_types": {}
    }
    for d in kb:
        t = d.get("type", "unknown")
        stats["doc_types"][t] = stats["doc_types"].get(t, 0) + 1
    for n in nodes:
        t = n["type"]
        stats["entity_types"][t] = stats["entity_types"].get(t, 0) + 1

    with open(STATS_PATH, "w") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print(f"✅ 节点写入: {NODES_PATH} ({len(nodes)} 个)")
    print(f"✅ 关系写入: {EDGES_PATH} ({len(edge_list)} 条)")
    print(f"📊 统计: {json.dumps(stats, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
