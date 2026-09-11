# 开发说明

面向接手开发的人。运行方式见 [README](../README.md)。

---

## 1. 环境

| 项 | 值 |
|----|----|
| Python | 3.12（开发用 `.venv`，CI 用 3.10；`pyproject.toml` 的 ruff target 是 py38） |
| Node | 24.x（仅管理面板前端需要） |
| 包管理 | pip + `requirements.txt` / `requirements-dev.txt` |
| 前端构建 | Vite 6 + TypeScript 5.6 |

Windows 下统一用虚拟环境里的解释器：

```powershell
.venv\Scripts\python.exe main.py
```

`run.bat` 已封装这一步。

---

## 2. 常用命令

```powershell
# 单元测试
.venv\Scripts\python.exe -m pytest

# Lint（CI 的 lint 阶段跑的就是这个，必须全绿）
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff check . --fix
.venv\Scripts\python.exe -m ruff format .          # 可选，仓库当前未启用 format

# 管理面板前端
cd web
npm install
npm run build        # 等价于 tsc --noEmit && vite build
npm run dev          # 见下方「前端开发」

# 手动 API 验证（会临时起一个服务并连真实桌宠对象）
.venv\Scripts\python.exe tools\test_web_api.py       # 阶段 3：状态/聊天/设置
.venv\Scripts\python.exe tools\test_phase4_api.py    # 阶段 4：游戏/技能
```

### 关于 `tools/`

`tools/` 不是测试套件，是**手动验证脚本**，需要在有 Tk 环境的机器上跑：

| 脚本 | 用途 |
|------|------|
| `test_web_api.py` | 起 `ManagementServer` + 假桌宠，逐一验证阶段 3 的 REST 端点 |
| `test_phase4_api.py` | 同上，验证游戏与技能端点 |
| `smoke_games.py` | 真实创建 5 个游戏窗口并截图，检查能否正常起停 |
| `inspect_games.py` | 打印各游戏的内部状态，排查可疑 bug |

改动 `core/web_server.py` 或 `game/` 之后请至少跑一遍对应的脚本。

---

## 3. 架构约定

### 分层

```
core/    领域层：无 Tk 依赖（web_server 除外，它需要读写 cfg）
game/    小游戏：rules.py 是纯逻辑（无 Tk，可单测）
ui/      表现层：tkinter 窗口与控件
web/     管理面板前端：零框架 TS
```

**新增游戏逻辑请优先放进 `game/rules.py`**，这样能直接被 pytest 覆盖；`game/<name>/game.py` 只做渲染与事件绑定。

### 线程模型

这是本项目最容易出错的地方。Tk 不是线程安全的。

| 线程 | 职责 | 约束 |
|------|------|------|
| Tk 主线程 | 所有窗口、控件、`after` 回调 | **唯一可以碰 Tk 的线程** |
| `PetStatus._loop` | 饱腹/活力数值 | 回调里必须用 `root.after(0, ...)` 回到主线程 |
| `ScheduleManager._scheduler` | 安排表轮询 | 同上（`_fire` 已用 `root.after`） |
| `chat_history` 防抖写盘 | `threading.Timer` | 只碰文件与锁 |
| `ManagementServer` | `ThreadingHTTPServer`，每个请求一个线程 | **任何 Tk 操作都必须 `root.after(...)` 转发** |

`core/web_server.py` 里已经这么做的：`/api/pet/restart`、`/api/pet/quit`、`/api/games/{key}/start`、`/api/games/stop`。
**不要**在 HTTP 处理函数里直接调用会创建 `Toplevel` 或调用 `after` 的桌宠方法。

因为转发是异步的，这类端点的响应会做**乐观回显**（见 `_games_payload(active_key=...)`），不要假设响应里的状态一定是执行后的真实状态。

### 配置与持久化

`core/config.py` 的模块级常量是**全局可变状态**，`_load()` 会用 `settings.json` 覆盖它们。持久化的字段必须在两处同步登记：`_save()` 的字典和 `_load()` 的映射表。

已持久化：`font_family`、`font_size`、`memory_context_size`、`min_auto_reply`、`max_auto_reply`、`auto_talk_duration`、`preset_min_interval`、`preset_max_interval`、`scale`。

其余数据文件各有独立 manager，都在数据目录下：

| 文件 | 负责模块 | 说明 |
|------|---------|------|
| `.env` | `ai_providers` | API 配置（Key 是 base64，**不是加密**，只是避免肩窥） |
| `chat_history.json` | `chat_history` | 上限 2000 条，`add()` 里就裁剪 |
| `pet_state.json` | `pet_state` | 饱腹/活力 + `saved_at`，用于离线衰减 |
| `companion.json` | `companion` | 陪伴统计，跨会话累加 |
| `facts.json` | `memory_facts` | 长期记忆（含总开关） |
| `reminders.json` | `reminder` | 安排表 |
| `skills_config.json` / `games.json` | `skill_manager` / `GameManager` | 开关 |

**写盘一律用「临时文件 + `os.replace`」**（见 `companion._atomic_write`）。
桌宠被强杀是常态，直接 `open(..., "w")` 会留下半截 JSON。

### 计数放在 core 层，不要放 UI 层

`feed_count`、`chat_rounds`、`games_played` 这类统计**不能写在 `ui/pet_window.py`**：
同一个动作有两条来源（桌宠右键菜单 与 管理面板 REST），放 UI 层必然漏计或重复计。
现在的归属：

| 计数 | 归属 | 原因 |
|------|------|------|
| `feed_count` | `PetStatus.feed()` | 菜单与 `/api/pet/feed` 都调它 |
| `chat_rounds` | `ChatHistoryManager.add(role="assistant")` | 一次回复算一轮，两条路径都经过 |
| `games_played` | `GameManager.start()` | 菜单与 `/api/games/{k}/start` 都调它 |
| `max_fly_meters` | `FlyHighGame._landing_reply()` | 只有这里知道最终高度 |

对应的调用方**不要再自己 bump**（`ChatHistoryManager` / `PetStatus` / `GameManager`
都接受一个可选的 `companion` 参数，由 `pet_window` 注入）。

### 隐私边界

涉及用户数据的决策集中在这两处，改动时要格外小心：

- **`core/screenshot_policy.py`** — 决定「什么时候会截屏并上传给模型厂商」。
  这是纯决策层（不碰 Tk、不发请求），因此可以完整单测。
  现有约束：系统空闲 ≥5 分钟或锁屏时**绝不截屏**；触发后有 90 秒节流。
  改这里等于改隐私行为，请同步更新 README 的「看屏幕的方式」一节。
- **`core/memory_facts.py`** — 长期记忆。必须始终保证：存在本地、
  面板可逐条查看/删除/清空、有总开关且关闭后**既不提炼也不注入**。

日志里出现的管理面板 token 由 `utils/logger.py` 的 `_ScrubFilter` 打码——
拿到 token 就能通过本地 REST 控制桌宠进程并截屏，而日志可能被备份工具读走。

### 资源路径

| 函数 | 用途 |
|------|------|
| `get_app_dir()` | EXE 所在目录 / 源码模式下的 CWD |
| `resolve_data_dir()` | 数据目录选址（**有缓存**，测试里用 `reset_cache()` 清） |
| `get_data_path(name)` | 数据目录下的可写文件，会自动建目录 |
| `get_log_dir()` | 数据目录下的 `logs/` |
| `get_resource_path(rel)` | 随包内置的只读资源，兼容 PyInstaller 的 `_MEIPASS` |

数据目录选址顺序：`OGURI_DATA_DIR` 环境变量 → 便携模式（EXE/仓库同级 `data/`，
已存在或可写）→ `%APPDATA%\OguriPet`。测试里一律用 `OGURI_DATA_DIR` 指向 `tmp_path`。

**新增随包资源时必须同时更新 `main.spec` 的 `datas`**，否则打包后读不到（`web/dist` 就是这么加进去的）。
反过来，**新增数据文件不要放进 `resources/` 或仓库根**，要走 `get_data_path()`。

---

## 4. 前端开发

### `npm run dev` 目前不可用

`vite.config.ts` 没有配 `server.proxy`，而 `src/api/client.ts` 用的是相对路径 `fetch("/api/...")`。dev server 跑在 5173，所有 API 请求都会打到 Vite 自己身上。

另外后端**每次启动随机端口 + 随机 token**，所以固定 proxy 目标也无法直接工作。

所以现在的开发流程是：**改完 `web/src/` 跑 `npm run build`，然后用桌宠托管的 `dist` 验证**。

### 视图生命周期约定

`router.ts` 在每次渲染前都会先调用上一个视图的 `unmount()`（**即使还是同一个视图**），所以：

- `mount()` 里不要假设这是第一次挂载，模块级状态要能安全重建
- `unmount()` 必须释放自己拿到的所有资源（EventSource、store 订阅、定时器）
- `mount()` 可以是 `async`，router 会 `await` 并捕获 rejection；但 `await` 之后 DOM 可能已被替换，查元素失败时请静默返回而不是抛异常

### 后端 API 契约

27 个端点（25 REST + 2 SSE），全部定义在 `web/src/api/client.ts`。后端实现在 `core/web_server.py`。

- 加端点时两边都要改，并在 `tools/test_web_api.py` / `test_phase4_api.py` 里补一条验证
- `src/api/types.ts` 的类型是**手写声明**，`request<T>()` 用 `as T` 断言，**没有运行时校验**——后端改字段名不会报错，只会在页面上渲染出 `undefined`
- 所有插入 DOM 的动态字符串都要过 `escapeHtml()`（`src/utils.ts`）
- 错误统一用 `client.ts` 的 `describeError(e)` 转成文案，它会区分「token 失效（401）」和「桌宠没开」，不要自己写 `catch { "未连接桌宠" }`
- 后端下发的**约束值**（如记忆轮数区间）请直接用返回的字段，不要在视图里硬编码

---

## 5. 换行与 git（重要）

仓库强制 LF：

```
# .gitattributes
* text=auto eol=lf
```

**背景**：`core/skill_system/manager.py` 曾以**二进制 blob** 形式提交（`git ls-files --eol` 显示 `i/-text`），文件里含字面 CR 字节。配合 `core.autocrlf=true`，checkout 后每行变成 `\r\r\n`。ruff 的 import 排序（`I001`）在重写 import 块时不认这种行尾，会把**整个 import 块合并成一行**，产出语法损坏的代码——而且 `ruff check` 事后还报 "All checks passed"。

加 `.gitattributes` 后，该文件会以 LF 正常存储。改完文件后可以用这个命令确认：

```powershell
git ls-files --eol core/skill_system/manager.py
# 期望：i/lf  w/lf  attr/text=auto eol=lf
```

如果看到 `i/-text`，说明又被当成二进制了，需要手工规范化为 LF 再提交。

一般做法：`ruff --fix` 之后**务必跑一遍 `pytest` 和 `python -c "import <改动的模块>"`**，不要只看 ruff 的退出码。

---

## 6. 测试现状

270 个测试，覆盖：

| 文件 | 测试数 | 覆盖 |
|------|-------|------|
| `test_web_server.py` | 61 | 管理面板后端全量：鉴权、端点、静态托管、日志读取、并发、Tk 线程转发 |
| `test_memory_facts.py` | 37 | 长期记忆：事实库增删改查/上限/去重/开关/注入/模型输出解析/提取器 |
| `test_games.py` | 29 | `game/rules.py` 纯规则 + 钓鱼难度回归 |
| `test_screenshot_policy.py` | 24 | **隐私边界**：何时不该截屏、节流、活动识别 |
| `test_game_lifecycle.py` | 19 | `BaseGame` 生命周期契约 + 一飞冲天抛高物理与帧率无关性 |
| `test_wander.py` | 15 | 待机漫步：位移上限、越界、游戏/交互抑制 |
| `test_autostart_and_screen.py` | 19 | 数据目录选址、开机自启快捷方式、分辨率变化防护 |
| `test_pet_state.py` | 7 | 状态机数值 + 低值提醒去抖 |
| `test_reminder.py` | 7 | 安排表增删改查与触发判定 |
| `test_skill_loader.py` | 6 | frontmatter / 参数表解析 / 脚本加载 |
| `test_companion.py` | 25 | 陪伴统计、离线衰减、计数归属 |
| `test_chat_history.py` | 8 | 聊天记忆读写与运行期裁剪 |
| `test_skill_manager.py` | 3 | 技能注册、tools 构建、重名跳过、异常兜底 |
| `test_game.py` | 4 | 一飞冲天落地台词分档 |

整套约 8 秒跑完。**仍然没有测试覆盖**：`core/ai_client.py` 与 `ai_providers.py`
（依赖网络）、`ui/` 各窗口模块（需要真实 Tk）。

### 写测试时的三个注意点

**1. 数据文件必须隔离。** 多个模块会往数据目录写。测试里务必用 `monkeypatch`
把 `core.config._SETTINGS_FILE` 指到 `tmp_path`，或设 `OGURI_DATA_DIR` 环境变量
（见 `test_autostart_and_screen.py` 的 `_reset_paths_cache` fixture）。
否则会覆写开发者本机的真实配置——曾经真的把 `pet_state.json` 写过一次。

**2. HTTP 断言要等状态落定。** 进程控制类端点（重启/退出/启停游戏）是
「先回响应、再 `root.after` 转发到 Tk 线程」，客户端拿到 200 时转发动作可能尚未执行。
用 `wait_for()` 轮询而不是立刻断言，否则会随机失败。

**3. PowerShell 传中文会坏。** 用 `Invoke-RestMethod -Body '{"text":"中文"}'`
发的请求体编码不是 UTF-8，中文会变成 `?`。验证中文内容时用
`curl.exe --data-binary "@file"` 配一个以 UTF-8 无 BOM 写出的 JSON 文件。

`conftest.py` 只做了一件事：把仓库根加进 `sys.path`。

---

## 7. CI

`.github/workflows/ci.yml` 三个 job：

| job | 内容 |
|-----|------|
| `lint` | `ruff check .`（Ubuntu，3.10） |
| `test` | 装 `python3-tk` 后 `pytest`（Ubuntu，3.10） |
| `build` | `pyinstaller main.spec` + 上传 `dist/main.exe`（Windows） |

注意 `build` job **不会先构建前端**，所以 CI 产出的 `main.exe` 里不含可用的管理面板。要么在 job 里加 `npm ci && npm run build`，要么把 `web/dist` 提交进仓库（当前被 `web/.gitignore` 忽略）。

---

## 8. 已知技术债

按影响排序，都是有据可查的：

1. **前端剩余问题**：`Settings.ts` 在 `await` 之后用 `getElementById` 查元素，若期间路由切走会走「DOM 已不属于本视图」分支直接返回（已不再崩溃，但用户看不到任何提示）；聊天记录无分页（后端截断为末 1000 条）；必填技能参数不校验；无障碍只做到焦点环与 `prefers-reduced-motion`。
2. **`/api/games/*` 分支缺少 `return`**：未匹配时穿透到 `web_server.py` 末尾的 404（功能上凑巧正确，但是隐患）。
3. **`_read_log_tail` 在无换行的超长行场景会读满整个文件**（`buf.count(b"\n")` 永远不达标）。
4. **只识别主显示器**：`winfo_screenwidth` 只反映主屏，副屏区域无法进入。分辨率变化有 15 秒轮询兜底，但不会主动迁到副屏。
5. **长期记忆的提炼质量取决于模型**：`parse_facts` 已过滤标题/元叙述/超长句，但仍可能出现模型编造的「事实」。目前靠面板可查看可删除来兜底，没有自动校验。
6. **没有测试覆盖**：`core/ai_client.py`、`ai_providers.py`（依赖网络）与 `ui/` 各窗口模块（需要真实 Tk）。

已修复（曾记录在此，留档避免重复排查）：

- ~~`core/web_server.py` 无任何测试~~ → 现有 61 个测试
- ~~`GameManager`/`BaseGame` 从未被测试构造过~~ → `test_game_lifecycle.py` 用假 Tk 对象覆盖
- ~~`router.ts` 同视图重渲染不调用 `unmount`，泄漏 EventSource 与 store 订阅~~ → 已改为始终先卸载
- ~~仪表盘统计量挂载后不刷新~~ → 已接上 store 订阅
- ~~`Settings` 首次加载失败后六个卡片零监听器（表单变砖）~~ → 已改为渲染错误条 + 重试按钮
- ~~终端「暂停」直接丢弃日志（后端游标自行推进，丢就没了）~~ → 已改为暂停期间缓冲，继续时补上
- ~~记忆轮数前端 5–250 与后端 10–500 不一致~~ → 区间与默认值改由后端下发
- ~~字体/宠物大小「已保存」但不落盘~~ → 均已写入 `settings.json`，并在启动时恢复
- ~~401 被显示成「未连接桌宠」~~ → 新增 `ApiError` + `describeError()` 区分 token 失效
- ~~`?theme=dark` 无法覆盖已存的浅色偏好；浅色用户首屏闪黑~~ → 内联预置脚本 + 只在用户点击时写 `localStorage`
- ~~`fly_high` 未继承 `BaseGame`~~ → 已继承，获得统一清理、Esc 退出与位置还原
- ~~计分板在所有 `BaseGame` 游戏里都拖不动~~ → `<B1-Motion>` 误绑 `_counter_press`，已修正
- ~~`_after_ids` 在长局游戏中无限增长~~ → 回调触发后自我摘除
- ~~`quit()`/`restart()` 不结束游戏，全屏置顶覆盖窗留在屏幕上~~ → 已加 `_stop_game_if_active()`
- ~~管理面板启停游戏跑在 HTTP 线程上（跨线程操作 Tk）~~ → 已改为 `root.after` 转发
- ~~日志终端首拉失败后以 `offset=0` 起流，后端重放整个日志文件~~ → 已改为从末尾开始
- ~~`BaseServer.shutdown()` 每次停服白等 0.5 秒~~ → 轮询间隔降到 0.05 秒，整套测试从 33 秒降到 6 秒
- ~~`ui/dialogs.py` 585 行死代码~~ → 已删除（全部功能由管理面板覆盖）
- ~~`fishing` 开局必中 `perfect`~~ → 浮标加上每回合随机的初相位，且开局位置偏置到区间外
- ~~`fly_high` 单位漂移（100 vs 10 px/m）导致后两档台词够不到~~ → 统一为 10 px/m
- ~~`fly_high` 把「每鼠标事件位移」当「每帧位移」，手感随鼠标轮询率变化~~ → 用事件时间戳归一化
- ~~`Games`/`Skills` 页无轮询，桌宠侧状态变化看不到~~ → 已加轮询（指纹比对，状态没变不重绘）
- ~~数据目录必须在 EXE 同级，只读安装位置写不了~~ → 已加 `%APPDATA%` 回退
- ~~`chat_history.max_length` 运行期不生效，长期运行无界增长~~ → `add()` 里也裁剪
- ~~管理面板 token 明文写进日志~~ → `logger` 加了打码 filter
- ~~状态每次启动重置，没有跨会话累积~~ → `pet_state.json` + `companion.json`
- ~~没有首次运行引导~~ → 首次启动给一次操作提示
- ~~AI 搭话无条件定时截屏~~ → 改为 `screenshot_policy` 按情境触发，离开/锁屏时绝不截屏
- ~~截屏与搭话在游戏期间照常触发~~ → 已让位
- ~~纯黑像素会被透明键挖空（限制美术）~~ → 键色改为从素材里自动挑一个未使用的深色
- ~~长时间盯着同一窗口不会提醒~~ → 已作为截屏触发条件之一
- ~~桌宠像贴纸一样钉在原地~~ → 待机漫步
- ~~插拔显示器/改分辨率后桌宠可能落在屏幕外消失~~ → 15 秒轮询 + 拉回可见区

---

## 9. 提交约定

历史提交用中文 Conventional Commits 风格，带作用域：

```
fix(schedule): 修复 number='all' 崩溃，delete/done 支持全部删除/完成
feat(web): 设置页独立「聊天记忆」卡片
style(web): 双主题切换（深色工业/暖色玻璃）
build(pack): main.spec 打包 web/dist
```

`git log --oneline` 可看全部历史。CI 会跑 lint + test，push 前本地跑一遍能省一轮。
