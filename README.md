# 弈墨 · 金铲铲画之灵助手

可直接部署的 FastAPI 项目，附手机与桌面自适应网页。前端为原生 HTML/CSS/JavaScript，无需 Node 构建、数据库、账号、第三方 AI Key。

## 已实现

- **阵容学习手册（首页）**：44 套官网方案，讲清适合选择的条件、不宜强玩的情况、搜牌窗口与最终人口的区别、过渡、装备分配和前置条件。不要求玩家实时同步对局。
- **连续棋子图鉴**：费用、羁绊、1–3 星基础属性与技能，固定阅读区域、上一位／下一位、键盘左右键、快速跳转，保留星级与筛选。手机上可横向滑动棋子列表。
- **棋子属性对比**：可排序的全棋子属性总表，以及最多三位棋子的同星级对比；缺失星级会明确显示实际数据星级。裸普攻 DPS 仅为攻击力乘攻速，不代表总体强度。
- **理解出装**：完整保留官网的装备组合和重复装备，按具体阵容查看，并解释启动、攻速、续航、防御和重伤等作用，提示技能与装备功能重叠。
- **海克斯双向查询**：225 个符文，按名称、效果、品阶、类型或阵容筛选；从阵容查优选／备选，也可从符文反查阵容。官网搭配名单与本项目的机制分析分别标注，专属强化、费用限制与随机奖励不能混用。
- **运营判断速查**：什么时候搜牌、升级、合装、换路线的条件式参考。
- **装备工坊**：普通、光明、神器、辅助、纹章等装备；合成路径、现有散件可合成筛选、阵容使用者。
- **阵容详情**：选阵与运营／装备与站位／海克斯搭配三个栏目，保留官网原攻略与作者、原始时间，4×7 棋盘可直接进入棋子图鉴。
- **赛季资料**：羁绊图鉴、绘境／狂风奇遇说明、数据时间与原始来源。
- **胜率与数据口径**：区分前四率、登顶率、平均名次与样本量。目前没有可验证的同赛季结算样本，页面明确显示未接入，绝不以匹配分冒充胜率。支持维护者导入有来源的数据。
- **可选条件匹配**：在「更多资料」中保留城邦、海克斯、来牌、装备等条件工具，采用可解释规则；有限库存逐件分配，不重复使用散件。它不是使用手册的前提。
- **手机使用**：底部导航、触控选择、浏览器本地收藏／条件记忆、分享阵容链接。HTTPS 下支持 PWA 与离线浏览缓存资料；重新计算推荐需要联网。

## 数据口径与来源

本项目核对的是 **2026 年返场版画之灵（Mode11 / S100030）**，不是 2024 年初版。内置快照取自 [金铲铲官网](https://jcc.qq.com/) 页面实际使用的腾讯公开 JSON：

- [官网版本配置](https://game.gtimg.cn/images/lol/act/jkzlk/js/config/versiondataconfig.js)：选取 `mode=11, season=S100030, is_newest_version=1`，发现当前资料版本 `18.11.1`。
- 该版本的英雄、装备、强化符文、羁绊、城邦等 JSON；完整 URL、上游更新时间和 SHA-256 保存在 `data/catalog.json` 的 `sources` 字段。
- [官网阵容库](https://game.gtimg.cn/images/lol/act/jkzlkauto/json/lineupJson/m100030/11/11/lineup_detail_total.json)：44 套阵容，保留作者、原建立时间、返场发布时间与官网页面链接。
- 官方 TapTap 账号：[绘境与羁绊更新](https://www.taptap.cn/moment/851886704909353222)、[狂风奇遇说明](https://www.taptap.cn/moment/852521787559247892)。

首个快照收录 64 个弈子条目（含形态与召唤物，合并星级变体）、226 个装备条目（界面隐藏上游 `type=-1` 的条目）、225 个强化符文、27 个羁绊、19 个城邦／开局奇遇、44 套阵容。官网资料最近更新时间为 **2026-10-09**，实际同步时间以页面和 JSON 为准。资料版本号与客户端公告版本号不是同一个字段。

**条件匹配规则由本项目实现，分数不代表胜率、实时排行或官方强度评级。** 部分官网攻略由 2024 年历史内容在 2026 年返场时重新发布；页面会显示两个时间并提示差异。上游公开数据没有提供完整绘境格与全部中途奇遇目录，当前只收录官方已经核实的机制说明，不臆造精确效果。英雄头像与装备图标直接引用腾讯 CDN；CDN 不可用时仍可阅读文字与使用推荐。

选阵条件、常见搜牌等级、装备作用和海克斯搭配理由属于学习分析；属性、效果、完整出装及官网优选名单来自官方快照。常见搜牌等级根据核心费用与路线归纳，不是固定回合指令。上游的「启程天使」依赖当前符文库未收录的「冒险启程」，会标为历史参考；部分标题和主C标记的矛盾也会提示。

## 本地启动

要求 Python 3.12+。Windows PowerShell：

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Linux / macOS：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

打开 `http://127.0.0.1:8000`。手机与电脑在同一局域网时，打开 `http://电脑局域网IP:8000`；Windows 防火墙需要允许该端口。局域网 HTTP 可以使用页面，但添加为 PWA、剪贴板等能力通常需要 HTTPS 或 localhost。

API 文档 `/docs`，OpenAPI `/openapi.json`，健康检查 `/healthz`。`.env` 不会自动覆盖 Python 进程环境；本地如需加载可运行 `uvicorn ... --env-file .env`。Docker Compose 自动读取项目的 `.env` 用于变量替换。

## 云服务器部署

### Docker 直接运行

```bash
docker compose up -d --build
```

默认监听服务器 8000 端口。云安全组／防火墙放行后，手机可访问 `http://服务器IP:8000`。可在 `.env` 中设置 `APP_PORT=8080` 改变宿主机端口。

### 域名 + 自动 HTTPS（推荐）

将真实域名 A/AAAA 记录解析到服务器，放行入站 80/443。复制 `.env.example` 为 `.env`，把 `APP_DOMAIN` 改成你的域名，然后运行：

```bash
docker compose -f compose.production.yml up -d --build
```

Caddy 会申请和续期证书，FastAPI 只在容器网络暴露。此时访问 `https://你的域名`。请单独使用这一份生产 Compose；不需要与普通 Compose 叠加。手机浏览器可选择「添加到主屏幕」，平台是否允许安装及图标支持以实际浏览器为准。

### 托管容器／应用服务

使用项目根目录 Dockerfile；健康检查路径 `/healthz`；默认端口 8000，支持平台注入 `PORT`。普通 Python 服务可使用启动命令：

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```

数据快照随镜像部署，运行时无外部网络依赖（头像除外），无持久磁盘要求。推荐使用 1 核 / 512 MB 或以上作为起点，实际容量以压测为准。`WEB_CONCURRENCY` 控制 Docker worker 数；前后端同域无需 CORS。若拆分前端，设置精确的 `CORS_ORIGINS=https://你的前端域名`。如需信任反向代理传入的客户端信息，应把实际代理 IP 填入 `FORWARDED_ALLOW_IPS`。

## 更新官网数据

更新命令固定抓取腾讯公开 JSON，不执行远程 JS，不抓取登录数据，也不会在用户请求或每次启动时抓取网站。

```bash
python -m scripts.sync_official --dry-run
python -m scripts.sync_official
```

先按版本配置发现对应赛季的数据地址，再下载并校验 ID、引用与棋盘位置。全部通过后原子替换 `data/catalog.json`；任一环节失败保留旧数据。**更新后需要重启 FastAPI 的全部 worker，或重新构建部署镜像**（服务使用进程内只读缓存）：

```bash
docker compose up -d --build
# 若使用 HTTPS 方案：
docker compose -f compose.production.yml up -d --build
```

只读容器中应在宿主机／CI 工作目录更新数据后重建镜像。建议在有版本更新时执行命令；资料超过七天未同步会提示维护者。官网接口可能改版，脚本会明确失败而不会跨赛季覆盖。`--from-cache` 仅用于开发时读取已下载的研究目录，不是正常更新流程。

## API 示例

手册、棋子和海克斯不需要提交对局状态，直接读取即可：

```http
GET /api/v1/guidebook
GET /api/v1/heroes/13213
GET /api/v1/lineups/2244/guide
GET /api/v1/augments/2922
```

以下是可选条件匹配接口：

```http
POST /api/v1/recommend
Content-Type: application/json

{
  "portal_id": "449",
  "augment_ids": [],
  "hero_counts": {"13213": 6},
  "component_ids": ["1002", "1003", "1002"],
  "owned_item_ids": [],
  "contested_hero_ids": [],
  "level": 7,
  "hp": 62,
  "gold": 50,
  "preferred_style": "auto",
  "limit": 6
}
```

`449` 是嘀嘀不绝，`13213` 是巴德，`1002/1003` 是弓／棒。散件和成装数组按数量重复传入；`hero_counts` 表示总张数，两星填写 3。返回 `results[].lineup`、`score`、`breakdown`、`equipment_plan`、`conditions` 和 `warnings`。错误或跨目录 ID 返回 422，未知详情返回 404。

| 接口 | 用途 |
| --- | --- |
| `GET /api/v1/meta` | 版本、同步时间、过期提示与来源 |
| `GET /api/v1/catalog` | 前端完整资料快照 |
| `GET /api/v1/guidebook` | 全部学习内容、双向符文关系与运营速查 |
| `GET /api/v1/heroes?q=巴德&cost=3` | 搜索英雄、费用与羁绊筛选 |
| `GET /api/v1/heroes/{id}` | 英雄属性、技能和参考出装 |
| `GET /api/v1/items?q=鬼索` | 装备检索，支持 `type` |
| `GET /api/v1/items/{id}` | 装备与官网使用者 |
| `GET /api/v1/augments?q=莲华&tier=2` | 海克斯检索 |
| `GET /api/v1/augments/{id}` | 效果、限制和关联阵容及理由 |
| `GET /api/v1/portals` | 城邦／开局奇遇 |
| `GET /api/v1/traits` | 羁绊与档位 |
| `GET /api/v1/lineups` | 官网候选阵容，支持 `q`、`style` |
| `GET /api/v1/lineups/{id}` | 阵容详情 |
| `GET /api/v1/lineups/{id}/guide` | 选阵条件、运营、装备作用与符文搭配 |
| `GET /api/v1/rankings?metric=top4_rate&min_samples=30` | 有来源的结算统计；未接入时返回空榜与原因 |
| `POST /api/v1/recommend` | 按对局条件匹配 |

## 接入真实统计（维护者）

官网公开阵容库提供攻略，未提供可用的结算样本。已检查的 [DataJ 统计页](https://www.dataj.cc/comp) 展示其他赛季，因此当前交付包不含 `data/statistics.json`，也不含伪造的示例排行榜。

取得有使用权限、可核验来源的画之灵数据后，按 `data/statistics.schema.json` 准备 JSON，再执行：

```bash
python -m scripts.import_statistics /path/to/verified-statistics.json
```

必须提供 `season=S100030`、与快照相同的 `data_version`、来源名称和网址、国服区域、分段、构筑识别口径、带时区的起止时间，以及 `samples`。每条样本用官网 `lineup_id` 映射构筑，`placement_counts` 必须是按第一到第八名顺序排列的八个非负整数，且至少有一条记录；不能将其他赛季、其他构筑或上游百分比反推成假样本。导入脚本验证后原子保存；重启全部 worker 或重建镜像才生效，也可用 `STATISTICS_PATH` 环境变量指定只读文件位置。

统计接口计算前四率、登顶率和加权平均名次，支持最低样本量筛选。版本不一致或构筑映射失败时停止展示；统计结束超过七天标为历史参考。来源的真实性仍须维护者审核，结构校验不能证明样本真实可靠。

## 测试与结构

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

测试覆盖库存不重复使用、重复装备、符文与来牌匹配、专属条件、同行降分、城邦影响、双向关系、费用与随机奖励限制、资料完整性，以及统计计算、样本筛选、跨赛季／跨版本／无效数据拒绝。

本次交付验证：43 项测试通过；JavaScript 语法检查通过；Linux x86_64 / Python 3.12 依赖解析通过。浏览器检查涵盖桌面与手机布局、棋子切换与星级保持、三棋子对比、属性排序、阵容栏目、符文双向查询和空榜说明。受 Windows 沙箱临时目录限制时，测试可加 `--basetemp=.cache/pytest-reference-qa`。当前开发机器没有 Docker，因此未执行实际镜像构建和云端部署；PWA 离线逻辑未在真机断网场景测试。

运行 `python -m scripts.package_project` 生成 `dist/yimo-fastapi.zip`，可上传云服务器后解压部署；包内不含虚拟环境、缓存、研究临时文件或私有 `.env`。

```text
app/main.py                 FastAPI 路由与静态页面
app/catalog.py              数据加载与关联校验
app/recommend.py            条件匹配与装备库存分配
app/reference.py            静态学习内容与双向符文关系
app/statistics.py           同版本结算统计模型与计算
app/static/                 响应式网页、PWA、前端交互
data/catalog.json           已核实的官网数据快照
data/statistics.schema.json 可选统计文件的格式规范
scripts/sync_official.py    可重复执行的数据更新命令
scripts/import_statistics.py 有来源统计的本地导入命令
tests/test_app.py           API 与推荐引擎测试
tests/test_reference.py     学习关系与统计口径测试
Dockerfile                  非 root 容器
compose.production.yml      Caddy HTTPS 部署
```

收藏和条件保存在当前设备浏览器，不跨设备同步。项目无数据库、无管理写接口；若以后增加用户账号或可写功能，再引入数据库和身份认证即可。


## AI 学习教练

首页和棋子、装备、阵容详情均提供「AI 教练」入口。提问自动附上当前对象、棋子星级和相关官网资料；支持连续追问、查看本次检索的资料卡片。回答仅基于本地赛季快照，无实时联网检索、截图识别或战斗模拟。

在项目根目录创建 `.env`（可从 `.env.example` 复制，不要覆盖已有配置），填写：

```dotenv
AI_API_KEY=你的服务商密钥
AI_MODEL=你的账户可用模型ID
AI_BASE_URL=https://你的服务商地址/v1
AI_API_STYLE=chat_completions
AI_ACCESS_TOKEN=自行设置英文数字访问口令
```

其他服务商须提供兼容 Chat Completions 的接口，基础地址按其文档填写，不含 `/chat/completions`；程序使用 `messages`、`max_tokens` 和非流式返回。OpenAI 或支持 Responses 的服务可设置 `AI_API_STYLE=responses`，OpenAI 基础地址为 `https://api.openai.com/v1`。模型 ID 必须由你的服务商账户提供，项目不默认指定模型。协议分别参照 [OpenAI 文本生成文档](https://developers.openai.com/api/docs/guides/text) 和 [Chat Completions 文档](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)，第三方兼容程度须实际测试。

本地启动：`.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000`，应用自动读取根目录 `.env`；更改配置后需重启。Docker Compose 已透传这些环境变量，更改后运行 `docker compose up -d --build`（生产部署使用对应 compose 文件）。

未配置密钥或模型时，AI 面板显示配置提示，其他功能照常使用。`GET /api/v1/ai/status` 仅返回是否配置，不测试上游连通性、不返回密钥。`POST /api/v1/ai/ask` 接收问题、页面种类/ID、星级及最多8条历史消息；访问口令通过 `X-AI-Access-Token` 传递。密钥仅由服务端读取，不会进入浏览器；访问口令不会保存到浏览器存储。问题、近期对话与相关资料会发送至你配置的服务商，服务商可能按其规则计费和保存数据；Responses 模式请求设置 `store=false`，第三方数据保留规则以其条款为准。

当前限制为每进程每分钟20次请求、3个并发，适用于个人使用；多 worker 会各自计数。公网使用请设置访问口令，服务商费用上限在服务商控制台设置。测试覆盖两种协议、资料关联、错误与超时处理、访问控制，不使用真实密钥或产生模型调用费用。


### DeepSeek 配置

本项目当前本地配置为 `AI_BASE_URL=https://api.deepseek.com`、`AI_MODEL=deepseek-flash`、`AI_API_STYLE=chat_completions`；只需在 `.env` 填入 `AI_API_KEY` 后重启。对应请求路径为 `/chat/completions`。为了快速完成页面问答，直连 DeepSeek 时请求显式使用 `thinking.type=disabled`，避免有限输出额度被思考过程占用。参数和返回格式参照 [DeepSeek 官方接口文档](https://api-docs.deepseek.com/api/create-chat-completion/)。此配置不包含密钥，也不表示已经完成真实连通性验证。
