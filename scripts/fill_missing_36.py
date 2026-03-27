#!/usr/bin/env python3
"""
补读36篇无raw_text的文档：
1. 从citadel读原文
2. 验证字数
3. LLM提取摘要+标签
4. 字段验证
5. 写入knowledge_base_rebuilt.json
每10篇设checkpoint
"""
import json, sys, time, re
from datetime import datetime
from pathlib import Path

BASE = Path('/mnt/openclaw/.openclaw/workspace/aiknowledge-cli')
REBUILT = BASE / 'data/knowledge_base_rebuilt.json'
sys.path.insert(0, str(BASE / 'scripts'))
import catclaw_llm

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def read_citadel(content_id):
    """读取citadel原文"""
    import subprocess
    result = subprocess.run(
        ['oa-skills', 'citadel', 'getMarkdown', '--contentId', str(content_id)],
        capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        raise RuntimeError(f"citadel error: {result.stderr[:200]}")
    return result.stdout

def extract_llm(title, raw_text):
    """LLM提取摘要+标签"""
    prompt = f"""请对以下文章进行信息提取。

文章标题：{title}
文章全文（{len(raw_text)}字）：
{raw_text[:8000]}
{"...（文章后半部分省略，以上已覆盖主要内容）" if len(raw_text) > 8000 else ""}

请严格按JSON格式返回（不要有任何多余文字）：
{{
  "summary": "200-500字的摘要，必须包含文章的核心论点、关键数据、主要结论，不能泛泛而谈",
  "tags": ["标签1", "标签2", "标签3", "标签4", "标签5"]
}}

要求：
- summary必须体现这篇文章区别于其他文章的具体内容
- tags必须是具体的技术词汇或人名/公司名，不能是"人工智能"这类大词"""

    out = catclaw_llm.call_llm(prompt, max_tokens=800, temperature=0.2)
    m = re.search(r'\{[\s\S]*\}', out)
    if not m:
        raise ValueError(f"LLM输出无JSON: {out[:100]}")
    data = json.loads(m.group())
    summary = data.get('summary', '')
    tags = data.get('tags', [])
    return summary, tags

def validate(title, raw_text, summary, tags):
    """字段验证"""
    errors = []
    if len(raw_text) < 200: errors.append(f"raw_text太短({len(raw_text)}字)")
    if len(summary) < 150: errors.append(f"summary太短({len(summary)}字)")
    if len(tags) < 3: errors.append(f"tags太少({len(tags)}个)")
    return errors

def main():
    # 需要补读的36篇
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
        ('2709082817', '周论文推荐：推理层佳作频出，上海 AI Lab 多篇论文亮眼，字节发布 Seed-Thinking-v1.5 '),
        ('2715414694', '周论文推荐：何恺明新研究，英伟达、字节、腾讯等产出佳作，多模态论文频现'),
        ('2715745822', '六月第三周：多模态与 Agent 热持续，OpenAI、MiniMax与月之暗面等接连更新，字节、阿里、腾讯逐'),
        ('2716784986', 'AI行业月度观察202506'),
        ('2717035867', '周论文推荐：清华强化学习新论文，小红书、字节新研究，Jeff Dean、朱军团队新作，Agent 领域多篇佳作'),
        ('2724182164', '周论文推荐：港大和可灵提出场景一致的交互式视频世界模型，阿里强化学习新研究，字节跳动提出首个大规模动态未来预测'),
        ('2724206028', '八月第四周：开源和多模态的双线主题'),
        ('2724352803', 'AI行业月度观察202508'),
        ('2725071908', '周论文推荐：Snap+CMU 提出可扩展分组推理，DeepMind、微软、苹果、Meta 等新研究，腾讯多智能'),
        ('2725389700', '九月第二周：ChatGPT 宣布支持 MCP，Meta 开源小模型，通义、混元、文心模型连发，支付宝推出国内首'),
        ('2727738797', '周论文推荐：陈怡然团队新作，Meta 论文高产，强化学习多篇研究'),
        ('2730365556', '十月第 4 周：OpenAI 首个 AI 浏览器 ChatGPT Atlas 发布，快手发布 AI 编程产品矩'),
        ('2733045029', '二月第三周：海外 AGI 叙事战与开源博弈，国内人才军备化与开源争夺'),
        ('2733134041', '二月第二周：海外重构技术栈，国内聚合新生态'),
        ('2735792255', 'AI行业月度观察202511'),
        ('2745794619', '周论文推荐：可灵提出高效强化学习后训练扩散模型新范式，LeCun、谢赛宁团队新作，腾讯提出推理新框架，英伟达多'),
        ('2745919284', 'AI行业月度观察202601'),
        ('2746288936', '1 月第 5 周：海外平台级 Agent 生态卡位，国产开源反攻与工业化落地并进'),
    ]

    log(f"{'='*60}")
    log(f"补读36篇无raw_text文档 @ {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log(f"总计: {len(missing_36)}篇")

    with open(REBUILT) as f:
        rebuilt = json.load(f)
    title_to_idx = {d.get('title',''): i for i, d in enumerate(rebuilt)}

    success, fail = 0, 0
    for i, (cid, title) in enumerate(missing_36):
        log(f"\n[{i+1}/{len(missing_36)}] {title[:50]}")
        log(f"  → citadel {cid}")
        try:
            raw = read_citadel(cid)
            raw = raw.strip()
            log(f"  原文: {len(raw)}字")
            if len(raw) < 100:
                log(f"  ⚠️ 原文过短，跳过")
                fail += 1
                continue

            log(f"  → LLM提取...")
            summary, tags = extract_llm(title, raw)

            errors = validate(title, raw, summary, tags)
            if errors:
                log(f"  ⚠️ 验证警告: {errors}")
            else:
                log(f"  ✅ sum={len(summary)}字 tags={tags}")

            # 写入rebuilt
            idx = title_to_idx.get(title, -1)
            if idx >= 0:
                rebuilt[idx]['raw_text'] = raw
                rebuilt[idx]['summary'] = summary
                rebuilt[idx]['tags'] = tags
                rebuilt[idx]['contentId'] = cid
                rebuilt[idx]['qc_status'] = 'filled'
            else:
                log(f"  ❌ 在rebuilt中找不到文档：{title}")
                fail += 1
                continue

            success += 1
        except Exception as e:
            log(f"  ❌ 失败: {e}")
            fail += 1

        # 每10篇保存一次
        if (i+1) % 10 == 0 or (i+1) == len(missing_36):
            with open(REBUILT, 'w') as f:
                json.dump(rebuilt, f, ensure_ascii=False, indent=2)
            log(f"  💾 ckpt {i+1}/{len(missing_36)} 已保存 (success={success}, fail={fail})")

        time.sleep(1)

    log(f"\n{'='*60}")
    log(f"✅ 完成: {success}篇成功 / {fail}篇失败")

if __name__ == '__main__':
    main()
