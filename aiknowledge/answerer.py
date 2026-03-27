"""
回答生成模块：基于检索结果调用 LLM 生成精准回答
风格：冷静、精准，有来源有引用，不猜不编
优先使用 CatClaw 内置 LLM，fallback 到 OpenAI 兼容接口
"""

import os
import sys
import json
from pathlib import Path
from typing import List, Dict, Optional

# 尝试使用 CatClaw LLM
_catclaw_available = False
try:
    scripts_dir = Path(__file__).parent.parent / "scripts"
    sys.path.insert(0, str(scripts_dir))
    from catclaw_llm import call_llm as catclaw_call
    _catclaw_available = True
except Exception:
    pass

# fallback: openai
try:
    from openai import OpenAI
    _has_openai = True
except ImportError:
    _has_openai = False

SYSTEM_PROMPT = """你是一个基于知识库的 AI 问答助手。风格：冷静、精准、有据可查。

核心原则：
1. 只使用提供的知识库片段回答，不凭空推断
2. 每个关键论断指明来源文档
3. 知识库中没有的信息，明确说"知识库中暂无相关记录"
4. 不用客套话，直接给出答案
5. 如有多个不同观点，分别列出各自来源

回答格式：直接回答（2-4句）→ 要点细节（如需要）→ 参考来源"""

ANSWER_PROMPT = """基于以下知识库内容，回答用户的问题。

【知识库相关内容】
{context}

【用户问题】
{question}

请根据知识库内容精准回答。知识库内容不足时明确说明。"""


def format_context(docs: List[Dict]) -> str:
    """将检索到的文档格式化为 context"""
    parts = []
    for i, doc in enumerate(docs):
        part = f"[文档{i+1}] {doc.get('title', '未知')}"
        if doc.get('date'):
            part += f"（{doc['date']}）"
        part += f"\n摘要：{doc.get('summary', '无摘要')}"
        if doc.get('key_points'):
            part += "\n核心论点：\n" + "\n".join(f"  • {p}" for p in doc['key_points'])
        parts.append(part)
    return "\n\n".join(parts)


def answer_with_llm(question: str, docs: List[Dict]) -> str:
    """使用 LLM 生成回答"""
    context = format_context(docs)
    full_prompt = ANSWER_PROMPT.format(context=context, question=question)

    answer = None

    # 优先 CatClaw（无需 API key，使用内置 kubeplex-maas 认证）
    if _catclaw_available:
        try:
            answer = catclaw_call(full_prompt, system=SYSTEM_PROMPT, max_tokens=1500, temperature=0.2)
        except Exception as e:
            pass

    # fallback: OpenAI 兼容接口（需设置 OPENAI_API_KEY）
    if not answer and _has_openai:
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if api_key:
            try:
                api_base = os.environ.get("OPENAI_API_BASE", "https://api.deepseek.com")
                model    = os.environ.get("LLM_MODEL", "deepseek-chat")
                client = OpenAI(api_key=api_key, base_url=api_base)
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": full_prompt},
                    ],
                    temperature=0.2,
                    max_tokens=1500,
                )
                answer = resp.choices[0].message.content.strip()
            except Exception as e:
                pass

    if not answer:
        return answer_without_llm(question, docs)
    
    # 附加来源列表
    sources = []
    for i, d in enumerate(docs):
        s = f"  [{i+1}] {d.get('title','')}"
        if d.get('km_url'):
            s += f"\n       {d['km_url']}"
        sources.append(s)
    
    return answer + "\n\n📚 参考来源：\n" + "\n".join(sources)


def answer_without_llm(question: str, docs: List[Dict]) -> str:
    """无 LLM 时直接返回相关文档摘要（降级模式）"""
    if not docs:
        return "❌ 知识库中未找到与该问题相关的内容。"
    
    lines = [f"🔍 找到 {len(docs)} 篇相关文档：\n"]
    for i, doc in enumerate(docs):
        lines.append(f"**[{i+1}] {doc.get('title', '未知')}**")
        if doc.get('date'):
            lines.append(f"   时间：{doc['date']}")
        if doc.get('summary'):
            lines.append(f"   摘要：{doc['summary']}")
        if doc.get('key_points'):
            lines.append("   要点：")
            for p in doc['key_points'][:3]:
                lines.append(f"     • {p}")
        if doc.get('km_url'):
            lines.append(f"   来源：{doc['km_url']}")
        lines.append("")
    
    return "\n".join(lines)
