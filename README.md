# agent-resume

> A stateful scheduler for terminal coding agents with persistent prompt queues and resume-on-interrupt.

agent-resume lets you define a queue of prompts and run them one by one through your CLI coding agent (e.g. Claude, Aider, Codex CLI). Jobs can be scheduled once via `at` or on a recurring schedule via `crontab`. When a usage limit or interruption stops execution mid-queue, agent-resume records exactly where it left off and resumes from that prompt on the next run — no manual intervention needed. A global config file and per-job overrides control agent binary, queue behavior, failure policy, and usage-limit detection patterns.

---

## 目录 / Contents

- [为什么需要 agent-resume](#why--为什么)
- [快速安装 / Install](#install--安装)
- [快速上手 / Quick Start](#quick-start--快速上手)
- [Prompt 文件格式 / Prompt File Formats](#prompt-file-formats--prompt-文件格式)
- [Queue 恢复机制 / Queue Resume](#queue-resume--断点续跑重点)
- [Usage Limit 处理 / Usage Limit Handling](#usage-limit-handling--用量限制处理重点)
- [Config 配置系统 / Config System](#config-system--配置系统)
- [CLI 命令参考 / CLI Reference](#cli-reference--命令参考)
- [数据存储结构 / Storage Layout](#storage-layout--数据目录)
- [Known Limitations](#known-limitations)
- [Roadmap](#roadmap)

---

## Why / 为什么

Long-running coding-agent workflows often break in the middle: usage limits are hit, shells close, machines reboot, or recurring jobs rerun work that was already completed. agent-resume is designed to make these workflows stateful: it persists prompt queues, resumes from the last incomplete step, and provides basic job control and inspection commands.

---

## Install / 安装

**要求 Requirements：** Python 3.11+，`at`（once 调度），`crontab`（recurring 调度）

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

验证安装 / Verify:

```bash
agent-resume --help
agent-resume doctor
```

---

## Quick Start / 快速上手

### 最小可跑示例 / Minimal example

Copy and run this to try agent-resume immediately:

```bash
agent-resume init-config
agent-resume schedule once \
  --dir "$PWD" \
  --session demo-session \
  --time "now + 1 minute" \
  --prompt "Summarize current repository status."
agent-resume list
```

### 1. 初始化配置 / Init config

```bash
agent-resume init-config
# 写入 ~/.config/agent-resume/config.yaml
```

### 2. 一次性任务（once）

4 小时后运行一次，使用 `at` 调度：

```bash
agent-resume schedule once \
  --dir /path/to/project \
  --session SESSION_ID \
  --time "now + 4 hours" \
  --prompt "Summarize the current implementation status."
```

多个 prompt 会按顺序逐一调用 agent，每次独立执行：

```bash
agent-resume schedule once \
  --dir /path/to/project \
  --session SESSION_ID \
  --time "now + 1 hour" \
  --prompt-file examples/prompts.txt
```

### 3. 重复任务（recurring）

每 4 小时执行一次，使用 `crontab` 调度（不覆盖其他 crontab 条目）：

```bash
agent-resume schedule recurring \
  --dir /path/to/project \
  --session SESSION_ID \
  --cron "0 */4 * * *" \
  --prompt-file examples/prompts.txt \
  --queue-mode resume
```

### 4. 从 job 配置文件创建 / Schedule from job config

```bash
agent-resume schedule from-config --file examples/job.yaml
```

示例 `examples/job.yaml`：

```yaml
dir: /path/to/project
session_id: xxx
cron: "0 */4 * * *"
prompt_file: examples/prompts.txt
queue_mode: resume
```

### 5. 立即运行 / Run immediately

```bash
agent-resume run-now JOB_ID
```

---

## Prompt File Formats / Prompt 文件格式

### 文本格式（`.txt`）

用 `=== PROMPT ===` 分隔多个 prompt：

```text
=== PROMPT ===
Summarize current progress and list blockers.

=== PROMPT ===
Continue the implementation from the last checkpoint.
```

### JSON 格式（`.json`）

字符串数组或对象数组：

```json
[
  { "name": "summary", "prompt": "Summarize current progress and list blockers." },
  { "name": "continue", "prompt": "Continue the implementation from the last checkpoint." }
]
```

也支持纯字符串数组 / Also supports plain string arrays:

```json
["Summarize current progress.", "Continue the implementation."]
```

### 内置模板 / Built-in templates

```bash
--template continue    # "Please continue from the last checkpoint..."
--template summary     # "Please summarize current progress, blockers, and next actions."
```

### 目录 / Directory

```bash
--prompt-dir prompts/
# 按文件名排序，加载目录下所有 .txt / .json 文件
```

---

## Queue Resume / 断点续跑（重点）

这是 agent-resume 的核心设计：

**每个 prompt 作为独立 agent 调用顺序执行，执行状态持久化，任何中断后均可恢复。**

每次执行后，以下状态会写入 `~/.agent-resume/jobs.json`：

```json
{
  "prompt_queue": ["prompt A", "prompt B", "prompt C"],
  "current_prompt_index": 2,
  "queue_status": "partially_completed"
}
```

### 具体场景示例

Suppose a job has three prompts:

1. **prompt 1** — completes successfully.
2. **prompt 2** — the agent hits a usage limit mid-run; agent-resume marks it as `interrupted` and records `current_prompt_index = 1`.
3. **prompt 3** — not yet executed.

On the next scheduled run, agent-resume reads `current_prompt_index = 1` and restarts from **prompt 2**, skipping prompt 1. Once prompt 2 finishes, it continues with prompt 3. No manual intervention is needed.

- **`--queue-mode resume`**（默认）：从 `current_prompt_index` 继续，已完成 prompt 不重复执行。
- **`--queue-mode restart`**：每次从队列第一个 prompt 重新开始（适合 recurring 任务每次全量执行）。

```bash
# 查看当前队列状态（>> 标记当前位置）
agent-resume queue JOB_ID

# 重置队列（从头开始）
agent-resume reset-queue JOB_ID
```

---

## Usage Limit Handling / 用量限制处理（重点）

当 agent 输出中匹配到以下模式（大小写不敏感，可在 config 中自定义）：

- `You're out of extra usage`
- `rate limit`
- `quota exceeded`

agent-resume 会：

1. 将当前 prompt 标记为 `interrupted`
2. 将 `queue_status` 设为 `partially_completed`
3. `current_prompt_index` 保留在中断位置
4. 等待下一次调度（cron）时从中断位置继续

> If usage-limit patterns are detected in the agent output or the agent exits abnormally with a quota-related failure, agent-resume marks the current prompt as interrupted and resumes from it on the next run.

**无需手动干预**，recurring 任务会自动在下次调度时接着跑。

---

## Config System / 配置系统

### 全局配置路径

```text
~/.config/agent-resume/config.yaml
```

也可以用 `--config path/to/custom.yaml` 指定其他路径。

### 示例配置（`examples/config.yaml`）

```yaml
default_agent_type: claude
default_agent_bin: /home/user/.local/bin/claude

storage_dir: ~/.agent-resume
log_dir: ~/.agent-resume/logs
runner_dir: ~/.agent-resume/runners

defaults:
  queue_mode: resume           # resume | restart
  on_prompt_failure: stop      # stop | continue
  prompt_interval_seconds: 0
  concurrency_policy: skip     # skip（当前仅支持 skip）

claude:
  command_template: "{agent_bin} --resume {session_id} --print {prompt}"
  usage_limit_patterns:
    - "You're out of extra usage"
    - "rate limit"
    - "quota exceeded"
```

`command_template` 支持变量：`{agent_bin}`、`{session_id}`、`{prompt}`。

### 配置优先级 / Priority order

```text
CLI arguments > job config > global config > built-in defaults
```

---

## CLI Reference / 命令参考

### 创建任务 / Create jobs

| 命令 | 说明 |
|---|---|
| `schedule once --dir D --session S --time T [prompt options]` | 通过 `at` 一次性调度 |
| `schedule recurring --dir D --session S --cron C [prompt options]` | 通过 `crontab` 循环调度 |
| `schedule from-config --file job.yaml` | 从 YAML job 配置创建 |

**Prompt 选项（四者互斥，每次只能指定一种 prompt source）：**

```
--prompt TEXT          单条 prompt
--template NAME        内置模板（continue, summary）
--prompt-file FILE     .txt 或 .json 文件
--prompt-dir DIR       目录（加载所有文件）
```

> Specify exactly one of `--prompt`, `--template`, `--prompt-file`, or `--prompt-dir`. Combining multiple prompt sources is not supported.

**执行策略选项：**

```
--queue-mode resume|restart         队列模式（默认 resume）
--on-prompt-failure stop|continue   失败策略（默认 stop）
--prompt-interval N                 prompt 间等待秒数（默认 0）
--concurrency-policy skip           并发策略（目前仅 skip）
```

### 查询 / Query

| 命令 | 说明 |
|---|---|
| `list` | 列出所有 job |
| `show JOB_ID` | 查看 job 详细信息（JSON） |
| `queue JOB_ID` | 查看 prompt 队列及当前位置 |

**状态枚举 / Status values:**

| Object | States |
|---|---|
| job | `scheduled`, `paused`, `cancelled`, `completed`, `failed` |
| queue | `pending`, `running`, `partially_completed`, `completed`, `failed` |
| prompt | `pending`, `running`, `completed`, `failed`, `interrupted` |

### 控制 / Control

| 命令 | 说明 |
|---|---|
| `cancel JOB_ID` | 取消任务（recurring 同时移除 crontab 条目） |
| `pause JOB_ID` | 暂停任务（下次调度时跳过执行） |
| `resume-job JOB_ID` | 恢复已暂停任务 |
| `reset-queue JOB_ID` | 重置队列，从第一个 prompt 开始 |
| `run-now JOB_ID` | 立即在当前 shell 执行 |

### 日志 / Logs

| 命令 | 说明 |
|---|---|
| `log JOB_ID` | 查看整体运行日志 |
| `log JOB_ID --prompt-index N` | 查看第 N 个 prompt 的独立日志 |

### 工具 / Tools

| 命令 | 说明 |
|---|---|
| `init-config` | 写出默认配置文件 |
| `cleanup` | 清理孤立的 runner 脚本 |
| `doctor` | 检查依赖（at、crontab）和目录 |

---

## Storage Layout / 数据目录

```text
~/.agent-resume/
├── jobs.json          # 所有 job 状态（含 prompt queue）
├── logs/
│   ├── JOB_ID.log           # 整体运行日志
│   └── JOB_ID_prompt_1.log  # 每条 prompt 的独立日志
└── runners/
    └── JOB_ID.sh            # 调度入口脚本（调用 runner_exec）
```

`jobs.json` is the source of truth for queue progress and resume state.

---

## Known Limitations

- Primarily tested on **Linux and macOS**; Windows is not currently supported.
- `once` scheduling depends on the `at` command being available.
- `recurring` scheduling depends on `crontab` being available; Windows Task Scheduler is not yet supported.
- Usage-limit detection is based on output pattern matching and is not guaranteed to work with every agent binary or version.
- Concurrency policy is currently limited to `skip` (only one concurrent execution per job).

---

## Roadmap

**Near term**
- [ ] Concurrency policies: `queue` and `restart` modes fully implemented
- [ ] Richer job filtering, sorting, and status display

**Mid term**
- [ ] More agent backends: Cursor CLI, Aider, Codex CLI, and others
- [ ] Richer retry and backoff strategies for failed prompts
- [ ] Expanded integration test coverage

**Long term**
- [ ] TUI / Web dashboard for monitoring jobs and queues
- [ ] Notifications on job completion or failure (email, webhook)
