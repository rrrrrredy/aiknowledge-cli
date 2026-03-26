"""
CatClaw LLM 调用工具（SSE 流式接口）
复用 kubeplex-maas 的认证 headers，无需额外 API key
"""

import json
import ssl
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional


_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE


def _get_maas_config():
    """从 openclaw.json 读取 kubeplex-maas 配置"""
    config_path = Path.home() / ".openclaw" / "openclaw.json"
    with open(config_path) as f:
        config = json.load(f)
    maas = config.get("models", {}).get("providers", {}).get("kubeplex-maas", {})
    return maas


def call_llm(prompt: str, system: Optional[str] = None, max_tokens: int = 2000, temperature: float = 0.1) -> str:
    """
    调用 CatClaw LLM（SSE 流式，自动拼接完整回答）
    返回完整的文本响应
    """
    maas = _get_maas_config()
    headers = maas.get("headers", {})
    base_url = maas.get("baseUrl", "https://mmc.sankuai.com/openclaw/v1")
    
    messages = []
    if system:
        messages.append({"role": "user", "content": system + "\n\n" + prompt})
    else:
        messages.append({"role": "user", "content": prompt})
    
    payload = {
        "model": "catclaw-proxy-model",
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": True,
    }
    
    url = f"{base_url}/chat/completions"
    data = json.dumps(payload).encode()
    req_headers = {"Content-Type": "application/json", **headers}
    req = urllib.request.Request(url, data=data, headers=req_headers)
    
    full_text = []
    
    with urllib.request.urlopen(req, timeout=60, context=_ssl_ctx) as resp:
        for line in resp:
            line = line.decode("utf-8", errors="replace").strip()
            # SSE 格式: "data:data: {...}" 或 "data: {...}"
            if not line:
                continue
            # 去掉 SSE 前缀
            if line.startswith("data:data:"):
                line = line[len("data:data:"):].strip()
            elif line.startswith("data:"):
                line = line[len("data:"):].strip()
            else:
                continue
            
            if line == "[DONE]":
                break
            
            try:
                chunk = json.loads(line)
                choices = chunk.get("choices", [])
                if choices:
                    delta = choices[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        full_text.append(content)
                    # 检查是否结束
                    if choices[0].get("finish_reason") == "stop":
                        break
            except json.JSONDecodeError:
                continue
    
    return "".join(full_text)


if __name__ == "__main__":
    # 快速测试
    result = call_llm("用一句话描述 GPT-4 的核心能力", max_tokens=100)
    print("测试结果:", result)
