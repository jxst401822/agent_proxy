# 百炼(DashScope)兼容转发网关

基于 **FastAPI** 的透明转发网关,面向部署在网关服务器、为**内网**提供统一出口的场景。
对内网呈现与阿里云百炼(DashScope)完全一致的 API 形态,收到请求后透明转发到真实上游
`https://dashscope.aliyuncs.com`,并把响应(含流式 SSE)逐块返回给内网客户端。

内网客户端无需感知网关的存在——直接以百炼官方路径调用即可。

## 特性

- **全端点覆盖**:采用通用路径转发,天然支持百炼全部端点(对话、responses、向量化、模型列表、图像、音频、原生 generation 等),无需为每个端点单独实现。
- **流式透传**:`chat/completions` 等 SSE 流式响应实时逐块转发,支持长连接。
- **透明认证**:内网客户端传入自己的 `Authorization: Bearer sk-xxx`,网关原样透传,不代持 Key。
- **错误透传**:上游任意状态码连同 body 原样返回,不吞错误。
- **两条路径线**:
  - `/compatible-mode/v1/*` → 阿里云 OpenAI 兼容模式(默认上游 `https://dashscope.aliyuncs.com`)
  - `/api/v1/*` → 原生 DashScope 接口(可配置独立上游,见下方"原生多区域端点")

## 目录结构

```
agent_proxy/
├── app/
│   ├── __init__.py
│   ├── main.py        # FastAPI 应用入口:路由、CORS、http 客户端生命周期
│   ├── config.py      # 配置(上游地址、端口、超时、CORS)
│   └── proxy.py       # 核心转发:认证检查 + httpx 转发 + SSE 流式透传
├── pyproject.toml   # uv 依赖与项目声明
├── .env.example
└── README.md
```

## 快速开始

项目采用 [uv](https://docs.astral.sh/uv/) 管理依赖与运行(依赖声明见 `pyproject.toml`)。

```bash
# 1. 安装依赖并创建虚拟环境(生成 .venv 与 uv.lock)
uv sync

# 2. 配置(可选,复制 .env.example 为 .env 修改)
cp .env.example .env

# 3. 启动网关
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

或以 `uv run uvicorn app.main:app --reload` 进入热重载开发模式。

> **离线/受限网络环境**:若机器无法访问 PyPI(如内网),可复用系统已安装的依赖,
> 创建继承系统包的虚拟环境后以 `--no-sync` 跳过联网同步:
>
> ```bash
> uv venv --system-site-packages --python C:/Python314/python.exe
> uv run --no-sync uvicorn app.main:app --host 0.0.0.0 --port 8000
> ```
>
> 注意:由于无法联网获取包元数据,离线环境下不会生成 `uv.lock`;待网络恢复后执行
> `uv sync` 即可补齐锁文件并进入标准的 uv 工作流。

## 内网客户端调用示例

### 同步对话(chat/completions)

```bash
curl -s http://<gateway>:8000/compatible-mode/v1/chat/completions \
  -H "Authorization: Bearer <你的百炼API-KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-plus",
    "messages": [{"role": "user", "content": "你好"}]
  }'
```

### 流式对话(SSE)

在请求体中加 `"stream": true`:

```bash
curl -sN http://<gateway>:8000/compatible-mode/v1/chat/completions \
  -H "Authorization: Bearer <你的百炼API-KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-plus",
    "messages": [{"role": "user", "content": "讲个笑话"}],
    "stream": true
  }'
```

返回 `text/event-stream`,逐行 `data: {...}`,收尾 `data: [DONE]`。

### 模型列表

```bash
curl -s http://<gateway>:8000/compatible-mode/v1/models \
  -H "Authorization: Bearer <你的百炼API-KEY>"
```

### 原生 DashScope 接口

```bash
curl -s http://<gateway>:8000/api/v1/services/aigc/text-generation/generation \
  -H "Authorization: Bearer <你的百炼API-KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-plus",
    "input": {"messages": [{"role": "user", "content": "你好"}]}
  }'
```

## 原生 DashScope 多区域端点

原生接口(`/api/v1/*`)按模型类型与区域使用不同入口,其中不少区域需要 `WorkspaceId` 域名。
网关通过 `NATIVE_UPSTREAM_BASE` 指向目标区域入口后,内网客户端即可用原生路径调用:

| 区域 | 纯文本模型 | 多模态模型 |
|---|---|---|
| 华北2(北京) | `https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api/v1/services/aigc/text-generation/generation` | `.../multimodal-generation/generation` |
| 新加坡 | `https://{WorkspaceId}.ap-southeast-1.maas.aliyuncs.com/api/v1/...` | 同上 |
| 美国(弗吉尼亚) | `https://dashscope-us.aliyuncs.com/api/v1/...` | 同上 |
| 德国(法兰克福) | `https://{WorkspaceId}.eu-central-1.maas.aliyuncs.com/api/v1/...` | 同上 |
| 日本(东京) | `https://{WorkspaceId}.ap-northeast-1.maas.aliyuncs.com/api/v1/...` | 同上 |

示例(指向北京工作空间):

```bash
# .env
NATIVE_UPSTREAM_BASE=https://w-abc123.cn-beijing.maas.aliyuncs.com
```

```bash
curl -s http://<gateway>:8000/api/v1/services/aigc/text-generation/generation \
  -H "Authorization: Bearer <你的API-KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-plus",
    "input": {"messages": [{"role": "user", "content": "你好"}]},
    "parameters": {"result_format": "message"}
  }'
```

> 提示:网关是**透明转发**,不解析请求体,因此原生模式(`input`/`parameters` 结构、`output.choices` 响应、
> 流式 SSE)与 OpenAI 兼容模式的不同格式都能原样透传,无需额外适配。

## 认证说明

网关采取**透传**模式:必须携带 `Authorization: Bearer <key>` 才会转发,否则返回 `401`。
网关不保存、不记录、不代持任何 API Key。内网客户端需要各自持有自己的百炼 API Key。

## 配置项

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `UPSTREAM_BASE` | `https://dashscope.aliyuncs.com` | OpenAI 兼容模式(`/compatible-mode/v1/*`)上游地址 |
| `NATIVE_UPSTREAM_BASE` | (空) | 原生 DashScope(`/api/v1/*`)上游地址;空则回退到 `UPSTREAM_BASE` |
| `HOST` | `0.0.0.0` | 监听地址 |
| `PORT` | `8000` | 监听端口 |
| `REQUEST_TIMEOUT` | `300` | 转发超时(秒),SSE 长连接需足够大 |
| `ALLOW_ORIGINS` | (空) | CORS 来源白名单,逗号分隔;空则禁用 CORS |
| `LOG_LEVEL` | `INFO` | 日志级别 |

## 健康检查

```bash
curl http://<gateway>:8000/health
# {"status":"ok"}
```

## 安全与运维建议

- 网关应仅暴露于内网,前端如确需公网暴露,建议叠加额外的接入鉴权(网关自身白名单 Key / 网关层认证),避免成为无鉴权的开放代理。
- 若内网客户端需访问外网百炼,但内网网络策略禁止直连,请确保网关服务器具备到 `dashscope.aliyuncs.com` 的出网能力。