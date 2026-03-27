#!/usr/bin/env python3
"""
导出公开版知识库（去掉 raw_text，只保留元数据）
输入：data/knowledge_base_rebuilt.json
输出：data/knowledge_base_public.json
"""

import json
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent.parent
INPUT = BASE_DIR / "data" / "knowledge_base_rebuilt.json"
OUTPUT = BASE_DIR / "data" / "knowledge_base_public.json"

KEEP_FIELDS = {"id", "title", "summary", "key_points", "tags", "entities", "km_url", "doc_key"}

def export():
    with open(INPUT, encoding="utf-8") as f:
        data = json.load(f)

    public = []
    for doc in data:
        entry = {k: v for k, v in doc.items() if k in KEEP_FIELDS}
        # 确保必要字段存在
        entry.setdefault("summary", "")
        entry.setdefault("key_points", [])
        entry.setdefault("tags", [])
        entry.setdefault("entities", [])
        public.append(entry)

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(public, f, ensure_ascii=False, indent=2)

    raw_size = INPUT.stat().st_size / 1024
    pub_size = OUTPUT.stat().st_size / 1024
    print(f"✅ 导出完成")
    print(f"   输入: {len(data)} 篇，{raw_size:.0f} KB（含 raw_text）")
    print(f"   输出: {len(public)} 篇，{pub_size:.0f} KB（仅元数据）")
    print(f"   压缩率: {pub_size/raw_size*100:.0f}%")
    print(f"   文件: {OUTPUT}")

if __name__ == "__main__":
    export()
