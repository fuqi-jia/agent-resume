# agent-resume

带有持久化 prompt queue、断点续跑、定时调度（once + recurring）、配置管理的终端 coding agent 调度器。  
A stateful CLI scheduler for coding agents with persistent prompt queues and resume support.

## Features / 功能

- once 调度（`at`）
- recurring 调度（`crontab`，不会覆盖用户已有 crontab，带 `# agent-resume:<job_id>` 标记）
- prompt queue 按顺序逐条执行（每条 prompt 独立 agent 调用）
- queue 持久化到 `~/.agent-resume/jobs.json`
- 断点续跑（默认 `queue_mode=resume`）
- usage limit 检测后保留剩余队列，下次继续
- `schedule from-config` + 全局 config

## Install / 安装

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Quick Start / 快速开始

### 1) 初始化配置

```bash
agent-resume init-config
```

### 2) 一次性任务（once）

```bash
agent-resume schedule once \
  --dir /path/to/project \
  --session SESSION_ID \
  --time "now + 4 hours" \
  --prompt "Continue implementation"
```

### 3) 重复任务（recurring）

```bash
agent-resume schedule recurring \
  --dir /path/to/project \
  --session SESSION_ID \
  --cron "0 */4 * * *" \
  --prompt-file examples/prompts.txt
```

### 4) 使用 job config

```bash
agent-resume schedule from-config --file examples/job.yaml
```

## Prompt File / Prompt 文件

### Text

```text
=== PROMPT ===
Prompt A

=== PROMPT ===
Prompt B
```

### JSON

```json
[
  { "name": "summary", "prompt": "..." },
  { "name": "continue", "prompt": "..." }
]
```

或：

```json
["prompt1", "prompt2"]
```

## Config / 配置

默认位置：

```text
~/.config/agent-resume/config.yaml
```

示例（见 `examples/config.yaml`）支持：

- 默认 agent 类型和二进制路径
- 存储目录
- queue 默认策略
- 不同 agent 的 command template / usage limit patterns

## Queue Resume / 队列恢复说明（重点）

- `prompt_queue`、`current_prompt_index`、`queue_status` 会持久化
- 默认 `--queue-mode resume`：从未完成 prompt 继续执行，不重复已完成 prompt
- `--queue-mode restart`：每次从队列开头重跑

## Usage Limit Handling / 用量限制处理（重点）

如果输出中匹配到以下模式（可配置）：

- `You're out of extra usage`
- `rate limit`
- `quota exceeded`

则 job 会：

- 标记 `queue_status=partially_completed`
- 保留剩余 prompts
- 等待下一次调度继续执行

## CLI Commands

- 创建任务：`schedule once|recurring|from-config`
- 查询：`list` `show JOB_ID` `queue JOB_ID`
- 控制：`cancel JOB_ID` `pause JOB_ID` `resume-job JOB_ID` `reset-queue JOB_ID`
- 执行：`run-now JOB_ID`
- 日志：`log JOB_ID` `log JOB_ID --prompt-index 2`
- 工具：`init-config` `cleanup` `doctor`

## Storage Layout

```text
~/.agent-resume/
  jobs.json
  logs/
  runners/
```

## Roadmap

- [ ] 实现 recurring 并发策略 `queue` / `restart`
- [ ] 增加更丰富的 job filters 和状态可视化
- [ ] 增加更多内置模板和 agent 适配
- [ ] 增加更完整的 e2e 测试
