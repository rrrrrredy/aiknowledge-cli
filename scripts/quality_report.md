# 质量验证报告 @ 2026-03-27 19:23

验证文档数: 200/263 (有原文+summary)

## 方案C：关键词命中率（全量200篇）
- 平均命中率: **23.5%**
- 命中率>50%（正常）: 35篇
- 命中率30-50%（需关注）: 25篇
- 命中率<30%（高风险）: 140篇

### 高风险文档（命中率<30%）
- [OpenAI近期信息报告-2024年初] hit=13% 缺失关键词: font, size, null, type, table
- [重点公司多模态在招人才分析] hit=13% 缺失关键词: font, null, size, type, attrs
- [多模态系列研究——字节视频生成模型] hit=0% 缺失关键词: font, https, size, sankuai, file
- [GPT-4o团队报告] hit=0% 缺失关键词: font, null, size, type, table
- [模型价格对比] hit=7% 缺失关键词: null, font, type, table, attrs
- [字节AI全景解析] hit=7% 缺失关键词: font, size, type, table, cell
- [大模型降价潮分析] hit=13% 缺失关键词: font, null, size, type, table
- [阿里AI全景解析] hit=27% 缺失关键词: font, size, 阿里在, 年开始, 钉钉
- [Stable Diffusion 生态论文] hit=7% 缺失关键词: https, sankuai, file, contentType, isNewContent
- [360 AI 搜索思路] hit=20% 缺失关键词: 比如, 在这种场景下, agents, 的大模型, prompts
- [小红书AI全景解析] hit=0% 缺失关键词: font, null, type, table, attrs
- [字节AI产品经理访谈] hit=20% 缺失关键词: font, 产品经理的工作内, 产品经理需要具备, 元素, 然而
- [国内大模型公司出海产品] hit=27% 缺失关键词: type, table, cell, attrs, colspan
- [十万卡集群解析] hit=20% 缺失关键词: sankuai, https, file, contentType, isNewContent
- [Kimi推理架构] hit=0% 缺失关键词: null, sankuai, file, https, type
- [快手可灵团队信息] hit=7% 缺失关键词: color, WAIC, 负责人, Haotian, Yang
- [AI搜索产品报告] hit=20% 缺失关键词: font, size, sankuai, https, file
- [AI视频生成市场概况] hit=20% 缺失关键词: null, type, table, attrs, colspan
- [基础模型评估报告] hit=20% 缺失关键词: 风险, https, adalovelaceinstitute, report, under
- [OpenAI、Google及字节近期信息202408] hit=7% 缺失关键词: Greg, null, 亿美金, color, table

## 方案B：LLM交叉验证（抽样25篇）
- pass: 7篇
- warning: 12篇
- fail: 6篇

### Fail文档（需重做）
- [周趋势：海外模型、应用齐发，DeepSeek持续开源，阿里系表现亮眼] score=2/5: 1.【关键错误】Alexa+和Perplexity Comet浏览器的内容在原文前4000字中完全未出现，疑似捏造或幻觉内容；2. Niki Parmar'于去年12月加入'的时间信息在原文截取范围内
- [周论文推荐：推理任务涌现新方法，字节、阿里“互卷”多模态] score=2/5: summary中大量关键内容（COAT方法、席浩诚/韩松/陈键飞、LongPPL/王奕森团队等）在原文提供的前4000字中完全不可见，无法验证真实性，存在严重捏造风险。仅CoE和Mixture-of-
- [2 月第 4 周：海外Agent落地引爆权限悖论，国内垂直模型深耕产业Know-how] score=2/5: summary明显不完整，内容在关键信息介绍OpenAI融资后突然截断，未覆盖原文的绝大多数核心观点：包括Agent范式转变与权限悖论、Anthropic放弃安全承诺、IBM股价暴跌事件、国内垂直模型
- [大模型领域近期热门论文202410-1] score=2/5: 1. 第五部分MixCon关于'大幅优于Jamba、Mixtral等模型'的表述在原文截断处之后，原文无此内容支撑；2. 第六（Janus）、第七（o1推理模式）、第八（MixEval-X）部分在原文
- [重点公司多模态在招人才分析] score=2/5: summary中大量具体数据（薪资40k-65k/16薪、经验3-5年/18个、职位属性19个）及技能要求（CLIP/BLIP/Stable Diffusion/PyTorch等）、核心能力描述（沟通
- [周论文推荐：快手世界模型新论文，CMU 开源首份 Agentic Search 日志数据，] score=2/5: summary中出现的SiameseNorm（清华+阿里千问）内容在原文前4000字中完全未见，疑似捏造；中科院自动化所、字节跳动、微软亚洲研究院等机构也未在原文中出现，属无依据添加；快手世界模型和M

### Warning文档（建议复核）
- [数据标注公司Scale AI研究报告] score=3/5: Summary内容准确，基本事实无误（创始人姓名、年龄、YC背景均正确）。但summary明显不完整，核心理念'数据是新的代码'被截断，未能呈现完整句子。覆盖度严重不足：缺失独角兽估值（73亿美金）、
- [周论文推荐：“Transformer 八子”新论文，快手三篇佳作，MCP 系列论文推荐] score=3/5: Summary内容准确，未捏造信息。但覆盖度不足：原文标题明确提及'Transformer八子新论文'和'快手三篇佳作'，但summary完全未提及这两个重要亮点；MCP系列论文也仅在开头提及但无任何
- [12月第3周：海外 Agent 平台化加速，国内入口与工作流迅速落地] score=3/5: 1.【准确性问题】原文提到Nemotron 3系列为Nano/Super/Ultra三档，但未明确标注'300亿到5000亿'这一参数范围，summary中该数字无法从原文前4000字中得到验证，存在
- [2025 年 AI 行业年度观察] score=3/5: Summary内容准确，未有明显捏造或错误，但严重不完整——原文列出了十大关键判断，summary仅提到'十大关键判断'这一框架性描述，却在'一、竞争范式从'处直接截断，未能呈现任何具体判断的实质内容
- [周论文推荐：OpenAI 提出新的监控性评估框架和指标，深度求索新论文，微信提出扩散语言模] score=3/5: Summary中出现了原文前4000字未涉及的内容：LSTM之父Jürgen Schmidhuber、瑞士AI实验室、极坐标位置嵌入（PoPE）解决RoPE信息纠缠问题，这些内容在提供的原文片段中完全
- [周趋势：7天近20款模型更新，OpenAI、Google、阿里、字节、快手等竞速] score=3/5: 1. o3/o4-mini发布细节（4月17日、约600次工具调用、思维链图像推理）在原文提供的前4000字中无从核实，存在信息来源不明风险；2. 原文前4000字中明确记录的OpenAI'经过验证组
- [七月第一周：Meta 成立「超级智能实验室」，Cursor 发布手机版，豆包上线「深入研究] score=3/5: 1. 准确性存疑：summary中提到'最低消费1000万美元'及'将与Palantir等机构竞争'等具体细节，在原文前4000字中无法核实，存在捏造风险。2. 覆盖度不足：summary明显被截断（
- [本周多模态论文推荐：字节高产，小红书佳作频出；扩散模型迎来多项新研究] score=3/5: Summary包含多项无法在所提供原文（前4000字）中验证的内容：英伟达的ILF和Omni-RGPT两项研究、UC Berkeley与Luma AI的去中心化扩散模型、RegVID-300k数据集等
- [周论文推荐：模型层新方法推荐，快手4篇多模态研究亮眼] score=3/5: 月之暗面Muon优化器的关键数据（AdamW效率2倍、Moonlight 3B/16B参数、5.7万亿tokens训练）及北京大学研究均未出现在给定原文前4000字中，存在信息来源不明或捏造风险；快手
- [LLM 架构范式探索与模型能力的提升] score=3/5: 1.RWKV、AFT、Mamba、RetNet等替代架构的技术细节、Richard Sutton Dynamic DL的Backbone/Fringe划分、「不可能三角」等内容均未出现在给定的4000
- [AI行业月度观察202602] score=3/5: 1.【准确性问题】称中国模型Token调用量'持续扩大领先优势'，原文仅描述'首次超过'，无'持续扩大'依据，属轻微过度延伸；2.【覆盖度不足】开源生态（千问3.5/DeepSeek V4 Lite）
- [周论文推荐：Anthropic 新研究，通义实验室推出智能体系统 AgentEvolver] score=3/5: 准确性方面无明显错误，已提及的内容与原文一致。但summary明显被截断，Anthropic研究部分只介绍了研究背景，未涵盖其三个核心发现（钓鱼执法、黑化现象、疫苗方法），且标题中提及的AgentEv

## 抽样详细结果
- [数据标注公司Scale AI研究报告] B=warning(3/5) C=7% | Summary内容准确，基本事实无误（创始人姓名、年龄、YC背景均正确）。但summary明显不完整，核心理念'数据是新的代码'被截断，未能呈现完整句子。覆盖度
- [周论文推荐：字节、阿里多篇论文发布，DeepSeek、小红书两项研究亮眼] B=pass(4/5) C=7% | Unsloth AI（GRPO优化降低80%内存、7GB VRAM）和上海AI Lab与清华的TTS框架等内容未出现在所提供的原文片段中，无法验证其准确性；但已
- [xAI核心华人报告] B=pass(4/5) C=13% | summary中出现'Tony Wu'作为吴宇怀的别名，原文中并未提及此称呼，属于原文未涵盖的信息，存在轻微捏造风险。其余内容与原文高度一致。
- [周趋势：海外模型、应用齐发，DeepSeek持续开源，阿里系表现亮眼] B=fail(2/5) C=7% | 1.【关键错误】Alexa+和Perplexity Comet浏览器的内容在原文前4000字中完全未出现，疑似捏造或幻觉内容；2. Niki Parmar'于去
- [周论文推荐：推理任务涌现新方法，字节、阿里“互卷”多模态] B=fail(2/5) C=0% | summary中大量关键内容（COAT方法、席浩诚/韩松/陈键飞、LongPPL/王奕森团队等）在原文提供的前4000字中完全不可见，无法验证真实性，存在严重捏
- [周论文推荐：“Transformer 八子”新论文，快手三篇佳作，MCP 系列论文推荐] B=warning(3/5) C=0% | Summary内容准确，未捏造信息。但覆盖度不足：原文标题明确提及'Transformer八子新论文'和'快手三篇佳作'，但summary完全未提及这两个重要亮
- [12月第3周：海外 Agent 平台化加速，国内入口与工作流迅速落地] B=warning(3/5) C=20% | 1.【准确性问题】原文提到Nemotron 3系列为Nano/Super/Ultra三档，但未明确标注'300亿到5000亿'这一参数范围，summary中该数
- [2025 年 AI 行业年度观察] B=warning(3/5) C=0% | Summary内容准确，未有明显捏造或错误，但严重不完整——原文列出了十大关键判断，summary仅提到'十大关键判断'这一框架性描述，却在'一、竞争范式从'处
- [周论文推荐：OpenAI 提出新的监控性评估框架和指标，深度求索新论文，微信提出扩散语言模] B=warning(3/5) C=7% | Summary中出现了原文前4000字未涉及的内容：LSTM之父Jürgen Schmidhuber、瑞士AI实验室、极坐标位置嵌入（PoPE）解决RoPE信息
- [2 月第 4 周：海外Agent落地引爆权限悖论，国内垂直模型深耕产业Know-how] B=fail(2/5) C=7% | summary明显不完整，内容在关键信息介绍OpenAI融资后突然截断，未覆盖原文的绝大多数核心观点：包括Agent范式转变与权限悖论、Anthropic放弃安
- [周趋势：7天近20款模型更新，OpenAI、Google、阿里、字节、快手等竞速] B=warning(3/5) C=13% | 1. o3/o4-mini发布细节（4月17日、约600次工具调用、思维链图像推理）在原文提供的前4000字中无从核实，存在信息来源不明风险；2. 原文前400
- [大模型领域近期热门论文202410-1] B=fail(2/5) C=67% | 1. 第五部分MixCon关于'大幅优于Jamba、Mixtral等模型'的表述在原文截断处之后，原文无此内容支撑；2. 第六（Janus）、第七（o1推理模式
- [七月第一周：Meta 成立「超级智能实验室」，Cursor 发布手机版，豆包上线「深入研究] B=warning(3/5) C=13% | 1. 准确性存疑：summary中提到'最低消费1000万美元'及'将与Palantir等机构竞争'等具体细节，在原文前4000字中无法核实，存在捏造风险。2.
- [本周多模态论文推荐：字节高产，小红书佳作频出；扩散模型迎来多项新研究] B=warning(3/5) C=0% | Summary包含多项无法在所提供原文（前4000字）中验证的内容：英伟达的ILF和Omni-RGPT两项研究、UC Berkeley与Luma AI的去中心化
- [重点公司多模态在招人才分析] B=fail(2/5) C=13% | summary中大量具体数据（薪资40k-65k/16薪、经验3-5年/18个、职位属性19个）及技能要求（CLIP/BLIP/Stable Diffusion
- [OpenAI o1 团队 Noam Brown 访谈] B=pass(5/5) C=33% | OK
- [周论文推荐：模型层新方法推荐，快手4篇多模态研究亮眼] B=warning(3/5) C=13% | 月之暗面Muon优化器的关键数据（AdamW效率2倍、Moonlight 3B/16B参数、5.7万亿tokens训练）及北京大学研究均未出现在给定原文前400
- [大模型领域近期热门论文202411-5] B=pass(4/5) C=27% | Summary在第七条被截断，内容不完整；SmoothCache描述为'缓存机制'是合理推断但原文未明确使用该词；部分细节（如SmoothCache支持图像/视
- [LLM 架构范式探索与模型能力的提升] B=warning(3/5) C=93% | 1.RWKV、AFT、Mamba、RetNet等替代架构的技术细节、Richard Sutton Dynamic DL的Backbone/Fringe划分、「不
- [AI行业月度观察202501] B=pass(5/5) C=20% | OK
- [字节 AI 研发调整继续：吴永辉直接管理范围扩大，AI Lab 3 个方向并入 Seed] B=pass(5/5) C=47% | OK
- [周论文推荐：快手世界模型新论文，CMU 开源首份 Agentic Search 日志数据，] B=fail(2/5) C=13% | summary中出现的SiameseNorm（清华+阿里千问）内容在原文前4000字中完全未见，疑似捏造；中科院自动化所、字节跳动、微软亚洲研究院等机构也未在原
- [AI行业月度观察202602] B=warning(3/5) C=20% | 1.【准确性问题】称中国模型Token调用量'持续扩大领先优势'，原文仅描述'首次超过'，无'持续扩大'依据，属轻微过度延伸；2.【覆盖度不足】开源生态（千问3
- [周论文推荐：Anthropic 新研究，通义实验室推出智能体系统 AgentEvolver] B=warning(3/5) C=13% | 准确性方面无明显错误，已提及的内容与原文一致。但summary明显被截断，Anthropic研究部分只介绍了研究背景，未涵盖其三个核心发现（钓鱼执法、黑化现象、
- [OpenAI近期信息报告-2024年初] B=pass(4/5) C=13% | summary内容准确，但存在两处遗漏：1）六大迭代方法论被截断，仅呈现前两条，后四条未体现；2）未覆盖顶级AI学术会议（NeurIPS/ICML/ICCV）成
