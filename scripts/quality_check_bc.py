#!/usr/bin/env python3
"""
质量验证脚本 - 方案B+C
B: LLM交叉验证（用原文判断summary是否准确）
C: 关键词命中率（去除citadel格式标记后）
抽样：每25篇随机抽5篇做B验证，全量做C验证
输出：质量报告 quality_report.md
"""
import json, sys, re, random, time
from datetime import datetime
from pathlib import Path

BASE = Path('/mnt/openclaw/.openclaw/workspace/aiknowledge-cli')
REBUILT = BASE / 'data/knowledge_base_rebuilt.json'
REPORT = BASE / 'scripts/quality_report.md'
sys.path.insert(0, str(BASE / 'scripts'))
import catclaw_llm

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def clean_citadel(text):
    """去掉citadel格式标记，提取纯文本内容"""
    # 去掉 :::xxx{...}::: 格式
    text = re.sub(r':::[\w]+\{[^}]*\}:::', '', text)
    text = re.sub(r':::[\w]+\{[^}]*\}', '', text)
    text = re.sub(r':::[^\n]*', '', text)
    # 去掉markdown表格格式符号
    text = re.sub(r'\|[-:]+\|', '', text)
    # 去掉多余空白
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def extract_keywords(text, topn=20):
    """从文本提取高频词（去停用词）"""
    text = clean_citadel(text)
    stopwords = {'的','了','是','在','和','有','也','都','这','那','就','而','到','与','或',
                 '对','为','以','中','及','等','其','他','她','它','我','你','该','被','将',
                 '从','由','但','还','又','则','已','各','每','此','其中','如果','如何',
                 'the','a','an','of','in','to','for','with','and','or','is','are','that',
                 '本文','文章','研究','介绍','通过','提出','实现','方法','技术','模型',
                 '可以','进行','使用','采用','基于','相比','较','更','最','主要','重要'}
    words = re.findall(r'[\u4e00-\u9fff]{2,8}|[a-zA-Z]{4,20}', text)
    freq = {}
    for w in words:
        if w not in stopwords and not w.isdigit():
            freq[w] = freq.get(w, 0) + 1
    return sorted(freq.items(), key=lambda x: -x[1])[:topn]

def keyword_hit_rate(raw_text, summary, topn=15):
    """C方案：关键词命中率"""
    raw_clean = clean_citadel(raw_text)
    kws = extract_keywords(raw_clean, topn)
    if not kws: return 0.0, []
    hits = [(kw, freq) for kw, freq in kws if kw in summary]
    missed = [(kw, freq) for kw, freq in kws if kw not in summary]
    rate = len(hits) / len(kws)
    return rate, [kw for kw, _ in kws], [kw for kw, _ in hits], [kw for kw, _ in missed]

def llm_verify(title, raw_text, summary, retries=2):
    """B方案：LLM交叉验证"""
    raw_clean = clean_citadel(raw_text)
    prompt = f"""你是一个严格的内容质检员。请判断以下summary是否准确反映了原文内容。

文章标题：{title}
原文（前4000字）：
{raw_clean[:4000]}

待验证的summary：
{summary}

请从以下3个维度打分（1-5分），并给出简短理由：
1. 准确性：summary的内容是否与原文一致，有无捏造或错误
2. 覆盖度：原文的核心观点是否都被summary覆盖
3. 区分度：这个summary是否有足够的具体细节，能区别于其他文章

严格按JSON格式返回：
{{"accuracy": 分数, "coverage": 分数, "specificity": 分数, "overall": 综合分(1-5), "issues": "主要问题，如无问题填none", "verdict": "pass/warning/fail"}}

verdict标准：overall>=4为pass，3为warning，<=2为fail"""

    for attempt in range(retries+1):
        try:
            out = catclaw_llm.call_llm(prompt, max_tokens=500, temperature=0.1)
            m = re.search(r'\{[\s\S]*\}', out)
            if m:
                try:
                    return json.loads(m.group())
                except:
                    pass
            # 简单提取verdict
            if 'pass' in out.lower(): return {'verdict': 'pass', 'overall': 4, 'issues': 'none'}
            if 'fail' in out.lower(): return {'verdict': 'fail', 'overall': 2, 'issues': out[:100]}
            return {'verdict': 'warning', 'overall': 3, 'issues': out[:100]}
        except Exception as e:
            log(f"  LLM验证异常: {e}")
            if attempt < retries: time.sleep(3)
    return None

def main():
    log("="*60)
    log(f"🔍 质量验证 B+C 启动 @ {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    with open(REBUILT) as f:
        docs = json.load(f)

    # 只验证有原文的文档
    valid_docs = [d for d in docs if len(d.get('raw_text','') or '') > 500
                  and len(d.get('summary','') or '') > 50]
    log(f"有效文档（有原文+有summary）: {len(valid_docs)}/{len(docs)}")

    # ===== 方案C：全量关键词命中率 =====
    log(f"\n📊 方案C：全量关键词命中率验证 ({len(valid_docs)}篇)")
    c_results = []
    c_fail = []  # hit_rate < 0.3
    c_warn = []  # 0.3 <= hit_rate < 0.5

    for i, doc in enumerate(valid_docs):
        title = doc.get('title','')
        raw = doc.get('raw_text','') or ''
        summ = doc.get('summary','') or ''
        rate, all_kws, hits, missed = keyword_hit_rate(raw, summ)
        c_results.append((title, rate, all_kws[:10], hits[:5], missed[:5]))
        if rate < 0.3:
            c_fail.append((title, rate, missed[:5]))
        elif rate < 0.5:
            c_warn.append((title, rate, missed[:5]))
        if (i+1) % 50 == 0:
            log(f"  进度 {i+1}/{len(valid_docs)}")

    avg_rate = sum(r for _,r,*_ in c_results) / len(c_results) if c_results else 0
    log(f"\n📊 C方案结果: 平均命中率={avg_rate:.1%}")
    log(f"  命中率<30%（高风险）: {len(c_fail)}篇")
    log(f"  命中率30-50%（需关注）: {len(c_warn)}篇")
    log(f"  命中率>50%（正常）: {len(c_results)-len(c_fail)-len(c_warn)}篇")

    # ===== 方案B：抽样LLM验证 =====
    # 策略：从c_fail里抽10篇（最可疑），random抽15篇，共25篇
    sample_fail = random.sample(c_fail, min(10, len(c_fail)))
    sample_fail_titles = {t for t,_,_ in sample_fail}
    remaining = [d for d in valid_docs if d.get('title','') not in sample_fail_titles]
    sample_random = random.sample(remaining, min(15, len(remaining)))
    b_sample = (
        [d for d in valid_docs if d.get('title','') in sample_fail_titles] +
        sample_random
    )
    log(f"\n🤖 方案B：LLM交叉验证 ({len(b_sample)}篇抽样)")
    log(f"  其中：高风险抽样={len(sample_fail)}篇，随机抽样={len(sample_random)}篇")

    b_results = []
    b_fail_list = []
    b_warn_list = []
    b_pass_list = []

    for i, doc in enumerate(b_sample):
        title = doc.get('title','')
        raw = doc.get('raw_text','') or ''
        summ = doc.get('summary','') or ''
        log(f"  [{i+1}/{len(b_sample)}] {title[:45]}...")
        result = llm_verify(title, raw, summ)
        if result:
            verdict = result.get('verdict','warning')
            overall = result.get('overall', 3)
            issues = result.get('issues','')
            b_results.append((title, verdict, overall, issues))
            if verdict == 'fail': b_fail_list.append((title, overall, issues))
            elif verdict == 'warning': b_warn_list.append((title, overall, issues))
            else: b_pass_list.append((title, overall, issues))
            log(f"    → {verdict} ({overall}/5): {issues[:60] if issues!='none' else 'OK'}")
        time.sleep(1)

    log(f"\n📊 B方案结果: pass={len(b_pass_list)}, warning={len(b_warn_list)}, fail={len(b_fail_list)}")

    # ===== 写质量报告 =====
    with open(REPORT, 'w') as f:
        f.write(f"# 质量验证报告 @ {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write(f"验证文档数: {len(valid_docs)}/{len(docs)} (有原文+summary)\n\n")

        f.write(f"## 方案C：关键词命中率（全量{len(valid_docs)}篇）\n")
        f.write(f"- 平均命中率: **{avg_rate:.1%}**\n")
        f.write(f"- 命中率>50%（正常）: {len(c_results)-len(c_fail)-len(c_warn)}篇\n")
        f.write(f"- 命中率30-50%（需关注）: {len(c_warn)}篇\n")
        f.write(f"- 命中率<30%（高风险）: {len(c_fail)}篇\n\n")
        if c_fail:
            f.write(f"### 高风险文档（命中率<30%）\n")
            for t, r, missed in c_fail[:20]:
                f.write(f"- [{t[:45]}] hit={r:.0%} 缺失关键词: {', '.join(missed[:5])}\n")

        f.write(f"\n## 方案B：LLM交叉验证（抽样{len(b_sample)}篇）\n")
        f.write(f"- pass: {len(b_pass_list)}篇\n")
        f.write(f"- warning: {len(b_warn_list)}篇\n")
        f.write(f"- fail: {len(b_fail_list)}篇\n\n")
        if b_fail_list:
            f.write(f"### Fail文档（需重做）\n")
            for t, s, iss in b_fail_list:
                f.write(f"- [{t[:45]}] score={s}/5: {iss[:100]}\n")
        if b_warn_list:
            f.write(f"\n### Warning文档（建议复核）\n")
            for t, s, iss in b_warn_list:
                f.write(f"- [{t[:45]}] score={s}/5: {iss[:100]}\n")

        f.write(f"\n## 抽样详细结果\n")
        for t, v, s, iss in b_results:
            # 找C方案对应命中率
            c_match = next((r for title,r,*_ in c_results if title==t), None)
            f.write(f"- [{t[:45]}] B={v}({s}/5) C={c_match:.0%} | {iss[:80] if iss!='none' else 'OK'}\n")

    log(f"\n{'='*60}")
    log(f"🏁 质量验证完成")
    log(f"报告: {REPORT}")
    # 打印关键结论
    if b_fail_list:
        log(f"\n⚠️ LLM判定FAIL（需重做）{len(b_fail_list)}篇:")
        for t, s, iss in b_fail_list:
            log(f"  [{t[:40]}] {iss[:60]}")
    log(f"\n综合判断:")
    total_issues = len(b_fail_list) + len(b_warn_list)
    if total_issues == 0:
        log(f"  ✅ 质量良好")
    elif len(b_fail_list) == 0:
        log(f"  ⚠️ 有{len(b_warn_list)}篇需关注，无明确fail")
    else:
        log(f"  ❌ {len(b_fail_list)}篇质量不合格，{len(b_warn_list)}篇需关注")

if __name__ == '__main__':
    main()
