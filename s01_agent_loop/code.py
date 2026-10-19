"""cd /mnt/d/software/study/code/learn-claude-code-handmade
    source /home/administrator/.venvs/learn-claude-code-handmade/bin/activate
    python s01_agent_loop/code.py
"""
"""s01 练习：在这里亲手实现最小 Agent Loop。"""
"""s02 加入其他工具 """
"""s03 执行前做权限判断"""
"""s04 Hooks — 挂在循环上，不写进循环里"""
import os 
from pathlib import Path
import subprocess

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

client =Anthropic(base_url=os.environ["BASE_URL"])
WORKDIR = Path.cwd()

ENVIRONMENT_PROMPT = (
    "Windows: the bash tool runs through cmd.exe; use cmd.exe syntax, not Unix "
    "Bash or PowerShell syntax"
    if os.name == "nt"
    else "Unix-like: the bash tool runs the system shell"
)

SYSTEM = (
    f"You are a coding agent at {os.getcwd()}. Environment: {ENVIRONMENT_PROMPT}. "
    "Use bash to solve tasks. Act, don't explain."
)

TOOLS=[
    {"name":"bash","description":"运行一条 bash 命令并返回结果",
    "input_schema":{"type":"object","properties":{"command":{"type":"string"}},"required":["command"],}},
    
    {"name":"read_file","description":"查看文件内容",
    "input_schema":{"type":"object","properties":{"path":{"type":"string"},"limit":{"type":"integer"}},"required":["path"]}},
    
    {"name":"write_file","description":"写入文件",
    "input_schema":{"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},"required":["path","content"]}},

    {"name":"edit_file","description":"编辑文件",
    "input_schema":{"type":"object","properties":{"path":{"type":"string"},"old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}},

    {"name": "glob", "description": "查找匹配 glob 模式的文件；** 代表递归匹配。",
     "input_schema": {"type": "object", "properties": {"pattern": {"type": "string"}}, "required": ["pattern"]}},
]

HOOKS={
    "UserPromptSubmit": [],
    "PreToolUse": [],
    "PostToolUse": [],
    "Stop": [],
}

# -- Tool execution --
def save_path(p:str)->Path:
    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")
    return path

def run_read(path: str, limit: int | None = None) -> str:
    try:
        lines = safe_path(path).read_text(encoding="utf-8").splitlines()
        if limit and limit <len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit} more lines)"]
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"

def run_write(path: str, content: str) -> str:
    try:
        file_path = save_path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error: {e}"

def run_edit(path: str, old_text: str, new_text: str) -> str:
    try:
        file_path = save_path(path)
        text = file_path.read_text(encoding="utf-8")
        if old_text not in text:
            return f"Error: text not found in {path}"
        file_path.write_text(text.replace(old_text, new_text, 1), encoding="utf-8")
        return f"Edited {path}"
    except Exception as e:
        return f"Error: {e}"

def run_glob(pattern: str) -> str:
    import glob as g
    try:
        matchs = sorted({
            match for match in g.glob(
                pattern,root_dir=WORKDIR , recursive=True
            )
            if (WORKDIR/match).resolve().is_relative_to(WORKDIR)
        })
        shown = matchs[:200]
        if len(matches) > 200:
            shown.append("... (more matches omitted; narrow the pattern)")
        return "\n".join(shown) if shown else "(no matches)"
    except Exception as e:
        return f"Error: {e}"


def run_bash(command: str) -> str:
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    if any(d in command for d in  dangerous):
        return "Error: Dangerous command blocked"
    try:
        r = subprocess.run(command,shell=True,cwd=os.getcwd(),
                   capture_output=True, text=True, errors="replace", timeout=120)

        out = (r.stdout + r.stderr).strip()

        return out[:50000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"
    except (FileNotFoundError, OSError) as e:
        return f"Error: {e}"

TOOL_HANDLERS = {
    "bash": run_bash, "read_file": run_read, "write_file": run_write,
    "edit_file": run_edit, "glob": run_glob,
}

# -- New in s03: three-gate permission pipeline --
# Gate 1: Hard deny list - always forbidden

DENY_LIST = ["rm -rf /", "sudo", "shutdown", "reboot", "mkfs", "dd if=", "> /dev/sda"]


# Gate 2: Rule matching - context-dependent checks
import re
DESTRUCTIVE_COMMAND_WORD = re.compile(
    r"(?i)(?:^|[;&|()\n])\s*(?:rm|del)(?=\s|$|[;&|()])"
)
DESTRUCTIVE = ["rm ", "> /etc/", "chmod 777"]

def contains_destructive_command(command: str) -> bool:
    return bool(DESTRUCTIVE_COMMAND_WORD.search(command))




# -- Hooks execution --

def permission_hook(block) :
    # 闸门 1: 硬拒绝
    if block.name == "bash":
        command = block.input.get("command","")
        for pattern in DENY_LIST:
            if pattern in command:
                print(f"\n\033[31m[blocked] '{pattern}'\033[0m")
                return  "Permission denied by deny list"
        if contains_destructive_command(command) or any(
            kw in command for kw in DESTRUCTIVE
        ):
            print(f"\n\033[33m[permission] Potentially destructive command\033[0m")
            print(f"   Tool: {block.name}({block.input})")
            choice = input("   Allow? [y/N] ").strip().lower()
            if choice not in ("y", "yes"):
                return "Permission denied by user"        

    # 闸门 2 + 3: 规则匹配 → 用户审批
    if block.name in ("read_file","write_file","edit_file"):
        path = block.input.get("path","")
        if not (WORKDIR/ path).resolve().is_relative_to(WORKDIR):
            print(f"\n\033[33m[permission] Access outside workspace\033[0m")
            print(f"   Tool: {block.name}({block.input})")
            choice = input("   Allow? [y/N] ").strip().lower()
            if choice not in ("y", "yes"):
                return "Permission denied by user"
    return None


def register_hook(event: str, callback):
    HOOKS[event].append(callback)

def trigger_hooks(event: str, *args):
    for callback in HOOKS[event]:
        result = callback(*args)
        if result is not None:
            return result
    return None

def context_inject_hook(query: str) -> str|None:
    """Inject current working directory info into every prompt."""
    print(f"\033[90m[HOOK] UserPromptSubmit: working in {WORKDIR}\033[0m")

register_hook("UserPromptSubmit", context_inject_hook)

# PreToolUse: 日志
def log_hook(block):
    """PreToolUse: log every tool call."""
    args_preview = str(list(block.input.values())[:2])[:60]
    print(f"\033[90m[HOOK] {block.name}({args_preview})\033[0m")

# PostToolUse: 大文件提醒
def large_output_hook(block, output):
    if len(str(output)) > 100000:
        print(f"[HOOK] ⚠ Large output from {block.name}")

register_hook("PreToolUse", permission_hook)
register_hook("PreToolUse", log_hook)
register_hook("PostToolUse", large_output_hook)

def summary_hook(messages: list) -> str | None:
    """Print a summary when the loop is about to stop."""
    tool_count = sum(1 for m in messages
                     for b in (m.get("content") if isinstance(m.get("content"), list) else [])
                     if isinstance(b, dict) and b.get("type") == "tool_result")
    print(f"\033[90m[HOOK] Stop: session used {tool_count} tool calls\033[0m")
    return None   # return None = allow stop, return string = force continuation

register_hook("Stop", summary_hook)


def agent_loop(messages: list):
    while True:
        response = client.messages.create(
            model = os.environ["MODEL_ID"],
            max_tokens = 8000,
            system=SYSTEM,
            messages=messages,
            tools=TOOLS
        )

        messages.append({"role": "assistant", "content": response.content})
        print(response.content)

        tool_calls=[
            block for block in response.content if block.type == "tool_use"
        ]
        if not tool_calls:
            force = trigger_hooks("Stop", messages)   # ← 退出之前
            if force :
                messages.append({"role":"user","content":force})
            return
        
        results = []

        for block in tool_calls:
            print(f"\033[33m$ {block.name}\033[0m")
            blocked = trigger_hooks("PreToolUse", block)
            if blocked :
                results.append({"type":"tool_result","tool_use_id": block.id,"content": str(blocked)})
                continue
            
            handler = TOOL_HANDLERS.get(block.name)
            output = handler(**block.input) if handler else f"Unknown: {block.name}"
            trigger_hooks("PostToolUse", block, output)
            results.append({
                "type":"tool_result",
                "tool_use_id": block.id,
                "content": output,
            })
        messages.append({"role":"user","content":results})

if __name__ == "__main__":
    print("s01: Agent Loop")
    print("Enter a question, press Enter to send. Type q to quit.\n")

    history=[]

    while True:
        try:
            query = input("s04 >>")
        except(EOFError, KeyboardInterrupt):
            break
        
        history.append({"role":"user","content":query})
        if query.strip().lower() in ("q", "exit", ""):
            break

        agent_loop(history)
        response_content = history[-1]["content"]
        if isinstance(response_content, list):
            for block in response_content:
                if getattr(block, "type", None) == "text":
                    print(block.text)
        print()