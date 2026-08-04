# 小栗帽桌宠

> 芦毛灰蓝 · 天然呆 · 大胃王 · 温柔陪伴

一只住在你电脑桌面上的赛马娘小栗帽。她会陪你聊天、看看屏幕、吃吃饭团，偶尔还会陪你玩抛高小游戏。

---

## 目录

- [两种使用方式](#两种使用方式)
- [EXE 直接运行](#exe-直接运行)
- [从源码运行](#从源码运行)
- [图片素材说明](#图片素材说明)
- [配置大模型（AI 对话）](#配置大模型ai-对话)
- [操作指南](#操作指南)
- [小游戏](#小游戏)
- [技能系统](#技能系统)
- [状态系统](#状态系统)
- [项目结构](#项目结构)
- [打包方法](#打包方法)

---

## 两种使用方式

| 方式 | 适合 | 前提 |
|------|------|------|
| 直接运行 EXE | 普通用户 | 无需安装任何环境 |
| 从源码运行 | 开发者/想修改代码 | 需要 Python 3.8+ |

---

## EXE 直接运行

1. 获取 `小栗帽.exe`
2. 准备好 `resources/images/` 文件夹（见下方图片素材说明），放在 EXE 同目录
3. 双击运行

> ⚠️ **重要提示：EXE 运行时会自动生成文件**
>
> 第一次运行后，EXE 所在目录会自动创建：
> - `data/.env` — 你的 API Key 配置（输入 Key 后产生）
> - `data/chat_history.json` — 聊天记录
> - `data/settings.json` — 系统设置
> - `data/reminders.json` — 安排表
> - `data/games.json` — 小游戏开关
>
> 这些是你自己的数据文件，**请勿随意删除**，否则会丢失聊天记录和 API 配置。分享 EXE 给他人时不要把这些文件一起打包。

同一路径下重复双击 EXE 会弹出提醒，不会启动第二个实例。

---

## 从源码运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动
python main.py
```

---

## 图片素材说明

`resources/images/` 目录需要 4 张 PNG 图片（透明背景，推荐 180×180）：

| 文件名 | 用途 |
|--------|------|
| `stay.png` | 待机状态 |
| `click.png` | 被点击/拖拽时 |
| `touch.png` | 鼠标悬停 |
| `talk.png` | 说话时 |

没有这些图片也能运行，但桌宠会变成透明方块。

---

## 配置大模型（AI 对话）

小栗帽的聊天功能需要接入一个大模型才能工作。不配置也没关系，她会用预置文案和你互动。

**操作步骤：**

1. 在桌宠身上 **右键** → **设置** → **API 设置**
2. 选择厂商（DeepSeek / 火山引擎 / 通义千问 / ChatGPT）
3. 模型会自动列出该厂商可用的选项
4. 填入你的 API Key
5. 点击 **「测试连接」** 验证是否可用
6. 点击 **「保存」** 完成配置

**Key 获取地址：**

| 厂商 | 获取地址 |
|------|---------|
| 火山引擎(豆包) | [console.volcengine.com/ark](https://console.volcengine.com/ark) |
| DeepSeek | [platform.deepseek.com](https://platform.deepseek.com) |
| 通义千问 | [dashscope.console.aliyun.com](https://dashscope.console.aliyun.com) |
| ChatGPT | [platform.openai.com](https://platform.openai.com) |

配置保存后即时生效，无需重启。

---

## 操作指南

### 鼠标交互

| 操作 | 效果 |
|------|------|
| 左键拖拽 | 移动小栗帽（松手有惯性滑行） |
| 左键单击 | 摇晃 + 随机对话 |
| 左键快速双击 | 弹跳 + 连击对话 |
| 鼠标悬停 | 切换触摸表情 |
| 鼠标中键 | 截图 + AI 描述屏幕内容 |
| 右键 | 弹出功能菜单 |

### 右键菜单（分组结构）

```
💬 对话
🍙 喂饭团
─────
📋 记录                    ← 子菜单
  ├ 📊 查看状态
  ├ 📋 聊天记录
  └ 🗑 清空记录
⚙ 设置                    ← 子菜单
  ├ 📏 调整大小
  ├ ⚡ 技能管理
  ├ 🔑 API 设置
  ├ 🔤 字体设置
  └ ⚙ 系统设置
🎮 小游戏                  ← 子菜单
  ├ 🎮 游戏管理
  ├────────
  └ 一飞冲天               ← 点击进入（禁用时隐藏）
─────
🔄 重启
🚪 退出
```

### 输入框说明

打开对话后，宠物上方出现输入条：
- 输入文字按 **回车** 发送
- 点 **📸** 按钮会同时截图发给 AI
- 不输入文字直接点 **📸** 会让 AI 描述当前屏幕

---

## 小游戏

进入方式：右键 → **小游戏** → **一飞冲天**

### 一飞冲天（抛高游戏）

- 进入游戏后小栗帽自动移动到屏幕底部，气泡提示「用力将我抛起来吧！」
- 用力向上甩动桌宠，它会沿脱手方向抛出（斜抛保留方向）
- 空中显示触摸表情，无视屏幕上下边框，受重力作用回落到屏幕底部
- 计数器固定在游戏开始位置，实时显示飞行高度（米），落地冻结在最高值
- 落地后根据最高高度给出不同的小栗帽台词

**落地分档台词：**

| 高度 | 台词 |
|------|------|
| < 50 米 | 「嗯……是不是最近吃太多变重了……」 |
| 50–200 米 | 「比想象中高了一点！」 |
| 200–350 米 | 「好高！就像冲刺时飞起来的感觉」 |
| 350–500 米 | 「哇啊啊啊啊啊！」 |
| > 500 米 | 「刚才……是不是飞到云上面去了？」 |

### 游戏管理

- 右键 → **小游戏** → **游戏管理**，可开启/关闭各游戏
- 关闭后该游戏入口从菜单隐藏
- 游戏进行中菜单出现「⏹ 退出游戏」，退出后恢复普通桌宠状态

---

## 技能系统

技能存放在 `skills/` 目录，每个技能一个目录：

```
skills/天气/
├── SKILL.md              # 元数据 + 参数定义
└── scripts/
    └── helper.py          # 可执行代码
```

内置技能：

| 技能 | 说明 |
|------|------|
| `weather` | 查询指定城市天气 |
| `schedule` | 管理安排表（列表/时间线/今日/搜索/添加/删除/完成） |

技能通过 AI Function Calling 自动调用：用户说「深圳天气」→ AI 调用天气技能 → 返回结果自然回复。安排表的单次提醒触发后自动删除，重复提醒（每天/每周）持续有效。

---

## 状态系统

小栗帽有两个隐藏数值，随时间自动变化：

| 数值 | 上限 | 自动变化 | 过低时 |
|------|------|---------|--------|
| 🍙 饱腹度 | 100 | 每分钟 -2 | 肚子咕咕叫，提示喂饭团 |
| ⚡ 活力值 | 100 | 每分钟 +1 | 犯困打盹动画 |

- **喂饭团**（右键菜单）：饱腹 +30，活力 +5
- **拖拽小栗帽**：每次消耗 1 点活力
- 鼠标点击不会消耗活力

查看状态条：右键 → **记录** → **查看状态**，双色进度条会跟随小栗帽移动，5 秒后自动隐藏。

---

## 项目结构

```
main.py                    入口（单实例锁 + --restart）
requirements.txt           依赖
requirements-dev.txt       开发依赖（pytest/ruff）
pyproject.toml             ruff/pytest 配置
tests/                     单元测试（pytest）
.github/workflows/ci.yml   CI：lint + 测试 + 打包
core/                      领域层
├── config.py              配置常量 + 持久化
├── chat_history.py        聊天记忆
├── pet_state.py           饱腹/活力状态机
├── prompts.py             截图 Prompt
├── reminder.py            安排表系统
├── ai_client.py           AI 客户端（Function Calling）
├── ai_providers.py        厂商预设
├── paths.py               资源/数据路径
└── skill_system/
    ├── loader.py          SKILL.md 解析 + 动态加载
    └── manager.py         技能注册/构建 tools/执行路由
game/                      小游戏系统
├── __init__.py            游戏管理器 + 注册表
└── fly_high/              一飞冲天
    └── game.py            抛高游戏逻辑
ui/                        表现层
├── pet_window.py          主窗口 + 生命周期 + 事件
├── pet_sprite.py          精灵图片加载与缓存
├── input_bar.py           聊天输入条
├── animations.py          动画系统
├── bubble.py              对话气泡
├── status_bar.py          状态进度条
└── dialogs.py             对话框
utils/
├── logger.py              统一日志（控制台 + data/logs 轮转）
└── tk_ext.py              Tkinter Canvas 圆角
resources/images/          图片素材（4张PNG）
skills/                    技能目录
```

---

## 打包方法

推荐使用仓库自带的 `main.spec`（已包含打包配置）：

```bash
pip install pyinstaller
pyinstaller main.spec
```

也可以手动指定参数（与 spec 等价）：

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --icon=icon.ico --add-data "resources/images;resources/images" --add-data "skills;skills" main.py
```

> 打包产物约 38MB，内含 Python 运行时 + 依赖 + 图片素材 + 技能目录。
> 运行日志写入 `data/logs/kurumi.log`（自动轮转，最多保留 3 份）。

---

## License

MIT
