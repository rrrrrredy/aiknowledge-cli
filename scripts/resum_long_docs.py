#!/usr/bin/env python3
"""
对原文>6000字的文档重新生成summary（解决截断问题）
策略：原文分段（每段4000字，overlap500字），分段提取要点，再合并生成最终summary
每25篇checkpoint
"""
import json, sys, time, re
from datetime import datetime
from pathlib import Path

BASE = Path('/mnt/openclaw/.openclaw/workspace/aiknowledge-cli')
REBUILT = BASE / 'data/knowledge_base_rebuilt.json'
LOG = BASE / 'scripts/resum_long_run.log'
sys.path.insert(0, str(BASE / 'scripts'))
import catclaw_llm

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line, flush=True)

def clean_text(raw):
    """去除citadel格式标记"""
    text = re.sub(r'目标 ClientId:[^\n]*\n', '', raw)
    text = re.sub(r':::[\w]+\{[^}]*\}:::', ' ', text)
    text = re.sub(r':::[\w]+\{[^}]*\}', ' ', text)
    text = re.sub(r':::[^\n]*', '', text)
    text = re.sub(r':\[font\][^\[]*\[/font\]', '', text)
    text = re.sub(r':\[[\w]+\]\{[^}]*\}', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def extract_chunk_points(title, chunk, chunk_idx, total_chunks):
    """从一段原文提取关键要点"""
    prompt = f"""文章标题：《{title}》
这是第{chunk_idx+1}/{total_chunks}段原文：

{chunk}

请提取这段内容中的关键信息点（3-8条），每条15-40字，只列事实，不要废话。
格式：每条以"- "开头"""
    out = catclaw_llm.call_llm(prompt, max_tokens=600, temperature=0.1)
    return out.strip()

def merge_to_summary(title, all_points, raw_len):
    """合并所有段落要点，生成最终summary"""
    prompt = f"""文章标题：《{title}》
原文长度：{raw_len}字

以下是从全文各段落提取的关键信息点：
{all_points}

请基于以上信息，生成一篇200-400字的摘要。要求：
1. 覆盖文章全部核心内容（不能只写前半部分）
2. 包含具体数据、人名、模型名等细节
3. 能区别于其他文章（有具体性）
4. 不要以"本文"开头，直接陈述内容

只输出摘要正文，不要JSON包装。"""
    out = catclaw_llm.call_llm(prompt, max_tokens=600, temperature=0.2)
    return out.strip()

def process_doc(doc):
    """重新生成一篇文档的summary"""
    title = doc.get('title', '')
    raw = doc.get('raw_text', '') or ''
    clean = clean_text(raw)
    
    # 分段处理：每段3500字，overlap300字
    chunk_size = 3500
    overlap = 300
    chunks = []
    start = 0
    while start < len(clean):
        end = min(start + chunk_size, len(clean))
        chunks.append(clean[start:end])
        if end >= len(clean): break
        start = end - overlap
    
    log(f"  分{len(chunks)}段处理 ({len(clean)}字净文本)")
    
    # 每段提取要点
    all_points = []
    for i, chunk in enumerate(chunks):
        points = extract_chunk_points(title, chunk, i, len(chunks))
        all_points.append(f"=== 第{i+1}段要点 ===\n{points}")
        time.sleep(0.5)
    
    combined_points = '\n\n'.join(all_points)
    
    # 合并生成最终summary
    summary = merge_to_summary(title, combined_points, len(clean))
    return summary

def main():
    log("="*60)
    log(f"长文档summary重建 @ {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    with open(REBUILT) as f:
        rebuilt = json.load(f)

    # 找出需要重新处理的文档：原文>6000字（确保覆盖截断风险）
    # 排除PDF
    pdf_kws = ['Technical Report','Genius Makers','综述（中文版）','DeepSeek-V3 技术报告','DeepSeek-R1 及类强推理']
    long_docs_idx = [
        i for i, d in enumerate(rebuilt)
        if len(d.get('raw_text','') or '') > 6000
        and not any(kw in (d.get('title','') or '') for kw in pdf_kws)
    ]
    
    log(f"原文>6000字的非PDF文档: {len(long_docs_idx)}篇")
    
    success, fail = 0, 0
    for n, idx in enumerate(long_docs_idx):
        doc = rebuilt[idx]
        title = doc.get('title','')
        raw_len = len(doc.get('raw_text','') or '')
        log(f"\n[{n+1}/{len(long_docs_idx)}] {title[:50]} ({raw_len}字)")
        
        try:
            new_summary = process_doc(doc)
            if len(new_summary) < 100:
                log(f"  ⚠️ summary过短({len(new_summary)}字)，跳过")
                fail += 1
                continue
            
            rebuilt[idx]['summary'] = new_summary
            rebuilt[idx]['summary_method'] = 'full_text_chunked'
            log(f"  ✅ 新summary={len(new_summary)}字")
            success += 1
        except Exception as e:
            log(f"  ❌ 失败: {e}")
            fail += 1
        
        # 每25篇保存
        if (n+1) % 25 == 0 or (n+1) == len(long_docs_idx):
            with open(REBUILT, 'w') as f:
                json.dump(rebuilt, f, ensure_ascii=False, indent=2)
            log(f"  💾 ckpt {n+1}/{len(long_docs_idx)} (success={success}, fail={fail})")
        
        time.sleep(1)

    log(f"\n{'='*60}")
    log(f"完成: {success}篇成功 / {fail}篇失败 / {len(long_docs_idx)}篇总计")

if __name__ == '__main__':
    main()
