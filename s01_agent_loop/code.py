"""s01 练习：在这里亲手实现最小 Agent Loop。"""
import os 
from pathlib import Path
import subprocess

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

client =Anthropic(base_url=os.environ["BASE_URL"])

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
    {
        "name":"bash",
        "description":"运行一条 bash 命令并返回结果",
        "input_schema":{
            "type":"object",
            "properties":{
                "command":{"type":"string"}
            },
            "required":["command"],
        },
}
]

# -- Tool execution --
def run_bash(command:str)->str:
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
            return
        
        results = []

        for block in tool_calls:
            print(f"\033[33m$ {block.input['command']}\033[0m")
            output = run_bash(block.input['command'])
            print(output[:200])
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
            query = input("s01 >>")
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