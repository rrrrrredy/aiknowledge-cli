#!/usr/bin/env python3
"""全量质检 257篇"""
import json, re, sys
from pathlib import Path

BASE = Path(__file__).parent.parent

def log(msg): print(msg, flush=True)

with open(BASE/'data/knowledge_base_rebuilt.json') as f:
    docs = json.load(f)

pdf_kws = ['Technical Report','Genius Makers','综述（中文版）','DeepSeek-V3 技术报告','DeepSeek-R1 及类强推理']
non_pdf = [d for d in docs if not any(kw in (d.get('title','') or '') for kw in pdf_kws)]

log(f"全量质检开始：{len(non_pdf)}篇")
log("="*60)

def extract_nouns(text):
    en = re.findall(r'\b[A-Z][A-Za-z0-9\-]{2,}\b', text)
    cn = re.findall(r'[\u4e00-\u9fa5]{2,4}(?=团队|提出|发布|研究|模型|公司)', text)
    return list(set(en[:8] + cn[:5]))

TRUNCATION = re.compile(r'[，,、；]$')
MEANINGLESS = re.compile(r'^(本文|这篇文章|文章介绍|本篇).{0,10}(介绍|讨论|分析|探讨)')

results = []
pass_n = warn_n = fail_n = 0

for i, d in enumerate(non_pdf):
    n = i + 1
    title = (d.get('title','') or '')[:50]
    raw   = d.get('raw_text','') or ''
    summ  = d.get('summary','') or ''
    issues = []

    if len(raw) < 500:
        issues.append(f"RAW_SHORT({len(raw)}字)")
    if len(summ) < 100:
        issues.append(f"SUM_SHORT({len(summ)}字)")
    if TRUNCATION.search(summ.strip()):
        issues.append("SUM_TRUNCATED")
    if MEANINGLESS.match(summ.strip()):
        issues.append("SUM_MEANINGLESS")

    if len(raw) >= 500 and len(summ) >= 100:
        nouns = extract_nouns(summ)
        missing = [n2 for n2 in nouns[:8] if len(n2) >= 3 and n2 not in raw]
        if len(missing) >= 3:
            issues.append(f"HALLUCINATION_RISK({','.join(missing[:3])})")

    has_h = any('HALLUCINATION' in x for x in issues)
    if has_h or len(issues) >= 2:
        status = 'FAIL'; fail_n += 1
    elif issues:
        status = 'WARN'; warn_n += 1
    else:
        status = 'PASS'; pass_n += 1

    results.append({'n':n,'title':title,'status':status,'issues':issues,'raw_len':len(raw),'sum_len':len(summ)})

    if status != 'PASS':
        log(f"[{n:3d}] {status} | {title} | {'; '.join(issues)}")

    if n % 25 == 0 or n == len(non_pdf):
        log(f"\n── CHECKPOINT {n}/{len(non_pdf)} | PASS={pass_n} WARN={warn_n} FAIL={fail_n} ──\n")

log("="*60)
log(f"PASS={pass_n}  WARN={warn_n}  FAIL={fail_n}  通过率={pass_n/len(non_pdf)*100:.1f}%")

report = {'total':len(non_pdf),'pass':pass_n,'warn':warn_n,'fail':fail_n,
          'pass_rate':f"{pass_n/len(non_pdf)*100:.1f}%",'details':results}
with open(BASE/'data/quality_check_full_report.json','w') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
log(f"报告已保存: data/quality_check_full_report.json")

fails = [r for r in results if r['status']=='FAIL']
warns = [r for r in results if r['status']=='WARN']
if fails:
    log(f"\nFAIL({len(fails)}篇):")
    for r in fails: log(f"  [{r['n']:3d}] {r['title']} | {'; '.join(r['issues'])}")
if warns:
    log(f"\nWARN({len(warns)}篇):")
    for r in warns: log(f"  [{r['n']:3d}] {r['title']} | {'; '.join(r['issues'])}")
