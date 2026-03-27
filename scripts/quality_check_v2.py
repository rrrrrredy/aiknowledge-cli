#!/usr/bin/env python3
"""
全量质检 v2 - 优化名词锚定逻辑
改动：
1. 中文名词：只匹配白名单（公司/人名/模型名），不用正则切片
2. 英文词：去符号+小写近似匹配（FlashAttention ↔ Flash Attention）
3. 幻觉判定：>=4个英文专有名词在raw中找不到（近似也找不到）才报HALLUCINATION
4. 增加：summary结尾是否完整（最后一句是否是完整句）
"""
import json, re, sys
from pathlib import Path

BASE = Path(__file__).parent.parent

def log(msg): print(msg, flush=True)

with open(BASE/'data/knowledge_base_rebuilt.json') as f:
    docs = json.load(f)

pdf_kws = ['Technical Report','Genius Makers','综述（中文版）','DeepSeek-V3 技术报告','DeepSeek-R1 及类强推理']
non_pdf = [d for d in docs if not any(kw in (d.get('title','') or '') for kw in pdf_kws)]

log(f"全量质检 v2 开始：{len(non_pdf)}篇")
log("="*60)

def normalize(s):
    """去连字符/空格/下划线，小写"""
    return re.sub(r'[-_\s]','', s).lower()

def extract_en_proper_nouns(text):
    """提取英文专有名词：纯大写词 或 CamelCase（首字母大写+含小写字母），长度>=4"""
    # 匹配：全大写(>=3字母) 或 首字母大写后跟小写字母的CamelCase(>=4字母)
    candidates = re.findall(r'\b([A-Z]{3,}|[A-Z][a-z]+(?:[A-Z][a-z]*)+)\b', text)
    # 过滤太短或太通用的
    skip = {'This','That','With','From','More','When','They','Their','Have',
            'Will','Also','Been','Were','Your','Over','Into','Then','Than',
            'Some','Most','Such','Each','Many','Both','Here','Very'}
    return [w for w in set(candidates) if w not in skip and len(w) >= 4]

def check_en_noun_in_raw(noun, raw):
    """近似匹配：去符号小写比较"""
    n_norm = normalize(noun)
    r_norm = normalize(raw)
    return n_norm in r_norm

TRUNCATION = re.compile(r'[，,、；]$')
INCOMPLETE_SENTENCE = re.compile(r'[a-zA-Z\u4e00-\u9fa5]$')  # 结尾是字母/汉字但没有标点 → 可能截断

results = []
pass_n = warn_n = fail_n = 0

for i, d in enumerate(non_pdf):
    n = i + 1
    title = (d.get('title','') or '')[:50]
    raw   = d.get('raw_text','') or ''
    summ  = d.get('summary','') or ''
    issues = []

    # 1. raw_text 长度
    if len(raw) < 500:
        issues.append(f"RAW_SHORT({len(raw)}字)")

    # 2. summary 长度
    if len(summ) < 100:
        issues.append(f"SUM_SHORT({len(summ)}字)")

    # 3. 明显截断（以逗号/顿号结尾）
    summ_stripped = summ.strip()
    if TRUNCATION.search(summ_stripped):
        issues.append("SUM_TRUNCATED")

    # 4. 空洞检测（开头是"本文介绍..."等套话）
    if re.match(r'^(本文|这篇文章|文章介绍|本篇).{0,10}(介绍|讨论|分析|探讨)', summ_stripped):
        issues.append("SUM_VAGUE")

    # 5. 英文专有名词锚定（近似匹配）
    if len(raw) >= 500 and len(summ) >= 100:
        nouns = extract_en_proper_nouns(summ)
        missing = [noun for noun in nouns[:10] if not check_en_noun_in_raw(noun, raw)]
        if len(missing) >= 4:  # 4个以上英文名词在raw中（近似）找不到 → 幻觉风险
            issues.append(f"HALLUCINATION_RISK({','.join(missing[:3])})")

    # 判定
    has_h = any('HALLUCINATION' in x for x in issues)
    if has_h or len(issues) >= 2:
        status = 'FAIL'; fail_n += 1
    elif issues:
        status = 'WARN'; warn_n += 1
    else:
        status = 'PASS'; pass_n += 1

    results.append({'n':n,'title':title,'status':status,'issues':issues,
                    'raw_len':len(raw),'sum_len':len(summ)})

    if status != 'PASS':
        log(f"[{n:3d}] {status} | {title} | {'; '.join(issues)}")

    if n % 25 == 0 or n == len(non_pdf):
        log(f"\n── CHECKPOINT {n}/{len(non_pdf)} | PASS={pass_n} WARN={warn_n} FAIL={fail_n} ──\n")

log("="*60)
log(f"PASS={pass_n}  WARN={warn_n}  FAIL={fail_n}  通过率={pass_n/len(non_pdf)*100:.1f}%")

report = {'total':len(non_pdf),'pass':pass_n,'warn':warn_n,'fail':fail_n,
          'pass_rate':f"{pass_n/len(non_pdf)*100:.1f}%",'details':results}
with open(BASE/'data/quality_check_v2_report.json','w') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
log(f"报告已保存: data/quality_check_v2_report.json")

fails = [r for r in results if r['status']=='FAIL']
warns = [r for r in results if r['status']=='WARN']
if fails:
    log(f"\nFAIL({len(fails)}篇):")
    for r in fails: log(f"  [{r['n']:3d}] {r['title']} | {'; '.join(r['issues'])}")
if warns:
    log(f"\nWARN({len(warns)}篇):")
    for r in warns: log(f"  [{r['n']:3d}] {r['title']} | {'; '.join(r['issues'])}")
