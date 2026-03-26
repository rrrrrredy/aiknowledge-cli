# 🧠 aiknowledge-cli

> 基于 Friday AI 知识库的问答 CLI — 冷静、精准、有据可查

[![Python](https://img.shields.io/badge/Python-3.9+-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

## 什么是 aiknowledge-cli

一个命令行问答工具，以 203+ 篇 AI/大模型领域的知识库文章为基础，回答你关于 AI 技术、产品、研究的问题。

知识库涵盖：
- **AI 周报/周刊**（持续更新）
- **论文解读**（前沿研究精选）
- **专题研究**（深度分析）
- **龙虾专题**（OpenClaw Agent/Skill 方法论）
- **AI 学习资源**（媒体/博主/课程推荐）

## 快速开始

### 安装

```bash
git clone https://github.com/rrrrrredy/aiknowledge-cli.git
cd aiknowledge-cli
pip install -e .
```

### 配置（可选，不配置则使用摘要检索模式）

```bash
export OPENAI_API_KEY="your-api-key"
export OPENAI_API_BASE="https://api.deepseek.com"   # 默认 DeepSeek
export LLM_MODEL="deepseek-chat"                     # 默认模型
```

支持任何 OpenAI 兼容接口（OpenAI / DeepSeek / Qwen / 本地 Ollama 等）。

### 使用

```bash
# 问答
aiknowledge ask "GPT-4o 和 Claude 3.5 Sonnet 谁更适合代码任务？"
aiknowledge ask "2025年最值得关注的开源模型有哪些？"
aiknowledge ask "RAG 有哪些主要的优化方向？"

# 关键词检索（返回相关文档列表）
aiknowledge search "Manus"
aiknowledge search "多模态"
aiknowledge search "Agent"

# 知识库统计
aiknowledge stats

# 交互模式（持续对话）
aiknowledge
```

### 不配置 API Key 的效果

直接返回知识库中最相关的文档摘要和核心论点，无需 LLM。

## 知识库数据

| 文件 | 说明 |
|------|------|
| `data/knowledge_base.json` | 结构化知识库（文档摘要+论点+实体） |
| `data/nodes.json` | 实体节点（供知识图谱使用） |
| `data/edges.json` | 实体关系（供知识图谱使用） |
| `data/stats.json` | 统计信息 |

## 重新提取（知识库更新时）

```bash
export OPENAI_API_KEY="your-key"
python scripts/enhance_extract.py
```

## 配合知识图谱

知识图谱可视化：https://rrrrrredy.github.io/ai-knowledge-graph/

## License

MIT
