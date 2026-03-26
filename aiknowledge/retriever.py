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
        # 英文按空格切，中文按字切，保留数字
        tokens = []
        # 英文词
        for w in re.findall(r'[a-zA-Z0-9\-\.]+', text.lower()):
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

    def _doc_text(self, doc: Dict) -> str:
        """将文档转为可检索文本"""
        parts = [
            doc.get("title", ""),
            doc.get("summary", ""),
            " ".join(doc.get("key_points", [])),
        ]
        for entities in doc.get("entities", {}).values():
            parts.extend(entities)
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
        
        # 计算分数
        scored = []
        for doc in self.docs:
            score = self._tfidf_score(query_tokens, doc)
            # 标题命中额外加分
            title_tokens = self._tokenize(doc.get("title", ""))
            title_hits = sum(1 for t in query_tokens if t in title_tokens)
            score += title_hits * 0.5
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
                return json.load(f)
        return {"total_docs": len(self.docs)}

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
