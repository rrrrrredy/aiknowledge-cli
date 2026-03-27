#!/usr/bin/env python3
"""
aiknowledge-cli 主入口
用法：
  aiknowledge ask "问题"       # 单次问答
  aiknowledge search "关键词"  # 关键词检索
  aiknowledge stats            # 知识库统计
  aiknowledge                  # 交互模式
"""

import sys
import os
import argparse
import json
from pathlib import Path

# 确保包路径正确
sys.path.insert(0, str(Path(__file__).parent.parent))

from aiknowledge.retriever import get_kb
from aiknowledge.answerer import answer_with_llm, answer_without_llm, _catclaw_available

BANNER = """
╔══════════════════════════════════════════════════╗
║   🧠  AI Knowledge CLI  v0.1.0                   ║
║   基于 Friday 知识库的 AI 问答工具               ║
╚══════════════════════════════════════════════════╝
输入问题直接回答，输入 /help 查看命令，Ctrl+C 退出
"""

HELP_TEXT = """
命令：
  ask <问题>      提问（默认模式）
  search <词>     关键词检索，返回相关文档列表
  stats           显示知识库统计信息
  /history        显示本次会话问答历史
  /verbose        切换详细模式（显示/隐藏摘要）
  /clear          清空历史记录
  help / /help    显示此帮助
  quit / exit     退出

环境变量：
  OPENAI_API_KEY   LLM API 密钥（支持 DeepSeek/OpenAI 等兼容接口）
  OPENAI_API_BASE  API 地址（默认 https://api.deepseek.com）
  LLM_MODEL        模型名称（默认 deepseek-chat）
  TOP_K            检索文档数量（默认 5）
"""


def cmd_ask(question: str, top_k: int = 5):
    """问答命令"""
    kb = get_kb()
    docs = kb.search(question, top_k=top_k)
    
    if not docs:
        print("❌ 知识库中未找到相关内容。")
        return
    
    has_llm = _catclaw_available or bool(os.environ.get("OPENAI_API_KEY", ""))
    if has_llm:
        print(answer_with_llm(question, docs))
    else:
        print("⚠️  LLM 不可用，使用摘要检索模式\n")
        print(answer_without_llm(question, docs))


def cmd_search(query: str, top_k: int = 8, verbose: bool = True):
    """关键词检索命令"""
    kb = get_kb()
    docs = kb.search(query, top_k=top_k)
    
    if not docs:
        print(f"❌ 未找到与「{query}」相关的文档")
        return
    
    print(f"🔍 找到 {len(docs)} 篇相关文档：\n")
    for i, doc in enumerate(docs):
        title = doc.get("title", "未知")
        date  = doc.get("date", "")
        dtype = doc.get("type", "")
        entities = doc.get("entities", [])
        entities_count = len(entities) if isinstance(entities, list) else sum(len(v) for v in entities.values() if isinstance(v, list))
        
        print(f"  [{i+1}] {title}")
        if date:
            print(f"       📅 {date}  |  类型: {dtype}  |  实体: {entities_count}")
        summary = doc.get("summary", "")
        if summary and verbose:
            # Show full summary in verbose mode
            lines = [summary[j:j+80] for j in range(0, len(summary), 80)]
            print(f"       摘要：{lines[0]}")
            for line in lines[1:3]:
                print(f"             {line}")
        elif not summary and verbose:
            print(f"       摘要：（暂无）")
        print()


def cmd_stats():
    """统计命令"""
    kb = get_kb()
    stats = kb.get_stats()
    
    print("📊 知识库统计\n")
    print(f"  总文档数：{stats.get('total_docs', 0)}")
    print(f"  总节点数：{stats.get('total_nodes', 0)}")
    print(f"  总关系数：{stats.get('total_edges', 0)}")
    
    print("\n  文档类型分布：")
    for dtype, count in sorted(stats.get("doc_types", {}).items(), key=lambda x: -x[1]):
        bar = "█" * min(count, 30)
        print(f"    {dtype:<25} {bar} {count}")
    
    print("\n  实体类型分布：")
    for etype, count in sorted(stats.get("entity_types", {}).items(), key=lambda x: -x[1]):
        bar = "█" * min(count // 5, 30)
        print(f"    {etype:<15} {bar} {count}")


def interactive_mode():
    """交互模式"""
    print(BANNER)
    kb = get_kb()
    stats = kb.get_stats()
    print(f"✅ 知识库已加载：{stats.get('total_docs', 0)} 篇文档，{stats.get('total_nodes', 0)} 个实体\n")
    
    top_k = int(os.environ.get("TOP_K", "5"))
    verbose = True
    history = []  # [(question, answer_snippet)]
    
    while True:
        try:
            user_input = input("❓ > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n👋 再见")
            break
        
        if not user_input:
            continue
        
        low = user_input.lower()
        
        if low in ("/help", "help", "h"):
            print(HELP_TEXT)
        elif low.startswith("/search ") or low.startswith("search "):
            query = user_input.split(" ", 1)[1].strip()
            cmd_search(query, top_k=top_k, verbose=verbose)
        elif low in ("/stats", "stats"):
            cmd_stats()
        elif low == "/history":
            if not history:
                print("  （暂无历史记录）\n")
            else:
                print(f"\n📜 本次会话记录（共 {len(history)} 条）\n")
                for idx, (q, a) in enumerate(history, 1):
                    print(f"  [{idx}] Q: {q}")
                    print(f"      A: {a[:120]}{'…' if len(a) > 120 else ''}\n")
        elif low == "/verbose":
            verbose = not verbose
            print(f"  详细模式：{'开启' if verbose else '关闭'}\n")
        elif low == "/clear":
            history.clear()
            print("  历史已清空\n")
        elif low in ("/quit", "/exit", "quit", "exit", "q"):
            print("👋 再见")
            break
        else:
            # 默认为问答
            print()
            import io
            from contextlib import redirect_stdout
            buf = io.StringIO()
            with redirect_stdout(buf):
                cmd_ask(user_input, top_k=top_k)
            answer_text = buf.getvalue()
            print(answer_text, end="")
            # Record to history
            history.append((user_input, answer_text.strip()))
            print()


def main():
    parser = argparse.ArgumentParser(
        prog="aiknowledge",
        description="AI 知识库问答 CLI — 基于 Friday 知识库",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  aiknowledge ask "GPT-4o 有哪些新特性？"
  aiknowledge search "RAG"
  aiknowledge stats
  aiknowledge                    # 进入交互模式
        """,
    )
    parser.add_argument("command", nargs="?", choices=["ask", "search", "stats"],
                        help="命令（默认进入交互模式）")
    parser.add_argument("query", nargs="?", help="问题或关键词")
    parser.add_argument("--top-k", type=int, default=5, help="检索文档数量（默认 5）")
    parser.add_argument("--no-llm", action="store_true", help="强制使用摘要模式，不调用 LLM")
    parser.add_argument("--verbose", "-v", action="store_true", help="显示文档摘要和详细信息")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出")
    
    args = parser.parse_args()
    
    if args.no_llm:
        os.environ.pop("OPENAI_API_KEY", None)
    
    if args.command == "ask":
        if not args.query:
            parser.error("ask 命令需要提供问题")
        cmd_ask(args.query, top_k=args.top_k)
    elif args.command == "search":
        if not args.query:
            parser.error("search 命令需要提供关键词")
        cmd_search(args.query, top_k=args.top_k * 2, verbose=args.verbose)
    elif args.command == "stats":
        cmd_stats()
    else:
        interactive_mode()


if __name__ == "__main__":
    main()
