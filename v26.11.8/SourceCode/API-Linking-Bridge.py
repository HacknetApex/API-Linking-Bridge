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
import shutil
import socket
import subprocess
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
VERSION = "26.11.8"
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

# ==================== 端口占用检测 ====================
def _find_port_pid(port):
    """Windows 下用 netstat/tasklist 找出监听某端口的进程，失败返回 (None, "")。"""
    if os.name != "nt":
        return None, ""
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        raw = subprocess.check_output(["netstat", "-ano", "-p", "TCP"],
                                      creationflags=flags, timeout=6)
        text = raw.decode("mbcs", errors="replace")
    except Exception:
        return None, ""
    pid = None
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        local, state, pid_text = parts[1], parts[3], parts[4]
        if not local.endswith(":" + str(port)):
            continue
        if state.upper() != "LISTENING":
            continue
        try:
            pid = int(pid_text)
        except ValueError:
            continue
        break
    if pid is None:
        return None, ""
    name = ""
    try:
        raw = subprocess.check_output(
            ["tasklist", "/FI", "PID eq %d" % pid, "/FO", "CSV", "/NH"],
            creationflags=flags, timeout=6)
        lines = raw.decode("mbcs", errors="replace").strip().splitlines()
        if lines:
            name = lines[0].split(",")[0].strip('"')
    except Exception:
        pass
    return pid, name


def _port_owner(port):
    """返回 (是否被监听, PID, 进程名)。只做提示，不参与业务判断。"""
    try:
        port = int(port)
    except Exception:
        return False, None, ""
    sock = None
    listening = False
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.4)
        listening = (sock.connect_ex(("127.0.0.1", port)) == 0)
    except Exception:
        listening = False
    finally:
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass
    if not listening:
        return False, None, ""
    pid, name = _find_port_pid(port)
    return True, pid, name


def describe_port(port, ours=False):
    """把端口状态翻译成一句人话，供界面/命令提示。"""
    if ours:
        return "● 本机中继运行中  http://127.0.0.1:%s" % port
    in_use, pid, name = _port_owner(port)
    if not in_use:
        return "○ 端口 %s 空闲，可用" % port
    who = name or "未知进程"
    if pid is not None:
        who += "（PID %s）" % pid
    extra = ""
    if pid is not None and pid == os.getpid():
        extra = "（当前进程）"
    elif name and name.lower().startswith(("python", "api-linking-bridge", "api linking bridge")):
        extra = "，可能是本程序的另一个实例"
    return "⚠ 端口 %s 已被其他程序占用：%s%s" % (port, who, extra)


# ==================== 缓存清理 ====================
# 只清理明确的缓存文件；auth.json / config.toml 等登录配置永远不碰。
CACHE_CATEGORIES = [
    ("models", "模型列表缓存", "解决 Codex / 客户端模型列表刷不出来"),
    ("chat", "聊天 / 会话缓存", "Codex 历史会话与本软件对话记录"),
    ("logs", "日志缓存", "本软件崩溃日志与 Codex 运行日志"),
    ("temp", "临时文件", "缓存目录下的临时文件"),
]
CACHE_TITLES = {key: title for key, title, _ in CACHE_CATEGORIES}
_CACHE_PROTECTED = {"auth.json", "config.toml", "config.json", "settings.json",
                    "AGENTS.md", "instructions.md"}


def codex_home():
    """定位 Codex 的配置/缓存目录：优先 CODEX_HOME，其次 ~/.codex。"""
    env_path = (os.environ.get("CODEX_HOME") or "").strip()
    if env_path:
        return os.path.expandvars(os.path.expanduser(env_path))
    return os.path.join(os.path.expanduser("~"), ".codex")


def _path_size(path):
    try:
        if os.path.isfile(path):
            return os.path.getsize(path)
        total = 0
        for root, _, files in os.walk(path):
            for name in files:
                try:
                    total += os.path.getsize(os.path.join(root, name))
                except OSError:
                    pass
        return total
    except OSError:
        return 0


def fmt_size(size):
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return ("%d %s" % (value, unit)) if unit == "B" else ("%.1f %s" % (value, unit))
        value /= 1024.0
    return "%.1f GB" % value


def _cache_targets(categories=None):
    """收集可清理的缓存路径；同一路径只出现一次，危险文件直接跳过。"""
    cats = set(categories or [key for key, _, _ in CACHE_CATEGORIES])
    targets, seen = [], set()

    def add(cat, source, path):
        if cat not in cats:
            return
        try:
            full = os.path.abspath(path)
        except Exception:
            return
        base = os.path.basename(full).lower()
        if base in _CACHE_PROTECTED or base.endswith((".toml", ".key", ".pem")):
            return
        if full in seen or not os.path.exists(full):
            return
        seen.add(full)
        targets.append({"cat": cat, "source": source, "path": full,
                        "is_dir": os.path.isdir(full), "size": _path_size(full)})

    home = codex_home()
    if os.path.isdir(home):
        # 模型列表缓存：Codex 新版的 model-catalog.json / cc-switch-model-catalog.json 等
        try:
            for name in os.listdir(home):
                low = name.lower()
                if "model" in low and ("cache" in low or "catalog" in low):
                    add("models", "Codex", os.path.join(home, name))
        except Exception:
            pass
        for name in ("sessions", "archived_sessions", "session_index.jsonl",
                     "history.jsonl", "history.json", "transcription-history.jsonl"):
            add("chat", "Codex", os.path.join(home, name))
        for name in ("log", "logs"):
            add("logs", "Codex", os.path.join(home, name))
        for name in ("tmp", "temp", "cache", ".tmp"):
            add("temp", "Codex", os.path.join(home, name))
        try:
            for name in os.listdir(home):
                if name.lower().endswith((".tmp", ".temp")):
                    add("temp", "Codex", os.path.join(home, name))
        except Exception:
            pass

    # 本软件自己的缓存
    add("temp", "本软件", os.path.join(BASE_DIR, "cache"))
    add("chat", "本软件", CHAT_HISTORY_FILE)
    add("models", "本软件", os.path.join(BASE_DIR, "model_cache.json"))
    if "logs" in cats:
        try:
            for name in os.listdir(LOG_DIR):
                if name.startswith("crash-") and name.endswith(".log"):
                    add("logs", "本软件", os.path.join(LOG_DIR, name))
        except Exception:
            pass

    targets.sort(key=lambda item: (item["cat"], item["path"].lower()))
    return targets


def remove_cache_targets(targets):
    """按列表删除缓存，返回 (成功列表, [(目标, 错误), ...])。"""
    removed, failed = [], []
    for target in targets:
        try:
            if target["is_dir"]:
                shutil.rmtree(target["path"])
            else:
                os.remove(target["path"])
            removed.append(target)
        except Exception as exc:
            failed.append((target, str(exc)))
    return removed, failed


# ==================== 内置对话 ====================
CHAT_HISTORY_FILE = os.path.join(BASE_DIR, "chat_history.json")


def load_chat_history():
    try:
        with open(CHAT_HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return [m for m in data
                    if isinstance(m, dict)
                    and m.get("role") in ("user", "assistant")
                    and isinstance(m.get("content"), str)]
    except Exception:
        pass
    return []


def save_chat_history(messages):
    try:
        os.makedirs(BASE_DIR, exist_ok=True)
        with open(CHAT_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(messages[-200:], f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def fetch_upstream_models(base, api_key, timeout=15):
    """Fetch the upstream model list (GET /models); returns (sorted ids, error)."""
    try:
        url = (base or "").rstrip("/") + "/models"
        headers = {"Authorization": "Bearer %s" % (api_key or "")}
        resp = requests.get(url, headers=headers, timeout=timeout)
        if resp.status_code != 200:
            return [], "HTTP %s: %s" % (resp.status_code, resp.text[:200])
        payload = resp.json()
        items = None
        if isinstance(payload, dict):
            items = payload.get("data")
            if items is None:
                items = payload.get("models")
        if not isinstance(items, list):
            return [], "Unexpected response format"
        out = []
        for item in items:
            if isinstance(item, dict):
                mid = item.get("id") or item.get("name")
            else:
                mid = item
            if mid and str(mid) not in out:
                out.append(str(mid))
        return sorted(out), ""
    except Exception as exc:
        return [], str(exc)

def iter_chat_stream(base, api_key, model, messages, stop_event=None):
    """调用上游 /chat/completions 流式接口，产出 ("content"|"reasoning"|"usage", 值)。"""
    url = base.rstrip("/") + "/chat/completions"
    headers = {"Authorization": "Bearer %s" % api_key,
               "Content-Type": "application/json"}
    body = {"model": model, "messages": messages, "stream": True,
            "stream_options": {"include_usage": True}}
    resp = None
    try:
        resp = requests.post(url, headers=headers, json=body, stream=True, timeout=600)
        if resp.status_code != 200:
            resp.close()
            # 少数服务商不认 stream_options，退回普通流式再试一次
            body.pop("stream_options", None)
            resp = requests.post(url, headers=headers, json=body, stream=True, timeout=600)
            if resp.status_code != 200:
                detail = resp.text[:500]
                resp.close()
                raise RuntimeError("上游返回 %s: %s" % (resp.status_code, detail))
    except Exception:
        if resp is not None:
            try:
                resp.close()
            except Exception:
                pass
        raise

    decoder = codecs.getincrementaldecoder("utf-8")("replace")
    buffer = ""
    try:
        for raw in resp.iter_content(chunk_size=1024):
            if stop_event is not None and stop_event.is_set():
                break
            if not raw:
                continue
            buffer += decoder.decode(raw)
            if "\n" not in buffer:
                continue
            lines = buffer.split("\n")
            buffer = lines.pop()
            for line in lines:
                line = line.strip()
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if not payload or payload == "[DONE]":
                    continue
                try:
                    chunk = json.loads(payload)
                except Exception:
                    continue
                usage = chunk.get("usage")
                if usage:
                    yield ("usage", usage)
                for choice in chunk.get("choices") or []:
                    delta = choice.get("delta") or {}
                    reasoning = delta.get("reasoning_content") or delta.get("reasoning")
                    if reasoning:
                        yield ("reasoning", reasoning)
                    content = delta.get("content")
                    if isinstance(content, str) and content:
                        yield ("content", content)
    finally:
        try:
            resp.close()
        except Exception:
            pass


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
        self.tab_chat = tk.Frame(self.notebook, bg="#1e1e1e")
        self.tab_conf = tk.Frame(self.notebook, bg="#1e1e1e")
        self.tab_cache = tk.Frame(self.notebook, bg="#1e1e1e")
        self.tab_upd = tk.Frame(self.notebook, bg="#1e1e1e")
        self.notebook.add(self.tab_dash, text=" 运行控制台 ")
        self.notebook.add(self.tab_chat, text=" 对话 ")
        self.notebook.add(self.tab_conf, text=" 链路管理 ")
        self.notebook.add(self.tab_cache, text=" 缓存清理 ")
        self.notebook.add(self.tab_upd, text=" 版本更新 ")

        self.setup_dashboard()
        self.setup_chat()
        self.setup_config()
        self.setup_cache()
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

    # ---------- 内置对话 ----------
    def setup_chat(self):
        self._chat_models_cache = {}
        wrap = tk.Frame(self.tab_chat, bg="#1e1e1e")
        wrap.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        bar = tk.Frame(wrap, bg="#1e1e1e")
        bar.pack(fill=tk.X, pady=(0, 4))

        tk.Label(bar, text="链路:", fg="#00ffcc", bg="#1e1e1e",
                 font=("Consolas", 10)).pack(side=tk.LEFT)
        self.cb_chat_links = ttk.Combobox(bar, state="readonly", width=16,
                                          font=("Consolas", 10))
        self.cb_chat_links.pack(side=tk.LEFT, padx=(4, 12))
        self.cb_chat_links.bind("<<ComboboxSelected>>", self.on_chat_link_select)

        tk.Label(bar, text="模型:", fg="#00ffcc", bg="#1e1e1e",
                 font=("Consolas", 10)).pack(side=tk.LEFT)
        self.ent_chat_model = ttk.Combobox(bar, width=24, font=("Consolas", 10),
                                           values=[])
        self.ent_chat_model.pack(side=tk.LEFT, padx=(4, 4), ipady=1)
        self.btn_chat_models = tk.Button(bar, text="获取模型", bg="#333", fg="#00ffcc",
                                         font=("Consolas", 9), relief=tk.FLAT,
                                         command=self.fetch_chat_models)
        self.btn_chat_models.pack(side=tk.LEFT, padx=(0, 12), ipady=1)

        tk.Label(bar, text="通道:", fg="#00ffcc", bg="#1e1e1e",
                 font=("Consolas", 10)).pack(side=tk.LEFT)
        self.cb_chat_route = ttk.Combobox(
            bar, state="readonly", width=22, font=("Consolas", 10),
            values=["自动（优先本机中继）", "上游直连", "本机中继"])
        self.cb_chat_route.set("自动（优先本机中继）")
        self.cb_chat_route.pack(side=tk.LEFT, padx=(4, 8))
        self.cb_chat_route.bind("<<ComboboxSelected>>", self.on_chat_route_select)

        tk.Button(bar, text="检查端口", bg="#333", fg="#00ffcc",
                  font=("Consolas", 9), relief=tk.FLAT,
                  command=self.update_chat_port_status).pack(side=tk.LEFT, padx=4, ipady=1)

        self.lbl_chat_port = tk.Label(wrap, text="○ 尚未选择链路", fg="#888",
                                      bg="#1e1e1e", font=("Consolas", 9),
                                      anchor="w", justify=tk.LEFT)
        self.lbl_chat_port.pack(fill=tk.X, pady=(0, 6))

        body = tk.Frame(wrap, bg="#1e1e1e")
        body.pack(fill=tk.BOTH, expand=True)
        self.chat_text = tk.Text(body, bg="#111", fg="#ddd", font=("Consolas", 10),
                                 wrap=tk.WORD, state=tk.DISABLED,
                                 insertbackground="white", relief=tk.FLAT)
        chat_sb = tk.Scrollbar(body, command=self.chat_text.yview)
        self.chat_text.config(yscrollcommand=chat_sb.set)
        self.chat_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        chat_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.chat_text.tag_config("user", foreground="#00ffcc", font=("Consolas", 10, "bold"))
        self.chat_text.tag_config("assistant", foreground="#eeeeee")
        self.chat_text.tag_config("reasoning", foreground="#777777", font=("Consolas", 9, "italic"))
        self.chat_text.tag_config("system", foreground="#888888", font=("Consolas", 9))
        self.chat_text.tag_config("err", foreground="#ff4444")

        inputf = tk.Frame(wrap, bg="#1e1e1e")
        inputf.pack(fill=tk.X, pady=(8, 0))
        self.chat_input = tk.Text(inputf, height=3, bg="#111", fg="#fff",
                                  insertbackground="white", font=("Consolas", 10),
                                  wrap=tk.WORD, relief=tk.FLAT)
        self.chat_input.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.chat_input.bind("<Return>", self.on_chat_enter)

        btns = tk.Frame(inputf, bg="#1e1e1e")
        btns.pack(side=tk.RIGHT, fill=tk.Y, padx=(8, 0))
        self.btn_chat_send = tk.Button(btns, text="发送", bg="#00ffcc", fg="#111",
                                       font=("Consolas", 10, "bold"), relief=tk.FLAT,
                                       command=self.send_chat_message, width=8)
        self.btn_chat_send.pack(fill=tk.X, pady=2)
        self.btn_chat_stop = tk.Button(btns, text="停止", bg="#333", fg="#ff6666",
                                       font=("Consolas", 10), relief=tk.FLAT,
                                       command=self.stop_chat, width=8, state=tk.DISABLED)
        self.btn_chat_stop.pack(fill=tk.X, pady=2)
        tk.Button(btns, text="新对话", bg="#333", fg="#ccc", font=("Consolas", 10),
                  relief=tk.FLAT, command=self.new_chat, width=8).pack(fill=tk.X, pady=2)
        tk.Button(btns, text="清空历史", bg="#333", fg="#ff4444", font=("Consolas", 10),
                  relief=tk.FLAT, command=self.clear_chat_history, width=8).pack(fill=tk.X, pady=2)

        tk.Label(wrap, text="纯对话模式 · Agent（工具调用/自动执行）功能尚未开发，欢迎在 GitHub 上贡献",
                 fg="#666", bg="#1e1e1e", font=("Consolas", 9)).pack(anchor="w", pady=(6, 0))

        self.chat_messages = load_chat_history()
        self.chat_streaming = False
        self._chat_stop = None
        self._chat_content_buf = ""
        self._chat_reasoning_buf = ""
        self._chat_shown_reasoning = False
        self._chat_shown_ai = False
        if self.chat_messages:
            self._append_chat("（已载入上次对话，共 %d 条消息）\n\n" % len(self.chat_messages),
                              "system")
            for item in self.chat_messages[-20:]:
                role = "你" if item.get("role") == "user" else "AI"
                text = item.get("content", "")
                if len(text) > 4000:
                    text = text[:4000] + "…"
                self._append_chat("%s：%s\n\n" % (role, text),
                                  "user" if role == "你" else "assistant")

    def _append_chat(self, text, tag=""):
        self.chat_text.config(state=tk.NORMAL)
        self.chat_text.insert(tk.END, text, tag)
        self.chat_text.see(tk.END)
        self.chat_text.config(state=tk.DISABLED)

    def on_chat_link_select(self, event=None):
        link = self.selected_chat_link()
        if link:
            self.ent_chat_model.delete(0, tk.END)
            self.ent_chat_model.insert(0, link.get("model", ""))
            self.ent_chat_model["values"] = self._chat_models_cache.get(link.get("name"), [])
            self.fetch_chat_models(auto=True)
        self.update_chat_port_status()

    def fetch_chat_models(self, auto=False):
        link = self.selected_chat_link()
        if not link or not link.get("apiURL") or not link.get("apiKey"):
            if not auto:
                messagebox.showwarning("提示", "请先选择一条已配置 Base URL 和 API Key 的链路")
            return
        name = link.get("name") or "未命名"
        if name in self._chat_models_cache:
            self.ent_chat_model["values"] = self._chat_models_cache[name]
            if auto:
                return
        self.log("正在获取 %s 的模型列表…" % name)
        threading.Thread(target=self._fetch_chat_models_worker,
                         args=(link,), daemon=True).start()

    def _fetch_chat_models_worker(self, link):
        models, err = fetch_upstream_models(api_base(link), link.get("apiKey", ""))
        UI_QUEUE.put(("chat_models", (link.get("name") or "未命名", models, err)))

    def on_chat_route_select(self, event=None):
        self.update_chat_port_status()

    def selected_chat_link(self):
        name = self.cb_chat_links.get()
        if not name:
            return None
        for item in self.api_data:
            if item.get("name") == name:
                return item
        return None

    def chat_route_mode(self):
        text = self.cb_chat_route.get()
        if "自动" in text:
            return "auto"
        if "直连" in text:
            return "direct"
        return "relay"

    def update_chat_port_status(self):
        link = self.selected_chat_link()
        if not link:
            try:
                self.lbl_chat_port.config(text="○ 尚未选择链路", fg="#888")
            except Exception:
                pass
            return
        port = int(link.get("ListenPort", 15721))
        ours = (PROXY_STATE.get("server") is not None
                and PROXY_STATE.get("port") == port
                and PROXY_STATE.get("active_link") == link.get("name"))
        text = describe_port(port, ours)
        color = "#00ff00" if ours else "#888"
        if not ours:
            in_use, _, _ = _port_owner(port)
            if in_use:
                color = "#ffaa44"
                if self.chat_route_mode() == "relay":
                    text += "（本机中继通道不可用：请换端口或先停止占用程序）"
                else:
                    text += "（自动模式将改用上游直连）"
        try:
            self.lbl_chat_port.config(text=text, fg=color)
        except Exception:
            pass

    def _ensure_relay(self, link):
        """确保本机中继在目标端口运行；返回 (是否成功, 说明)。"""
        port = int(link.get("ListenPort", 15721))
        if (PROXY_STATE.get("server") is not None
                and PROXY_STATE.get("port") == port
                and PROXY_STATE.get("active_link") == link.get("name")):
            return True, ""
        in_use, _, _ = _port_owner(port)
        if in_use:
            return False, describe_port(port)
        if not self.start_server(link):
            return False, "本机中继启动失败，详见运行日志"
        self.is_running = True
        self.btn_toggle.config(text="🛑 停止链路", bg="#ff4444", fg="#fff")
        self.status_label.config(
            text="● 监听: http://127.0.0.1:%s [ %s ]" % (port, link.get("name")), fg="#00ff00")
        UI_QUEUE.put(("log", "对话需要本机中继，已自动开启链路: %s (端口 %s)"
                      % (link.get("name"), port)))
        return True, ""

    def resolve_chat_route(self, link, mode):
        """返回 (route, base, warning, error)；route 为 relay / direct。"""
        port = int(link.get("ListenPort", 15721))
        ours = (PROXY_STATE.get("server") is not None
                and PROXY_STATE.get("port") == port
                and PROXY_STATE.get("active_link") == link.get("name"))
        if mode == "relay":
            ok, detail = self._ensure_relay(link)
            if not ok:
                return None, None, None, "无法使用本机中继：" + detail
            return "relay", "http://127.0.0.1:%s/v1" % port, None, None
        if mode == "auto" and ours:
            return "relay", "http://127.0.0.1:%s/v1" % port, None, None
        if mode == "auto":
            in_use, _, _ = _port_owner(port)
            if in_use:
                return ("direct", api_base(link),
                        describe_port(port) + "；本次对话自动改为上游直连", None)
        return "direct", api_base(link), None, None

    def on_chat_enter(self, event):
        if event.state & 0x0001:      # Shift+Enter 换行
            self.chat_input.insert(tk.INSERT, "\n")
            return "break"
        self.send_chat_message()
        return "break"

    def send_chat_message(self):
        if self.chat_streaming:
            return
        link = self.selected_chat_link()
        if not link:
            return messagebox.showwarning("提示", "请先在「链路管理」里选择一条链路")
        if not link.get("apiURL") or not link.get("apiKey"):
            return messagebox.showwarning("提示", "该链路未配置完整（Base URL / API Key）")
        model = self.ent_chat_model.get().strip() or (link.get("model") or "").strip()
        if not model:
            return messagebox.showwarning("提示", "请填写模型名（上游模型名）")
        text = self.chat_input.get("1.0", tk.END).strip()
        if not text:
            return

        route, base, warning, error = self.resolve_chat_route(link, self.chat_route_mode())
        if error:
            return messagebox.showerror("端口占用提示", error)
        if warning:
            messagebox.showwarning("端口占用提示", warning)
            UI_QUEUE.put(("log_err", warning))

        self.chat_messages.append({"role": "user", "content": text})
        self._append_chat("\n你：%s\n\n" % text, "user")
        self.chat_input.delete("1.0", tk.END)
        self._chat_content_buf = ""
        self._chat_reasoning_buf = ""
        self._chat_shown_reasoning = False
        self._chat_shown_ai = False
        self.chat_streaming = True
        self._chat_stop = threading.Event()
        self.btn_chat_send.config(state=tk.DISABLED, text="发送中…")
        self.btn_chat_stop.config(state=tk.NORMAL)
        UI_QUEUE.put(("log", "对话请求 → %s（%s）" % (
            "本机中继" if route == "relay" else "上游直连", base)))

        threading.Thread(
            target=self._chat_worker,
            args=(base, link.get("apiKey", ""), model, list(self.chat_messages), self._chat_stop),
            daemon=True).start()

    def _chat_worker(self, base, api_key, model, messages, stop_event):
        content = ""
        try:
            for kind, value in iter_chat_stream(base, api_key, model, messages, stop_event):
                if kind == "content":
                    content += value
                    UI_QUEUE.put(("chat_delta", ("content", value)))
                elif kind == "reasoning":
                    UI_QUEUE.put(("chat_delta", ("reasoning", value)))
                else:
                    UI_QUEUE.put(("chat_usage", value))
            if stop_event.is_set():
                UI_QUEUE.put(("chat_stopped", content))
            else:
                UI_QUEUE.put(("chat_done", content))
        except Exception as exc:
            UI_QUEUE.put(("chat_err", str(exc)))
        finally:
            UI_QUEUE.put(("chat_end", None))

    def stop_chat(self):
        if self._chat_stop is not None:
            self._chat_stop.set()
            self.btn_chat_stop.config(state=tk.DISABLED)
            UI_QUEUE.put(("log", "正在停止对话…"))

    def new_chat(self):
        if self.chat_streaming:
            return messagebox.showwarning("提示", "当前对话还在生成，请先停止")
        self.chat_messages = []
        self._chat_content_buf = ""
        self._chat_reasoning_buf = ""
        self.chat_text.config(state=tk.NORMAL)
        self.chat_text.delete("1.0", tk.END)
        self.chat_text.config(state=tk.DISABLED)
        save_chat_history([])
        UI_QUEUE.put(("log", "已开始新对话"))

    def clear_chat_history(self):
        if self.chat_streaming:
            return messagebox.showwarning("提示", "当前对话还在生成，请先停止")
        if not messagebox.askyesno("确认", "清空全部对话记录？（不可恢复）"):
            return
        self.chat_messages = []
        self.chat_text.config(state=tk.NORMAL)
        self.chat_text.delete("1.0", tk.END)
        self.chat_text.config(state=tk.DISABLED)
        try:
            if os.path.exists(CHAT_HISTORY_FILE):
                os.remove(CHAT_HISTORY_FILE)
        except Exception as exc:
            UI_QUEUE.put(("log_err", "删除对话记录失败: %s" % exc))
        UI_QUEUE.put(("log", "对话记录已清空"))

    # ---------- 缓存清理 ----------
    def setup_cache(self):
        wrap = tk.Frame(self.tab_cache, bg="#1e1e1e")
        wrap.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        tk.Label(wrap, text="◈ 缓存清理", font=("Consolas", 16, "bold"),
                 fg="#00ffcc", bg="#1e1e1e").pack(anchor="w")
        tk.Label(wrap, text="Codex 会把模型列表、会话等缓存在本机。模型列表刷不出来时，"
                            "通常清掉「模型列表缓存」即可；聊天缓存不会被默认勾选。",
                 fg="#aaa", bg="#1e1e1e", font=("Consolas", 10),
                 wraplength=820, justify=tk.LEFT).pack(anchor="w", pady=(8, 4))
        tk.Label(wrap, text="Codex 缓存目录：%s" % codex_home(),
                 fg="#666", bg="#1e1e1e", font=("Consolas", 9)).pack(anchor="w", pady=(0, 10))

        cats = tk.LabelFrame(wrap, text=" 选择要清理的缓存 ", fg="#00ffcc", bg="#1e1e1e",
                             font=("Consolas", 10))
        cats.pack(fill=tk.X, pady=(0, 10))
        self.var_cache_models = tk.BooleanVar(value=True)
        self.var_cache_chat = tk.BooleanVar(value=False)
        self.var_cache_logs = tk.BooleanVar(value=False)
        self.var_cache_temp = tk.BooleanVar(value=False)
        for var, title, desc in (
                (self.var_cache_models, "模型列表缓存", "解决 Codex 模型列表刷不出来"),
                (self.var_cache_chat, "聊天 / 会话缓存", "Codex 历史会话与本软件对话记录（删除后不可恢复）"),
                (self.var_cache_logs, "日志缓存", "崩溃日志与 Codex 运行日志"),
                (self.var_cache_temp, "临时文件", "缓存目录下的临时文件")):
            row = tk.Frame(cats, bg="#1e1e1e")
            row.pack(fill=tk.X, padx=8, pady=2)
            tk.Checkbutton(row, text=title, variable=var, bg="#1e1e1e", fg="#fff",
                           selectcolor="#111", activebackground="#1e1e1e",
                           activeforeground="#00ffcc",
                           font=("Consolas", 10)).pack(side=tk.LEFT)
            tk.Label(row, text="— " + desc, fg="#777", bg="#1e1e1e",
                     font=("Consolas", 9)).pack(side=tk.LEFT, padx=(6, 0))

        btns = tk.Frame(wrap, bg="#1e1e1e")
        btns.pack(fill=tk.X, pady=(0, 8))
        tk.Button(btns, text="🔍 扫描缓存", bg="#333", fg="#00ffcc", font=("Consolas", 10),
                  relief=tk.FLAT, command=self.scan_cache).pack(side=tk.LEFT, padx=(0, 8), ipady=2)
        tk.Button(btns, text="🧹 清除选中缓存", bg="#ff4444", fg="#fff",
                  font=("Consolas", 10, "bold"), relief=tk.FLAT,
                  command=self.clear_cache_selected).pack(side=tk.LEFT, padx=(0, 8), ipady=2)
        tk.Button(btns, text="⚡ 只清模型缓存", bg="#00ffcc", fg="#111",
                  font=("Consolas", 10, "bold"), relief=tk.FLAT,
                  command=self.quick_clear_models).pack(side=tk.LEFT, padx=(0, 8), ipady=2)
        tk.Button(btns, text="📂 打开 Codex 目录", bg="#333", fg="#00ffcc",
                  font=("Consolas", 9), relief=tk.FLAT,
                  command=self.open_codex_dir).pack(side=tk.LEFT, ipady=2)

        self.lbl_cache_summary = tk.Label(wrap, text="点击「扫描缓存」查看将删除的文件",
                                          fg="#888", bg="#1e1e1e",
                                          font=("Consolas", 9), anchor="w")
        self.lbl_cache_summary.pack(fill=tk.X, pady=(0, 4))
        self.cache_text = tk.Text(wrap, bg="#111", fg="#bbb", font=("Consolas", 9),
                                  relief=tk.FLAT, state=tk.DISABLED)
        self.cache_text.pack(fill=tk.BOTH, expand=True)
        self.cache_targets = []

    def selected_cache_cats(self):
        cats = []
        if self.var_cache_models.get():
            cats.append("models")
        if self.var_cache_chat.get():
            cats.append("chat")
        if self.var_cache_logs.get():
            cats.append("logs")
        if self.var_cache_temp.get():
            cats.append("temp")
        return cats

    def scan_cache(self):
        cats = self.selected_cache_cats()
        if not cats:
            self.cache_text.config(state=tk.NORMAL)
            self.cache_text.delete("1.0", tk.END)
            self.cache_text.insert(tk.END, "未勾选任何类别。\n")
            self.cache_text.config(state=tk.DISABLED)
            return
        self.lbl_cache_summary.config(text="正在扫描缓存…")
        UI_QUEUE.put(("log", "正在扫描缓存…"))

        def work():
            try:
                UI_QUEUE.put(("cache_scan", _cache_targets(cats)))
            except Exception as exc:
                UI_QUEUE.put(("cache_scan_err", str(exc)))

        threading.Thread(target=work, daemon=True).start()

    def render_cache_scan(self, targets):
        self.cache_targets = targets
        self.cache_text.config(state=tk.NORMAL)
        self.cache_text.delete("1.0", tk.END)
        if not targets:
            self.cache_text.insert(tk.END, "未发现可清理的缓存（可能已经清理干净）。\n")
            self.lbl_cache_summary.config(text="未发现缓存。Codex 目录：%s" % codex_home())
        else:
            total = 0
            current = None
            for target in targets:
                total += target["size"]
                if target["cat"] != current:
                    current = target["cat"]
                    self.cache_text.insert(tk.END, "\n[%s]\n" % CACHE_TITLES.get(current, current))
                self.cache_text.insert(
                    tk.END, "  · %s  %s  (%s)\n" % (
                        target["source"], target["path"], fmt_size(target["size"])))
            self.lbl_cache_summary.config(
                text="共 %d 项，合计 %s。auth.json / config.toml 等登录配置不会被删除。"
                     % (len(targets), fmt_size(total)))
        self.cache_text.config(state=tk.DISABLED)

    def clear_cache_selected(self):
        self._clear_cache(self.selected_cache_cats())

    def quick_clear_models(self):
        self.var_cache_models.set(True)
        self.var_cache_chat.set(False)
        self.var_cache_logs.set(False)
        self.var_cache_temp.set(False)
        self._clear_cache(["models"])

    def _clear_cache(self, cats):
        if not cats:
            return messagebox.showwarning("提示", "请至少勾选一个缓存类别")
        try:
            targets = _cache_targets(cats)
        except Exception as exc:
            return messagebox.showerror("错误", "扫描缓存失败: %s" % exc)
        if not targets:
            self.render_cache_scan([])
            return messagebox.showinfo("提示", "没有需要清理的缓存")
        total = sum(t["size"] for t in targets)
        preview = "\n".join("  · [%s] %s" % (CACHE_TITLES.get(t["cat"], t["cat"]), t["path"])
                            for t in targets[:12])
        if len(targets) > 12:
            preview += "\n  … 另有 %d 项" % (len(targets) - 12)
        warn = ""
        if "chat" in cats:
            warn = "\n\n⚠ 包含聊天 / 会话缓存，删除后无法恢复！"
        msg = ("将清理 %d 项缓存，共 %s%s\n\n%s\n\n确定继续吗？"
               % (len(targets), fmt_size(total), warn, preview))
        if not messagebox.askyesno("确认清理缓存", msg):
            return

        self.cache_text.config(state=tk.NORMAL)
        self.cache_text.delete("1.0", tk.END)
        self.cache_text.insert(tk.END, "正在清理…\n")
        self.cache_text.config(state=tk.DISABLED)
        self.lbl_cache_summary.config(text="正在清理…")

        def work():
            try:
                removed, failed = remove_cache_targets(targets)
                UI_QUEUE.put(("cache_clear_done", (removed, failed)))
            except Exception as exc:
                UI_QUEUE.put(("cache_scan_err", str(exc)))

        threading.Thread(target=work, daemon=True).start()

    def on_cache_clear_done(self, removed, failed):
        freed = sum(t["size"] for t in removed)
        for target in removed:
            UI_QUEUE.put(("log", "已删除缓存: %s" % target["path"]))
        for target, err in failed:
            UI_QUEUE.put(("log_err", "删除失败: %s（%s）" % (target["path"], err)))
        self.scan_cache()
        summary = "已清理 %d 项，释放 %s" % (len(removed), fmt_size(freed))
        if failed:
            summary += "；%d 项失败，详见日志" % len(failed)
            messagebox.showwarning("清理完成", summary)
        else:
            messagebox.showinfo("清理完成", summary)

    def open_codex_dir(self):
        home = codex_home()
        if not os.path.isdir(home):
            return messagebox.showinfo("提示", "未找到 Codex 缓存目录：\n%s" % home)
        try:
            os.startfile(home)
        except Exception as exc:
            messagebox.showerror("错误", "无法打开目录: %s" % exc)

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

        # 对话页的链路下拉同步
        try:
            if hasattr(self, "cb_chat_links"):
                self.cb_chat_links["values"] = names
                if names:
                    if self.cb_chat_links.get() not in names:
                        self.cb_chat_links.current(0)
                    self.on_chat_link_select()
                else:
                    self.cb_chat_links.set("")
                    self.ent_chat_model.delete(0, tk.END)
                    self.update_chat_port_status()
        except Exception:
            pass

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
        """启动 Flask 在指定端口（启动前先检查端口是否被其他程序占用）"""
        port = int(cfg.get("ListenPort", 15721))
        host = "127.0.0.1"
        in_use, _, _ = _port_owner(port)
        if in_use:
            UI_QUEUE.put(("log_err", "启动失败：" + describe_port(port)))
            return False
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
            self.update_chat_port_status()
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

            port = cfg.get("ListenPort", 15721)
            in_use, _, _ = _port_owner(port)
            if in_use:
                msg = describe_port(port)
                UI_QUEUE.put(("log_err", "启动失败：" + msg))
                return messagebox.showerror("端口被占用", msg + "\n\n请修改该链路的监听端口，或先停止占用该端口的程序。")

            if self.start_server(cfg):
                self.is_running = True
                self.btn_toggle.config(text="🛑 停止链路", bg="#ff4444", fg="#fff")
                self.status_label.config(text=f"● 监听: http://127.0.0.1:{port} [ {name} ]", fg="#00ff00")
                UI_QUEUE.put(("log", f"已开启链路: {name} (端口 {port})"))
                self.update_chat_port_status()
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
                elif msg == "chat_delta":
                    kind, text = data
                    if kind == "reasoning":
                        self._chat_reasoning_buf += text
                        if not self._chat_shown_reasoning:
                            self._chat_shown_reasoning = True
                            self._append_chat("（思考）", "reasoning")
                        self._append_chat(text, "reasoning")
                    else:
                        self._chat_content_buf += text
                        if not self._chat_shown_ai:
                            self._chat_shown_ai = True
                            if self._chat_shown_reasoning:
                                self._append_chat("\n\n", "assistant")
                            self._append_chat("AI：", "assistant")
                        self._append_chat(text, "assistant")
                elif msg == "chat_usage":
                    inp = data.get("prompt_tokens", data.get("input_tokens", 0)) or 0
                    out = data.get("completion_tokens", data.get("output_tokens", 0)) or 0
                    self._append_chat("\n（tokens: 输入 %s / 输出 %s）" % (inp, out), "system")
                elif msg == "chat_stopped":
                    self._append_chat("\n\n[已停止生成]\n", "system")
                    UI_QUEUE.put(("log", "对话已手动停止"))
                elif msg == "chat_done":
                    if not self._chat_shown_ai and self._chat_shown_reasoning:
                        self._append_chat("\n\n", "assistant")
                    if self._chat_content_buf.strip():
                        self.chat_messages.append(
                            {"role": "assistant", "content": self._chat_content_buf})
                        save_chat_history(self.chat_messages)
                    self._append_chat("\n\n", "system")
                    GLOBAL_STATS["requests"] += 1
                    UI_QUEUE.put(("log", "对话完成"))
                elif msg == "chat_err":
                    self._append_chat("\n[错误] %s\n\n" % data, "err")
                    UI_QUEUE.put(("log_err", "对话请求失败: %s" % data))
                elif msg == "chat_end":
                    self.chat_streaming = False
                    self.btn_chat_send.config(state=tk.NORMAL, text="发送")
                    self.btn_chat_stop.config(state=tk.DISABLED)
                elif msg == "chat_models":
                    name, models, err = data
                    if models:
                        self._chat_models_cache[name] = models
                        if self.cb_chat_links.get() == name:
                            self.ent_chat_model["values"] = models
                            if not self.ent_chat_model.get().strip():
                                self.ent_chat_model.set(models[0])
                        self.log("已获取 %s 的 %d 个模型，可在下拉框中选择" % (name, len(models)))
                    elif err:
                        self.log("获取模型列表失败（%s）：%s" % (name, err), is_err=True)
                elif msg == "cache_scan":
                    self.render_cache_scan(data if isinstance(data, list) else [])
                elif msg == "cache_scan_err":
                    self.lbl_cache_summary.config(text="扫描失败：%s" % data)
                    UI_QUEUE.put(("log_err", "扫描缓存失败: %s" % data))
                elif msg == "cache_clear_done":
                    self.on_cache_clear_done(data[0], data[1])
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