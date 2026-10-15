# Learn Claude Code 手写练习

这里用于自己实现 [learn-claude-code](https://github.com/shareAI-lab/learn-claude-code) 的每一章。先动手写，再与原仓库对照。

## 开发环境

在 VS Code 中连接 `WSL: Ubuntu`，然后打开：

```text
/mnt/d/software/study/code/learn-claude-code-handmade
```

本项目的 Python 虚拟环境位于：

```text
/home/administrator/.venvs/learn-claude-code-handmade/bin/python
```

每次打开新的 WSL 终端，可以这样激活：

```bash
source /home/administrator/.venvs/learn-claude-code-handmade/bin/activate
```

以后需要重装依赖时，在本目录运行：

```bash
python -m pip install -r requirements.txt -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple
```

本地 `.env` 已创建。将你自己的 API Key 填在 `ANTHROPIC_API_KEY=` 后；该文件已被 Git 忽略。

## s01：Agent Loop

从 `s01_agent_loop/code.py` 开始自己实现。核心流程是：

```text
用户消息 -> 模型回答 -> 工具调用 -> 工具结果 -> 模型再次回答
```

当模型不再调用工具时，输出最终回答。命令执行实验只在 `sandbox/` 中进行。
