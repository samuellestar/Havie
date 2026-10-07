"""Havie: a local computer assistant with reviewed command execution."""

import argparse
from pathlib import Path
import platform
import shlex
import subprocess


def plan(request, system=None):
    """Translate shortcuts or explicit commands into argument lists."""
    system = system or platform.system()
    text = request.strip().lower()
    if text in {"list files", "show files"}:
        return ["python", "-c", "from pathlib import Path; print('\\n'.join(sorted(p.name for p in Path('.').iterdir())))"]
    if text in {"where am i", "current folder"}:
        return ["python", "-c", "import os; print(os.getcwd())"]
    if text in {"system info", "computer info"}:
        return ["python", "-c", "import platform; print(platform.platform())"]
    if text in {"git status", "git diff", "git log"}:
        return {"git status": ["git", "status", "--short"], "git diff": ["git", "diff"], "git log": ["git", "log", "-5", "--oneline"]}[text]
    if text.startswith("run "):
        raw = request.strip()[4:]
        if not raw.strip():
            raise ValueError("Supply a command after 'run'.")
        if system == "Windows":
            return ["cmd.exe", "/d", "/s", "/c", raw]
        command = shlex.split(raw)
        if not command:
            raise ValueError("Supply a command after 'run'.")
        return command
    raise ValueError("Try: list files, current folder, system info, git status, git diff, git log, or run <command>.")


def execute(command, cwd):
    import sys
    if command[0] == "python":
        command = [sys.executable, *command[1:]]
    try:
        result = subprocess.run(command, cwd=cwd, timeout=60, check=False)
        print(f"Exit code: {result.returncode}")
        return result.returncode
    except subprocess.TimeoutExpired:
        print("Command timed out after 60 seconds. Child processes may still be running.")
        return 124
    except OSError as exc:
        print(f"Could not run command: {exc}")
        return 1


def main():
    from assistant import Assistant
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--data-dir", type=Path, help="Location for notes, tasks and reminders")
    parser.add_argument("--model", default="llama3.2", help="Installed Ollama model name")
    parser.add_argument("--gui", action="store_true", help="Launch the desktop interface")
    parser.add_argument("--phone", action="store_true", help="Start the paired mobile browser interface")
    parser.add_argument("--host", default="127.0.0.1", help="Phone server bind address; use 0.0.0.0 for a private LAN")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--allow-phone-pc", action="store_true", help="Allow paired phones to request reviewed PC actions")
    parser.add_argument("--cert", help="TLS certificate for optional HTTPS")
    parser.add_argument("--key", help="TLS private key for optional HTTPS")
    args = parser.parse_args()
    if args.gui and args.phone:
        parser.error("Choose --gui or --phone; run separate processes to use both.")
    try:
        assistant = Assistant(args.workspace, args.data_dir, args.model)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    if args.phone:
        from phone import launch
        launch(assistant, args.host, args.port, args.allow_phone_pc, args.cert, args.key)
        return
    if args.gui:
        from desktop import launch
        launch(assistant)
        return
    print(f"Havie — local computer assistant\nWorkspace: {assistant.workspace}")
    print("Type help for supported tasks; exit to quit. Actions require confirmation.")
    import threading
    stopped = threading.Event()
    def reminders():
        while not stopped.wait(1):
            try:
                for reminder in assistant.due_reminders():
                    print("\n" + reminder, flush=True)
            except Exception as exc:
                print(f"Reminder check failed: {exc}", flush=True)
                return
    threading.Thread(target=reminders, daemon=True).start()
    try:
        while True:
            try:
                request = input("You > ").strip()
                if request.lower() in {"exit", "quit"}:
                    break
                if not request:
                    continue
                action = assistant.prepare(request)
                if action.confirm:
                    print(action.preview)
                    print("Actions run with your account permissions and can change files or access the network.")
                    if input("Execute? Type yes: ").strip().lower() != "yes":
                        print("Cancelled.")
                        continue
                print(action.run())
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye.")
                break
            except Exception as exc:
                print(f"Action failed: {exc}")
    finally:
        stopped.set()


if __name__ == "__main__":
    main()
