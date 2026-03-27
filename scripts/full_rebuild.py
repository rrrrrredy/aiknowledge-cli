#!/usr/bin/env python3
"""
知识库全量重建脚本 v4
- citadel读全文 + LLM提取
- 每10篇checkpoint，每25篇质检
- JSON解析健壮性加强，LLM重试机制
"""

import json, subprocess, sys, os, time, re, argparse, random
from datetime import datetime

BASE_DIR = "/mnt/openclaw/.openclaw/workspace/aiknowledge-cli"
DATA_DIR = f"{BASE_DIR}/data"
SCRIPTS_DIR = f"{BASE_DIR}/scripts"
KB_FILE = f"{DATA_DIR}/knowledge_base.json"
OUTPUT_FILE = f"{DATA_DIR}/knowledge_base_rebuilt.json"
LOG_FILE = f"{SCRIPTS_DIR}/rebuild_log.md"
CHECKPOINT_DIR = f"{DATA_DIR}/checkpoints"
os.makedirs(CHECKPOINT_DIR, exist_ok=True)

sys.path.insert(0, SCRIPTS_DIR)
import catclaw_llm

EXTRACT_PROMPT = """你是专业的AI领域知识提取专家。仔细阅读文章全文，深度理解后输出JSON。

规则：
1. summary: 真实总结核心内容，300-600字。若包含多篇论文/产品，每个都要提到
2. key_points: 5个最重要结论，每条20-50字
3. tags: 3-6个精准标签
4. entities: 核心人物/机构/产品/论文名，5-10个

文章标题：{title}
文章全文（前8000字）：
{content}

输出格式（严格JSON，不得有注释，字符串用双引号，逗号不能有多余）：
{{"summary":"此处写摘要","key_points":["要点1","要点2","要点3","要点4","要点5"],"tags":["标签1","标签2","标签3"],"entities":["实体1","实体2","实体3"]}}"""

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def clean_json_str(s):
    """尝试修复常见的JSON问题"""
    # 移除markdown代码块
    s = re.sub(r'```(?:json)?\s*', '', s)
    s = re.sub(r'```\s*$', '', s, flags=re.MULTILINE)
    # 提取最外层{}
    m = re.search(r'\{[\s\S]*\}', s, re.DOTALL)
    if m:
        s = m.group()
    # 移除行尾注释
    s = re.sub(r'//[^\n"]*(?=\n)', '', s)
    return s.strip()

def parse_llm_json(text):
    """健壮的JSON解析，多种策略"""
    # 策略1: 直接解析
    try:
        return json.loads(text)
    except: pass
    # 策略2: 清理后解析
    try:
        return json.loads(clean_json_str(text))
    except: pass
    # 策略3: 正则提取各字段
    try:
        result = {}
        sm = re.search(r'"summary"\s*:\s*"((?:[^"\\]|\\.)*)"', text, re.DOTALL)
        if sm: result['summary'] = sm.group(1).replace('\\"', '"')
        kpm = re.findall(r'"([^"]{10,100})"', text)
        # 尝试找key_points数组
        kpa = re.search(r'"key_points"\s*:\s*\[(.*?)\]', text, re.DOTALL)
        if kpa:
            pts = re.findall(r'"([^"]+)"', kpa.group(1))
            if pts: result['key_points'] = pts
        ta = re.search(r'"tags"\s*:\s*\[(.*?)\]', text, re.DOTALL)
        if ta:
            tags = re.findall(r'"([^"]+)"', ta.group(1))
            if tags: result['tags'] = tags
        ea = re.search(r'"entities"\s*:\s*\[(.*?)\]', text, re.DOTALL)
        if ea:
            ents = re.findall(r'"([^"]+)"', ea.group(1))
            if ents: result['entities'] = ents
        if result.get('summary'): return result
    except: pass
    return None

def citadel_read(content_id):
    try:
        r = subprocess.run(
            ["npx", "--yes", "@it/oa-skills", "citadel", "getMarkdown",
             "--contentId", str(content_id)],
            capture_output=True, timeout=90
        )
        # 用latin-1解码避免utf-8截断问题，再转utf-8
        raw = r.stdout.decode('utf-8', errors='replace')
        skip_kw = ['✓','🔐','[load','[init','[probe','[detect','[sso','[ensure',
                   'MOA','认证','✅ 认证','版本检查','获取用户','正在认证',
                   'TargetClientId','mtsso','无感登录','缓存','认证成功',
                   'Node.js','从 OpenClaw']
        lines = [l for l in raw.split('\n')
                 if not any(kw in l for kw in skip_kw)]
        content = re.sub(r'\x1b\[[0-9;]*m', '', '\n'.join(lines)).strip()
        return content if len(content) > 300 else None
    except subprocess.TimeoutExpired:
        log(f"  ⏰ citadel超时 id={content_id}")
        return None
    except Exception as e:
        log(f"  citadel异常: {e}")
        return None

def llm_extract(title, content, retries=2):
    """LLM提取，失败自动重试"""
    prompt = EXTRACT_PROMPT.format(title=title, content=content[:8000])
    for attempt in range(retries+1):
        try:
            out = catclaw_llm.call_llm(prompt, max_tokens=2000, temperature=0.1)
            result = parse_llm_json(out)
            if result and result.get('summary'):
                return result
            if attempt < retries:
                log(f"  ↩️ JSON解析失败，重试({attempt+1}/{retries})...")
                time.sleep(2)
        except Exception as e:
            log(f"  LLM异常(attempt={attempt}): {e}")
            if attempt < retries:
                time.sleep(3)
    return None

def validate(doc):
    issues = []
    if len(doc.get('summary','')) < 100:
        issues.append(f"summary短({len(doc.get('summary',''))}字)")
    if len(doc.get('key_points',[])) < 3:
        issues.append("key_points<3条")
    if len(doc.get('tags',[])) < 2:
        issues.append("tags<2个")
    if len(doc.get('raw_text','')) < 500:
        issues.append(f"raw_text短({len(doc.get('raw_text',''))}字)")
    return issues

def do_checkpoint(docs, n):
    p = f"{CHECKPOINT_DIR}/ckpt_{n:04d}.json"
    json.dump(docs, open(p,'w',encoding='utf-8'), ensure_ascii=False, indent=2)
    log(f"  💾 ckpt_{n:04d}.json ({n}篇)")

def quality_report(docs, b, e, label=""):
    batch = docs[b:e]
    if not batch: return
    ok = sum(1 for d in batch if not validate(d))
    problems = [(d.get('title','?'), validate(d)) for d in batch if validate(d)]
    samples = random.sample(batch, min(3, len(batch)))
    with open(LOG_FILE,'a',encoding='utf-8') as f:
        f.write(f"\n## 质检[{b+1}-{e}]{label} @ {datetime.now().strftime('%m-%d %H:%M')}\n")
        f.write(f"通过: {ok}/{len(batch)}\n")
        for title, iss in problems[:10]:
            f.write(f"- ⚠️ [{title[:40]}]: {'; '.join(iss)}\n")
        f.write("样本:\n")
        for d in samples:
            f.write(f"  - [{d.get('title','?')[:50]}] "
                    f"raw={len(d.get('raw_text',''))}字 "
                    f"sum={len(d.get('summary',''))}字 "
                    f"tags={d.get('tags',[])}\n")
    log(f"  📝 质检[{b+1}-{e}]{label}: {ok}/{len(batch)}通过")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--start', type=int, default=0)
    ap.add_argument('--end', type=int, default=None)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--resume', type=str, default=None)
    args = ap.parse_args()

    kb = json.load(open(KB_FILE, encoding='utf-8'))
    all_docs = kb.get('documents', kb) if isinstance(kb, dict) else kb
    log(f"📚 知识库: {len(all_docs)}篇")

    rebuilt = []
    done_ids = set()
    if args.resume and os.path.exists(args.resume):
        rebuilt = json.load(open(args.resume, encoding='utf-8'))
        done_ids = {str(d['id']) for d in rebuilt}
        log(f"🔄 恢复: {len(rebuilt)}篇已完成")

    todo = all_docs[args.start:args.end]
    if args.dry_run:
        todo = all_docs[:5]
        log("🧪 dry-run: 前5篇")

    with open(LOG_FILE,'a',encoding='utf-8') as f:
        f.write(f"\n# 全量重建v4 @ {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"总文档:{len(all_docs)}, 本次:{len(todo)}\n")

    ok_cnt = fail_cnt = skip_cnt = 0
    batch_start_idx = len(rebuilt)

    for i, doc in enumerate(todo):
        doc_id = str(doc.get('id',''))
        title = doc.get('title', f'doc_{doc_id}')
        km_url = doc.get('km_url','')

        if doc_id in done_ids:
            skip_cnt += 1
            continue

        log(f"\n[{i+1}/{len(todo)}] 📖 {title[:60]}")

        # Step1: 读原文
        raw = ''
        if km_url:
            m = re.search(r'/(\d+)$', km_url)
            if m:
                cid = m.group(1)
                log(f"  → citadel {cid}")
                raw = citadel_read(cid) or ''
                log(f"  原文: {len(raw)}字" if raw else "  ⚠️ citadel失败，用已有raw_text")
        if not raw:
            raw = doc.get('raw_text','')
            if raw: log(f"  → 已有raw_text: {len(raw)}字")

        new_doc = dict(doc)
        new_doc['raw_text'] = raw

        if len(raw) < 200:
            log(f"  ❌ 原文不足200字，跳过LLM")
            fail_cnt += 1
            rebuilt.append(new_doc)
        else:
            log(f"  → LLM提取 ({len(raw)}字)...")
            ext = llm_extract(title, raw)
            if ext:
                new_doc['summary'] = ext.get('summary', doc.get('summary',''))
                new_doc['key_points'] = ext.get('key_points', doc.get('key_points',[]))
                new_doc['tags'] = ext.get('tags', doc.get('tags',[]))
                if ext.get('entities'):
                    new_doc['entities'] = ext['entities']
                iss = validate(new_doc)
                status = "✅" if not iss else "⚠️"
                log(f"  {status} sum={len(new_doc['summary'])}字 tags={new_doc.get('tags',[])} iss={iss or '无'}")
                ok_cnt += 1
            else:
                log(f"  ❌ LLM失败，保留原数据")
                fail_cnt += 1
            rebuilt.append(new_doc)

        done_ids.add(doc_id)

        if (i+1) % 10 == 0:
            do_checkpoint(rebuilt, len(rebuilt))
        if (i+1) % 25 == 0:
            b = max(0, len(rebuilt)-25)
            quality_report(rebuilt, b, len(rebuilt))

        time.sleep(1)

    # 保存
    json.dump(rebuilt, open(OUTPUT_FILE,'w',encoding='utf-8'), ensure_ascii=False, indent=2)
    log(f"\n🏁 完成 ok={ok_cnt} fail={fail_cnt} skip={skip_cnt} total={len(rebuilt)}")
    log(f"💾 {OUTPUT_FILE}")
    quality_report(rebuilt, batch_start_idx, len(rebuilt), label="【最终】")
    log(f"📝 质检报告: {LOG_FILE}")

if __name__ == '__main__':
    main()
