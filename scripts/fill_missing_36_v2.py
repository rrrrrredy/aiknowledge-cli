#!/usr/bin/env python3
"""
补读36篇无raw_text文档 v2
修复：
1. 使用contentId精确匹配（回退到模糊标题匹配）
2. 更健壮的JSON解析（处理LLM返回含特殊字符的情况）
3. utf-8解码错误容错（使用errors='replace'）
4. 写入验证
"""
import json, sys, time, re, subprocess
from datetime import datetime
from pathlib import Path

BASE = Path('/mnt/openclaw/.openclaw/workspace/aiknowledge-cli')
REBUILT = BASE / 'data/knowledge_base_rebuilt.json'
sys.path.insert(0, str(BASE / 'scripts'))
import catclaw_llm

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def read_citadel(content_id):
    result = subprocess.run(
        ['oa-skills', 'citadel', 'getMarkdown', '--contentId', str(content_id)],
        capture_output=True, timeout=60
    )
    if result.returncode != 0:
        err = result.stderr.decode('utf-8', errors='replace')[:200]
        raise RuntimeError(f"citadel error: {err}")
    return result.stdout.decode('utf-8', errors='replace')

def extract_llm(title, raw_text):
    prompt = f"""请对以下文章进行信息提取。

文章标题：{title}
文章全文（{len(raw_text)}字）：
{raw_text[:8000]}
{"...（文章后半部分省略）" if len(raw_text) > 8000 else ""}

请严格按JSON格式返回（不要有任何多余文字，summary写成一行不换行）：
{{"summary": "200-500字摘要写成一行", "tags": ["标签1", "标签2", "标签3", "标签4", "标签5"]}}

要求：
- summary体现文章具体内容，不泛泛而谈，写成单行不换行
- tags是具体技术词汇或人名/公司名"""

    out = catclaw_llm.call_llm(prompt, max_tokens=800, temperature=0.2)
    
    # 提取JSON
    m = re.search(r'\{[\s\S]*\}', out)
    if not m:
        raise ValueError(f"LLM输出无JSON: {out[:100]}")
    
    json_str = m.group()
    
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        # 尝试清理后解析
        json_str2 = re.sub(r'[\x00-\x1f\x7f]', ' ', json_str)
        try:
            data = json.loads(json_str2)
        except json.JSONDecodeError:
            # 正则提取fallback
            sum_m = re.search(r'"summary"\s*:\s*"((?:[^"\\]|\\.)*)"\s*[,}]', json_str, re.DOTALL)
            tags_m = re.search(r'"tags"\s*:\s*\[(.*?)\]', json_str, re.DOTALL)
            if sum_m and tags_m:
                summary = sum_m.group(1)
                tags = re.findall(r'"([^"]+)"', tags_m.group(1))
                return summary, tags
            raise ValueError(f"JSON解析彻底失败: {json_str[:100]}")
    
    return data.get('summary', ''), data.get('tags', [])

def find_doc_idx(rebuilt, cid, title):
    # 1. contentId精确匹配
    for i, d in enumerate(rebuilt):
        if str(d.get('contentId', '')) == str(cid):
            return i
    # 2. title精确匹配
    for i, d in enumerate(rebuilt):
        if d.get('title', '') == title:
            return i
    # 3. 前20字模糊匹配
    prefix = title[:20]
    for i, d in enumerate(rebuilt):
        if d.get('title', '').startswith(prefix):
            return i
    return -1

def main():
    missing_36 = [
        ('2751553539', 'OpenClaw龙虾系统专题4'),
        ('2752073271', 'OpenClaw龙虾系统专题5'),
        ('2752212952', 'OpenClaw龙虾系统专题6'),
        ('2752292150', 'OpenClaw龙虾系统专题7'),
        ('2752575346', 'OpenClaw龙虾系统专题8'),
        ('2290737002', '大模型处理时序数据的挑战和方法'),
        ('2397485693', 'OpenAI及Apple近期信息（202407）'),
        ('2411625824', '小模型浪潮'),
        ('2471778177', 'Scaling Law 收益递减的争议和技术探索'),
        ('2524320782', 'OpenAI信息更新20241015'),
        ('2573617039', '近期大模型行业重要信息202411-2'),
        ('2580113283', '豆包大模型在招岗位信息'),
        ('2622291986', '字节Coze/扣子概况'),
        ('2662594004', 'Gemini 2.0 如何映射 DeepMind 的研究路线'),
        ('2698405037', '海外市场进入蓄力期，谷歌、微软开始发力；国内企业多点开花，阿里系表现亮眼'),
        ('2702209638', '谷歌两篇新研究瞩目；推理和 agent 仍是重点'),
        ('2708439983', '周论文推荐：多领域多篇佳作，字节、腾讯持续高产'),
        ('2708977771', '周趋势：OpenAI将发布系列产品；Google Deep Research迎来重大更新；各公司积极拥抱MCP'),
        ('2709082817', '周论文推荐：推理层佳作频出，上海 AI Lab 多篇论文亮眼，字节发布 Seed-Thinking-v1.5'),
        ('2715414694', '周论文推荐：何恺明新研究，英伟达、字节、腾讯等产出佳作，多模态论文频现'),
        ('2715745822', '六月第三周：多模态与 Agent 热持续，OpenAI、MiniMax与月之暗面等接连更新'),
        ('2716784986', 'AI行业月度观察202506'),
        ('2717035867', '周论文推荐：清华强化学习新论文，小红书、字节新研究，Jeff Dean、朱军团队新作，Agent 领域多篇佳作'),
        ('2724182164', '周论文推荐：港大和可灵提出场景一致的交互式视频世界模型，阿里强化学习新研究，字节跳动提出首个大规模动态未来预测'),
        ('2724206028', '八月第四周：开源和多模态的双线主题'),
        ('2724352803', 'AI行业月度观察202508'),
        ('2725071908', '周论文推荐：Snap+CMU 提出可扩展分组推理，DeepMind、微软、苹果、Meta 等新研究，腾讯多智能'),
        ('2725389700', '九月第二周：ChatGPT 宣布支持 MCP，Meta 开源小模型，通义、混元、文心模型连发，支付宝推出国内首'),
        ('2727738797', '周论文推荐：陈怡然团队新作，Meta 论文高产，强化学习多篇研究'),
        ('2730365556', '十月第 4 周：OpenAI 首个 AI 浏览器 ChatGPT Atlas 发布，快手发布 AI 编程产品矩阵'),
        ('2733045029', '二月第三周：海外 AGI 叙事战与开源博弈，国内人才军备化与开源争夺'),
        ('2733134041', '二月第二周：海外重构技术栈，国内聚合新生态'),
        ('2735792255', 'AI行业月度观察202511'),
        ('2745794619', '周论文推荐：可灵提出高效强化学习后训练扩散模型新范式，LeCun、谢赛宁团队新作，腾讯提出推理新框架'),
        ('2745919284', 'AI行业月度观察202601'),
        ('2746288936', '1 月第 5 周：海外平台级 Agent 生态卡位，国产开源反攻与工业化落地并进'),
    ]

    log(f"{'='*60}")
    log(f"补读36篇无raw_text文档 v2 @ {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log(f"总计: {len(missing_36)}篇")

    with open(REBUILT) as f:
        rebuilt = json.load(f)

    success, fail = 0, 0
    fail_list = []
    
    for i, (cid, title) in enumerate(missing_36):
        log(f"\n[{i+1}/{len(missing_36)}] {title[:50]}")
        log(f"  → citadel {cid}")
        try:
            raw = read_citadel(cid)
            raw = raw.strip()
            log(f"  原文: {len(raw)}字")
            if len(raw) < 100:
                raise ValueError(f"原文过短({len(raw)}字)")

            idx = find_doc_idx(rebuilt, cid, title)
            if idx < 0:
                raise ValueError(f"在rebuilt中找不到文档")
            actual_title = rebuilt[idx].get('title', '')
            if actual_title != title:
                log(f"  ⚠️ 模糊匹配到: [{actual_title[:50]}]")

            log(f"  → LLM提取...")
            summary, tags = extract_llm(actual_title, raw)

            if len(summary) < 100:
                log(f"  ⚠️ summary较短({len(summary)}字)")
            log(f"  ✅ sum={len(summary)}字 tags={tags[:3]}...")

            rebuilt[idx]['raw_text'] = raw
            rebuilt[idx]['summary'] = summary
            rebuilt[idx]['tags'] = tags
            rebuilt[idx]['contentId'] = cid
            rebuilt[idx]['qc_status'] = 'filled'
            success += 1

        except Exception as e:
            log(f"  ❌ 失败: {e}")
            fail += 1
            fail_list.append((cid, title[:40], str(e)[:100]))

        if (i+1) % 10 == 0 or (i+1) == len(missing_36):
            with open(REBUILT, 'w') as f:
                json.dump(rebuilt, f, ensure_ascii=False, indent=2)
            log(f"  💾 ckpt {i+1}/{len(missing_36)} 已保存 (success={success}, fail={fail})")

        time.sleep(0.5)

    log(f"\n{'='*60}")
    log(f"✅ 完成: {success}篇成功 / {fail}篇失败")
    
    if fail_list:
        log(f"\n失败列表:")
        for cid, title, err in fail_list:
            log(f"  ❌ {cid} [{title}]: {err}")
    
    # 最终验证
    with open(REBUILT) as f:
        rebuilt_final = json.load(f)
    count_36_with_raw = 0
    for cid, title in missing_36:
        idx = find_doc_idx(rebuilt_final, cid, title)
        if idx >= 0 and rebuilt_final[idx].get('raw_text','').strip():
            count_36_with_raw += 1
    
    total_raw = sum(1 for d in rebuilt_final if d.get('raw_text','').strip())
    log(f"\n最终验证：36篇中有raw_text: {count_36_with_raw}/36")
    log(f"全库有raw_text: {total_raw}/{len(rebuilt_final)}")

if __name__ == '__main__':
    main()
