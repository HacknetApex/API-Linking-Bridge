#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API Linking Bridge - Codex Nexus
单文件配置：APIsetting.json（list 结构，每条链路独立端口）
"""

import os
import sys
import json
import time
import webbrowser
import codecs
import uuid
import threading
import queue
import logging
import traceback
import platform
import requests
import tkinter as tk
from tkinter import ttk, messagebox
from flask import Flask, request, Response, jsonify

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# ==================== 版本信息 ====================
VERSION = "26.11.3"
UPDATE_API = "https://apicheckupdate.ctxcode.cn/APILinkingBridge"
HOMEPAGE = "https://alb.ctxcode.cn"
ICON_FILE = "Logo-192x192.ico"   # 窗口/任务栏图标，与脚本同目录

# ==================== 环境与配置 ====================
def resource_path(filename):
    """定位与脚本同目录的静态文件（图标等）。

    - 源码运行：以本 .py 所在目录为基准，与当前工作目录无关；
    - PyInstaller 打包：优先用解包目录 sys._MEIPASS，其次用 exe 所在目录。
    """
    candidates = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            candidates.append(meipass)
        candidates.append(os.path.dirname(os.path.abspath(sys.executable)))
    candidates.append(os.path.dirname(os.path.abspath(__file__)))
    for base in candidates:
        path = os.path.join(base, filename)
        if os.path.exists(path):
            return path
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

def init_environment():
    admin_path = r"C:\Users\Administrator"
    if os.path.exists(admin_path):
        base_dir = os.path.join(admin_path, "APILinkingBridge")
    else:
        base_dir = os.path.join(os.environ.get('USERPROFILE', os.path.expanduser("~")), "APILinkingBridge")
    os.makedirs(base_dir, exist_ok=True)
    return os.path.join(base_dir, "APIsetting.json")

API_FILE = init_environment()


# ==================== 崩溃日志 ====================
BASE_DIR = os.path.dirname(API_FILE)
LOG_DIR = os.path.join(BASE_DIR, "logs")
try:
    os.makedirs(LOG_DIR, exist_ok=True)
except Exception:
    LOG_DIR = BASE_DIR

_LAST_CRASH = {"key": "", "time": 0.0}
_DIALOG_COUNT = {"n": 0}
MAX_CRASH_DIALOGS = 3          # 一次运行最多弹 3 个错误窗，避免刷屏
_LOG_SINK = None               # 由 install_crash_handlers 绑定到界面日志


def ui_log(text, level="info"):
    """把消息送到界面日志（后台线程安全）；界面还没起来时静默忽略。"""
    sink = _LOG_SINK
    if sink is None:
        return
    try:
        sink(text, level)
    except Exception:
        pass


def _write_crash_log(exc_type, exc, tb, context="GUI", recent=None):
    """把一次异常写进 logs 目录，返回日志文件绝对路径。自身绝不抛异常。"""
    path = ""
    try:
        now = time.localtime()
        name = "crash-%s-%03d-%d.log" % (
            time.strftime("%Y%m%d-%H%M%S", now),
            int((time.time() % 1) * 1000),
            os.getpid(),
        )
        path = os.path.join(LOG_DIR, name)
        lines = [
            "=" * 78,
            " API Linking Bridge 崩溃日志 / Crash Report",
            "=" * 78,
            "时间      : %s" % time.strftime("%Y-%m-%d %H:%M:%S", now),
            "版本      : %s" % VERSION,
            "界面      : %s" % (context or "unknown"),
            "Python    : %s (%s)" % (sys.version.split()[0], platform.machine()),
            "系统      : %s" % platform.platform(),
            "进程 ID   : %s" % os.getpid(),
            "当前目录  : %s" % os.getcwd(),
            "配置目录  : %s" % BASE_DIR,
            "=" * 78,
            "",
            "------------- 调用栈 / Traceback -------------",
            "".join(traceback.format_exception(exc_type, exc, tb)).rstrip(),
            "",
        ]
        if recent:
            lines.append("------------- 最近的界面日志 / Recent Logs -------------")
            lines.extend(str(x) for x in recent)
            lines.append("")
        with open(path, "w", encoding="utf-8", errors="replace") as f:
            f.write("\n".join(lines) + "\n")
        # 只保留最近 50 个崩溃日志，避免目录无限膨胀
        try:
            olds = sorted(
                (os.path.join(LOG_DIR, f) for f in os.listdir(LOG_DIR)
                 if f.startswith("crash-") and f.endswith(".log")),
                key=os.path.getmtime)
            for old in olds[:-50]:
                if old != path:
                    try:
                        os.remove(old)
                    except Exception:
                        pass
        except Exception:
            pass
    except Exception:
        path = path or "(日志写入失败)"
    return path


def install_crash_handlers(root=None, app=None):
    """接管未捕获异常：写日志、弹窗提示路径，但窗口不退出。"""
    global _LOG_SINK
    _LOG_SINK = lambda text, level="info": UI_QUEUE.put(
        ("log_err" if level == "err" else "log", text))

    def _recent():
        # Tk 控件只能在主线程访问，后台线程出错时跳过界面日志
        if threading.current_thread() is not threading.main_thread():
            return []
        try:
            if app is not None and getattr(app, "log_text", None) is not None:
                return app.log_text.get("1.0", "end").splitlines()[-60:]
        except Exception:
            return []
        return []

    def _notify(text, path):
        try:
            messagebox.showerror(
                "发生错误（程序不会退出）",
                text + "\n\n错误日志已保存到：\n" + path +
                "\n\n可以把该文件发给开发者分析。",
                parent=root,
            )
        except Exception:
            pass

    def handle(exc_type, exc, tb, context, show_dialog=True):
        if exc_type in (KeyboardInterrupt, SystemExit):
            return ""
        path = _write_crash_log(exc_type, exc, tb, context, _recent())
        msg = "%s: %s" % (exc_type.__name__, exc)
        try:
            if app is not None:
                if threading.current_thread() is threading.main_thread():
                    app.log("发生错误：%s" % msg, is_err=True)
                    app.log("错误日志已保存：%s" % path, is_err=True)
                else:
                    # 后台线程不能碰 Tk，走队列交给主线程显示
                    UI_QUEUE.put(("log_err", "发生错误：%s" % msg))
                    UI_QUEUE.put(("log_err", "错误日志已保存：%s" % path))
        except Exception:
            pass
        # 同一类错误 30 秒内只弹一次窗，避免卡死操作
        now = time.time()
        key = "%s|%s" % (exc_type.__name__, str(exc))
        if (show_dialog and _DIALOG_COUNT["n"] < MAX_CRASH_DIALOGS and
                not (key == _LAST_CRASH["key"] and
                     now - _LAST_CRASH["time"] < 30)):
            _LAST_CRASH["key"] = key
            _LAST_CRASH["time"] = now
            _DIALOG_COUNT["n"] += 1
            _notify("程序捕获到一个错误，已继续运行。\n\n" + msg, path)
        return path

    def hook(exc_type, exc, tb):
        handle(exc_type, exc, tb, "GUI 主线程")

    sys.excepthook = hook

    if hasattr(threading, "excepthook"):
        def thook(args):
            if args.exc_type in (KeyboardInterrupt, SystemExit):
                return
            name = args.thread.name if args.thread else "后台线程"
            handle(args.exc_type, args.exc_value, args.exc_traceback,
                   "后台线程 %s" % name, show_dialog=False)
        threading.excepthook = thook

    if root is not None:
        def tk_hook(exc_type, exc, tb):
            handle(exc_type, exc, tb, "GUI 回调（tkinter）")
        root.report_callback_exception = tk_hook

    return handle


# Base URL 会被后端直接用 f"{apiURL}{path}" 拼接，因此：
#   1) 必须自带 /v1（或平台自己的版本前缀，如千帆 /v2、火山 /api/v3）；
#   2) 结尾不能有斜杠，否则会拼出 //chat/completions。
# 直连模式（ExChangeModel=direct）走 /responses，只有原生支持 Responses API 的
# 上游（OpenAI 官方、Azure OpenAI、LiteLLM 等）才能用，其余请选“转译”模式。
PROVIDERS = {
    "自定义 (Custom)": "",

    # ---------- 原有内置 ----------
    "NVIDIA": "https://integrate.api.nvidia.com/v1",
    "DeepSeek": "https://api.deepseek.com/v1",
    "OpenAI": "https://api.openai.com/v1",
    "Moonshot (Kimi)": "https://api.moonshot.cn/v1",
    "Aliyun (Qwen)": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "Zhipu (GLM)": "https://open.bigmodel.cn/api/paas/v4",
    "Groq": "https://api.groq.com/openai/v1",

    # ---------- 国内厂商 ----------
    "[国内] Moonshot (Kimi) 国际版": "https://api.moonshot.ai/v1",
    "[国内] Zhipu (GLM) 国际版": "https://api.z.ai/api/paas/v4",
    "[国内] Aliyun (Qwen) 国际站": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    "[国内] Aliyun (Qwen) 美国站": "https://dashscope-us.aliyuncs.com/compatible-mode/v1",
    "[国内] SiliconFlow 硅基流动": "https://api.siliconflow.cn/v1",
    "[国内] Volcengine Ark 火山方舟": "https://ark.cn-beijing.volces.com/api/v3",
    "[国内] Baidu Qianfan 百度千帆": "https://qianfan.baidubce.com/v2",
    "[国内] Tencent Hunyuan 腾讯混元": "https://api.hunyuan.cloud.tencent.com/v1",
    "[国内] iFlytek Spark 讯飞星火": "https://spark-api-open.xf-yun.com/v1",
    "[国内] MiniMax": "https://api.minimaxi.com/v1",
    "[国内] MiniMax 国际版": "https://api.minimax.io/v1",
    "[国内] StepFun 阶跃星辰": "https://api.stepfun.com/v1",
    "[国内] 01.AI 零一万物": "https://api.lingyiwanwu.com/v1",
    "[国内] Baichuan 百川智能": "https://api.baichuan-ai.com/v1",
    "[国内] SenseNova 商汤日日新": "https://api.sensenova.cn/compatible-mode/v1",
    "[国内] Infini 无问芯穹": "https://cloud.infini-ai.com/maas/v1",

    # ---------- 海外厂商 ----------
    "[海外] xAI (Grok)": "https://api.x.ai/v1",
    "[海外] Mistral": "https://api.mistral.ai/v1",
    "[海外] Together AI": "https://api.together.xyz/v1",
    "[海外] Fireworks AI": "https://api.fireworks.ai/inference/v1",
    "[海外] DeepInfra": "https://api.deepinfra.com/v1/openai",
    # Perplexity 没有 /v1 前缀，且不实现 GET /models，“测试连接”会报失败但聊天可用
    "[海外] Perplexity": "https://api.perplexity.ai",
    "[海外] Cerebras": "https://api.cerebras.ai/v1",
    "[海外] SambaNova": "https://api.sambanova.ai/v1",
    "[海外] Nebius Token Factory": "https://api.tokenfactory.nebius.com/v1",
    "[海外] Hyperbolic": "https://api.hyperbolic.xyz/v1",
    "[海外] Novita AI": "https://api.novita.ai/openai/v1",
    "[海外] Lambda Inference": "https://api.lambda.ai/v1",
    "[海外] Google Gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
    "[海外] Cohere": "https://api.cohere.ai/compatibility/v1",

    # ---------- 聚合网关 / 云平台 ----------
    "[聚合] OpenRouter": "https://openrouter.ai/api/v1",
    "[聚合] AIML API": "https://api.aimlapi.com/v1",
    "[聚合] Requesty": "https://router.requesty.ai/v1",
    "[聚合] GitHub Models": "https://models.inference.ai.azure.com",
    # 需把 {ACCOUNT_ID} 换成 Cloudflare 账户 ID
    "[聚合] Cloudflare Workers AI": "https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/v1",
    # 本脚本只发 Authorization: Bearer，Azure 需要 api-key 头 + ?api-version=，直接填会 401/404
    "[聚合] Azure OpenAI (需 api-key 头, 本脚本不适配)": "https://{resource}.openai.azure.com/openai/deployments/{deployment}",

    # ---------- 本地 / 自建 ----------
    "[本地] Ollama": "http://localhost:11434/v1",
    "[本地] LM Studio": "http://localhost:1234/v1",
    "[本地] vLLM": "http://localhost:8000/v1",
    "[本地] llama.cpp": "http://localhost:8080/v1",
    "[本地] LocalAI": "http://localhost:8080/v1",
    "[本地] Xinference": "http://localhost:9997/v1",
    "[本地] LiteLLM Proxy": "http://localhost:4000/v1",
    "[本地] One API / New API": "http://localhost:3000/v1",
}

def load_json(path, default_data):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default_data, f, indent=4, ensure_ascii=False)
        return default_data
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else default_data
    except Exception:
        return default_data

def migrate_legacy_config(data, path):
    """旧版 APIsetting.json 是 {url, key, mode, disable_tools, links} 字典，这里转成 list。"""
    links = []
    legacy = data.get("links") if isinstance(data, dict) else None
    if isinstance(legacy, dict):
        for i, (name, v) in enumerate(legacy.items(), 1):
            if not isinstance(v, dict):
                continue
            links.append({
                "name": name or f"Link{i}",
                "apiURL": v.get("url", v.get("apiURL", "")),
                "apiKey": v.get("key", v.get("apiKey", "")),
                "model": v.get("model", ""),
                "ListenPort": int(v.get("ListenPort", 15720 + i)),
                "disable_tools": bool(v.get("disable_tools", False)),
                "ExChangeModel": "direct" if v.get("mode") == "direct" else "translation",
            })
    if not links and (data.get("url") or data.get("key")):
        # 不从旧的 AppearanceSetting.json 里继承模型名：那是上一个服务商的模型，
        # 套到当前 Base URL 上会 404。留空由用户在界面上填写。
        default_model = data.get("model") or ""
        links.append({
            "name": "默认链路",
            "apiURL": data.get("url", ""),
            "apiKey": data.get("key", ""),
            "model": default_model,
            "ListenPort": 15721,
            "disable_tools": bool(data.get("disable_tools", False)),
            "ExChangeModel": "direct" if data.get("mode") == "direct" else "translation",
        })
    return links

def save_links(links):
    with open(API_FILE, "w", encoding="utf-8") as f:
        json.dump(links, f, indent=4, ensure_ascii=False)

def load_links():
    """读取链路列表；若遇到旧版字典格式，自动迁移并备份原文件。"""
    if not os.path.exists(API_FILE):
        return []
    try:
        with open(API_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    if isinstance(data, list):
        return data
    migrated = migrate_legacy_config(data, API_FILE)
    try:
        with open(API_FILE + ".bak", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        save_links(migrated)
    except Exception:
        pass
    return migrated

# ==================== 核心代理状态 ====================
PROXY_APP = Flask(__name__)
UI_QUEUE = queue.Queue()
GLOBAL_STATS = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0,
                "requests": 0, "missing": 0}

PROXY_STATE = {"active_link": None, "config": {}, "server": None, "thread": None}


@PROXY_APP.errorhandler(Exception)
def _proxy_internal_error(e):
    """请求处理中的异常：写日志、保持服务运行、把日志路径回显给客户端。"""
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        return e
    path = _write_crash_log(type(e), e, e.__traceback__, "HTTP 请求处理",
                            ["%s %s" % (request.method, request.path)])
    ui_log("请求处理出错：%s: %s" % (type(e).__name__, e), "err")
    ui_log("错误日志已保存：%s" % path, "err")
    return jsonify({
        "error": {
            "message": "服务内部错误，详细信息见日志文件：%s" % path,
            "type": "internal_error",
        }
    }), 500


def get_active_config():
    return PROXY_STATE.get("config", {})

# ---------- 协议转换 ----------
def convert_tools_for_chat(tools):
    if not tools:
        return []
    chat_tools = []
    for t in tools:
        if not isinstance(t, dict):
            continue
        t_type = t.get("type", "")
        nested = t.get("function") if isinstance(t.get("function"), dict) else {}
        name = (t.get("name") or nested.get("name") or "").strip()
        description = t.get("description") or nested.get("description") or ""
        parameters = t.get("parameters") or nested.get("parameters")
        if t_type == "function":
            if not parameters:
                parameters = {"type": "object", "properties": {}}
            if not name:
                continue
            chat_tools.append({"type": "function", "function": {"name": name, "description": description, "parameters": parameters}})
        elif t_type == "custom":
            if not name:
                continue
            chat_tools.append({"type": "function", "function": {"name": name, "description": description, "parameters": parameters or {"type": "object", "properties": {"input": {"type": "string"}}}}})
        elif t_type == "web_search":
            chat_tools.append({"type": "function", "function": {"name": "web_search", "description": "Search the web", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}}}})
        else:
            if name:
                chat_tools.append({"type": "function", "function": {"name": name, "description": description, "parameters": parameters or {"type": "object", "properties": {}}}})
    return chat_tools

def responses_to_chat(payload, default_model="gpt-4o", disable_tools=False, model_override=""):
    model = model_override or payload.get("model") or default_model
    messages = []
    if payload.get("instructions"):
        messages.append({"role": "system", "content": payload["instructions"]})
    raw_input = payload.get("input")
    if isinstance(raw_input, str):
        messages.append({"role": "user", "content": raw_input})
    elif isinstance(raw_input, list):
        for item in raw_input:
            if not isinstance(item, dict):
                continue
            item_type = item.get("type")
            if item_type in (None, "message"):
                role = item.get("role", "user")
                content = item.get("content", "")
                if isinstance(content, list):
                    parts = []
                    for c in content:
                        if isinstance(c, dict):
                            if c.get("type") in ("input_text", "output_text", "text"):
                                parts.append({"type": "text", "text": c.get("text", "")})
                            elif c.get("type") in ("input_image", "image_url"):
                                url = c.get("image_url")
                                if isinstance(url, dict):
                                    url = url.get("url")
                                if url:
                                    parts.append({"type": "image_url", "image_url": {"url": url}})
                    content = parts if parts else ""
                messages.append({"role": role, "content": content})
            elif item_type == "function_call":
                # 助手发起的工具调用：必须还原成 assistant.tool_calls，
                # 否则下一轮的 tool 消息会对应不到任何调用，严格的上游会直接 400
                call = {
                    "id": item.get("call_id") or item.get("id") or ("call_" + uuid.uuid4().hex),
                    "type": "function",
                    "function": {
                        "name": item.get("name", ""),
                        "arguments": item.get("arguments") or "{}",
                    },
                }
                if messages and messages[-1].get("role") == "assistant":
                    messages[-1].setdefault("tool_calls", []).append(call)
                    if messages[-1].get("content") == "":
                        messages[-1]["content"] = None
                else:
                    messages.append({"role": "assistant", "content": None, "tool_calls": [call]})
            elif item_type == "function_call_output":
                output = item.get("output", "")
                if not isinstance(output, str):
                    output = json.dumps(output, ensure_ascii=False)
                messages.append({"role": "tool", "tool_call_id": item.get("call_id", ""), "content": output})
            # reasoning 等其它条目直接忽略

    chat = {"model": model, "messages": messages, "stream": bool(payload.get("stream", False))}
    if payload.get("temperature") is not None:
        chat["temperature"] = payload["temperature"]
    if payload.get("top_p") is not None:
        chat["top_p"] = payload["top_p"]
    if payload.get("max_output_tokens"):
        chat["max_tokens"] = payload["max_output_tokens"]

    if not disable_tools:
        chat_tools = convert_tools_for_chat(payload.get("tools"))
        if chat_tools:
            chat["tools"] = chat_tools
    return chat

def sse(event_type, data):
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

def stream_chat_to_responses(upstream, model, response_id):
    created_at = int(time.time())
    yield sse("response.created", {"type": "response.created", "response": {"id": response_id, "object": "response", "created_at": created_at, "status": "in_progress", "model": model, "output": []}})

    output_index = 0
    output_items = []
    usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    reasoning_started, reasoning_text, reasoning_id = False, "", "rs_" + uuid.uuid4().hex
    text_started, content_text, text_id = False, "", "msg_" + uuid.uuid4().hex
    tool_buffers = {}
    last_data_time = time.time()
    # 增量解码器 + 行缓冲：跨块的 UTF-8 字符与半行 JSON 都不会再被丢弃
    decoder = codecs.getincrementaldecoder("utf-8")("replace")
    buffer = ""
    finished = False
    usage_seen = False

    for raw_bytes in upstream.iter_content(chunk_size=1024):
        if not raw_bytes:
            continue
        if time.time() - last_data_time > 3:
            yield ": keep-alive\n\n"
            last_data_time = time.time()
        buffer += decoder.decode(raw_bytes)
        if "\n" not in buffer:
            continue
        lines = buffer.split("\n")
        buffer = lines.pop()  # 最后一段可能是半行，留到下一块再拼
        for line in lines:
            line = line.strip()
            if not line.startswith("data:"):
                continue
            data_str = line[5:].strip()
            if data_str == "[DONE]":
                finished = True
                break
            try:
                chunk = json.loads(data_str)
            except Exception:
                continue
            last_data_time = time.time()

            if chunk.get("usage"):
                u = chunk["usage"]
                usage = {"input_tokens": u.get("prompt_tokens", 0) or 0,
                         "output_tokens": u.get("completion_tokens", 0) or 0,
                         "total_tokens": u.get("total_tokens", 0) or 0}
                usage_seen = True
                UI_QUEUE.put(("stats", {"input": usage["input_tokens"], "output": usage["output_tokens"], "total": usage["total_tokens"]}))

            for choice in chunk.get("choices") or []:
                delta = choice.get("delta") or {}

                reasoning = delta.get("reasoning_content") or delta.get("reasoning")
                if reasoning and not text_started:
                    if not reasoning_started:
                        reasoning_started = True
                        yield sse("response.output_item.added", {"type": "response.output_item.added", "output_index": output_index, "item": {"type": "reasoning", "id": reasoning_id, "summary": []}})
                        yield sse("response.reasoning_summary_part.added", {"type": "response.reasoning_summary_part.added", "item_id": reasoning_id, "output_index": output_index, "summary_index": 0, "part": {"type": "summary_text", "text": ""}})
                    reasoning_text += reasoning
                    yield sse("response.reasoning_summary_text.delta", {"type": "response.reasoning_summary_text.delta", "item_id": reasoning_id, "output_index": output_index, "summary_index": 0, "delta": reasoning})

                content = delta.get("content")
                if content:
                    if reasoning_started and not text_started:
                        reasoning_item = {"type": "reasoning", "id": reasoning_id, "summary": [{"type": "summary_text", "text": reasoning_text}]}
                        yield sse("response.reasoning_summary_text.done", {"type": "response.reasoning_summary_text.done", "item_id": reasoning_id, "output_index": output_index, "summary_index": 0, "text": reasoning_text})
                        yield sse("response.reasoning_summary_part.done", {"type": "response.reasoning_summary_part.done", "item_id": reasoning_id, "output_index": output_index, "summary_index": 0, "part": {"type": "summary_text", "text": reasoning_text}})
                        yield sse("response.output_item.done", {"type": "response.output_item.done", "output_index": output_index, "item": reasoning_item})
                        output_items.append(reasoning_item)
                        output_index += 1
                        reasoning_started = False

                    if not text_started:
                        text_started = True
                        yield sse("response.output_item.added", {"type": "response.output_item.added", "output_index": output_index, "item": {"type": "message", "id": text_id, "role": "assistant", "status": "in_progress", "phase": "final_answer", "content": []}})
                        yield sse("response.content_part.added", {"type": "response.content_part.added", "item_id": text_id, "output_index": output_index, "content_index": 0, "part": {"type": "output_text", "text": "", "annotations": []}})

                    content_text += content
                    yield sse("response.output_text.delta", {"type": "response.output_text.delta", "item_id": text_id, "output_index": output_index, "content_index": 0, "delta": content})

                tcs = delta.get("tool_calls")
                if tcs and isinstance(tcs, list):
                    for tc in tcs:
                        idx = tc.get("index", 0)
                        buf = tool_buffers.setdefault(idx, {"id": None, "name": "", "arguments": ""})
                        if tc.get("id"):
                            buf["id"] = tc["id"]
                        fn = tc.get("function") or {}
                        if fn.get("name") and not buf["name"]:
                            buf["name"] = fn["name"]
                        if fn.get("arguments"):
                            buf["arguments"] += fn["arguments"]
        if finished:
            break

    if reasoning_started:
        reasoning_item = {"type": "reasoning", "id": reasoning_id, "summary": [{"type": "summary_text", "text": reasoning_text}]}
        yield sse("response.reasoning_summary_text.done", {"type": "response.reasoning_summary_text.done", "item_id": reasoning_id, "output_index": output_index, "summary_index": 0, "text": reasoning_text})
        yield sse("response.reasoning_summary_part.done", {"type": "response.reasoning_summary_part.done", "item_id": reasoning_id, "output_index": output_index, "summary_index": 0, "part": {"type": "summary_text", "text": reasoning_text}})
        yield sse("response.output_item.done", {"type": "response.output_item.done", "output_index": output_index, "item": reasoning_item})
        output_items.append(reasoning_item)
        output_index += 1

    if text_started:
        message_item = {"type": "message", "id": text_id, "role": "assistant", "status": "completed", "phase": "final_answer", "content": [{"type": "output_text", "text": content_text, "annotations": []}]}
        yield sse("response.output_text.done", {"type": "response.output_text.done", "item_id": text_id, "output_index": output_index, "content_index": 0, "text": content_text})
        yield sse("response.content_part.done", {"type": "response.content_part.done", "item_id": text_id, "output_index": output_index, "content_index": 0, "part": {"type": "output_text", "text": content_text, "annotations": []}})
        yield sse("response.output_item.done", {"type": "response.output_item.done", "output_index": output_index, "item": message_item})
        output_items.append(message_item)
        output_index += 1

    for idx in sorted(tool_buffers.keys()):
        buf = tool_buffers[idx]
        if not buf["name"]:
            continue
        cid = buf["id"] or "call_" + uuid.uuid4().hex
        fid = "fc_" + uuid.uuid4().hex
        fc_item = {"type": "function_call", "id": fid, "call_id": cid, "name": buf["name"], "arguments": buf["arguments"] or "{}", "status": "completed"}
        yield sse("response.output_item.added", {"type": "response.output_item.added", "output_index": output_index, "item": {"type": "function_call", "id": fid, "call_id": cid, "name": buf["name"], "arguments": "", "status": "in_progress"}})
        yield sse("response.function_call_arguments.delta", {"type": "response.function_call_arguments.delta", "item_id": fid, "output_index": output_index, "delta": buf["arguments"]})
        yield sse("response.function_call_arguments.done", {"type": "response.function_call_arguments.done", "item_id": fid, "output_index": output_index, "arguments": buf["arguments"]})
        yield sse("response.output_item.done", {"type": "response.output_item.done", "output_index": output_index, "item": fc_item})
        output_items.append(fc_item)
        output_index += 1

    if not usage_seen:
        UI_QUEUE.put(("stats", None))
    yield sse("response.completed", {"type": "response.completed", "response": {"id": response_id, "object": "response", "created_at": created_at, "status": "completed", "model": model, "output": output_items, "usage": usage}})

def chat_to_responses(chat, model, response_id):
    """把非流式的 chat.completion 转成 Responses API 对象。"""
    created_at = int(time.time())
    output = []
    choices = chat.get("choices") or [{}]
    msg = (choices[0] or {}).get("message") or {}

    reasoning = msg.get("reasoning_content") or msg.get("reasoning")
    if reasoning:
        output.append({"type": "reasoning", "id": "rs_" + uuid.uuid4().hex,
                       "summary": [{"type": "summary_text", "text": reasoning}]})

    content = msg.get("content")
    if content:
        output.append({"type": "message", "id": "msg_" + uuid.uuid4().hex, "role": "assistant",
                       "status": "completed",
                       "content": [{"type": "output_text", "text": content, "annotations": []}]})

    for tc in msg.get("tool_calls") or []:
        fn = tc.get("function") or {}
        output.append({"type": "function_call", "id": "fc_" + uuid.uuid4().hex,
                       "call_id": tc.get("id") or ("call_" + uuid.uuid4().hex),
                       "name": fn.get("name", ""),
                       "arguments": fn.get("arguments") or "{}",
                       "status": "completed"})

    u = chat.get("usage") or {}
    return {"id": response_id, "object": "response", "created_at": created_at,
            "status": "completed", "model": model, "output": output,
            "usage": {"input_tokens": u.get("prompt_tokens", 0) or 0,
                      "output_tokens": u.get("completion_tokens", 0) or 0,
                      "total_tokens": u.get("total_tokens", 0) or 0}}

def api_base(api):
    """取 Base URL 并去掉结尾的斜杠。

    后端是直接用 f"{apiURL}{path}" 拼接的，用户手输 "https://x/v1/" 会拼出
    "https://x/v1//chat/completions"，多数上游直接 404，所以统一在这里归一化。
    """
    return (api.get("apiURL") or "").strip().rstrip("/")

def _post_upstream(api, path, body, stream):
    """向upstream发请求。

    流式请求会带上 stream_options.include_usage，让服务商在最后一个 chunk 里回报
    真实 token 用量（不带你永远只能统计到 0）。有的服务商不认这个字段会 400，
    这时自动去掉它重试一次。
    """
    headers = {"Authorization": f"Bearer {api['apiKey']}", "Content-Type": "application/json"}
    body = dict(body)
    if stream:
        opts = dict(body.get("stream_options") or {})
        opts["include_usage"] = True
        body["stream_options"] = opts
    upstream = requests.post(f"{api_base(api)}{path}", headers=headers, json=body, stream=stream, timeout=600)
    if stream and upstream.status_code != 200 and "stream_options" in body:
        upstream.close()
        body.pop("stream_options", None)
        UI_QUEUE.put(("log", "上游不支持 stream_options，已退回普通流式（token 用量可能拿不到）"))
        upstream = requests.post(f"{api_base(api)}{path}", headers=headers, json=body, stream=stream, timeout=600)
    return upstream

def _push_stats(data):
    u = (data or {}).get("usage") or {}
    if not u:
        UI_QUEUE.put(("stats", None))
        return
    inp = u.get("prompt_tokens", u.get("input_tokens", 0)) or 0
    out = u.get("completion_tokens", u.get("output_tokens", 0)) or 0
    tot = u.get("total_tokens", 0) or 0
    if not tot:
        tot = inp + out
    UI_QUEUE.put(("stats", {"input": inp, "output": out, "total": tot}))

@PROXY_APP.route("/v1/responses", methods=["POST"])
def handle_responses():
    api = get_active_config()
    if not api:
        return jsonify({"error": "请先在软件首页开启一条链路"}), 403

    payload = request.get_json(force=True, silent=True) or {}
    UI_QUEUE.put(("anim_start", None))

    model_override = (api.get("model") or "").strip()
    stream = bool(payload.get("stream", False))

    if api.get("ExChangeModel") == "direct":
        if model_override:
            payload["model"] = model_override
        try:
            upstream = _post_upstream(api, "/responses", payload, stream)
        except Exception as e:
            UI_QUEUE.put(("anim_end", None))
            return jsonify({"error": f"网络异常: {e}"}), 502

        if upstream.status_code != 200:
            UI_QUEUE.put(("anim_end", None))
            UI_QUEUE.put(("log_err", f"上游直连拒绝 {upstream.status_code}: {upstream.text[:300]}"))
            return jsonify({"error": upstream.text}), upstream.status_code

        if not stream:
            UI_QUEUE.put(("anim_end", None))
            try:
                data = upstream.json()
            except Exception:
                data = {}
            upstream.close()
            _push_stats(data)
            return jsonify(data)

        def direct_gen():
            decoder = codecs.getincrementaldecoder("utf-8")("replace")
            buffer = ""
            usage_seen = False
            try:
                for c in upstream.iter_content(chunk_size=1024):
                    if not c:
                        continue
                    yield c
                    buffer += decoder.decode(c)
                    if "\n" not in buffer:
                        continue
                    lines = buffer.split("\n")
                    buffer = lines.pop()
                    for line in lines:
                        line = line.strip()
                        if not line.startswith("data:"):
                            continue
                        try:
                            obj = json.loads(line[5:].strip())
                        except Exception:
                            continue
                        resp = obj.get("response") if isinstance(obj, dict) else None
                        if isinstance(resp, dict) and resp.get("usage"):
                            usage_seen = True
                            _push_stats(resp)
                if not usage_seen:
                    UI_QUEUE.put(("stats", None))
            finally:
                upstream.close()
                UI_QUEUE.put(("anim_end", None))

        return Response(direct_gen(), status=200, mimetype="text/event-stream")

    try:
        chat_req = responses_to_chat(payload, disable_tools=api.get("disable_tools", False), model_override=model_override)
    except Exception as e:
        UI_QUEUE.put(("anim_end", None))
        return jsonify({"error": f"参数转换失败: {e}"}), 400

    stream = chat_req.get("stream", False)

    try:
        upstream = _post_upstream(api, "/chat/completions", chat_req, stream)
    except Exception as e:
        UI_QUEUE.put(("anim_end", None))
        return jsonify({"error": f"网络异常: {e}"}), 502

    if upstream.status_code != 200:
        UI_QUEUE.put(("anim_end", None))
        err_text = upstream.text
        UI_QUEUE.put(("log_err", f"上游报错 {upstream.status_code}: {err_text[:300]}"))
        return jsonify({"error": err_text}), upstream.status_code

    response_id = "resp_" + uuid.uuid4().hex

    if not stream:
        try:
            chat_resp = upstream.json()
        except Exception:
            chat_resp = {}
        upstream.close()
        UI_QUEUE.put(("anim_end", None))
        _push_stats(chat_resp)
        return jsonify(chat_to_responses(chat_resp, chat_req["model"], response_id))

    def generate():
        try:
            for chunk in stream_chat_to_responses(upstream, chat_req["model"], response_id):
                yield chunk
        finally:
            upstream.close()
            UI_QUEUE.put(("anim_end", None))

    return Response(generate(), status=200, mimetype="text/event-stream")

@PROXY_APP.route("/v1/chat/completions", methods=["POST"])
def handle_chat_completions():
    """给普通 OpenAI 风格客户端用的直通接口。"""
    api = get_active_config()
    if not api:
        return jsonify({"error": "请先在软件首页开启一条链路"}), 403

    payload = request.get_json(force=True, silent=True) or {}
    UI_QUEUE.put(("anim_start", None))

    model_override = (api.get("model") or "").strip()
    if model_override:
        payload["model"] = model_override

    stream = bool(payload.get("stream", False))

    try:
        upstream = _post_upstream(api, "/chat/completions", payload, stream)
    except Exception as e:
        UI_QUEUE.put(("anim_end", None))
        return jsonify({"error": f"网络异常: {e}"}), 502

    if upstream.status_code != 200:
        UI_QUEUE.put(("anim_end", None))
        UI_QUEUE.put(("log_err", f"上游报错 {upstream.status_code}: {upstream.text[:300]}"))
        return jsonify({"error": upstream.text}), upstream.status_code

    if not stream:
        try:
            data = upstream.json()
        except Exception:
            data = {}
        upstream.close()
        UI_QUEUE.put(("anim_end", None))
        _push_stats(data)
        return jsonify(data)

    def generate():
        # 原样转发的同时顺手扫一遍尾部的 usage chunk，用来做 token 统计
        decoder = codecs.getincrementaldecoder("utf-8")("replace")
        buffer = ""
        usage_seen = False
        try:
            for c in upstream.iter_content(chunk_size=1024):
                if not c:
                    continue
                yield c
                buffer += decoder.decode(c)
                if "\n" not in buffer:
                    continue
                lines = buffer.split("\n")
                buffer = lines.pop()
                for line in lines:
                    line = line.strip()
                    if not line.startswith("data:"):
                        continue
                    ds = line[5:].strip()
                    if not ds or ds == "[DONE]":
                        continue
                    try:
                        obj = json.loads(ds)
                    except Exception:
                        continue
                    if obj.get("usage"):
                        usage_seen = True
                        _push_stats(obj)
            if not usage_seen:
                UI_QUEUE.put(("stats", None))
        finally:
            upstream.close()
            UI_QUEUE.put(("anim_end", None))

    return Response(generate(), status=200, mimetype="text/event-stream")

@PROXY_APP.route("/v1/models", methods=["GET"])
def list_models():
    api = get_active_config()
    if not api or not api.get("apiURL") or not api.get("apiKey"):
        return jsonify({"data": []})
    try:
        resp = requests.get(f"{api_base(api)}/models", headers={"Authorization": f"Bearer {api['apiKey']}"}, timeout=10)
        if resp.status_code == 200:
            return jsonify(resp.json())
    except Exception:
        pass
    return jsonify({"data": []})

# ==================== Tkinter UI ====================
class APIBridgeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("API Linking Bridge - Made by Apex - 授权使用 - 具体使用明细请访问 https://ctxcode.cn")
        self.root.geometry("960x720")
        self.root.configure(bg="#1e1e1e")

        self.api_data = load_links()
        self.current_selected_index = -1
        self.is_new_link = False
        self.is_running = False
        self.particles = []

        self._updating = False
        self.apply_icon()
        self.setup_ui()
        self.root.after(100, self.process_queue)
        # 版本检查放后台线程，服务器慢/超时都不影响窗口启动
        threading.Thread(target=self.check_update, daemon=True).start()

    def apply_icon(self):
        """把脚本同目录下的 Logo-192x192.ico 设为窗口标题栏与任务栏图标。

        Windows 走 iconbitmap（原生 .ico，由系统按 DPI 自行缩放）；
        万一 .ico 缺失或损坏，再退回旧的 Logo.png（Tk 8.6 原生支持 PNG）。
        """
        ico = resource_path(ICON_FILE)
        if os.path.exists(ico):
            try:
                self.root.iconbitmap(ico)           # 立即作用到当前窗口
                self.root.iconbitmap(default=ico)   # 之后新建的 Toplevel 也继承
                self._icon_path = ico
                return
            except Exception as e:
                UI_QUEUE.put(("log_err", f"ICO 图标加载失败，尝试 PNG 兜底: {e}"))

        path = resource_path("Logo.png")
        if not os.path.exists(path):
            UI_QUEUE.put(("log_err", f"未找到图标 {ICON_FILE} / Logo.png，应放在: {os.path.dirname(ico)}"))
            return
        try:
            base = tk.PhotoImage(file=path)
            icons = [base]
            for factor in (4, 8, 16):
                try:
                    icons.append(base.subsample(factor, factor))
                except tk.TclError:
                    pass
            self.root.iconphoto(True, *icons)
            self._icon_images = icons  # 必须持有引用，否则被 GC 后图标会消失
        except Exception as e:
            UI_QUEUE.put(("log_err", f"图标 Logo.png 加载失败（需为 PNG 格式）: {e}"))

    def setup_ui(self):
        top = tk.Frame(self.root, bg="#1e1e1e")
        top.pack(fill=tk.X, pady=10, padx=20)
        tk.Label(top, text="◈ API Linking Bridge", font=("Consolas", 18, "bold"), fg="#00ffcc", bg="#1e1e1e").pack(side=tk.LEFT)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)
        self.tab_dash = tk.Frame(self.notebook, bg="#1e1e1e")
        self.tab_conf = tk.Frame(self.notebook, bg="#1e1e1e")
        self.tab_upd = tk.Frame(self.notebook, bg="#1e1e1e")
        self.notebook.add(self.tab_dash, text=" 运行控制台 ")
        self.notebook.add(self.tab_conf, text=" 链路管理 ")
        self.notebook.add(self.tab_upd, text=" 版本更新 ")

        self.setup_dashboard()
        self.setup_config()
        self.setup_update_tab()
        self.refresh_link_list()

    def setup_dashboard(self):
        ctrl = tk.Frame(self.tab_dash, bg="#1e1e1e")
        ctrl.pack(fill=tk.X, pady=5, padx=20)

        self.status_label = tk.Label(ctrl, text="● 当前未监听", font=("Consolas", 11), fg="#888", bg="#1e1e1e")
        self.status_label.pack(side=tk.LEFT)

        tk.Label(ctrl, text="选择链路:", font=("Consolas", 11), fg="#ccc", bg="#1e1e1e").pack(side=tk.LEFT, padx=(20, 5))
        self.cb_dash_links = ttk.Combobox(ctrl, font=("Consolas", 11), state="readonly", width=15)
        self.cb_dash_links.pack(side=tk.LEFT)

        self.btn_toggle = tk.Button(ctrl, text="⚡ 开启链路", bg="#333", fg="#00ffcc", font=("Consolas", 11, "bold"), relief=tk.FLAT, command=self.toggle_link)
        self.btn_toggle.pack(side=tk.LEFT, padx=10, ipady=2)

        self.canvas = tk.Canvas(self.tab_dash, height=220, bg="#111", highlightthickness=0)
        self.canvas.pack(fill=tk.X, padx=20, pady=10)

        self.nodes = {
            "client": {"x": 150, "y": 110, "label": "Codex 客户端"},
            "proxy": {"x": 480, "y": 110, "label": "本地中继"},
            "upstream": {"x": 810, "y": 110, "label": "API 服务器"}
        }
        self.canvas.create_line(150, 110, 480, 110, width=12, fill="#222", capstyle=tk.ROUND)
        self.canvas.create_line(150, 110, 480, 110, width=6, fill="#333", capstyle=tk.ROUND)
        self.canvas.create_line(480, 110, 810, 110, width=12, fill="#222", capstyle=tk.ROUND)
        self.canvas.create_line(480, 110, 810, 110, width=6, fill="#333", capstyle=tk.ROUND)
        for k, n in self.nodes.items():
            self.canvas.create_oval(n["x"]-25, n["y"]-25, n["x"]+25, n["y"]+25, fill="#1e1e1e", outline="#00ffcc", width=2)
            self.canvas.create_text(n["x"], n["y"]+45, text=n["label"], fill="#ccc", font=("Consolas", 10))
            self.canvas.create_text(n["x"], n["y"], text=k[0].upper(), fill="#00ffcc", font=("Consolas", 14, "bold"))

        self.tick()

        bottom = tk.Frame(self.tab_dash, bg="#1e1e1e")
        bottom.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        stats = tk.LabelFrame(bottom, text=" Token 运量统计 ", fg="#00ffcc", bg="#1e1e1e", font=("Consolas", 10))
        stats.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        self.lbl_in = tk.Label(stats, text="输入: 0", fg="#fff", bg="#1e1e1e", font=("Consolas", 11)); self.lbl_in.pack(anchor="w", padx=10, pady=2)
        self.lbl_out = tk.Label(stats, text="输出: 0", fg="#fff", bg="#1e1e1e", font=("Consolas", 11)); self.lbl_out.pack(anchor="w", padx=10, pady=2)
        self.lbl_total = tk.Label(stats, text="总计: 0", fg="#fff", bg="#1e1e1e", font=("Consolas", 11)); self.lbl_total.pack(anchor="w", padx=10, pady=2)
        self.lbl_req = tk.Label(stats, text="请求: 0", fg="#888", bg="#1e1e1e", font=("Consolas", 9)); self.lbl_req.pack(anchor="w", padx=10, pady=(6, 0))
        tk.Button(stats, text="重置统计", bg="#333", fg="#00ffcc", font=("Consolas", 9), relief=tk.FLAT,
                  command=self.reset_stats).pack(anchor="w", padx=10, pady=6, fill=tk.X)

        logf = tk.LabelFrame(bottom, text=" 运行日志 ", fg="#00ffcc", bg="#1e1e1e", font=("Consolas", 10))
        logf.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.log_text = tk.Text(logf, bg="#111", fg="#aaa", font=("Consolas", 9), state=tk.DISABLED)
        self.log_text.tag_config("err", foreground="#ff4444")
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def setup_config(self):
        main = tk.Frame(self.tab_conf, bg="#1e1e1e")
        main.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        left = tk.Frame(main, bg="#1e1e1e", width=200)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 15))
        tk.Label(left, text="已保存的链路", fg="#00ffcc", bg="#1e1e1e", font=("Consolas", 11)).pack(anchor="w")
        self.listbox_links = tk.Listbox(left, bg="#111", fg="#fff", font=("Consolas", 11), selectbackground="#005544", relief=tk.FLAT)
        self.listbox_links.pack(fill=tk.BOTH, expand=True, pady=5)
        self.listbox_links.bind("<<ListboxSelect>>", self.on_link_select)

        btnf = tk.Frame(left, bg="#1e1e1e")
        btnf.pack(fill=tk.X, pady=5)
        tk.Button(btnf, text="+ 新建", bg="#333", fg="#00ffcc", command=self.add_new_link).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        tk.Button(btnf, text="- 删除", bg="#333", fg="#ff4444", command=self.delete_link).pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=2)

        right = tk.Frame(main, bg="#1e1e1e")
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        tk.Label(right, text="链路名称 (唯一标识):", fg="#00ffcc", bg="#1e1e1e", font=("Consolas", 11)).pack(anchor="w", pady=(0, 5))
        self.ent_name = tk.Entry(right, bg="#2a2a2a", fg="#fff", insertbackground="white", font=("Consolas", 11), borderwidth=0)
        self.ent_name.pack(fill=tk.X, ipady=5, pady=(0, 15))

        tk.Label(right, text="Base URL:", fg="#00ffcc", bg="#1e1e1e", font=("Consolas", 11)).pack(anchor="w", pady=(0, 5))
        self.cb_provider = ttk.Combobox(right, values=list(PROVIDERS.keys()), font=("Consolas", 11))
        self.cb_provider.pack(fill=tk.X, pady=(0, 5))
        self.cb_provider.bind("<<ComboboxSelected>>", self.on_provider_select)
        self.ent_url = tk.Entry(right, bg="#2a2a2a", fg="#fff", insertbackground="white", font=("Consolas", 11), borderwidth=0)
        self.ent_url.pack(fill=tk.X, ipady=5, pady=(0, 15))

        tk.Label(right, text="上游模型名 (留空 = 透传客户端模型):", fg="#00ffcc", bg="#1e1e1e", font=("Consolas", 11)).pack(anchor="w", pady=(0, 5))
        self.ent_model = tk.Entry(right, bg="#2a2a2a", fg="#fff", insertbackground="white", font=("Consolas", 11), borderwidth=0)
        self.ent_model.pack(fill=tk.X, ipady=5, pady=(0, 15))

        tk.Label(right, text="API Key:", fg="#00ffcc", bg="#1e1e1e", font=("Consolas", 11)).pack(anchor="w", pady=(0, 5))
        keyf = tk.Frame(right, bg="#1e1e1e")
        keyf.pack(fill=tk.X, pady=(0, 15))
        self.ent_key = tk.Entry(keyf, bg="#2a2a2a", fg="#fff", insertbackground="white", font=("Consolas", 11), borderwidth=0, show="*")
        self.ent_key.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5)
        self.btn_test = tk.Button(keyf, text="测试连接", bg="#333", fg="#00ffcc", font=("Consolas", 10), relief=tk.FLAT, command=self.test_connection)
        self.btn_test.pack(side=tk.RIGHT, padx=(10, 0), ipady=2)

        tk.Label(right, text="本地监听端口 (ListenPort):", fg="#00ffcc", bg="#1e1e1e", font=("Consolas", 11)).pack(anchor="w", pady=(0, 5))
        self.ent_port = tk.Entry(right, bg="#2a2a2a", fg="#fff", insertbackground="white", font=("Consolas", 11), borderwidth=0)
        self.ent_port.pack(fill=tk.X, ipady=5, pady=(0, 15))

        tk.Label(right, text="转换模式 (ExChangeModel):", fg="#00ffcc", bg="#1e1e1e", font=("Consolas", 11)).pack(anchor="w", pady=(0, 5))
        self.cb_mode = ttk.Combobox(right, values=["translation (Chat 转译 - 推荐)", "direct (原生直连)"], font=("Consolas", 11), state="readonly")
        self.cb_mode.pack(fill=tk.X, pady=(0, 15))
        self.cb_mode.set("translation (Chat 转译 - 推荐)")

        self.var_disable_tools = tk.BooleanVar()
        tk.Checkbutton(right, text="禁用工具调用 (解决部分提供商 400)", variable=self.var_disable_tools, bg="#1e1e1e", fg="#00ffcc", selectcolor="#111", font=("Consolas", 10)).pack(anchor="w", pady=(0, 15))

        tk.Button(right, text="💾 保存链路配置", bg="#00ffcc", fg="#111", font=("Consolas", 12, "bold"), relief=tk.FLAT, command=self.save_current_link).pack(fill=tk.X, ipady=5, pady=(10, 20))

        self.ent_name.config(state='readonly')

    # ---------- 版本更新 ----------
    def setup_update_tab(self):
        wrap = tk.Frame(self.tab_upd, bg="#1e1e1e")
        wrap.pack(fill=tk.BOTH, expand=True, padx=40, pady=30)

        tk.Label(wrap, text="◈ 版本更新", font=("Consolas", 16, "bold"),
                 fg="#00ffcc", bg="#1e1e1e").pack(anchor="w")
        tk.Label(wrap, text=f"当前版本：v{VERSION}", font=("Consolas", 12),
                 fg="#fff", bg="#1e1e1e").pack(anchor="w", pady=(14, 6))

        self.lbl_upd_status = tk.Label(wrap, text="正在向服务器查询版本…", font=("Consolas", 12),
                                       fg="#888", bg="#1e1e1e")
        self.lbl_upd_status.pack(anchor="w", pady=(4, 10))

        self.lbl_upd_msg = tk.Label(wrap, text="", font=("Consolas", 12, "bold"),
                                    fg="#ffaa44", bg="#1e1e1e", justify=tk.LEFT)
        self.lbl_upd_msg.pack(anchor="w", pady=(0, 14))

        tk.Button(wrap, text="🌐 打开官网下载页面", bg="#00ffcc", fg="#111",
                  font=("Consolas", 12, "bold"), relief=tk.FLAT,
                  command=self.open_homepage).pack(anchor="w", ipady=4, ipadx=12, pady=(0, 12))
        tk.Button(wrap, text="🔄 重新检查", bg="#333", fg="#00ffcc",
                  font=("Consolas", 10), relief=tk.FLAT,
                  command=self.recheck_update).pack(anchor="w", ipady=2, ipadx=10)

        tk.Label(wrap, text=f"程序出错时的日志目录：{LOG_DIR}", font=("Consolas", 9),
                 fg="#666", bg="#1e1e1e").pack(anchor="w", pady=(16, 4))
        tk.Button(wrap, text="🗂 打开错误日志目录", bg="#333", fg="#00ffcc",
                  font=("Consolas", 10), relief=tk.FLAT,
                  command=self.open_log_dir).pack(anchor="w", ipady=2, ipadx=10)

        self._badge = self._make_dot()
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

    def _make_dot(self, size=12, color="#ff3b30"):
        """画一个纯红小圆点当未读徽标（ttk 标签页没法直接改颜色，用图片最稳）。"""
        img = tk.PhotoImage(width=size, height=size)
        r = size / 2.0
        c = (size - 1) / 2.0
        for y in range(size):
            dy = y - c
            if abs(dy) > r:
                continue
            half = (r * r - dy * dy) ** 0.5
            x0 = max(0, int(round(c - half)))
            x1 = min(size, int(round(c + half)) + 1)
            if x1 > x0:
                img.put(color, to=(x0, y, x1, y + 1))
        return img

    def set_badge(self, on):
        """在「版本更新」标签页上点亮/熄灭红点。"""
        try:
            if on:
                self.notebook.tab(self.tab_upd, image=self._badge, compound="right")
            else:
                self.notebook.tab(self.tab_upd, image="", compound="none")
        except Exception:
            pass

    def on_tab_changed(self, event=None):
        # 用户点开版本更新页，说明消息已经看到了，红点自动消失
        try:
            if self.notebook.select() == str(self.tab_upd):
                self.set_badge(False)
        except Exception:
            pass

    def _fetch_update_info(self):
        """请求更新接口，失败自动重试一次（服务器偶尔抽风，起步阶段更稳）。"""
        last = None
        for attempt in range(2):
            try:
                resp = requests.get(UPDATE_API, timeout=10,
                                    headers={"User-Agent": f"APILinkingBridge/{VERSION}"})
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                last = e
                if attempt == 0:
                    time.sleep(1.5)
        raise last

    @staticmethod
    def _friendly_update_error(e):
        """把 urllib3 那串 ConnectionPool/MaxRetry 翻译成人话，别让用户看天书。"""
        if isinstance(e, requests.exceptions.Timeout):
            return "连接更新服务器超时"
        if isinstance(e, requests.exceptions.ConnectionError):
            return "无法连接更新服务器，请检查网络"
        resp = getattr(e, "response", None)
        if isinstance(e, requests.exceptions.HTTPError) and resp is not None:
            return f"更新服务器返回错误（HTTP {resp.status_code}）"
        if isinstance(e, ValueError):
            return "更新服务器返回的数据格式异常"
        return "网络异常"

    def check_update(self):
        """后台线程：GET 更新接口，返回 {"Version": "x.y.z"}。"""
        if self._updating:
            return
        self._updating = True
        try:
            data = self._fetch_update_info()
        except Exception as e:
            UI_QUEUE.put(("update_status", ("error", self._friendly_update_error(e))))
            return
        finally:
            self._updating = False

        remote = ""
        if isinstance(data, dict):
            remote = str(data.get("Version") or data.get("version") or "").strip()
        if not remote:
            UI_QUEUE.put(("update_status", ("error", "服务器未返回有效版本号")))
        elif remote == VERSION:
            UI_QUEUE.put(("update_status", ("ok", remote)))
        else:
            UI_QUEUE.put(("update_status", ("new", remote)))

    def recheck_update(self):
        self.lbl_upd_status.config(text="正在向服务器查询版本…", fg="#888")
        self.lbl_upd_msg.config(text="")
        threading.Thread(target=self.check_update, daemon=True).start()

    def render_update_state(self, state, info):
        if state == "ok":
            self.lbl_upd_status.config(text=f"✅ 已是最新版本（v{info}）", fg="#00ff00")
            self.lbl_upd_msg.config(text="")
            self.set_badge(False)
        elif state == "new":
            self.lbl_upd_status.config(text="🔔 发现新版本", fg="#ffaa44")
            self.lbl_upd_msg.config(text=f"请到官网下载新版本  Version：{info}")
            self.set_badge(True)
        else:
            self.lbl_upd_status.config(
                text=f"⚠ {info}，可稍后点「重新检查」重试", fg="#ff6666")
            self.lbl_upd_msg.config(text="")

    def open_homepage(self):
        try:
            ok = webbrowser.open(HOMEPAGE)
        except Exception:
            ok = False
        if ok:
            UI_QUEUE.put(("log", "已在浏览器中打开官网下载页"))
        else:
            UI_QUEUE.put(("log_err", "无法自动打开浏览器，请手动访问官网下载"))

    def open_log_dir(self):
        """打开错误日志目录，方便用户把 .log 发给开发者。"""
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
        except Exception:
            pass
        try:
            os.startfile(LOG_DIR)
            UI_QUEUE.put(("log", f"已打开错误日志目录：{LOG_DIR}"))
        except Exception:
            UI_QUEUE.put(("log_err", f"无法自动打开目录，请手动进入：{LOG_DIR}"))

    # ---------- 列表/表单 ----------
    def refresh_link_list(self):
        self.listbox_links.delete(0, tk.END)
        names = [x.get("name", "Unnamed") for x in self.api_data]
        for n in names:
            self.listbox_links.insert(tk.END, n)
        self.cb_dash_links["values"] = names

        if names:
            if self.current_selected_index < 0 or self.current_selected_index >= len(names):
                self.current_selected_index = 0
            self.cb_dash_links.current(self.current_selected_index)
            self.listbox_links.selection_clear(0, tk.END)
            self.listbox_links.selection_set(self.current_selected_index)
            self.on_link_select(None)
        else:
            self.cb_dash_links.set('')
            self.current_selected_index = -1
            self.ent_name.config(state='normal')
            self.ent_name.delete(0, tk.END)
            self.ent_name.config(state='readonly')
            self.ent_url.delete(0, tk.END)
            self.ent_model.delete(0, tk.END)
            self.ent_key.delete(0, tk.END)
            self.ent_port.delete(0, tk.END)

    def on_link_select(self, event):
        sel = self.listbox_links.curselection()
        if not sel:
            return
        idx = sel[0]
        self.current_selected_index = idx
        self.is_new_link = False
        d = self.api_data[idx]

        self.ent_name.config(state='normal')
        self.ent_name.delete(0, tk.END)
        self.ent_name.insert(0, d.get("name", ""))
        self.ent_name.config(state='readonly')

        self.ent_url.delete(0, tk.END)
        self.ent_url.insert(0, d.get("apiURL", ""))
        self.ent_model.delete(0, tk.END)
        self.ent_model.insert(0, d.get("model", ""))
        self.ent_key.delete(0, tk.END)
        self.ent_key.insert(0, d.get("apiKey", ""))
        self.ent_port.delete(0, tk.END)
        self.ent_port.insert(0, str(d.get("ListenPort", 15721)))

        self.cb_mode.set("direct (原生直连)" if d.get("ExChangeModel") == "direct" else "translation (Chat 转译 - 推荐)")
        self.var_disable_tools.set(d.get("disable_tools", False))

    def add_new_link(self):
        self.listbox_links.selection_clear(0, tk.END)
        self.current_selected_index = -1
        self.is_new_link = True

        self.ent_name.config(state='normal')
        self.ent_name.delete(0, tk.END)
        self.ent_name.insert(0, f"Link{len(self.api_data) + 1}")

        self.cb_provider.set("自定义 (Custom)")
        self.ent_url.delete(0, tk.END)
        self.ent_model.delete(0, tk.END)
        self.ent_key.delete(0, tk.END)

        # 自动分配端口：15721 起，避开已占用的
        used_ports = {x.get("ListenPort", 15721) for x in self.api_data}
        port = 15721
        while port in used_ports:
            port += 1
        self.ent_port.delete(0, tk.END)
        self.ent_port.insert(0, str(port))

        self.cb_mode.set("translation (Chat 转译 - 推荐)")
        self.var_disable_tools.set(False)

    def delete_link(self):
        if self.current_selected_index < 0 or self.current_selected_index >= len(self.api_data):
            return
        link = self.api_data[self.current_selected_index]
        name = link.get("name", "Unnamed")

        if not messagebox.askyesno("确认", f"确定删除链路 {name} 吗？"):
            return

        # 若删除的是正在运行的链路，先停止服务器
        if PROXY_STATE.get("active_link") == name:
            self.stop_server()
            self.is_running = False
            self.btn_toggle.config(text="⚡ 开启链路", bg="#333", fg="#00ffcc")
            self.status_label.config(text="● 当前未监听", fg="#888")

        del self.api_data[self.current_selected_index]
        self.save_json_data()
        self.current_selected_index = -1
        self.refresh_link_list()
        UI_QUEUE.put(("log", f"已删除链路: {name}"))

    def save_current_link(self):
        new_name = self.ent_name.get().strip()
        if not new_name:
            return messagebox.showwarning("提示", "链路名称不能为空")

        # 名称唯一性检查（新建时；重命名时也要排除自己）
        for i, x in enumerate(self.api_data):
            if x.get("name") == new_name and i != self.current_selected_index:
                return messagebox.showerror("错误", "该名称已存在，请换一个")

        try:
            port = int(self.ent_port.get().strip())
            if port < 1 or port > 65535:
                raise ValueError
        except Exception:
            return messagebox.showerror("错误", "端口必须是 1-65535 的数字")

        data = {
            "name": new_name,
            "apiURL": self.ent_url.get().strip(),
            "apiKey": self.ent_key.get().strip(),
            "model": self.ent_model.get().strip(),
            "ListenPort": port,
            "disable_tools": self.var_disable_tools.get(),
            "ExChangeModel": "direct" if "直连" in self.cb_mode.get() else "translation",
        }

        if self.is_new_link or self.current_selected_index < 0:
            self.api_data.append(data)
            self.current_selected_index = len(self.api_data) - 1
            self.is_new_link = False
        else:
            old_name = self.api_data[self.current_selected_index].get("name")
            self.api_data[self.current_selected_index] = data
            # 如果正在运行的就是这条链路，热更新配置（端口变了要提示重启）
            if PROXY_STATE.get("active_link") == old_name:
                PROXY_STATE["active_link"] = new_name
                PROXY_STATE["config"] = data
                UI_QUEUE.put(("log", f"链路 [{new_name}] 配置已热更新"))
                if PROXY_STATE.get("port") != port:
                    UI_QUEUE.put(("log_err", "端口已变更，请停止后重新开启链路以生效"))

        self.save_json_data()
        self.refresh_link_list()
        messagebox.showinfo("成功", f"链路 [{new_name}] 已保存！")

    def save_json_data(self):
        try:
            with open(API_FILE, "w", encoding="utf-8") as f:
                json.dump(self.api_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            messagebox.showerror("错误", f"保存配置失败: {e}")

    def on_provider_select(self, event):
        p = self.cb_provider.get()
        if p in PROVIDERS and PROVIDERS[p]:
            self.ent_url.delete(0, tk.END)
            self.ent_url.insert(0, PROVIDERS[p])

    def test_connection(self):
        url = self.ent_url.get().strip().rstrip("/")
        key = self.ent_key.get().strip()
        if not url or not key:
            return messagebox.showwarning("提示", "请先填写 Base URL 和 API Key")
        self.btn_test.config(text="测试中...", state=tk.DISABLED)

        def _test():
            try:
                resp = requests.get(f"{url}/models", headers={"Authorization": f"Bearer {key}"}, timeout=10)
                if resp.status_code == 200:
                    models = [m.get("id") for m in resp.json().get("data", []) if m.get("id")]
                    UI_QUEUE.put(("log", f"✅ 连接成功，检测到 {len(models)} 个模型"))
                    self.root.after(0, lambda: messagebox.showinfo("成功", f"接口连接成功！\n检测到 {len(models)} 个模型"))
                else:
                    UI_QUEUE.put(("log_err", f"❌ 连接失败 {resp.status_code}: {resp.text[:200]}"))
                    self.root.after(0, lambda: messagebox.showerror("失败", f"HTTP {resp.status_code}\n{resp.text[:200]}"))
            except Exception as e:
                UI_QUEUE.put(("log_err", f"❌ 异常: {e}"))
                self.root.after(0, lambda: messagebox.showerror("错误", str(e)))
            finally:
                self.root.after(0, lambda: self.btn_test.config(text="测试连接", state=tk.NORMAL))

        threading.Thread(target=_test, daemon=True).start()

    # ---------- 服务器控制 ----------
    def start_server(self, cfg):
        """启动 Flask 在指定端口"""
        port = cfg.get("ListenPort", 15721)
        host = "127.0.0.1"
        try:
            from werkzeug.serving import make_server
            server = make_server(host, port, PROXY_APP, threaded=True)
            t = threading.Thread(target=server.serve_forever, daemon=True)
            t.start()
            PROXY_STATE["server"] = server
            PROXY_STATE["thread"] = t
            PROXY_STATE["port"] = port
            PROXY_STATE["config"] = cfg
            PROXY_STATE["active_link"] = cfg.get("name")
            return True
        except Exception as e:
            UI_QUEUE.put(("log_err", f"启动失败: {e}"))
            return False

    def stop_server(self):
        server = PROXY_STATE.get("server")
        if server:
            try:
                server.shutdown()
            except Exception:
                pass
        PROXY_STATE["server"] = None
        PROXY_STATE["thread"] = None
        PROXY_STATE["active_link"] = None
        PROXY_STATE["config"] = {}
        PROXY_STATE["port"] = None

    def toggle_link(self):
        if self.is_running:
            # 停止
            self.stop_server()
            self.is_running = False
            self.btn_toggle.config(text="⚡ 开启链路", bg="#333", fg="#00ffcc")
            self.status_label.config(text="● 当前未监听", fg="#888")
            UI_QUEUE.put(("log", "链路已停止"))
        else:
            # 开启
            name = self.cb_dash_links.get()
            if not name:
                return messagebox.showwarning("提示", "请先选择一条链路")
            # 从 list 里找到对应配置
            cfg = None
            for x in self.api_data:
                if x.get("name") == name:
                    cfg = x
                    break
            if not cfg:
                return messagebox.showwarning("提示", f"找不到链路 {name}")
            if not cfg.get("apiURL") or not cfg.get("apiKey"):
                return messagebox.showwarning("提示", f"链路 {name} 未配置完整，请先保存")

            if self.start_server(cfg):
                self.is_running = True
                port = cfg.get("ListenPort", 15721)
                self.btn_toggle.config(text="🛑 停止链路", bg="#ff4444", fg="#fff")
                self.status_label.config(text=f"● 监听: http://127.0.0.1:{port} [ {name} ]", fg="#00ff00")
                UI_QUEUE.put(("log", f"已开启链路: {name} (端口 {port})"))
                # 顺带验证一下连通性
                threading.Thread(target=self._probe_upstream, args=(cfg,), daemon=True).start()

    def _probe_upstream(self, cfg):
        try:
            r = requests.get(f"{api_base(cfg)}/models", headers={"Authorization": f"Bearer {cfg['apiKey']}"}, timeout=10)
            if r.status_code == 200:
                ids = [x.get("id") for x in r.json().get("data", []) if x.get("id")]
                UI_QUEUE.put(("log", f"上游就绪，获取到 {len(ids)} 个模型"))
                if not cfg.get("model"):
                    sample = ", ".join(ids[:5]) if ids else "(无)"
                    UI_QUEUE.put(("log_err",
                                  f"未填写「上游模型名」，客户端发来的模型名会被原样转发，很可能 404。"
                                  f"可用模型示例: {sample}"))
            else:
                UI_QUEUE.put(("log_err", f"上游返回 {r.status_code}: {r.text[:150]}"))
        except Exception as e:
            UI_QUEUE.put(("log_err", f"上游连通性检测失败: {e}"))

    # ---------- 日志/动画/队列 ----------
    def render_stats(self):
        missing = GLOBAL_STATS["missing"]
        req = GLOBAL_STATS["requests"]
        self.lbl_in.config(text=f"输入: {GLOBAL_STATS['input_tokens']}")
        self.lbl_out.config(text=f"输出: {GLOBAL_STATS['output_tokens']}")
        self.lbl_total.config(text=f"总计: {GLOBAL_STATS['total_tokens']}")
        if missing:
            self.lbl_req.config(text=f"请求: {req}（{missing} 次上游未返回用量）", fg="#ffaa44")
        else:
            self.lbl_req.config(text=f"请求: {req}", fg="#888")

    def reset_stats(self):
        for k in GLOBAL_STATS:
            GLOBAL_STATS[k] = 0
        self.render_stats()
        UI_QUEUE.put(("log", "Token 统计已清零"))

    def log(self, msg, is_err=False):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {msg}\n", "err" if is_err else "")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def spawn_particle(self, start, end, color="#00ffcc"):
        p = self.canvas.create_oval(0, 0, 6, 6, fill=color, outline="")
        self.particles.append({
            "id": p,
            "sx": self.nodes[start]["x"], "sy": self.nodes[start]["y"],
            "ex": self.nodes[end]["x"], "ey": self.nodes[end]["y"],
            "p": 0.0
        })

    def tick(self):
        for p in list(self.particles):
            p["p"] += 0.04
            if p["p"] >= 1.0:
                self.canvas.delete(p["id"])
                self.particles.remove(p)
            else:
                cx = p["sx"] + (p["ex"] - p["sx"]) * p["p"]
                cy = p["sy"] + (p["ey"] - p["sy"]) * p["p"]
                self.canvas.coords(p["id"], cx - 3, cy - 3, cx + 3, cy + 3)
        self.root.after(30, self.tick)

    def process_queue(self):
        try:
            while True:
                msg, data = UI_QUEUE.get_nowait()
                if msg == "log":
                    self.log(data)
                elif msg == "log_err":
                    self.log(data, is_err=True)
                elif msg == "stats":
                    GLOBAL_STATS["requests"] += 1
                    if data is None:
                        # 上游没回报 usage，如实记账，不编数字
                        GLOBAL_STATS["missing"] += 1
                    else:
                        GLOBAL_STATS["input_tokens"] += data["input"]
                        GLOBAL_STATS["output_tokens"] += data["output"]
                        GLOBAL_STATS["total_tokens"] += data["total"]
                    self.render_stats()
                elif msg == "anim_start":
                    self.spawn_particle("client", "proxy", "#00ffcc")
                    self.root.after(300, lambda: self.spawn_particle("proxy", "upstream", "#ffcc00"))
                elif msg == "anim_end":
                    self.spawn_particle("upstream", "proxy", "#ffcc00")
                    self.root.after(300, lambda: self.spawn_particle("proxy", "client", "#00ffcc"))
                elif msg == "update_status":
                    self.render_update_state(data[0], data[1])
        except queue.Empty:
            pass
        self.root.after(100, self.process_queue)


if __name__ == "__main__":
    try:
        root = tk.Tk()
    except Exception as exc:
        path = _write_crash_log(type(exc), exc, exc.__traceback__,
                                "GUI 启动（创建窗口）")
        print("窗口创建失败，错误日志已保存到：", path)
        try:
            input("按回车键退出…")
        except Exception:
            pass
        raise SystemExit(1)

    install_crash_handlers(root)
    app = None
    startup_failed = False
    try:
        app = APIBridgeApp(root)
        install_crash_handlers(root, app)
    except Exception as exc:
        startup_failed = True
        path = _write_crash_log(type(exc), exc, exc.__traceback__,
                                "GUI 启动（初始化）")
        try:
            root.title("API Linking Bridge - 启动时发生错误（窗口保留）")
            messagebox.showerror(
                "启动错误",
                "程序初始化时出现错误，但窗口不会自动关闭。\n\n"
                "错误日志已保存到：\n%s\n\n请把该文件发给开发者分析。" % path,
                parent=root,
            )
        except Exception:
            print("启动错误，错误日志：", path)

    if startup_failed:
        root.mainloop()          # 窗口留着，用户可以截图/取日志
    else:
        try:
            root.mainloop()
        except Exception as exc:
            path = _write_crash_log(type(exc), exc, exc.__traceback__,
                                    "GUI 主循环")
            try:
                messagebox.showerror(
                    "程序错误",
                    "主循环出现错误，窗口会尽量保留。\n\n错误日志：\n%s" % path,
                    parent=root,
                )
            except Exception:
                print("程序错误，错误日志：", path)
            try:
                root.mainloop()      # 还能继续就继续，不直接关掉
            except Exception:
                try:
                    input("按回车键退出…")
                except Exception:
                    pass