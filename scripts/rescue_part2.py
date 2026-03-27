#!/usr/bin/env python3
"""
补救重建 Part 2：处理未完成的37篇KM文档 + 26篇summary偏短
"""
import json, subprocess, sys, time, re, os
from datetime import datetime
from pathlib import Path

BASE = Path('/mnt/openclaw/.openclaw/workspace/aiknowledge-cli')
REBUILT = BASE / 'data/knowledge_base_rebuilt.json'
RESCUE_LIST = BASE / 'data/rescue_list.json'
LOG = BASE / 'scripts/rescue_run.log'
REPORT = BASE / 'scripts/rescue_log.md'
sys.path.insert(0, str(BASE / 'scripts'))

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG, 'a') as f:
        f.write(line + '\n')

SKIP_KW = ['✓','🔐','[load','[init','[probe','[detect','[sso','[ensure',
           'MOA','认证','✅ 认证','版本检查','获取用户','正在认证',
           'TargetClientId','mtsso','无感登录','缓存','认证成功',
           'Node.js','从 OpenClaw','目标 ClientId']

def citadel_read(content_id, retries=3):
    for attempt in range(retries):
        try:
            r = subprocess.run(
                ["npx", "--yes", "@it/oa-skills", "citadel", "getMarkdown",
                 "--contentId", str(content_id)],
                capture_output=True, timeout=90
            )
            raw = r.stdout.decode('utf-8', errors='replace')
            lines = [l for l in raw.split('\n')
                     if not any(kw in l for kw in SKIP_KW)]
            content = re.sub(r'\x1b\[[0-9;]*m', '', '\n'.join(lines)).strip()
            if len(content) > 300:
                return content
        except subprocess.TimeoutExpired:
            log(f"  ⏱ citadel超时 attempt={attempt+1}")
        except Exception as e:
            log(f"  ❌ citadel异常: {e}")
        if attempt < retries-1:
            time.sleep(5)
    return None

def clean_json_str(s):
    s = re.sub(r'```(?:json)?\s*', '', s)
    s = re.sub(r'```\s*$', '', s, flags=re.MULTILINE)
    m = re.search(r'\{[\s\S]*\}', s, re.DOTALL)
    if m: s = m.group()
    s = re.sub(r'//[^\n"]*(?=\n)', '', s)
    return s.strip()

def parse_llm_json(text):
    try: return json.loads(text)
    except: pass
    try: return json.loads(clean_json_str(text))
    except: pass
    try:
        result = {}
        sm = re.search(r'"summary"\s*:\s*"((?:[^"\\]|\\.)*)"', text, re.DOTALL)
        if sm: result['summary'] = sm.group(1).replace('\\"','"')
        kpa = re.search(r'"key_points"\s*:\s*\[(.*?)\]', text, re.DOTALL)
        if kpa: result['key_points'] = re.findall(r'"([^"]+)"', kpa.group(1))
        ta = re.search(r'"tags"\s*:\s*\[(.*?)\]', text, re.DOTALL)
        if ta: result['tags'] = re.findall(r'"([^"]+)"', ta.group(1))
        ea = re.search(r'"entities"\s*:\s*\[(.*?)\]', text, re.DOTALL)
        if ea: result['entities'] = re.findall(r'"([^"]+)"', ea.group(1))
        if result.get('summary'): return result
    except: pass
    return None

def llm_extract(title, content, min_summ=200, retries=2):
    import catclaw_llm
    prompt = f"""你是专业AI知识提取专家。仔细阅读文章后输出结构化JSON。

文章标题：{title}
文章全文（前8000字）：
{content[:8000]}

严格要求：summary必须至少{min_summ}字，覆盖主要观点、关键发现、技术细节和实际意义。

输出格式（严格JSON，不得有注释）：
{{"summary":"至少{min_summ}字的详细总结","key_points":["要点1","要点2","要点3","要点4","要点5"],"tags":["标签1","标签2","标签3","标签4","标签5"],"entities":["实体1","实体2","实体3"]}}"""

    for attempt in range(retries+1):
        try:
            out = catclaw_llm.call_llm(prompt, max_tokens=2000, temperature=0.1)
            result = parse_llm_json(out)
            if result and result.get('summary'):
                return result
            log(f"  ↩️ JSON解析失败，重试({attempt+1}/{retries})...")
            time.sleep(2)
        except Exception as e:
            log(f"  LLM异常(attempt={attempt}): {e}")
            if attempt < retries: time.sleep(3)
    return None

def save(docs):
    with open(REBUILT,'w') as f:
        json.dump(docs, f, ensure_ascii=False, indent=2)

def main():
    log("="*60)
    log(f"🔧 补救重建 Part2 启动 @ {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    docs = json.loads(REBUILT.read_text())
    rescue = json.loads(RESCUE_LIST.read_text())
    km_list = rescue['km']
    title_to_idx = {d.get('title',''): i for i,d in enumerate(docs)}

    # Find not-yet-fixed KM docs
    todo_km = []
    for i, (doc_id, title) in enumerate(km_list):
        idx = title_to_idx.get(title)
        if idx is not None:
            doc = docs[idx]
            raw = len(doc.get('raw_text','') or '')
            summ = len(doc.get('summary','') or '')
            if not (raw >= 200 and summ >= 100):
                todo_km.append((i, doc_id, title, idx))

    log(f"\n📚 任务1：{len(todo_km)}篇KM文档待处理（跳过已完成）")
    km_ok = km_fail = 0

    for j, (orig_i, doc_id, title, idx) in enumerate(todo_km):
        log(f"\n[KM {j+1}/{len(todo_km)}] ({orig_i+1}/56) {title[:50]}")
        log(f"  → citadel {doc_id}")

        raw_text = citadel_read(doc_id)
        if not raw_text:
            log(f"  ❌ citadel失败，跳过")
            km_fail += 1
            continue

        log(f"  原文: {len(raw_text)}字")
        log(f"  → LLM提取 (min_summ=200字)...")
        extracted = llm_extract(title, raw_text, min_summ=200)

        if extracted:
            summ_len = len(extracted.get('summary',''))
            log(f"  ✅ sum={summ_len}字 tags={extracted.get('tags',[])}")
            docs[idx]['raw_text'] = raw_text
            docs[idx]['doc_id'] = doc_id
            docs[idx]['summary'] = extracted.get('summary','')
            docs[idx]['key_points'] = extracted.get('key_points',[])
            docs[idx]['tags'] = extracted.get('tags',[])
            docs[idx]['entities'] = extracted.get('entities',[])
            km_ok += 1
        else:
            log(f"  ❌ LLM提取失败，保留原文")
            docs[idx]['raw_text'] = raw_text
            docs[idx]['doc_id'] = doc_id
            km_fail += 1

        # checkpoint every 5
        if (j+1) % 5 == 0:
            save(docs)
            log(f"  💾 ckpt P2_KM_{j+1}")

    save(docs)
    log(f"\n📊 KM补救: ok={km_ok}, fail={km_fail}")

    # ===== 任务2：summary偏短重跑 =====
    short_list = [(i, d) for i,d in enumerate(docs)
                  if len(d.get('raw_text','') or '') >= 200
                  and len(d.get('summary','') or '') < 100]
    log(f"\n📚 任务2：{len(short_list)}篇summary偏短重跑")
    summ_ok = summ_fail = 0

    for j, (idx, doc) in enumerate(short_list):
        title = doc.get('title','')
        raw_text = doc.get('raw_text','')
        old_len = len(doc.get('summary','') or '')
        log(f"\n[SUM {j+1}/{len(short_list)}] {title[:50]}")
        log(f"  原文:{len(raw_text)}字 旧sum:{old_len}字 → 重提取(min=200字)")
        extracted = llm_extract(title, raw_text, min_summ=200)
        if extracted:
            new_summ = extracted.get('summary','')
            log(f"  ✅ 新sum={len(new_summ)}字")
            docs[idx]['summary'] = new_summ
            if extracted.get('key_points'): docs[idx]['key_points'] = extracted['key_points']
            if extracted.get('tags'): docs[idx]['tags'] = extracted['tags']
            summ_ok += 1
        else:
            log(f"  ❌ LLM失败")
            summ_fail += 1
        if (j+1) % 5 == 0:
            save(docs)
            log(f"  💾 中间保存 SUM_{j+1}")

    save(docs)
    log(f"\n📊 summary补救: ok={summ_ok}, fail={summ_fail}")

    # ===== 最终质检 =====
    log(f"\n🔍 最终质检全库...")
    final_ok = 0
    final_issues = []
    for doc in docs:
        raw = len(doc.get('raw_text','') or '')
        summ = len(doc.get('summary','') or '')
        kp = len(doc.get('key_points',[]) or [])
        tags = len(doc.get('tags',[]) or [])
        issues = []
        if raw < 200: issues.append(f'raw_text短({raw}字)')
        if summ < 100: issues.append(f'summary短({summ}字)')
        if kp < 3: issues.append(f'key_points少')
        if tags < 2: issues.append(f'tags少')
        if not issues:
            final_ok += 1
        else:
            final_issues.append((doc.get('title','')[:50], issues))

    with open(REPORT,'a') as f:
        f.write(f"\n## 最终质检 Part2 @ {datetime.now().strftime('%H:%M')}\n")
        f.write(f"**通过: {final_ok}/263 ({final_ok/263*100:.1f}%)**\n")
        f.write(f"仍有问题: {len(final_issues)}篇\n\n")
        for t, iss in final_issues:
            f.write(f"- ⚠️ [{t}]: {'; '.join(iss)}\n")
        f.write(f"\n### PDF({len(rescue['pdf'])}篇，需单独处理)\n")
        for did, title in rescue['pdf']:
            f.write(f"- [{did}] {title[:50]}\n")

    log(f"\n{'='*60}")
    log(f"🏁 补救完成！最终通过: {final_ok}/263 ({final_ok/263*100:.1f}%)")
    if final_issues[:10]:
        log(f"仍有问题(前10):")
        for t,iss in final_issues[:10]:
            log(f"  [{t}]: {'; '.join(iss)}")

if __name__ == '__main__':
    main()
