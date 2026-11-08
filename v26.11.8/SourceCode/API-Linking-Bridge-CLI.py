#!/usr/bin/env python3
_As='\x1b[?25h\x1b[?1049l'
_Ar='/chat/completions'
_Aq='请先在控制台开启一条链路'
_Ap='reasoning_content'
_Ao='http://localhost:8080/v1'
_An='latest'
_Am='clear'
_Al='restart'
_Ak='completion_tokens'
_Aj='prompt_tokens'
_Ai='created_at'
_Ah='tools'
_Ag='call_'
_Af='thread'
_Ae='发生错误：%s: %s'
_Ad='(日志写入失败)'
_Ac='unknown'
_Ab='secret'
_Aa='version'
_AZ='providers'
_AY='help'
_AX='Authorization'
_AW='annotations'
_AV='summary'
_AU='total'
_AT='tool_calls'
_AS='function_call'
_AR='last'
_AQ='replace'
_AP='steps'
_AO='port'
_AN='del'
_AM='start'
_AL='new'
_AK='stop'
_AJ='stream'
_AI='assistant'
_AH='call_id'
_AG='output_text'
_AF='lock'
_AE='missing'
_AD='错误日志已保存：%s'
_AC='logs'
_AB='choices'
_AA='completed'
_A9='summary_text'
_A8='reasoning'
_A7='input'
_A6='message'
_A5='server'
_A4='config'
_A3='url'
_A2='choice'
_A1='data'
_A0='response'
_z='object'
_y='inflight'
_x='='
_w='default'
_v='values'
_u='usage'
_t='output'
_s='log'
_r='info'
_q='editing'
_p='log_err'
_o='status'
_n='buffer'
_m='stats'
_l='role'
_k='requests'
_j='output_tokens'
_i='input_tokens'
_h='ExChangeModel'
_g='mode'
_f='utf-8'
_e='translation'
_d='cyan'
_c='  '
_b='total_tokens'
_a='\n'
_Z='direct'
_Y='content'
_X='active_link'
_W='arguments'
_V='dim'
_U='function'
_T='warn'
_S='disable_tools'
_R='apiURL'
_Q='ok'
_P='label'
_O='index'
_N='ListenPort'
_M='apiKey'
_L='text'
_K='id'
_J='error'
_I='key'
_H='model'
_G='err'
_F=' '
_E=True
_D=False
_C=None
_B='name'
_A='type'
import os,sys,time,json,uuid,codecs,shutil,socket,subprocess,logging,threading,queue,unicodedata,webbrowser,traceback,platform
from collections import deque
import requests
from flask import Flask,request,Response,jsonify,g
try:import msvcrt
except ImportError:msvcrt=_C
class _NullIO:
	'无控制台（例如 --noconsole 打包）时的替身流，避免 None.write / None.isatty。';encoding=_f
	def write(A,data=''):return len(data)
	def flush(A):0
	def isatty(A):return _D
	def reconfigure(A,**B):0
	def readline(A,*B):raise EOFError
	def __iter__(A):return iter(())
HAS_CONSOLE=sys.stdout is not _C and sys.stdin is not _C
if sys.stdout is _C:sys.stdout=_NullIO()
if sys.stderr is _C:sys.stderr=_NullIO()
if sys.stdin is _C:sys.stdin=_NullIO()
log=logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
VERSION = "26.11.8"
UPDATE_API='https://apicheckupdate.ctxcode.cn/APILinkingBridge'
HOMEPAGE='https://alb.ctxcode.cn'
RESET='\x1b[0m'
DIM='\x1b[2m'
REV='\x1b[7m'
C_OK='\x1b[32m'
C_ERR='\x1b[31m'
C_WARN='\x1b[33m'
C_INFO='\x1b[37m'
C_DIM='\x1b[90m'
C_CYAN='\x1b[36m'
LEVEL_COLOR={_Q:C_OK,_G:C_ERR,_T:C_WARN,_V:C_DIM,_d:C_CYAN,'cmd':C_CYAN,'chat_user':C_CYAN,'chat_ai':C_INFO,'chat_reason':C_DIM}
def init_console():
	if os.name=='nt':
		try:
			import ctypes as B;A=B.windll.kernel32;A.SetConsoleOutputCP(65001);A.SetConsoleCP(65001);C=A.GetStdHandle(-11);D=B.c_uint32()
			if A.GetConsoleMode(C,B.byref(D)):A.SetConsoleMode(C,D.value|4)
		except Exception:0
	for E in(sys.stdout,sys.stderr,sys.stdin):
		try:E.reconfigure(encoding=_f,errors=_AQ)
		except Exception:0
def dwidth(text):
	A=0
	for B in text:A+=2 if unicodedata.east_asian_width(B)in('W','F')else 1
	return A
def cut_text(text,width):
	B=width
	if B<=0:return'',0
	C,A=[],0
	for D in text:
		E=2 if unicodedata.east_asian_width(D)in('W','F')else 1
		if A+E>B:break
		C.append(D);A+=E
	return''.join(C),A
def pad_display(text,width):return text+_F*max(0,width-dwidth(text))
def colorize(text,color,width):B=width;A=color;C,D=cut_text(text,B);return(A or'')+C+_F*(B-D)+(RESET if A else'')
def border_seg(n,title):
	A=_F+title.strip()+_F
	if dwidth(A)>n-1:A,B=cut_text(A,max(0,n-1))
	return'═'+A+'═'*max(0,n-1-dwidth(A))
FORM_FIELDS=[{_I:_B,_P:'链路名称',_A:_L},{_I:_R,_P:'Base URL',_A:_L},{_I:_M,_P:'API Key',_A:_L,_Ab:_E},{_I:_H,_P:'上游模型名',_A:_L},{_I:_N,_P:'监听端口',_A:_L},{_I:_g,_P:'转换模式',_A:_A2,_AB:[_e,_Z]},{_I:_S,_P:'禁用工具调用',_A:_A2,_AB:[_D,_E]},{_I:'__save',_P:'保存',_A:'action'},{_I:'__cancel',_P:'取消',_A:'action'}]
ACTION_SAVE=7
ACTION_CANCEL=8
def render_segments(segments,width,base=''):
	E=width;B=base;A=[B]if B else[];C=0
	for(D,F)in segments:
		if C>=E:break
		D,G=cut_text(D,E-C);C+=G
		if F:A.append(F+D+RESET+B)
		else:A.append(D)
	if B:A.append(B)
	A.append(_F*max(0,E-C));A.append(RESET);return''.join(A)
def init_environment():
	C='APILinkingBridge';B='C:\\Users\\Administrator'
	if os.path.exists(B):A=os.path.join(B,C)
	else:A=os.path.join(os.environ.get('USERPROFILE',os.path.expanduser('~')),C)
	os.makedirs(A,exist_ok=_E);return os.path.join(A,'APIsetting.json')
API_FILE=init_environment()
BASE_DIR=os.path.dirname(API_FILE)
LOG_DIR=os.path.join(BASE_DIR,_AC)
try:os.makedirs(LOG_DIR,exist_ok=_E)
except Exception:LOG_DIR=BASE_DIR
_LOG_SINK=_C
def ui_log(text,level=_r):
	A=_LOG_SINK
	if A is _C:return
	try:A(text,level)
	except Exception:0
def _write_crash_log(exc_type,exc,tb,context='CLI',recent=_C):
	C=recent;A=''
	try:
		D=time.localtime();F='crash-%s-%03d-%d.log'%(time.strftime('%Y%m%d-%H%M%S',D),int(time.time()%1*1000),os.getpid());A=os.path.join(LOG_DIR,F);B=[_x*78,' API Linking Bridge 崩溃日志 / Crash Report',_x*78,'时间      : %s'%time.strftime('%Y-%m-%d %H:%M:%S',D),'版本      : %s'%VERSION,'界面      : %s'%(context or _Ac),'Python    : %s (%s)'%(sys.version.split()[0],platform.machine()),'系统      : %s'%platform.platform(),'进程 ID   : %s'%os.getpid(),'当前目录  : %s'%os.getcwd(),'配置目录  : %s'%BASE_DIR,_x*78,'','------------- 调用栈 / Traceback -------------',''.join(traceback.format_exception(exc_type,exc,tb)).rstrip(),'']
		if C:B.append('------------- 最近的界面日志 / Recent Logs -------------');B.extend(str(A)for A in C);B.append('')
		with open(A,'w',encoding=_f,errors=_AQ)as G:G.write(_a.join(B)+_a)
		try:
			H=sorted((os.path.join(LOG_DIR,A)for A in os.listdir(LOG_DIR)if A.startswith('crash-')and A.endswith('.log')),key=os.path.getmtime)
			for E in H[:-50]:
				if E!=A:
					try:os.remove(E)
					except Exception:0
		except Exception:0
	except Exception:A=A or _Ad
	return A
def install_crash_handlers(app=_C):
	A=app;global _LOG_SINK
	if A is not _C:_LOG_SINK=A.log
	def E():
		try:return[A for(A,B)in list(A.logs)[-40:]]
		except Exception:return[]
	def B(exc_type,exc,tb,context):
		B=exc_type
		if B in(KeyboardInterrupt,SystemExit):return''
		C=_write_crash_log(B,exc,tb,context,E());D=_Ae%(B.__name__,exc)
		try:
			if A is not _C:A.log(D,_G);A.log(_AD%C,_G)
			else:print(D,file=sys.stderr);print(_AD%C,file=sys.stderr)
		except Exception:0
		return C
	def C(exc_type,exc,tb):B(exc_type,exc,tb,'CLI 主线程')
	sys.excepthook=C
	if hasattr(threading,'excepthook'):
		def D(args):
			A=args
			if A.exc_type in(KeyboardInterrupt,SystemExit):return
			C=A.thread.name if A.thread else'后台线程';B(A.exc_type,A.exc_value,A.exc_traceback,'后台线程 %s'%C)
		threading.excepthook=D
	return B
PROVIDERS={'自定义 (Custom)':'','NVIDIA':'https://integrate.api.nvidia.com/v1','DeepSeek':'https://api.deepseek.com/v1','OpenAI':'https://api.openai.com/v1','Moonshot (Kimi)':'https://api.moonshot.cn/v1','Aliyun (Qwen)':'https://dashscope.aliyuncs.com/compatible-mode/v1','Zhipu (GLM)':'https://open.bigmodel.cn/api/paas/v4','Groq':'https://api.groq.com/openai/v1','[国内] Moonshot (Kimi) 国际版':'https://api.moonshot.ai/v1','[国内] Zhipu (GLM) 国际版':'https://api.z.ai/api/paas/v4','[国内] Aliyun (Qwen) 国际站':'https://dashscope-intl.aliyuncs.com/compatible-mode/v1','[国内] Aliyun (Qwen) 美国站':'https://dashscope-us.aliyuncs.com/compatible-mode/v1','[国内] SiliconFlow 硅基流动':'https://api.siliconflow.cn/v1','[国内] Volcengine Ark 火山方舟':'https://ark.cn-beijing.volces.com/api/v3','[国内] Baidu Qianfan 百度千帆':'https://qianfan.baidubce.com/v2','[国内] Tencent Hunyuan 腾讯混元':'https://api.hunyuan.cloud.tencent.com/v1','[国内] iFlytek Spark 讯飞星火':'https://spark-api-open.xf-yun.com/v1','[国内] MiniMax':'https://api.minimaxi.com/v1','[国内] MiniMax 国际版':'https://api.minimax.io/v1','[国内] StepFun 阶跃星辰':'https://api.stepfun.com/v1','[国内] 01.AI 零一万物':'https://api.lingyiwanwu.com/v1','[国内] Baichuan 百川智能':'https://api.baichuan-ai.com/v1','[国内] SenseNova 商汤日日新':'https://api.sensenova.cn/compatible-mode/v1','[国内] Infini 无问芯穹':'https://cloud.infini-ai.com/maas/v1','[海外] xAI (Grok)':'https://api.x.ai/v1','[海外] Mistral':'https://api.mistral.ai/v1','[海外] Together AI':'https://api.together.xyz/v1','[海外] Fireworks AI':'https://api.fireworks.ai/inference/v1','[海外] DeepInfra':'https://api.deepinfra.com/v1/openai','[海外] Perplexity':'https://api.perplexity.ai','[海外] Cerebras':'https://api.cerebras.ai/v1','[海外] SambaNova':'https://api.sambanova.ai/v1','[海外] Nebius Token Factory':'https://api.tokenfactory.nebius.com/v1','[海外] Hyperbolic':'https://api.hyperbolic.xyz/v1','[海外] Novita AI':'https://api.novita.ai/openai/v1','[海外] Lambda Inference':'https://api.lambda.ai/v1','[海外] Google Gemini':'https://generativelanguage.googleapis.com/v1beta/openai','[海外] Cohere':'https://api.cohere.ai/compatibility/v1','[聚合] OpenRouter':'https://openrouter.ai/api/v1','[聚合] AIML API':'https://api.aimlapi.com/v1','[聚合] Requesty':'https://router.requesty.ai/v1','[聚合] GitHub Models':'https://models.inference.ai.azure.com','[聚合] Cloudflare Workers AI':'https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/v1','[聚合] Azure OpenAI (需 api-key 头, 本工具不适配)':'https://{resource}.openai.azure.com/openai/deployments/{deployment}','[本地] Ollama':'http://localhost:11434/v1','[本地] LM Studio':'http://localhost:1234/v1','[本地] vLLM':'http://localhost:8000/v1','[本地] llama.cpp':_Ao,'[本地] LocalAI':_Ao,'[本地] Xinference':'http://localhost:9997/v1','[本地] LiteLLM Proxy':'http://localhost:4000/v1','[本地] One API / New API':'http://localhost:3000/v1'}
def resolve_provider(name):
	A=name
	if not A:return
	if A in PROVIDERS:return PROVIDERS[A]
	B=A.lower()
	for(D,E)in PROVIDERS.items():
		if D.lower()==B:return E
	C=[A for(C,A)in PROVIDERS.items()if A and B in C.lower()]
	if len(C)==1:return C[0]
def migrate_legacy_config(data,path):
	A=data;C=[];D=A.get('links')if isinstance(A,dict)else _C
	if isinstance(D,dict):
		for(E,(F,B))in enumerate(D.items(),1):
			if not isinstance(B,dict):continue
			C.append({_B:F or f"Link{E}",_R:B.get(_A3,B.get(_R,'')),_M:B.get(_I,B.get(_M,'')),_H:B.get(_H,''),_N:int(B.get(_N,15720+E)),_S:bool(B.get(_S,_D)),_h:_Z if B.get(_g)==_Z else _e})
	if not C and(A.get(_A3)or A.get(_I)):C.append({_B:'默认链路',_R:A.get(_A3,''),_M:A.get(_I,''),_H:A.get(_H)or'',_N:15721,_S:bool(A.get(_S,_D)),_h:_Z if A.get(_g)==_Z else _e})
	return C
def save_links(links):
	with open(API_FILE,'w',encoding=_f)as A:json.dump(links,A,indent=4,ensure_ascii=_D)
def load_links():
	if not os.path.exists(API_FILE):return[]
	try:
		with open(API_FILE,'r',encoding=_f)as B:A=json.load(B)
	except Exception:return[]
	if isinstance(A,list):return A
	C=migrate_legacy_config(A,API_FILE)
	try:
		with open(API_FILE+'.bak','w',encoding=_f)as B:json.dump(A,B,indent=4,ensure_ascii=_D)
		save_links(C)
	except Exception:0
	return C
# ==================== 端口占用检测 ====================
def _find_port_pid(port):
    """Windows 下用 netstat/tasklist 找出监听某端口的进程，失败返回 (None, "")。"""
    if os.name != 'nt':
        return None, ''
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    try:
        raw = subprocess.check_output(['netstat', '-ano', '-p', 'TCP'],
                                      creationflags=flags, timeout=6)
        text = raw.decode('mbcs', errors='replace')
    except Exception:
        return None, ''
    pid = None
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        local, state, pid_text = parts[1], parts[3], parts[4]
        if not local.endswith(':' + str(port)):
            continue
        if state.upper() != 'LISTENING':
            continue
        try:
            pid = int(pid_text)
        except ValueError:
            continue
        break
    if pid is None:
        return None, ''
    name = ''
    try:
        raw = subprocess.check_output(
            ['tasklist', '/FI', 'PID eq %d' % pid, '/FO', 'CSV', '/NH'],
            creationflags=flags, timeout=6)
        lines = raw.decode('mbcs', errors='replace').strip().splitlines()
        if lines:
            name = lines[0].split(',')[0].strip('"')
    except Exception:
        pass
    return pid, name

def _port_owner(port):
    """返回 (是否被监听, PID, 进程名)。只做提示，不参与业务判断。"""
    try:
        port = int(port)
    except Exception:
        return False, None, ''
    sock = None
    listening = False
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.4)
        listening = (sock.connect_ex(('127.0.0.1', port)) == 0)
    except Exception:
        listening = False
    finally:
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass
    if not listening:
        return False, None, ''
    pid, name = _find_port_pid(port)
    return True, pid, name

def describe_port(port, ours=False):
    """把端口状态翻译成一句人话，供界面/命令提示。"""
    if ours:
        return '● 本机中继运行中  http://127.0.0.1:%s' % port
    in_use, pid, name = _port_owner(port)
    if not in_use:
        return '○ 端口 %s 空闲，可用' % port
    who = name or '未知进程'
    if pid is not None:
        who += '（PID %s）' % pid
    extra = ''
    if pid is not None and pid == os.getpid():
        extra = '（当前进程）'
    elif name and name.lower().startswith(('python', 'api-linking-bridge', 'api linking bridge')):
        extra = '，可能是本程序的另一个实例'
    return '⚠ 端口 %s 已被其他程序占用：%s%s' % (port, who, extra)

# ==================== 缓存清理 ====================
CACHE_CATEGORIES = [
    ('models', '模型列表缓存', '解决 Codex / 客户端模型列表刷不出来'),
    ('chat', '聊天 / 会话缓存', 'Codex 历史会话与本软件对话记录'),
    ('logs', '日志缓存', '本软件崩溃日志与 Codex 运行日志'),
    ('temp', '临时文件', '缓存目录下的临时文件'),
]
CACHE_TITLES = {key: title for key, title, _ in CACHE_CATEGORIES}
_CACHE_PROTECTED = {'auth.json', 'config.toml', 'config.json', 'settings.json',
                    'AGENTS.md', 'instructions.md'}

def codex_home():
    """定位 Codex 的配置/缓存目录：优先 CODEX_HOME，其次 ~/.codex。"""
    env_path = (os.environ.get('CODEX_HOME') or '').strip()
    if env_path:
        return os.path.expandvars(os.path.expanduser(env_path))
    return os.path.join(os.path.expanduser('~'), '.codex')

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
    for unit in ('B', 'KB', 'MB', 'GB'):
        if value < 1024 or unit == 'GB':
            return ('%d %s' % (value, unit)) if unit == 'B' else ('%.1f %s' % (value, unit))
        value /= 1024.0
    return '%.1f GB' % value

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
        if base in _CACHE_PROTECTED or base.endswith(('.toml', '.key', '.pem')):
            return
        if full in seen or not os.path.exists(full):
            return
        seen.add(full)
        targets.append({'cat': cat, 'source': source, 'path': full,
                        'is_dir': os.path.isdir(full), 'size': _path_size(full)})

    home = codex_home()
    if os.path.isdir(home):
        try:
            for name in os.listdir(home):
                low = name.lower()
                if 'model' in low and ('cache' in low or 'catalog' in low):
                    add('models', 'Codex', os.path.join(home, name))
        except Exception:
            pass
        for name in ('sessions', 'archived_sessions', 'session_index.jsonl',
                     'history.jsonl', 'history.json', 'transcription-history.jsonl'):
            add('chat', 'Codex', os.path.join(home, name))
        for name in ('log', 'logs'):
            add('logs', 'Codex', os.path.join(home, name))
        for name in ('tmp', 'temp', 'cache', '.tmp'):
            add('temp', 'Codex', os.path.join(home, name))
        try:
            for name in os.listdir(home):
                if name.lower().endswith(('.tmp', '.temp')):
                    add('temp', 'Codex', os.path.join(home, name))
        except Exception:
            pass

    add('temp', '本软件', os.path.join(BASE_DIR, 'cache'))
    add('chat', '本软件', CHAT_HISTORY_FILE)
    add('models', '本软件', os.path.join(BASE_DIR, 'model_cache.json'))
    if 'logs' in cats:
        try:
            for name in os.listdir(LOG_DIR):
                if name.startswith('crash-') and name.endswith('.log'):
                    add('logs', '本软件', os.path.join(LOG_DIR, name))
        except Exception:
            pass

    targets.sort(key=lambda item: (item['cat'], item['path'].lower()))
    return targets

def remove_cache_targets(targets):
    """按列表删除缓存，返回 (成功列表, [(目标, 错误), ...])。"""
    removed, failed = [], []
    for target in targets:
        try:
            if target['is_dir']:
                shutil.rmtree(target['path'])
            else:
                os.remove(target['path'])
            removed.append(target)
        except Exception as exc:
            failed.append((target, str(exc)))
    return removed, failed

# ==================== 内置对话 ====================
CHAT_HISTORY_FILE = os.path.join(BASE_DIR, 'chat_history.json')

def load_chat_history():
    try:
        with open(CHAT_HISTORY_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list):
            return [m for m in data
                    if isinstance(m, dict)
                    and m.get('role') in ('user', 'assistant')
                    and isinstance(m.get('content'), str)]
    except Exception:
        pass
    return []

def save_chat_history(messages):
    try:
        os.makedirs(BASE_DIR, exist_ok=True)
        with open(CHAT_HISTORY_FILE, 'w', encoding='utf-8') as f:
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
    url = base.rstrip('/') + '/chat/completions'
    headers = {'Authorization': 'Bearer %s' % api_key,
               'Content-Type': 'application/json'}
    body = {'model': model, 'messages': messages, 'stream': True,
            'stream_options': {'include_usage': True}}
    resp = None
    try:
        resp = requests.post(url, headers=headers, json=body, stream=True, timeout=600)
        if resp.status_code != 200:
            resp.close()
            body.pop('stream_options', None)
            resp = requests.post(url, headers=headers, json=body, stream=True, timeout=600)
            if resp.status_code != 200:
                detail = resp.text[:500]
                resp.close()
                raise RuntimeError('上游返回 %s: %s' % (resp.status_code, detail))
    except Exception:
        if resp is not None:
            try:
                resp.close()
            except Exception:
                pass
        raise

    decoder = codecs.getincrementaldecoder('utf-8')('replace')
    buffer = ''
    try:
        for raw in resp.iter_content(chunk_size=1024):
            if stop_event is not None and stop_event.is_set():
                break
            if not raw:
                continue
            buffer += decoder.decode(raw)
            if '\n' not in buffer:
                continue
            lines = buffer.split('\n')
            buffer = lines.pop()
            for line in lines:
                line = line.strip()
                if not line.startswith('data:'):
                    continue
                payload = line[5:].strip()
                if not payload or payload == '[DONE]':
                    continue
                try:
                    chunk = json.loads(payload)
                except Exception:
                    continue
                usage = chunk.get('usage')
                if usage:
                    yield ('usage', usage)
                for choice in chunk.get('choices') or []:
                    delta = choice.get('delta') or {}
                    reasoning = delta.get('reasoning_content') or delta.get('reasoning')
                    if reasoning:
                        yield ('reasoning', reasoning)
                    content = delta.get('content')
                    if isinstance(content, str) and content:
                        yield ('content', content)
    finally:
        try:
            resp.close()
        except Exception:
            pass

def wrap_display(text, width):
    """按终端显示宽度把长文本折成多行（中文按 2 列计算）。"""
    lines, current, used = [], '', 0
    for ch in text:
        if ch == '\n':
            lines.append(current)
            current, used = '', 0
            continue
        char_width = 2 if unicodedata.east_asian_width(ch) in ('W', 'F') else 1
        if used + char_width > width:
            lines.append(current)
            current, used = '', 0
        current += ch
        used += char_width
    if current or not lines:
        lines.append(current)
    return lines

PROXY_APP=Flask(__name__)
UI_QUEUE=queue.Queue()
GLOBAL_STATS={_i:0,_j:0,_b:0,_k:0,_AE:0}
LIVE={_y:0,_AF:threading.Lock()}
LINK_STATS={}
PROXY_STATE={_X:_C,_A4:{},_A5:_C,_Af:_C}
def _link_stat(name,create=_D):
	A=name
	if not A:return
	if not create:return LINK_STATS.get(A)
	return LINK_STATS.setdefault(A,{_k:0,_AE:0,_i:0,_j:0,_b:0,_AR:.0})
def _inflight():
	with LIVE[_AF]:return LIVE[_y]
@PROXY_APP.before_request
def _mark_request_start():
	g._t0=time.time()
	with LIVE[_AF]:LIVE[_y]+=1
@PROXY_APP.after_request
def _mark_status(response):A=response;g._status=A.status_code;return A
@PROXY_APP.teardown_request
def _mark_request_end(exc=_C):
	if not getattr(g,'_streaming',_D):
		with LIVE[_AF]:LIVE[_y]=max(0,LIVE[_y]-1)
	try:
		if request.method=='POST'and request.path.startswith('/v1/'):A=time.time()-getattr(g,'_t0',time.time());UI_QUEUE.put((_s,'请求 %s → %s · %.2fs'%(request.path,getattr(g,'_status','?'),A)))
	except Exception:0
@PROXY_APP.errorhandler(Exception)
def _proxy_internal_error(e):
	from werkzeug.exceptions import HTTPException as B
	if isinstance(e,B):return e
	A=_write_crash_log(type(e),e,e.__traceback__,'HTTP 请求处理',['%s %s'%(request.method,request.path)]);ui_log('请求处理出错：%s: %s'%(type(e).__name__,e),_G);ui_log(_AD%A,_G);return jsonify({_J:{_A6:'服务内部错误，详细信息见日志文件：%s'%A,_A:'internal_error'}}),500
def get_active_config():return PROXY_STATE.get(_A4,{})
def api_base(api):return(api.get(_R)or'').strip().rstrip('/')
def convert_tools_for_chat(tools):
	M='web_search';L='string';K=tools;G='properties';D='parameters';C='description'
	if not K:return[]
	E=[]
	for A in K:
		if not isinstance(A,dict):continue
		H=A.get(_A,'');I=A.get(_U)if isinstance(A.get(_U),dict)else{};B=(A.get(_B)or I.get(_B)or'').strip();J=A.get(C)or I.get(C)or'';F=A.get(D)or I.get(D)
		if H==_U:
			if not F:F={_A:_z,G:{}}
			if not B:continue
			E.append({_A:_U,_U:{_B:B,C:J,D:F}})
		elif H=='custom':
			if not B:continue
			E.append({_A:_U,_U:{_B:B,C:J,D:F or{_A:_z,G:{_A7:{_A:L}}}}})
		elif H==M:E.append({_A:_U,_U:{_B:M,C:'Search the web',D:{_A:_z,G:{'query':{_A:L}}}}})
		elif B:E.append({_A:_U,_U:{_B:B,C:J,D:F or{_A:_z,G:{}}}})
	return E
def responses_to_chat(payload,default_model='gpt-4o',disable_tools=_D,model_override=''):
	S='max_output_tokens';R='user';Q='instructions';N='top_p';M='temperature';K='image_url';A=payload;T=model_override or A.get(_H)or default_model;B=[]
	if A.get(Q):B.append({_l:'system',_Y:A[Q]})
	G=A.get(_A7)
	if isinstance(G,str):B.append({_l:R,_Y:G})
	elif isinstance(G,list):
		for C in G:
			if not isinstance(C,dict):continue
			L=C.get(_A)
			if L in(_C,_A6):
				U=C.get(_l,R);H=C.get(_Y,'')
				if isinstance(H,list):
					I=[]
					for D in H:
						if isinstance(D,dict):
							if D.get(_A)in('input_text',_AG,_L):I.append({_A:_L,_L:D.get(_L,'')})
							elif D.get(_A)in('input_image',K):
								E=D.get(K)
								if isinstance(E,dict):E=E.get(_A3)
								if E:I.append({_A:K,K:{_A3:E}})
					H=I if I else''
				B.append({_l:U,_Y:H})
			elif L==_AS:
				O={_K:C.get(_AH)or C.get(_K)or _Ag+uuid.uuid4().hex,_A:_U,_U:{_B:C.get(_B,''),_W:C.get(_W)or'{}'}}
				if B and B[-1].get(_l)==_AI:
					B[-1].setdefault(_AT,[]).append(O)
					if B[-1].get(_Y)=='':B[-1][_Y]=_C
				else:B.append({_l:_AI,_Y:_C,_AT:[O]})
			elif L=='function_call_output':
				J=C.get(_t,'')
				if not isinstance(J,str):J=json.dumps(J,ensure_ascii=_D)
				B.append({_l:'tool','tool_call_id':C.get(_AH,''),_Y:J})
	F={_H:T,'messages':B,_AJ:bool(A.get(_AJ,_D))}
	if A.get(M)is not _C:F[M]=A[M]
	if A.get(N)is not _C:F[N]=A[N]
	if A.get(S):F['max_tokens']=A[S]
	if not disable_tools:
		P=convert_tools_for_chat(A.get(_Ah))
		if P:F[_Ah]=P
	return F
def sse(event_type,data):return f"event: {event_type}\ndata: {json.dumps(data,ensure_ascii=_D)}\n\n"
def stream_chat_to_responses(upstream,model,response_id):
	A7='response.completed';A6='response.function_call_arguments.done';A5='response.function_call_arguments.delta';A4='response.content_part.done';A3='response.output_text.done';A2='response.output_text.delta';A1='response.content_part.added';A0='final_answer';z='phase';y='response.reasoning_summary_text.delta';x='response.reasoning_summary_part.added';w='response.created';m=response_id;l=model;k='in_progress';b='content_index';a='response.reasoning_summary_part.done';Z='response.reasoning_summary_text.done';Y='delta';Q='part';K='summary_index';J='response.output_item.added';H='item';F='response.output_item.done';D='item_id';B='output_index';n=int(time.time());yield sse(w,{_A:w,_A0:{_K:m,_z:_A0,_Ai:n,_o:k,_H:l,_t:[]}});A=0;L=[];M={_i:0,_j:0,_b:0};N,G,E=_D,'','rs_'+uuid.uuid4().hex;O,R,I=_D,'','msg_'+uuid.uuid4().hex;c={};d=time.time();A8=codecs.getincrementaldecoder(_f)(_AQ);S='';o=_D;p=_D
	for q in upstream.iter_content(chunk_size=1024):
		if not q:continue
		if time.time()-d>3:yield': keep-alive\n\n';d=time.time()
		S+=A8.decode(q)
		if _a not in S:continue
		r=S.split(_a);S=r.pop()
		for T in r:
			T=T.strip()
			if not T.startswith('data:'):continue
			s=T[5:].strip()
			if s=='[DONE]':o=_E;break
			try:e=json.loads(s)
			except Exception:continue
			d=time.time()
			if e.get(_u):f=e[_u];M={_i:f.get(_Aj,0)or 0,_j:f.get(_Ak,0)or 0,_b:f.get(_b,0)or 0};p=_E;UI_QUEUE.put((_m,{_A7:M[_i],_t:M[_j],_AU:M[_b]}))
			for A9 in e.get(_AB)or[]:
				U=A9.get(Y)or{};g=U.get(_Ap)or U.get(_A8)
				if g and not O:
					if not N:N=_E;yield sse(J,{_A:J,B:A,H:{_A:_A8,_K:E,_AV:[]}});yield sse(x,{_A:x,D:E,B:A,K:0,Q:{_A:_A9,_L:''}})
					G+=g;yield sse(y,{_A:y,D:E,B:A,K:0,Y:g})
				h=U.get(_Y)
				if h:
					if N and not O:P={_A:_A8,_K:E,_AV:[{_A:_A9,_L:G}]};yield sse(Z,{_A:Z,D:E,B:A,K:0,_L:G});yield sse(a,{_A:a,D:E,B:A,K:0,Q:{_A:_A9,_L:G}});yield sse(F,{_A:F,B:A,H:P});L.append(P);A+=1;N=_D
					if not O:O=_E;yield sse(J,{_A:J,B:A,H:{_A:_A6,_K:I,_l:_AI,_o:k,z:A0,_Y:[]}});yield sse(A1,{_A:A1,D:I,B:A,b:0,Q:{_A:_AG,_L:'',_AW:[]}})
					R+=h;yield sse(A2,{_A:A2,D:I,B:A,b:0,Y:h})
				i=U.get(_AT)
				if i and isinstance(i,list):
					for V in i:
						j=V.get(_O,0);C=c.setdefault(j,{_K:_C,_B:'',_W:''})
						if V.get(_K):C[_K]=V[_K]
						W=V.get(_U)or{}
						if W.get(_B)and not C[_B]:C[_B]=W[_B]
						if W.get(_W):C[_W]+=W[_W]
		if o:break
	if N:P={_A:_A8,_K:E,_AV:[{_A:_A9,_L:G}]};yield sse(Z,{_A:Z,D:E,B:A,K:0,_L:G});yield sse(a,{_A:a,D:E,B:A,K:0,Q:{_A:_A9,_L:G}});yield sse(F,{_A:F,B:A,H:P});L.append(P);A+=1
	if O:t={_A:_A6,_K:I,_l:_AI,_o:_AA,z:A0,_Y:[{_A:_AG,_L:R,_AW:[]}]};yield sse(A3,{_A:A3,D:I,B:A,b:0,_L:R});yield sse(A4,{_A:A4,D:I,B:A,b:0,Q:{_A:_AG,_L:R,_AW:[]}});yield sse(F,{_A:F,B:A,H:t});L.append(t);A+=1
	for j in sorted(c.keys()):
		C=c[j]
		if not C[_B]:continue
		u=C[_K]or _Ag+uuid.uuid4().hex;X='fc_'+uuid.uuid4().hex;v={_A:_AS,_K:X,_AH:u,_B:C[_B],_W:C[_W]or'{}',_o:_AA};yield sse(J,{_A:J,B:A,H:{_A:_AS,_K:X,_AH:u,_B:C[_B],_W:'',_o:k}});yield sse(A5,{_A:A5,D:X,B:A,Y:C[_W]});yield sse(A6,{_A:A6,D:X,B:A,_W:C[_W]});yield sse(F,{_A:F,B:A,H:v});L.append(v);A+=1
	if not p:UI_QUEUE.put((_m,_C))
	yield sse(A7,{_A:A7,_A0:{_K:m,_z:_A0,_Ai:n,_o:_AA,_H:l,_t:L,_u:M}})
def chat_to_responses(chat,model,response_id):
	H=int(time.time());A=[];I=chat.get(_AB)or[{}];B=(I[0]or{}).get(_A6)or{};D=B.get(_Ap)or B.get(_A8)
	if D:A.append({_A:_A8,_K:'rs_'+uuid.uuid4().hex,_AV:[{_A:_A9,_L:D}]})
	E=B.get(_Y)
	if E:A.append({_A:_A6,_K:'msg_'+uuid.uuid4().hex,_l:_AI,_o:_AA,_Y:[{_A:_AG,_L:E,_AW:[]}]})
	for F in B.get(_AT)or[]:G=F.get(_U)or{};A.append({_A:_AS,_K:'fc_'+uuid.uuid4().hex,_AH:F.get(_K)or _Ag+uuid.uuid4().hex,_B:G.get(_B,''),_W:G.get(_W)or'{}',_o:_AA})
	C=chat.get(_u)or{};return{_K:response_id,_z:_A0,_Ai:H,_o:_AA,_H:model,_t:A,_u:{_i:C.get(_Aj,0)or 0,_j:C.get(_Ak,0)or 0,_b:C.get(_b,0)or 0}}
def _post_upstream(api,path,body,stream):
	E=api;D='stream_options';B=stream;A=body;F={_AX:f"Bearer {E[_M]}",'Content-Type':'application/json'};A=dict(A)
	if B:G=dict(A.get(D)or{});G['include_usage']=_E;A[D]=G
	C=requests.post(f"{api_base(E)}{path}",headers=F,json=A,stream=B,timeout=600)
	if B and C.status_code!=200 and D in A:C.close();A.pop(D,_C);UI_QUEUE.put((_s,'上游不支持 stream_options，已退回普通流式（token 用量可能拿不到）'));C=requests.post(f"{api_base(E)}{path}",headers=F,json=A,stream=B,timeout=600)
	return C
def _push_stats(data):
	A=(data or{}).get(_u)or{}
	if not A:UI_QUEUE.put((_m,_C));return
	C=A.get(_Aj,A.get(_i,0))or 0;D=A.get(_Ak,A.get(_j,0))or 0;B=A.get(_b,0)or 0
	if not B:B=C+D
	UI_QUEUE.put((_m,{_A7:C,_t:D,_AU:B}))
def _stream_response(gen):
	g._streaming=_E
	def A():
		try:
			for A in gen:yield A
		finally:
			with LIVE[_AF]:LIVE[_y]=max(0,LIVE[_y]-1)
	return Response(A(),status=200,mimetype='text/event-stream')
def _stream_passthrough(upstream):
	G=upstream;K=codecs.getincrementaldecoder(_f)(_AQ);A='';H=_D
	try:
		for C in G.iter_content(chunk_size=1024):
			if not C:continue
			yield C;A+=K.decode(C)
			if _a not in A:continue
			I=A.split(_a);A=I.pop()
			for B in I:
				B=B.strip()
				if not B.startswith('data:'):continue
				D=B[5:].strip()
				if not D or D=='[DONE]':continue
				try:E=json.loads(D)
				except Exception:continue
				J=E.get(_A0)if isinstance(E,dict)else _C;F=J if isinstance(J,dict)else E
				if isinstance(F,dict)and F.get(_u):H=_E;_push_stats(F)
		if not H:UI_QUEUE.put((_m,_C))
	finally:G.close()
@PROXY_APP.route('/v1/responses',methods=['POST'])
def handle_responses():
	B=get_active_config()
	if not B:return jsonify({_J:_Aq}),403
	E=request.get_json(force=_E,silent=_E)or{};G=(B.get(_H)or'').strip();C=bool(E.get(_AJ,_D))
	if B.get(_h)==_Z:
		if G:E[_H]=G
		try:A=_post_upstream(B,'/responses',E,C)
		except Exception as D:return jsonify({_J:f"网络异常: {D}"}),502
		if A.status_code!=200:UI_QUEUE.put((_p,f"上游直连拒绝 {A.status_code}: {A.text[:300]}"));return jsonify({_J:A.text}),A.status_code
		if not C:
			try:H=A.json()
			except Exception:H={}
			A.close();_push_stats(H);return jsonify(H)
		return _stream_response(_stream_passthrough(A))
	try:F=responses_to_chat(E,disable_tools=B.get(_S,_D),model_override=G)
	except Exception as D:return jsonify({_J:f"参数转换失败: {D}"}),400
	C=F.get(_AJ,_D)
	try:A=_post_upstream(B,_Ar,F,C)
	except Exception as D:return jsonify({_J:f"网络异常: {D}"}),502
	if A.status_code!=200:J=A.text;UI_QUEUE.put((_p,f"上游报错 {A.status_code}: {J[:300]}"));return jsonify({_J:J}),A.status_code
	K='resp_'+uuid.uuid4().hex
	if not C:
		try:I=A.json()
		except Exception:I={}
		A.close();_push_stats(I);return jsonify(chat_to_responses(I,F[_H],K))
	def L():
		try:
			for B in stream_chat_to_responses(A,F[_H],K):yield B
		finally:A.close()
	return _stream_response(L())
@PROXY_APP.route('/v1/chat/completions',methods=['POST'])
def handle_chat_completions():
	B=get_active_config()
	if not B:return jsonify({_J:_Aq}),403
	C=request.get_json(force=_E,silent=_E)or{};E=(B.get(_H)or'').strip()
	if E:C[_H]=E
	F=bool(C.get(_AJ,_D))
	try:A=_post_upstream(B,_Ar,C,F)
	except Exception as G:return jsonify({_J:f"网络异常: {G}"}),502
	if A.status_code!=200:UI_QUEUE.put((_p,f"上游报错 {A.status_code}: {A.text[:300]}"));return jsonify({_J:A.text}),A.status_code
	if not F:
		try:D=A.json()
		except Exception:D={}
		A.close();_push_stats(D);return jsonify(D)
	return _stream_response(_stream_passthrough(A))
@PROXY_APP.route('/v1/models',methods=['GET'])
def list_models():
	A=get_active_config()
	if not A or not A.get(_R)or not A.get(_M):return jsonify({_A1:[]})
	try:
		B=requests.get(f"{api_base(A)}/models",headers={_AX:f"Bearer {A[_M]}"},timeout=10)
		if B.status_code==200:return jsonify(B.json())
	except Exception:0
	return jsonify({_A1:[]})
COMMANDS=[(_AY,'显示命令帮助'),('list / ls','列出全部链路'),('start [N|名称]','启动链路（默认当前选中项）'),(_AK,'停止正在运行的链路'),(_Al,'重启当前链路'),('chat [N|名称]','进入对话模式（纯对话，Agent 未开发）'),('add','新建链路（引导式逐项填写）'),('set [N|名称]','打开链路设置界面（BIOS 风格，↑↓←→ 操作）'),('set N k=v','命令行直接改：url key model port mode tools name'),('del N|名称','删除链路'),('show N|名称','查看链路详情'),('test N|名称','测试与上游的连通性（GET /models）'),('cache [类别] [--yes]','查看/清理缓存：models chat logs temp all'),(_AZ,'列出内置服务商的 Base URL'),(_m,'查看 token 用量统计'),(_Aa,'查看当前版本与更新状态'),('check','重新检查更新'),('web','打开官网下载页'),(_Am,'清空日志面板'),(_AC,'查看错误日志目录（可发给开发者分析）'),('quit / exit','退出')]
ALIASES={'h':_AY,'?':_AY,'ls':'list','l':'list','open':_AM,'run':_AM,'on':_AM,'off':_AK,'shutdown':_AK,_AL:'add','create':'add','rm':_AN,'remove':_AN,'delete':_AN,'edit':'set',_r:'show','provider':_AZ,'providerlist':_AZ,'stat':_m,_u:_m,'ver':_Aa,'update':'web','download':'web','cls':_Am,_s:_AC,'crashes':_AC,'exit':'quit','q':'quit','talk':'chat','caches':'cache','clearcache':'cache'}
KIND_WORDS='bridge','link','tunnel','tunnels'
def tokenize(line):
	D,A,C=[],'',_C
	for B in line:
		if C:
			if B==C:C=_C
			else:A+=B
		elif B in('"',"'"):C=B
		elif B.isspace():
			if A:D.append(A);A=''
		else:A+=B
	if A:D.append(A)
	return D
class TerminalApp:
	def __init__(A):
		A.links=[];A.selected=0;A.buffer='';A.history=[];A.hist_pos=0;A.logs=deque(maxlen=1000);A.log_offset=0;A.running=_E;A.wizard=_C;A.flash='';A.flash_color=C_INFO;A.update_remote='';A.update_state=_Ac
		try:A.interactive=sys.stdout.isatty()
		except Exception:A.interactive=_D
		A._last_size=_C;A._checking=_D;A.flash_until=.0;A.form=_C;A._list_space=10
		A.chat=_C;A.chat_streaming=_D;A._chat_stop=_C;A._chat_live_owned=_D;A._chat_content='';A._chat_reason=''
	def log(A,text,level=_r):
		B=level;C=time.strftime('%H:%M:%S');A.logs.append((f"[{C}] {text}",B));A.log_offset=0
		if not A.interactive:D=LEVEL_COLOR.get(B,'');print(D+f"[{C}] {text}"+(RESET if D else''))
	def flash_msg(A,text,level=_r):A.flash=text;A.flash_color=LEVEL_COLOR.get(level,C_INFO);A.flash_until=time.time()+6
	def drain_events(E):
		F='_tokens'
		while _E:
			try:D,B=UI_QUEUE.get_nowait()
			except queue.Empty:break
			if D==_s:E.log(B)
			elif D==_p:E.log(B,_G)
			elif D=='chat_delta':E._chat_delta(B[0],B[1])
			elif D=='chat_usage':E._chat_usage(B)
			elif D=='chat_done':E._chat_done(B)
			elif D=='chat_err':E._chat_error(B)
			elif D=='chat_end':E.chat_streaming=_D
			elif D=='chat_models':
				link,models,err=B
				if E.chat and E.chat.get('active')and E.chat.get('link')is link:
					E.chat['models']=models
					E.chat['_tab_cands']=[];E.chat['_tab_idx']=-1;E.chat['_tab_last']=''
					if models:
						E.log('已获取 %d 个可用模型；输入 /model 后按 Tab 循环选择，/model 可列出全部'%len(models),_Q)
						E.log('示例：'+' · '.join(models[:12])+(' …'if len(models)>12 else''),_V)
					else:E.log('获取模型列表失败：%s'%err,_T)
			elif D==_m:
				GLOBAL_STATS[_k]+=1;A=_link_stat(PROXY_STATE.get(_X),_E)
				if A:A[_k]+=1;A[_AR]=time.time()
				if B is _C:
					GLOBAL_STATS[_AE]+=1
					if A:A[_AE]+=1
				else:
					for C in(_A7,_t,_AU):GLOBAL_STATS[C+F]+=B[C]
					if A:
						for C in(_A7,_t,_AU):A[C+F]+=B[C]
	def startup_sequence(A):init_console();A._step('Loading System',A._load_system);A._step('Loading Config Files',A._load_config);A._step('Loading Bridge Lists',A._load_bridges);A._step('Checking Update Versions',A._check_update_blocking);A._step('Starting Console GUI',lambda:_C);A._banner()
	def _step(E,label,work):
		K='    ! %s';F=label;G=max(12,min(30,shutil.get_terminal_size((100,30)).columns-dwidth(F)-20));H=F+_c;A={_Q:_C,_G:_C}
		def L():
			try:A[_Q]=work()
			except Exception as B:A[_G]=B
		if not E.interactive:sys.stdout.write(H);sys.stdout.flush()
		C=threading.Thread(target=L,daemon=_E);C.start()
		if not E.interactive:
			C.join();M=C_ERR+'Failed'if A[_G]else C_OK+'Completely';sys.stdout.write(M+RESET+_a)
			if A[_G]:sys.stdout.write(C_ERR+K%A[_G]+RESET+_a)
			return A[_Q]
		def D(pct,done=_D):B=int(G*pct/1e2);C=C_CYAN+'#'*B+RESET+C_DIM+'.'*(G-B)+RESET;D=(C_ERR+' Failed'if A[_G]else C_OK+' Completely')if done else' %3d%%'%int(pct);sys.stdout.write('\r'+H+'['+C+']'+D+(RESET if done else''));sys.stdout.flush()
		I,B=time.time(),.0;D(B)
		while C.is_alive()or time.time()-I<.6:
			J=min(9e1,9e1*(time.time()-I)/.9)
			if J>B+.5:B=J;D(B)
			time.sleep(.04)
		C.join()
		while B<99.9:B=min(1e2,B+5.);D(B,done=B>=99.9);time.sleep(.03)
		D(1e2,done=_E);sys.stdout.write(_a);sys.stdout.flush()
		if A[_G]:sys.stdout.write(C_ERR+K%A[_G]+RESET+_a)
		return A[_Q]
	def _load_system(A):return API_FILE
	def _load_config(B):
		if not os.path.exists(API_FILE):return
		with open(API_FILE,'r',encoding=_f)as A:json.load(A)
		return _E
	def _load_bridges(A):A.links=load_links();A.selected=0 if A.links else-1;return len(A.links)
	def _check_update_blocking(A):A._do_update_check();return A.update_state
	def _banner(F):D=shutil.get_terminal_size((100,30)).columns;E=max(60,min(88,D-2));C='Welcome To use API Linking Bridge Tool';A=E-2;B=max(0,A-dwidth(C));print();print('╔'+'═'*A+'╗');print('║'+_F*(B//2)+C+_F*(B-B//2)+'║');print('╚'+'═'*A+'╝');print(DIM+'  Console Edition · 输入 help 查看命令，Tab 补全，Ctrl+C 退出'+RESET);print()
	def _do_update_check(A):
		C=_C;D=_C
		for F in range(2):
			try:E=requests.get(UPDATE_API,timeout=8,headers={'User-Agent':f"APILinkingBridge-CLI/{VERSION}"});E.raise_for_status();D=E.json();C=_C;break
			except Exception as G:
				C=G
				if F==0:time.sleep(.8)
		if C is not _C:A.update_state=_J;A.update_remote='';A.log(f"版本检查失败：{A._friendly_error(C)}",_T);return
		B=''
		if isinstance(D,dict):B=str(D.get('Version')or D.get(_Aa)or'').strip()
		if not B:A.update_state=_J;A.log('版本检查：服务器未返回有效版本号',_T)
		elif B==VERSION:A.update_state=_An;A.update_remote=B
		else:A.update_state=_AL;A.update_remote=B;A.log(f"发现新版本 {B}（当前 v{VERSION}），输入 web 打开下载页",_T)
	@staticmethod
	def _friendly_error(e):
		if isinstance(e,requests.exceptions.Timeout):return'连接更新服务器超时'
		if isinstance(e,requests.exceptions.ConnectionError):return'无法连接更新服务器，请检查网络'
		A=getattr(e,_A0,_C)
		if isinstance(e,requests.exceptions.HTTPError)and A is not _C:return f"更新服务器返回错误（HTTP {A.status_code}）"
		if isinstance(e,ValueError):return'更新服务器返回的数据格式异常'
		return'网络异常'
	def run(A):
		A.startup_sequence()
		if A.links:A.log(f"系统就绪，已载入 {len(A.links)} 条链路",_Q)
		else:A.log('系统就绪，但还没有链路。输入 add 新建一条',_T)
		A.log('输入 help 查看命令 · Tab 补全 · ↑↓ 选择链路 · PgUp/PgDn 翻日志',_V)
		if not A.interactive or msvcrt is _C:A.plain_loop();return
		A.enter_screen()
		try:A.loop()
		finally:A.leave_screen()
	def enter_screen(A):sys.stdout.write('\x1b[?1049h\x1b[?25l\x1b[2J');sys.stdout.flush()
	def leave_screen(A):sys.stdout.write(RESET+_As);sys.stdout.flush()
	def plain_loop(A):
		print(DIM+'非交互终端，进入纯文本模式。输入 help 查看命令，quit 退出。'+RESET)
		while A.running:
			try:A.drain_events();C=input('> ')
			except(EOFError,KeyboardInterrupt):break
			except Exception as B:A._report_crash(B,'CLI 纯文本模式');continue
			try:A.submit(C)
			except Exception as B:A._report_crash(B,'CLI 命令执行')
		A.shutdown_servers()
	def _report_crash(B,exc,context):
		A=exc
		try:D=[A for(A,B)in list(B.logs)[-40:]];C=_write_crash_log(type(A),A,A.__traceback__,context,D)
		except Exception:C=_Ad
		try:
			B.log(_Ae%(type(A).__name__,A),_G);B.log(_AD%C,_G)
			if not B.interactive:print(_Ae%(type(A).__name__,A));print(_AD%C)
		except Exception:0
		return C
	def loop(A):
		B=0
		while A.running:
			try:
				A.drain_events();A.render()
				while msvcrt and msvcrt.kbhit():
					A.handle_key(msvcrt.getwch())
					if not A.running:break
				time.sleep(.03);B=0
			except Exception as C:
				B+=1;D=A._report_crash(C,'CLI 主循环')
				if B>=20:
					A.leave_screen();print('连续出现 20 次错误，已停止界面。');print('错误日志：%s'%D)
					try:input('按回车键退出…')
					except Exception:0
					A.running=_D;break
				time.sleep(.2)
		A.shutdown_servers()
	def shutdown_servers(A):
		try:A.stop_server()
		except Exception:0
	def handle_key(A,ch):
		B=ch
		if B in('\x00','à'):
			C=msvcrt.getwch()
			if A.form:A.form_arrow(C)
			else:A._main_arrow(C)
			return
		if B=='\x03':A.running=_D;return
		if A.form:A.form_key(B);return
		if B=='\r':A.submit(A.buffer)
		elif B=='\x08':A.buffer=A.buffer[:-1]
		elif B=='\t':A.complete()
		elif B=='\x1b':
			if A.wizard:A.wizard=_C;A.buffer='';A.log('已取消新建',_V)
			else:A.buffer=''
		elif B=='\x10':A.history_move(-1)
		elif B=='\x0e':A.history_move(1)
		elif ord(B)>=32:A.buffer+=B
	def move_selection(A,delta):
		if not A.links:return
		A.selected=(A.selected+delta)%len(A.links)
	def scroll_logs(A,lines):B=max(0,len(A.logs)-5);A.log_offset=max(0,min(B,A.log_offset+lines))
	def history_move(A,delta):
		if not A.history:return
		A.hist_pos=max(0,min(len(A.history),A.hist_pos+delta));A.buffer=A.history[A.hist_pos]if A.hist_pos<len(A.history)else''
	def _main_arrow(A,code):
		B=code
		if B=='H':A.move_selection(-1)
		elif B=='P':A.move_selection(1)
		elif B=='I':A.scroll_logs(5)
		elif B=='Q':A.scroll_logs(-5)
		elif B=='G':A.selected=0
		elif B=='O':A.selected=max(0,len(A.links)-1)
	def open_settings(B,link):A=link;B.form={'orig':A,_v:{_B:A.get(_B,''),_R:api_base(A),_M:A.get(_M,''),_H:A.get(_H,''),_N:str(A.get(_N,15721)),_g:_Z if A.get(_h)==_Z else _e,_S:bool(A.get(_S))},_O:0,_q:_D,_n:'',_J:''};B.buffer=''
	def form_key(C,ch):
		A=ch;B=C.form
		if B[_q]:
			if A=='\r':C.form_commit()
			elif A=='\x08':B[_n]=B[_n][:-1]
			elif A=='\x1b':B[_q]=_D;B[_n]=''
			elif ord(A)>=32:B[_n]+=A
			return
		if A=='\r':C.form_enter()
		elif A=='\t':C.form_move(1)
		elif A=='\x1b':C.form_exit()
		elif ord(A)>=32:
			D=FORM_FIELDS[B[_O]]
			if D[_A]==_L:B[_q]=_E;B[_n]=A;B[_J]=''
			elif D[_A]==_A2:C.form_cycle(1)
	def form_arrow(A,code):
		B=code
		if A.form[_q]:return
		if B=='H':A.form_move(-1)
		elif B=='P':A.form_move(1)
		elif B=='K':A.form_left_right(-1)
		elif B=='M':A.form_left_right(1)
	def form_move(B,delta):A=B.form;A[_O]=(A[_O]+delta)%len(FORM_FIELDS);A[_J]=''
	def form_left_right(B,delta):
		C=B.form;A=C[_O]
		if A in(ACTION_SAVE,ACTION_CANCEL):C[_O]=ACTION_CANCEL if A==ACTION_SAVE else ACTION_SAVE;return
		if FORM_FIELDS[A][_A]==_A2:B.form_cycle(delta)
	def form_cycle(E,delta):
		A=E.form;B=FORM_FIELDS[A[_O]]
		if B[_A]!=_A2:return
		C=B[_AB];D=A[_v].get(B[_I]);F=C.index(D)if D in C else 0;A[_v][B[_I]]=C[(F+delta)%len(C)];A[_J]=''
	def form_enter(B):
		A=B.form
		if A[_O]==ACTION_SAVE:B.form_save();return
		if A[_O]==ACTION_CANCEL:B.form_exit();return
		C=FORM_FIELDS[A[_O]]
		if C[_A]==_L:A[_q]=_E;A[_n]=str(A[_v].get(C[_I],''));A[_J]=''
		else:B.form_cycle(1)
	def form_commit(D):
		A=D.form;C=FORM_FIELDS[A[_O]];B=A[_n].strip()
		if C[_I]==_N:
			try:B=str(int(B))
			except Exception:A[_J]='端口必须是数字';return
		A[_v][C[_I]]=B;A[_q]=_D;A[_n]='';A[_J]=''
	def form_save(D):
		B=D.form;C=B[_v];A=(C.get(_B)or'').strip()
		if not A:B[_J]='链路名称不能为空';return
		if any(C is not B['orig']and C.get(_B)==A for C in D.links):B[_J]='该名称已存在';return
		try:
			G=int(C.get(_N))
			if not 1<=G<=65535:raise ValueError
		except Exception:B[_J]='端口必须是 1-65535 的数字';return
		F=(C.get(_R)or'').strip().rstrip('/');J=resolve_provider(F)
		if J:F=J
		if not F:B[_J]='Base URL 不能为空';return
		H=B['orig'];E=H.get(_B);K=PROXY_STATE.get(_X)==E;H.update({_B:A,_R:F,_M:C.get(_M,''),_H:C.get(_H,''),_N:G,_S:bool(C.get(_S)),_h:C.get(_g,_e)})
		if E and E!=A and E in LINK_STATS:LINK_STATS[A]=LINK_STATS.pop(E)
		save_links(D.links);I=''
		if K:
			PROXY_STATE[_X]=A;PROXY_STATE[_A4]=H;I='，配置已热更新'
			if PROXY_STATE.get(_AO)!=G:I+='（端口改动需 restart 生效）'
		D.form=_C;D.log(f"已保存链路：{A}{I}",_Q);D.flash_msg(f"已保存链路：{A}",_Q)
	def form_exit(A):A.form=_C;A.log('已退出链路设置（未保存）',_V)
	def complete(A):
		if A.wizard:return
		if A.chat and A.chat.get('active'):
			first=A.buffer.split(None,1)[0].lower()if A.buffer.strip()else''
			if first in('/model','/models'):
				A._complete_chat_model();return
		E=A.buffer;B=E.split()
		if not B or len(B)==1 and not E.endswith(_F):
			G=B[0]if B else'';D=[A for A in sorted(A._command_names())if A.startswith(G.lower())]
			if len(D)==1:A.buffer=D[0]+_F
			elif D:A.log('可用命令：'+_c.join(D),_d)
			else:A.log('没有匹配的命令，输入 help 查看全部',_T)
			return
		H=A._resolve(ALIASES.get(B[0].lower(),B[0].lower()))
		if H in(_AM,_AK,_AN,'show','test','set',_Al):
			F=B[-1]if not E.endswith(_F)else'';C=[A.get(_B,'')for A in A.links if A.get(_B,'').lower().startswith(F.lower())]
			if len(C)==1:A.buffer=_F.join(B[:-1]+[C[0]]if F else B+[C[0]])+_F
			elif C:A.log('候选链路：'+_c.join(C),_d)
			else:A.log('没有匹配的链路',_T)
			return
		A.log('Tab：命令为空时列出全部命令；在 start/del/show/test/set 后按 Tab 补全链路名',_V)
	@staticmethod
	def _command_names():
		A=[]
		for(D,E)in COMMANDS:
			for B in D.split('/'):
				C=B.strip().split()[0]if B.strip()else''
				if C:A.append(C)
		A.extend(ALIASES.keys());return set(A)
	@staticmethod
	def _resolve(cmd):return cmd
	def submit(A,line):
		B=line
		if A.wizard:A.wizard_submit(B);return
		B=B.strip();A.buffer='';A.hist_pos=len(A.history)
		if not B:return
		A.history.append(B);A.history=A.history[-100:];A.hist_pos=len(A.history)
		if A.chat and A.chat.get('active'):
			if B.startswith('/'):A.chat_command(B)
			else:A.send_chat(B)
			return
		A.log('> '+B,'cmd');A.dispatch(B)
	def dispatch(A,line):
		D=tokenize(line)
		if not D:return
		B=D[0].lower();B=ALIASES.get(B,B);C=D[1:]
		while C and C[0].lower()in KIND_WORDS:C.pop(0)
		F={_AY:A.cmd_help,'list':A.cmd_list,_AM:A.cmd_start,_AK:A.cmd_stop,_Al:A.cmd_restart,'chat':A.cmd_chat,'add':A.cmd_add,'set':A.cmd_set,_AN:A.cmd_del,'show':A.cmd_show,'test':A.cmd_test,'cache':A.cmd_cache,_AZ:A.cmd_providers,_m:A.cmd_stats,_Aa:A.cmd_version,'check':A.cmd_check,'web':A.cmd_web,_Am:A.cmd_clear,_AC:A.cmd_logs,'quit':A.cmd_quit};E=F.get(B)
		if not E:A.log(f"未知命令：{B}（输入 help 查看全部）",_G);A.flash_msg(f"未知命令：{B}  ·  输入 help 查看全部",_G);return
		try:E(C)
		except Exception as G:A.log(f"命令执行出错：{G}",_G)
	def cmd_help(A,args):
		A.log('可用命令：',_d)
		for(B,C)in COMMANDS:A.log(_c+pad_display(B,20)+_F+C,_r)
		A.log('快捷键：Tab 补全 · ↑↓ 选择链路 · PgUp/PgDn 翻日志 · Ctrl+P/N 历史 · Esc 取消 · Ctrl+C 退出',_V)
	def cmd_list(A,args):
		if not A.links:A.log('暂无链路，输入 add 新建一条',_T);return
		A.log(f"共 {len(A.links)} 条链路：",_d);D=PROXY_STATE.get(_X)
		for(E,B)in enumerate(A.links,1):C=' [loaded]'if B.get(_B)==D else'';F=B.get(_h,_e);A.log(f"  {E}. {pad_display(B.get(_B,"Unnamed"),16)} :{B.get(_N,15721):<6} {F:<11} {api_base(B)}{C}",_Q if C else _r)
	def cmd_start(A,args):
		B=A._need_link(args,_E)
		if not B:return
		if not B.get(_R)or not B.get(_M):A.log(f"链路 {B.get(_B)} 未配置完整（需要 Base URL 和 API Key）",_G);return
		if PROXY_STATE.get(_A5):A.log('先停止当前链路再开启新的',_T);A.stop_server()
		port=int(B.get(_N,15721));in_use,_,_=_port_owner(port)
		if in_use:A.log('启动失败：'+describe_port(port),_G);A.flash_msg('端口被其他程序占用',_G);return
		if A.start_server(B):A.log(f"已开启链路：{B.get(_B)}  →  http://127.0.0.1:{port}",_Q);threading.Thread(target=A._probe_upstream,args=(dict(B),),daemon=_E).start()
		else:A.log('链路启动失败，详见运行日志',_G)
	def cmd_stop(A,args):
		if not PROXY_STATE.get(_A5):A.log('当前没有运行中的链路',_T);return
		B=PROXY_STATE.get(_X);A.stop_server();A.log(f"已停止链路：{B}",_Q)
	def cmd_restart(A,args):
		B=PROXY_STATE.get(_X);A.stop_server()
		if B:
			for C in A.links:
				if C.get(_B)==B:A.cmd_start([B]);return
		A.cmd_start(args)
	def cmd_add(A,args):
		C={A.get(_N,15721)for A in A.links};B=15721
		while B in C:B+=1
		A.wizard={_AP:[{_I:_B,_P:'链路名称',_w:f"Link{len(A.links)+1}"},{_I:_R,_P:'Base URL（可输入内置服务商名，如 OpenAI）',_w:''},{_I:_M,_P:'API Key',_w:'',_Ab:_E},{_I:_H,_P:'上游模型名（留空 = 透传客户端模型）',_w:''},{_I:_N,_P:'本地监听端口',_w:str(B)},{_I:_g,_P:'转换模式 direct / translation',_w:_e}],_O:0,_A1:{}};A.buffer='';A.log('新建链路：逐项填写，直接回车使用默认值，Esc 取消',_d)
	def wizard_submit(A,line):
		F=A.wizard[_AP][A.wizard[_O]];B=line.strip()or F[_w];D=F[_I]
		if D==_R:
			G=resolve_provider(B);B=G if G is not _C else B.strip().rstrip('/')
			if B and not B.startswith(('http://','https://')):A.log(f"Base URL 看起来不完整：{B}（应形如 https://api.xxx.com/v1）",_T)
		elif D==_N:
			try:
				B=int(B)
				if not 1<=B<=65535:raise ValueError
			except Exception:A.log('端口必须是 1-65535 的数字，已取消',_G);A.wizard=_C;return
		elif D==_g:B=_Z if _Z in B.lower()or'直连'in B else _e
		elif D==_B:
			if any(A.get(_B)==B for A in A.links):A.log('该名称已存在，已取消',_G);A.wizard=_C;return
		A.wizard[_A1][D]=B;A.wizard[_O]+=1;A.buffer=''
		if A.wizard[_O]<len(A.wizard[_AP]):return
		C=A.wizard[_A1];A.wizard=_C;E={_B:C.get(_B),_R:C.get(_R,'').strip().rstrip('/'),_M:C.get(_M,''),_H:C.get(_H,''),_N:int(C.get(_N,15721)),_S:_D,_h:C.get(_g,_e)};A.links.append(E);save_links(A.links);A.selected=len(A.links)-1;A.log(f"已保存链路：{E[_B]}  →  {api_base(E)}",_Q)
	def cmd_set(C,args):
		F=args
		if not any(_x in A for A in F):
			A=C._need_link(F,_E)
			if not A:return
			C.open_settings(A);return
		if F and _x not in F[0]:A=C._pick_link(F);G=F[1:]
		else:A=C._pick_link([]);G=list(F)
		if not A:C.log('用法：set <编号|名称> url=... key=... model=... port=... mode=direct|translation tools=on|off',_G);return
		if not G:C.log('请给出要修改的字段，例如：set 1 model=deepseek-chat',_T);return
		E=[]
		for H in G:
			if _x not in H:continue
			D,B=H.split(_x,1);D=D.strip().lower();B=B.strip()
			try:
				if D in(_A3,'apiurl'):I=resolve_provider(B);A[_R]=(I if I is not _C else B).rstrip('/');E.append(_R)
				elif D in(_I,'apikey'):A[_M]=B;E.append(_M)
				elif D==_H:A[_H]=B;E.append(_H)
				elif D in(_AO,'listenport'):
					J=int(B)
					if not 1<=J<=65535:raise ValueError('端口超范围')
					A[_N]=J;E.append(_N)
				elif D==_g:A[_h]=_Z if B.lower().startswith('d')or'直连'in B else _e;E.append(_g)
				elif D in(_Ah,_S):A[_S]=B.lower()in('on','1','true','yes','off_tools','disable');E.append(_S)
				elif D==_B:
					if any(C.get(_B)==B for C in C.links if C is not A):raise ValueError('名称已存在')
					K=A.get(_B);A[_B]=B
					if K in LINK_STATS:LINK_STATS[B]=LINK_STATS.pop(K)
					E.append(_B)
				else:C.log(f"未知字段：{D}",_T)
			except Exception as L:C.log(f"设置 {D} 失败：{L}",_G)
		if E:
			save_links(C.links);C.log(f"已更新 {A.get(_B)}：{", ".join(E)}",_Q)
			if PROXY_STATE.get(_X)==A.get(_B):PROXY_STATE[_A4]=A;C.log('该链路正在运行，配置已热更新（端口改动需 restart 生效）',_V)
	def cmd_del(A,args):
		B=A._need_link(args)
		if not B:return
		if PROXY_STATE.get(_X)==B.get(_B):A.stop_server()
		LINK_STATS.pop(B.get(_B),_C);A.links.remove(B);save_links(A.links);A.selected=max(0,min(A.selected,len(A.links)-1));A.log(f"已删除链路：{B.get(_B)}",_Q)
	def cmd_show(B,args):
		A=B._need_link(args)
		if not A:return
		C=A.get(_M,'');D=C[:6]+'…'+C[-4:]if len(C)>12 else'*'*len(C);B.log(f"链路：{A.get(_B)}",_d);B.log(f"  Base URL : {api_base(A)}");B.log(f"  API Key  : {D}");B.log(f"  模型     : {A.get(_H)or"(透传客户端模型名)"}");B.log(f"  监听端口 : {A.get(_N)}");B.log(f"  模式     : {A.get(_h,_e)}"+('（需要上游原生支持 Responses API）'if A.get(_h)==_Z else''));B.log(f"  禁用工具 : {"是"if A.get(_S)else"否"}")
	def cmd_test(A,args):
		B=A._need_link(args)
		if not B:return
		A.log(f"正在测试 {B.get(_B)} …",_V);threading.Thread(target=A._test_link,args=(dict(B),),daemon=_E).start()
	def _test_link(E,link):
		A=link
		try:
			B=requests.get(f"{api_base(A)}/models",headers={_AX:f"Bearer {A.get(_M,"")}"},timeout=10)
			if B.status_code==200:C=[A.get(_K)for A in B.json().get(_A1,[])if A.get(_K)];UI_QUEUE.put((_s,f"{A.get(_B)} 连接成功，检测到 {len(C)} 个模型"))
			else:UI_QUEUE.put((_p,f"{A.get(_B)} 连接失败 {B.status_code}: {B.text[:150]}"))
		except Exception as D:UI_QUEUE.put((_p,f"{A.get(_B)} 测试异常: {D}"))
	# ---------- 内置对话 ----------
	def cmd_chat(A,args):
		B=A._pick_link(args)
		if not B:A.log('找不到指定链路（用 list 查看编号）',_G);return
		if not B.get(_R)or not B.get(_M):A.log('该链路未配置完整（需要 Base URL 和 API Key）',_G);return
		port=int(B.get(_N,15721))
		ours=(PROXY_STATE.get(_A5)is not _C and PROXY_STATE.get(_AO)==port and PROXY_STATE.get(_X)==B.get(_B))
		A.chat={'link':B,'messages':[],'model':B.get(_H,''),'route':'auto','active':_E,'models':[],'_tab_cands':[],'_tab_idx':-1,'_tab_last':''}
		A.chat_streaming=_D;A._chat_stop=_C;A._chat_content='';A._chat_reason='';A._chat_live_owned=_D
		A.log('已进入对话模式（纯对话；Agent 功能尚未开发，欢迎在 GitHub 上贡献）',_d)
		A.log('链路：%s  模型：%s'%(B.get(_B),B.get(_H)or'（未填写，输入 /model 后按 Tab 选择）'),_r)
		A.log('端口：'+describe_port(port,ours),_Q if ours else _V)
		A.log('输入消息回车发送；/help 查看对话命令；/exit 返回控制台',_V)
		A.log('提示：输入 /model 后按 Tab 可循环切换上游模型（多按几次循环选择）',_V)
		if A.interactive:threading.Thread(target=A._fetch_chat_models,daemon=_E).start()
	def leave_chat(A):
		A.chat=_C;A.chat_streaming=_D;A._chat_stop=_C;A._chat_content='';A._chat_reason='';A._chat_live_owned=_D
		A.buffer='';A.log('已退出对话模式',_V);A.flash_msg('已返回控制台',_V)
	def chat_command(A,line):
		parts=tokenize(line[1:].strip());cmd=parts[0].lower()if parts else'help';args=parts[1:]
		if cmd in('exit','quit','q','back'):A.leave_chat();return
		if cmd in('help','h','?'):
			A.log('对话命令：',_d)
			A.log(_c+'/exit          返回控制台',_r)
			A.log(_c+'/new           开始新对话（清空上下文）',_r)
			A.log(_c+'/model [名称]  指定上游模型；不带名称则列出；输入 /model 后按 Tab 循环选择',_r)
			A.log(_c+'/route auto|direct|relay  切换通道',_r)
			A.log(_c+'/stop          停止当前生成',_r)
			A.log(_c+'/status        查看链路、端口与用量',_r)
			return
		if cmd in('new','clear'):
			A.chat['messages']=[];save_chat_history([]);A.log('已开始新对话',_Q);return
		if cmd in('model','models'):
			if not args:
				models=list(A.chat.get('models')or[])
				if models:A._list_chat_models(models);return
				if A.interactive:
					A.log('正在获取模型列表…获取完成后会自动列出；也可以直接输入 /model <名称> 后按 Tab 选择',_V)
					threading.Thread(target=A._fetch_chat_models,daemon=_E).start()
				else:
					models,err=A._fetch_chat_models_sync();A.chat['models']=models
					if models:A._list_chat_models(models)
					else:A.log('获取模型列表失败：%s'%err,_G)
				return
			A.chat['model']=args[0];A.chat['_tab_last']='';A.log('模型已切换为：%s'%args[0],_Q);return
		if cmd=='route':
			mode=args[0].lower()if args else''
			if mode not in('auto','direct','relay'):A.log('用法：/route auto|direct|relay',_T);return
			A.chat['route']=mode;A.log('对话通道：%s'%mode,_Q);return
		if cmd=='stop':
			if A._chat_stop is not _C:A._chat_stop.set();A.log('正在停止生成…',_V)
			else:A.log('当前没有正在生成的回复',_V)
			return
		if cmd=='status':
			B=A.chat['link'];port=int(B.get(_N,15721));ours=(PROXY_STATE.get(_A5)is not _C and PROXY_STATE.get(_AO)==port and PROXY_STATE.get(_X)==B.get(_B))
			A.log('链路：%s'%B.get(_B),_d)
			A.log(_c+'模型：%s'%(A.chat.get('model')or'（未指定）'))
			A.log(_c+'通道：%s（auto 优先本机中继）'%A.chat.get('route','auto'))
			A.log(_c+'端口：'+describe_port(port,ours))
			A.log(_c+'进行中请求：%s'%_inflight())
			A.log(_c+'本软件对话记录：%s'%CHAT_HISTORY_FILE)
			return
		A.log('未知对话命令：/%s（输入 /help 查看）'%cmd,_G)
	def _fetch_chat_models_sync(A):
		C=A.chat
		if not C:return [],'未在对话模式'
		B=C.get('link')or{}
		return fetch_upstream_models(api_base(B),B.get(_M,''))
	def _fetch_chat_models(A):
		C=A.chat
		if not C:return
		B=C.get('link')or{}
		models,err=A._fetch_chat_models_sync()
		UI_QUEUE.put(('chat_models',(B,models,err)))
	def _list_chat_models(A,models):
		A.log('可用模型（%d 个）：'%len(models),_d)
		limit=min(len(models),60)
		for i in range(limit):A.log(_c+'  %d. %s'%(i+1,models[i]),_r)
		if len(models)>limit:A.log(_c+'  … 还有 %d 个未显示'%(len(models)-limit),_V)
		A.log('提示：输入 /model 后按 Tab 可循环切换；也可直接 /model <名称>',_V)
	def _complete_chat_model(A):
		parts=A.buffer.split(None,1);prefix=parts[1].strip()if len(parts)>1 else''
		models=list(A.chat.get('models')or[])
		if not models:
			A.log('模型列表尚未加载，正在获取…稍候再按 Tab 即可循环选择',_V)
			if A.interactive:threading.Thread(target=A._fetch_chat_models,daemon=_E).start()
			else:
				models,err=A._fetch_chat_models_sync();A.chat['models']=models
				if not models:A.log('获取模型列表失败：%s'%err,_G)
			return
		if A.buffer==A.chat.get('_tab_last')and A.chat.get('_tab_cands'):
			cands=A.chat['_tab_cands'];idx=(A.chat.get('_tab_idx',-1)+1)%len(cands)
		else:
			cands=[m for m in models if not prefix or m.lower().startswith(prefix.lower())]
			if not cands:A.log('没有匹配的模型：%s'%prefix,_T);return
			idx=0
		A.buffer='/model '+cands[idx]
		A.chat['_tab_last']=A.buffer;A.chat['_tab_idx']=idx;A.chat['_tab_cands']=cands
		A.flash_msg('模型 %d/%d：%s'%(idx+1,len(cands),cands[idx]),_Q)
	def _ensure_relay(A,link):
		port=int(link.get(_N,15721))
		if PROXY_STATE.get(_A5)is not _C and PROXY_STATE.get(_AO)==port and PROXY_STATE.get(_X)==link.get(_B):return _E,''
		in_use,_,_=_port_owner(port)
		if in_use:return _D,describe_port(port)
		if A.start_server(link):A.log('已自动开启本机中继：%s（端口 %s）'%(link.get(_B),port),_Q);return _E,''
		return _D,'本机中继启动失败，详见日志'
	def _resolve_chat_route(A,link):
		mode=A.chat.get('route','auto');port=int(link.get(_N,15721))
		ours=(PROXY_STATE.get(_A5)is not _C and PROXY_STATE.get(_AO)==port and PROXY_STATE.get(_X)==link.get(_B))
		if mode=='relay'or(mode=='auto'and ours):
			ok,detail=A._ensure_relay(link)
			if not ok:return _C,_C,detail
			return'relay','http://127.0.0.1:%s/v1'%port,_C
		if mode=='auto':
			in_use,_,_=_port_owner(port)
			if in_use:return'direct',api_base(link),describe_port(port)+'；本次对话使用上游直连'
		return'direct',api_base(link),_C
	def send_chat(A,text):
		if A.chat_streaming:A.log('上一条回复还在生成，输入 /stop 可中断',_T);return
		B=A.chat['link']
		if not B.get(_R)or not B.get(_M):A.log('该链路未配置完整（Base URL / API Key）',_G);return
		model=(A.chat.get('model')or B.get(_H)or'').strip()
		if not model:A.log('未指定上游模型名，请先输入 /model <名称>',_G);return
		route,base,warn=A._resolve_chat_route(B)
		if route is _C:A.log('无法开启对话：%s'%warn,_G);return
		if warn:A.log(warn,_T)
		A.chat['messages'].append({'role':'user','content':text})
		A.log('你> '+text,'chat_user')
		A._chat_content='';A._chat_reason='';A._chat_live_owned=_D
		A.chat_streaming=_E;A._chat_stop=threading.Event()
		if not A.interactive:
			A._chat_sync(base,B.get(_M,''),model,list(A.chat['messages']))
			return
		threading.Thread(target=A._chat_worker,args=(base,B.get(_M,''),model,list(A.chat['messages']),A._chat_stop),daemon=_E).start()
	def _chat_worker(A,base,key,model,messages,stop_event):
		try:
			content=''
			for kind,value in iter_chat_stream(base,key,model,messages,stop_event):
				if kind=='content':content+=value;UI_QUEUE.put(('chat_delta',('content',value)))
				elif kind=='reasoning':UI_QUEUE.put(('chat_delta',('reasoning',value)))
				else:UI_QUEUE.put(('chat_usage',value))
			if stop_event.is_set():UI_QUEUE.put(('chat_err','已手动停止生成'))
			else:UI_QUEUE.put(('chat_done',content))
		except Exception as exc:UI_QUEUE.put(('chat_err',str(exc)))
		finally:UI_QUEUE.put(('chat_end',_C))
	def _chat_sync(A,base,key,model,messages):
		try:
			sys.stdout.write('AI> ');sys.stdout.flush();content=''
			for kind,value in iter_chat_stream(base,key,model,messages,_C):
				if kind=='content':content+=value;sys.stdout.write(value);sys.stdout.flush()
			sys.stdout.write('\n');sys.stdout.flush()
			if content.strip():
				A.chat['messages'].append({'role':'assistant','content':content});save_chat_history(A.chat['messages'])
		except Exception as exc:
			print('\n对话请求失败：%s'%exc)
		finally:A.chat_streaming=_D
	def _chat_delta(A,kind,text):
		if kind=='reasoning':
			A._chat_reason+=text;A.flash_msg('思考中…',_V);return
		A._chat_content+=text
		width=max(20,A._size()[0]-6);tail=text if len(text)<=width else text[-width:]
		line='AI> '+('…'if len(tail)<len(A._chat_content)else'')+tail
		if A.logs and A.logs[-1][1]=='chat_ai':A.logs[-1]=(line,'chat_ai');A._chat_live_owned=_E
		else:A.logs.append((line,'chat_ai'));A._chat_live_owned=_E
		A.log_offset=0
	def _chat_print(A,prefix,text,tag):
		width=max(20,A._size()[0]-dwidth(prefix))
		for i,line in enumerate(wrap_display(text,width)):
			A.logs.append(((prefix if i==0 else _F*dwidth(prefix))+line,tag))
		A.log_offset=0
	def _chat_done(A,content):
		A.chat_streaming=_D
		if A._chat_live_owned and A.logs and A.logs[-1][1]=='chat_ai':A.logs.pop()
		A._chat_live_owned=_D
		if A._chat_reason:A._chat_print('思考> ',A._chat_reason,'chat_reason')
		final=content or A._chat_content
		if final:A._chat_print('AI> ',final,'chat_ai')
		else:A.log('（上游没有返回文本内容）',_T)
		if final.strip():
			A.chat['messages'].append({'role':'assistant','content':final});save_chat_history(A.chat['messages'])
		A._chat_content='';A._chat_reason=''
		A.log_offset=0;A.flash_msg('对话完成',_Q)
	def _chat_usage(A,usage):
		inp=usage.get('prompt_tokens',usage.get('input_tokens',0))or 0
		out=usage.get('completion_tokens',usage.get('output_tokens',0))or 0
		A.log('（tokens: 输入 %s / 输出 %s）'%(inp,out),_V)
	def _chat_error(A,msg):
		A.chat_streaming=_D
		if A._chat_live_owned and A.logs and A.logs[-1][1]=='chat_ai':A.logs.pop()
		A._chat_live_owned=_D
		if A._chat_content:A._chat_print('AI> ',A._chat_content,'chat_ai')
		A._chat_content='';A._chat_reason=''
		A.log('对话请求失败：%s'%msg,_G);A.flash_msg('对话失败',_G);A.log_offset=0
	# ---------- 缓存清理 ----------
	def cmd_cache(A,args):
		cat=(args[0].lower()if args else'')
		yes=any(x.lower()in('--yes','-y','confirm')for x in args[1:])
		if cat in('','status','list'):
			targets=_cache_targets(_C)
			A.log('Codex 缓存目录：%s'%codex_home(),_d)
			A.log('本软件缓存目录：%s'%BASE_DIR,_d)
			if not targets:A.log('  未发现可清理的缓存',_V);return
			total=0
			for t in targets:
				total+=t['size'];A.log('  [%s] %s  %s  (%s)'%(CACHE_TITLES.get(t['cat'],t['cat']),t['source'],t['path'],fmt_size(t['size'])),_r)
			A.log('合计 %d 项 / %s'%(len(targets),fmt_size(total)),_Q)
			A.log('清理：cache models --yes · cache chat --yes · cache logs --yes · cache temp --yes · cache all --yes',_V)
			return
		if cat=='all':cats=_C
		elif cat in CACHE_TITLES:cats=[cat]
		else:A.log('未知类别：%s（可用 models / chat / logs / temp / all）'%cat,_G);return
		targets=_cache_targets(cats)
		if not targets:A.log('没有可清理的缓存',_V);return
		total=sum(t['size']for t in targets)
		A.log('将清理 %d 项，共 %s：'%(len(targets),fmt_size(total)),_T)
		for t in targets[:20]:A.log('  [%s] %s  (%s)'%(CACHE_TITLES.get(t['cat'],t['cat']),t['path'],fmt_size(t['size'])),_r)
		if len(targets)>20:A.log('  … 另有 %d 项'%(len(targets)-20),_V)
		if any(t['cat']=='chat'for t in targets):A.log('⚠ 包含聊天 / 会话缓存，删除后无法恢复',_G)
		if not yes:A.log('确认执行：cache %s --yes'%(cat or'all'),_T);return
		removed,failed=remove_cache_targets(targets)
		freed=sum(t['size']for t in removed)
		A.log('已清理 %d 项，释放 %s'%(len(removed),fmt_size(freed)),_Q)
		for t,err in failed:A.log('删除失败：%s（%s）'%(t['path'],err),_G)
	def cmd_providers(A,args):
		A.log(f"内置服务商（共 {len(PROVIDERS)} 项）：",_d)
		for(C,B)in PROVIDERS.items():
			if B:A.log(_c+pad_display(C,40)+B)
	def cmd_stats(C,args):
		A=GLOBAL_STATS;C.log(f"请求 {A[_k]} 次 | 进行中 {_inflight()} | 输入 {A[_i]} | 输出 {A[_j]} | 合计 {A[_b]} | 未回报用量 {A[_AE]} 次",_d);D=[(B,A)for(B,A)in LINK_STATS.items()if A.get(_k)]
		if D:
			C.log('各链路统计：',_V)
			for(E,B)in D:C.log(_c+pad_display(E,24)+f"请求 {B[_k]} 次 · in {B[_i]} / out {B[_j]} · 合计 {B[_b]}",_V)
	def cmd_version(A,args):
		B={_An:'已是最新',_AL:f"有新版本 {A.update_remote}",_J:'检查失败',_Ac:'尚未检查'}.get(A.update_state);A.log(f"当前版本 v{VERSION}  ·  更新状态：{B}",_d)
		if A.update_state==_AL:A.log('输入 web 打开官网下载页面',_T)
	def cmd_check(A,args):
		if A._checking:A.log('正在检查中…',_V);return
		A.log('正在向服务器查询版本…',_V);threading.Thread(target=A._check_thread,daemon=_E).start()
	def _check_thread(A):
		A._checking=_E
		try:A._do_update_check()
		finally:A._checking=_D
		B=A.update_state
		if B==_An:UI_QUEUE.put((_s,f"已是最新版本 v{VERSION}"))
		elif B!=_AL and B!=_J:UI_QUEUE.put((_s,'版本检查完成'))
	def cmd_web(B,args):
		try:A=webbrowser.open(HOMEPAGE)
		except Exception:A=_D
		B.log('已在浏览器中打开官网下载页'if A else'无法自动打开浏览器，请手动访问官网下载',_Q if A else _G)
	def cmd_clear(A,args):A.logs.clear();A.log_offset=0
	def cmd_logs(A,args):
		A.log('错误日志目录：',_d);A.log(_c+LOG_DIR,_r)
		try:B=sorted((A for A in os.listdir(LOG_DIR)if A.lower().endswith('.log')),reverse=_E)
		except Exception:B=[]
		if not B:A.log('  （还没有错误日志，说明目前运行正常）',_V)
		else:
			A.log(f"  最近 {min(len(B),5)} 个文件：",_V)
			for C in B[:5]:
				D=os.path.join(LOG_DIR,C)
				try:E=os.path.getsize(D);F=time.strftime('%m-%d %H:%M',time.localtime(os.path.getmtime(D)))
				except Exception:E,F=0,'?'
				A.log(f"    {C}  {E} B  {F}",_r)
		try:os.startfile(LOG_DIR);A.log('已在资源管理器中打开该目录',_Q)
		except Exception:A.log('无法自动打开目录，请按上面的路径手动进入',_T)
	def cmd_quit(A,args):A.running=_D
	def _need_link(A,args,hint=_D):
		B=A._pick_link(args)
		if not B:A.log('找不到指定链路（用 list 查看编号）'if hint else'找不到指定链路',_G)
		return B
	def _pick_link(A,args):
		if not A.links:return
		if not args:
			if 0<=A.selected<len(A.links):return A.links[A.selected]
			return
		C=args[0]
		if C.isdigit():D=int(C)-1;return A.links[D]if 0<=D<len(A.links)else _C
		for B in A.links:
			if B.get(_B)==C:return B
		for B in A.links:
			if B.get(_B,'').lower().startswith(C.lower()):return B
	def start_server(E,cfg):
		A=cfg;B=int(A.get(_N,15721));F='127.0.0.1'
		in_use,_,_=_port_owner(B)
		if in_use:E.log('启动失败：'+describe_port(B),_G);return _D
		try:from werkzeug.serving import make_server as G;C=G(F,B,PROXY_APP,threaded=_E);D=threading.Thread(target=C.serve_forever,daemon=_E);D.start();PROXY_STATE[_A5]=C;PROXY_STATE[_Af]=D;PROXY_STATE[_AO]=B;PROXY_STATE[_A4]=A;PROXY_STATE[_X]=A.get(_B);return _E
		except Exception as H:E.log(f"启动失败: {H}",_G);return _D
	def stop_server(B):
		A=PROXY_STATE.get(_A5)
		if A:
			try:A.shutdown()
			except Exception:0
		PROXY_STATE[_A5]=_C;PROXY_STATE[_Af]=_C;PROXY_STATE[_X]=_C;PROXY_STATE[_A4]={};PROXY_STATE[_AO]=_C
	def _probe_upstream(F,cfg):
		B=cfg
		try:
			A=requests.get(f"{api_base(B)}/models",headers={_AX:f"Bearer {B.get(_M,"")}"},timeout=10)
			if A.status_code==200:
				C=[A.get(_K)for A in A.json().get(_A1,[])if A.get(_K)];UI_QUEUE.put((_s,f"上游就绪，获取到 {len(C)} 个模型"))
				if not B.get(_H):D=', '.join(C[:5])if C else'(无)';UI_QUEUE.put((_p,f"未填写「上游模型名」，客户端模型名会被原样转发，很可能 404。可用示例: {D}"))
			else:UI_QUEUE.put((_p,f"上游返回 {A.status_code}: {A.text[:150]}"))
		except Exception as E:UI_QUEUE.put((_p,f"上游连通性检测失败: {E}"))
	def _size(B):A=shutil.get_terminal_size((110,32));return max(60,A.columns-1),max(16,A.lines-1)
	def current_prompt(A):
		if A.chat and A.chat.get('active'):return'[聊天] > '
		if A.wizard:B=A.wizard[_AP][A.wizard[_O]];return f"{B[_P]} [{B[_w]or"空"}] > "
		return'> '
	def is_secret(A):
		if not A.wizard:return _D
		return bool(A.wizard[_AP][A.wizard[_O]].get(_Ab))
	def hint_text(A):
		if A.flash and time.time()<A.flash_until:return A.flash,A.flash_color or C_INFO
		if A.chat and A.chat.get('active'):return'输入消息回车发送 · /model 后按 Tab 循环选模型 · /help 命令 · /exit 返回',C_DIM
		if A.wizard:return'回车确认 · Esc 取消',C_DIM
		if 0<=A.selected<len(A.links):B=A.links[A.selected];return f"链路 {A.selected+1}/{len(A.links)} · {B.get(_B)} · 端口 {B.get(_N)} · ↑↓ 选择 · PgUp/PgDn 翻日志",C_DIM
		return'输入 help 查看命令 · ↑↓ 选择链路 · PgUp/PgDn 翻日志',C_DIM
	def _title_bar(D,w,right):
		A=right;B=f" API Linking Bridge  v{VERSION} ";C=w-dwidth(B)-dwidth(A)
		if C<0:A,C='',max(0,w-dwidth(B))
		return REV+B+_F*C+A+RESET
	def _box_lines(E,title,width,height,rows):B=width;A=rows;D=max(1,height-2);C=['╔'+border_seg(B,title)+'╗'];A=list(A[:D])+[_F*B]*max(0,D-len(A));C.extend('║'+A+'║'for A in A);C.append('╚'+'═'*B+'╝');return C
	def build_frame(A,w,h):
		F=[A._title_bar(w,'[Tab]补全  [↑↓]选择  [Enter]执行  [Ctrl+C]退出 ')];C=max(6,h-3);D=max(20,int((w-4)*.62));B=max(16,w-4-D)
		if D+B+4>w:D=max(16,w-4-B)
		E=max(3,min(C-3,int(C*.62)));H=max(3,C-E);J=A._log_rows(C-2,D);K=A._link_rows(E-2,B);L=A._stat_rows(H-2,B);I=A._box_lines(' Console Logs ',D,C,J);M=A._box_lines(' Linking Bridge Lists ',B,E,K);N=A._box_lines(' Requests / Tokens ',B,H,L)
		for G in range(len(I)):O=M[G]if G<E else N[G-E];F.append(I[G]+O)
		P=A.current_prompt();Q='*'*len(A.buffer)if A.is_secret()else A.buffer;R=_F+P+Q+'_';S,T=cut_text(R,w);F.append(C_CYAN+S+_F*(w-T)+RESET);U,V=A.hint_text();W,X=cut_text(U,w);F.append(V+W+_F*max(0,w-X)+RESET);return F[:h]
	def form_hint(A):
		if A.form[_q]:return'输入内容 · Enter 确认 · Esc 取消编辑（本次输入不生效）'
		return'↑↓ 选择字段 · ←→ 切换选项 · Enter 编辑/执行 · Esc 返回（不保存）'
	def _form_display(D,fld):
		B=fld;A=D.form[_v].get(B[_I],'');C=B[_I]
		if C==_M:
			if len(A)>12:return A[:6]+'…'+A[-4:]
			return'*'*len(A)
		if C==_S:return'‹ 是 ›'if A else'‹ 否 ›'
		if B[_A]==_A2:return f"‹ {A} ›"
		return str(A)if A!=''else'(空)'
	def _form_row(C,idx,fld,width):
		D=width;A=C.form;E=idx==A[_O]
		if E and A[_q]:F=A[_n]+'_'
		else:F=C._form_display(fld)
		B=_c+pad_display(fld[_P],14)+F;B,G=cut_text(B,D);H=REV if E else'';return(H or'')+B+_F*max(0,D-G)+RESET
	def _form_actions(D,width):A=D.form;B=' [ 保存 ] ';C=' [ 取消 ] ';E=REV if A[_O]==ACTION_SAVE else'';F=REV if A[_O]==ACTION_CANCEL else'';G=_c+E+B+RESET+'   '+F+C+RESET;H=2+dwidth(B)+3+dwidth(C);return G+_F*max(0,width-H)
	def build_form_frame(D,w,h):
		E=D.form;C=[D._title_bar(w,'[↑↓]选择  [←→]切换  [Enter]编辑  [Esc]返回 ')];G=min(w,92);H=min(h-2,18);A=G-2;F=_F*max(0,(w-G)//2);I=f" 链路设置 · {E[_v].get(_B)or"未命名"} ";C.append(F+'╔'+border_seg(A,I)+'╗');B=[_F*A]
		for(J,K)in enumerate(FORM_FIELDS[:ACTION_SAVE]):B.append(D._form_row(J,K,A))
		B.append(_F*A);B.append(colorize(_c+'─'*max(0,A-4),C_DIM,A));B.append(D._form_actions(A))
		if E.get(_J):B.append(colorize(_c+E[_J],C_ERR,A))
		else:B.append(colorize('  修改后选「保存」生效 · Esc 不保存直接返回',C_DIM,A))
		B=B[:max(0,H-2)]
		while len(B)<H-2:B.append(_F*A)
		for L in B:C.append(F+'║'+L+'║')
		C.append(F+'╚'+'═'*A+'╝');M=D.form_hint();N,O=cut_text(M,w);C.append(C_DIM+N+_F*max(0,w-O)+RESET)
		while len(C)<h:C.append(_F*w)
		return C[:h]
	def _log_rows(A,inner_h,width):
		D=width;B=inner_h;F=max(0,len(A.logs)-B);A.log_offset=max(0,min(A.log_offset,F));E=max(0,len(A.logs)-B-A.log_offset);G=list(A.logs)[E:E+B];C=[colorize(_F+A,LEVEL_COLOR.get(B,''),D)for(A,B)in G]
		while len(C)<B:C.append(_F*D)
		return C
	def _link_rows(A,inner_h,width):
		N=inner_h;C=width;D=[];P=PROXY_STATE.get(_X);B=max(1,N);A._list_space=B
		if not A.links:D.append(colorize('  （暂无链路，输入 add 新建）',C_DIM,C))
		G=len(A.links)
		if G<=B:H=0
		else:H=min(max(0,A.selected-B+1),G-B)
		for I in range(H,min(G,H+B)):
			Q=A.links[I];E=Q.get(_B,'Unnamed');R=E==P;S=I==A.selected;J=f"{I+1}. ";K=' loaded 'if R else'';L=_link_stat(E);F=f"{L[_k]}次"if L and L.get(_k)else'';O=dwidth(K)+(dwidth(F)+1 if F else 0);T=C-1-dwidth(J)-O;E,U=cut_text(E,max(4,T));V=C-1-dwidth(J)-U-O;M=[(_F+J+E,''),(_F*max(1,V),'')]
			if K:M.append((K,RESET+'\x1b[42;30;1m'))
			if F:M.append((_F+F+_F,C_DIM))
			W=REV if S else'';D.append(render_segments(M,C,W))
		while len(D)<B:D.append(_F*C)
		return D[:N]
	def _stat_rows(K,inner_h,width):
		E=inner_h;A=width;F=PROXY_STATE.get(_X);B=_link_stat(F)or{};H=B.get(_k,0);I=_inflight();G=PROXY_STATE.get(_AO);C=time.time()-B[_AR]if B.get(_AR)else _C;J='—'if C is _C else'刚刚'if C<10 else f"{int(C)} 秒前";D=[colorize(f"  链路    {F or"未启动"}",C_INFO,A),colorize(f"  请求    {H} 次 · 进行中 {I}",'',A),colorize(f"  输入    {B.get(_i,0)} tokens",C_DIM,A),colorize(f"  输出    {B.get(_j,0)} tokens",C_DIM,A),colorize(f"  合计    {B.get(_b,0)} tokens",C_DIM,A),colorize(f"  最近    {J}",C_DIM,A),colorize(f"  端口    {"127.0.0.1:"+str(G)if G else"—"}",C_DIM,A),colorize(f"  版本    v{VERSION}",C_DIM,A)]
		while len(D)<E:D.append(_F*A)
		return D[:E]
	def render(A):
		B,C=A._size()
		if(B,C)!=A._last_size:sys.stdout.write('\x1b[2J');A._last_size=B,C
		D=A.build_form_frame(B,C)if A.form else A.build_frame(B,C);sys.stdout.write('\x1b[H'+'\r\n'.join(D)+'\x1b[J');sys.stdout.flush()
if __name__=='__main__':
	if not HAS_CONSOLE:
		msg='API Linking Bridge 终端版需要在命令行窗口中运行。\n\n请用 cmd 或 PowerShell 启动，或者重新打包时加 --console 参数。\n\n（日志目录：%s）'%LOG_DIR
		try:import ctypes;ctypes.windll.user32.MessageBoxW(_C,msg,'API Linking Bridge - Terminal Edition',16)
		except Exception:0
		try:
			os.makedirs(LOG_DIR,exist_ok=_E)
			with open(os.path.join(LOG_DIR,'no-console.txt'),'a',encoding=_f)as f:f.write(time.strftime('%Y-%m-%d %H:%M:%S  ')+msg.replace(_a,_F)+_a)
		except Exception:0
		raise SystemExit(1)
	app=TerminalApp();install_crash_handlers(app);fatal_path='';failed=_D
	try:app.run()
	except KeyboardInterrupt:0
	except SystemExit:0
	except Exception as exc:
		failed=_E
		try:recent=[A for(A,B)in list(app.logs)[-40:]];fatal_path=_write_crash_log(type(exc),exc,exc.__traceback__,'CLI 启动/主流程',recent)
		except Exception:fatal_path=_Ad
	finally:
		if app.interactive:sys.stdout.write(RESET+_As);sys.stdout.flush()
	if failed:
		print('');print('程序遇到错误，但没有直接退出。');print('错误日志已保存到：');print(_c+fatal_path);print('请把上面这个 .log 文件发给开发者，方便定位问题。')
		try:input('按回车键退出…')
		except Exception:0
	else:print(RESET+'已退出 API Linking Bridge - Terminal Edition')