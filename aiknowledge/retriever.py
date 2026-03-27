"""
知识检索模块：基于 TF-IDF + 关键词匹配从知识库检索相关文档片段
（无需向量数据库，纯 Python，零额外依赖）
"""

import json
import math
import re
from pathlib import Path
from typing import List, Dict, Tuple

DATA_DIR = Path(__file__).parent.parent / "data"


class KnowledgeBase:
    def __init__(self):
        self.docs: List[Dict] = []
        self.idf: Dict[str, float] = {}
        self._loaded = False

    def load(self):
        kb_path = DATA_DIR / "knowledge_base.json"
        if not kb_path.exists():
            raise FileNotFoundError(
                f"知识库文件不存在: {kb_path}\n"
                "请先运行: python scripts/enhance_extract.py"
            )
        with open(kb_path) as f:
            self.docs = json.load(f)
        self._build_idf()
        self._loaded = True
        return self

    def _tokenize(self, text: str) -> List[str]:
        """简单分词：中英文混合，按字/词切割"""
        tokens = []
        # 英文词（含版本号如 GPT-4o）
        for w in re.findall(r'[a-zA-Z0-9][a-zA-Z0-9\-\.]*[a-zA-Z0-9]|[a-zA-Z0-9]', text.lower()):
            if len(w) >= 2:
                tokens.append(w)
        # 中文字符（bigram）
        chs = re.findall(r'[\u4e00-\u9fff]', text)
        for i in range(len(chs)):
            tokens.append(chs[i])
            if i + 1 < len(chs):
                tokens.append(chs[i] + chs[i+1])
        return tokens

    def _build_idf(self):
        """构建 IDF 表"""
        N = len(self.docs)
        df: Dict[str, int] = {}
        for doc in self.docs:
            text = self._doc_text(doc)
            tokens = set(self._tokenize(text))
            for t in tokens:
                df[t] = df.get(t, 0) + 1
        self.idf = {t: math.log((N + 1) / (cnt + 1)) for t, cnt in df.items()}

    def _entity_names(self, doc: Dict) -> List[str]:
        """统一处理 entities 字段（list[{name,type}] 格式）"""
        entities = doc.get("entities", [])
        if isinstance(entities, list):
            return [e.get("name", "") for e in entities if isinstance(e, dict)]
        elif isinstance(entities, dict):
            # 旧格式兼容：{type: [name, ...]}
            names = []
            for v in entities.values():
                if isinstance(v, list):
                    names.extend(v)
            return names
        return []

    def _doc_text(self, doc: Dict) -> str:
        """将文档转为可检索文本"""
        parts = [
            doc.get("title", "") * 3,  # 标题权重×3
            doc.get("summary", ""),
            " ".join(doc.get("key_points", [])),
            " ".join(self._entity_names(doc)),
        ]
        # tags 字段（增强提取后新增）
        tags = doc.get("tags", [])
        if tags:
            parts.append(" ".join(tags))
        return " ".join(parts)

    def _tfidf_score(self, query_tokens: List[str], doc: Dict) -> float:
        """计算查询与文档的 TF-IDF 相似度"""
        text = self._doc_text(doc)
        doc_tokens = self._tokenize(text)
        tf: Dict[str, int] = {}
        for t in doc_tokens:
            tf[t] = tf.get(t, 0) + 1
        total = max(len(doc_tokens), 1)

        score = 0.0
        for t in query_tokens:
            if t in tf:
                tfidf = (tf[t] / total) * self.idf.get(t, 0)
                score += tfidf
        return score

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """检索最相关的 top_k 篇文档"""
        if not self._loaded:
            self.load()
        query_tokens = self._tokenize(query)

        # 实体名精确匹配加分
        scored = []
        for doc in self.docs:
            score = self._tfidf_score(query_tokens, doc)

            # 标题命中额外加分
            title_tokens = self._tokenize(doc.get("title", ""))
            title_hits = sum(1 for t in query_tokens if t in title_tokens)
            score += title_hits * 0.8

            # 实体名精确命中加分
            entity_names_lower = [n.lower() for n in self._entity_names(doc)]
            query_lower = query.lower()
            for name in entity_names_lower:
                if name and name in query_lower:
                    score += 1.0

            if score > 0:
                scored.append((score, doc))

        scored.sort(key=lambda x: -x[0])
        return [doc for _, doc in scored[:top_k]]

    def get_stats(self) -> Dict:
        """获取知识库统计信息"""
        if not self._loaded:
            self.load()
        stats_path = DATA_DIR / "stats.json"
        if stats_path.exists():
            with open(stats_path) as f:
                base = json.load(f)
        else:
            base = {}

        # 实时计算文档类型分布
        from collections import Counter
        type_dist = Counter(d.get("type", "unknown") for d in self.docs)
        has_summary = sum(1 for d in self.docs if d.get("summary"))

        base.update({
            "total_docs": len(self.docs),
            "doc_types": dict(type_dist),
            "docs_with_summary": has_summary,
        })
        return base

    def get_all_docs(self) -> List[Dict]:
        if not self._loaded:
            self.load()
        return self.docs


# 全局单例
_kb = None

def get_kb() -> KnowledgeBase:
    global _kb
    if _kb is None:
        _kb = KnowledgeBase().load()
    return _kb
