# Havie

A Windows-focused personal computer assistant with a desktop interface and a
terminal interface, plus a phone-friendly browser interface for iPhone and Android.
Personal tools include a daily agenda, appointments, notes, tasks, reminders and
saved preferences. Core features use only Python's standard library. Local AI
chat is optional and uses Ollama; no cloud API key is required.

## Start on Windows

1. Install Python 3.10+ from [python.org](https://www.python.org/downloads/windows/), including Tcl/Tk and the Python launcher.
2. Download this project and double-click **Start-Havie.bat**, or run:

   ```powershell
   py -3 havie.py --gui
   ```

Use `py -3 havie.py` for the terminal. Choose a working folder with
`py -3 havie.py --gui --workspace "C:\Users\YourName\Documents"`.
Git shortcuts require Git for Windows. Speech and microphone features use
Windows PowerShell and System.Speech; dictation requires a supported installed
speech recognizer and access to a microphone. Desktop capture requires an
interactive Windows session.

## Use on your phone (iPhone or Android)

1. On your Windows PC, double-click **Start-Havie-Phone.bat**, or run:

   ```powershell
   py -3 havie.py --phone --host 0.0.0.0
   ```

2. Connect your phone and PC to the same trusted private Wi-Fi. If Windows asks,
   allow Python on **Private networks**. Do not enable public-network access.
3. Run `ipconfig` on the PC and find its Wi-Fi IPv4 address. Open that address
   with port `8765` in Safari or Chrome on your phone. For example, if the PC
   address is `192.168.1.20`, enter `http://192.168.1.20:8765` in the address bar.
4. Paste the pairing code displayed in the PC terminal. It changes whenever the
   server restarts. Keep the code private.

The mobile interface includes **Today**, **Tasks**, **Notes**, **Calendar** and
**Assistant**. You can save tasks and notes, schedule appointments and reminders,
and record personal preferences. Chat requires Ollama on the PC; the other
personal tools work without AI. This is a browser interface, not an Android APK
or iOS native app. You can bookmark it for quick access.

Phone and desktop share data when they use the same `--data-dir` (the default
Windows data directory is shared automatically). Run the desktop and phone
server in separate terminals if you want both open. Keep the PC awake and Havie
running; this version does not work with the PC offline or provide public-cloud
sync. Guest Wi-Fi/client isolation may prevent the devices connecting.

Calendar times and daily agenda use **the PC's timezone**, shown on the phone.
Reminders appear while the phone page is open and connected; they do not generate
background push notifications. The page refreshes shared data every 15 seconds.
The desktop may also deliver and complete due reminders when it is running.

Phone mode only allows personal assistant tools by default. To enable reviewed
PC actions, start it with:

```powershell
py -3 havie.py --phone --host 0.0.0.0 --allow-phone-pc
```

Use **Assistant → Assistant command** for commands such as `open app notepad`.
Pairing then grants access to computer tools, so enable this only for trusted
phones. Each action still shows a preview and requires confirmation. Action
confirmations expire after five minutes and cannot be reused.

The default private-LAN server uses HTTP, so pairing and data are not encrypted
in transit. Do not port-forward it or expose it directly to the Internet. For
HTTPS, supply `--cert <certificate.pem> --key <private-key.pem>` using a certificate
trusted by the phone. Store private keys outside the project. Public hosting,
remote access from other networks and automatic certificate management are not
configured by this project.

## Features and examples

| Feature | Example |
| --- | --- |
| Phone-friendly interface | `py -3 havie.py --phone --host 0.0.0.0` |
| Daily agenda | `today` |
| Calendar appointments | `event 2030-01-02 13:30 Lunch with Alex`, `events`, `cancel event 4` |
| Personal preferences | `remember my name = Sam`, `memory`, `forget my name` |
| Desktop chat-style interface | `py -3 havie.py --gui` |
| Commands with review | `run dir` |
| Saved automation routines | `save routine check = git status --short`, then `routine check` |
| Routine management | `routines`, `delete routine check` |
| App launching | `open app notepad`, `open app calculator`, `open app paint`, `open app explorer` |
| File navigation | `list files`, `current folder`, `open file "report.txt"` |
| Filename search | `find files report` |
| Text file reading | `read file "report.txt"` |
| Folder creation | `make folder "new folder"` |
| Copy and move without overwrite | `copy file "report.txt" "report backup.txt"`, `move file "report.txt" "archive/report.txt"` |
| System and disk information | `system info`, `disk space`, `processes` |
| Git tools | `git status`, `git diff`, `git log` |
| Notes | `note Remember the project deadline`, `notes`, `delete note 1` |
| Tasks | `task Finish presentation`, `tasks`, `done 2` |
| Reminders | `remind 15 Take a break`, `reminders`, `cancel reminder 3` |
| Calculator | `calculate (12 + 8) / 4` |
| Local date and time | `time` |
| Web search and browser | `search web Python tutorial`, `open url https://example.com` |
| Speech output (Windows) | `speak Welcome back` |
| Microphone transcription (Windows) | `listen`, or the desktop Listen button |
| Clipboard (Windows) | `clipboard`, `copy text Hello world` |
| Screenshot of all monitors (Windows) | `screenshot "desktop.png"` |
| Lock session (Windows) | `lock computer` |
| Optional local AI conversation | `chat Help me plan today's work` |

Type `help` for the command reference. Microphone transcription displays text;
it does not automatically execute recognized commands. AI replies also do not
execute tools. Enter an explicit tool command and approve its preview to act.

## Local AI setup (optional)

Install [Ollama](https://ollama.com/) on your Windows PC, then:

```powershell
ollama pull llama3.2
py -3 havie.py --gui --model llama3.2
```

Ollama must be running on `127.0.0.1:11434`. A different installed model can be
selected with `--model`. Model downloads need Internet access and sufficient
memory/disk; requirements depend on the model. Havie sends only the messages
entered with `chat` and its session chat context to the local model. It does not
automatically send notes, files, clipboard contents or command output. Saved
personal preferences are included as context in local AI chat.

## Storage and reminders

Notes, tasks, appointments, preferences, reminders and routines are saved in SQLite at `%LOCALAPPDATA%\Havie`
on Windows. Other systems default to `.havie` inside the workspace. Override
this location with `--data-dir`. Keep this directory to preserve your data.
Stored data is local, unencrypted, and not synced. Chat context stays in memory
and is reset on restart. Paired phones share the phone server’s chat session;
the desktop has its own session. The pairing code is stored in the phone tab’s
session storage and cleared by Disconnect.

Keep Havie open for reminder notifications. The desktop checks every second and
plays a bell; the terminal prints notifications. Overdue reminders are shown on
reopening. Reminders do not launch commands or apps.

## Execution boundaries

Actions that change state, launch apps, use the microphone, read the clipboard,
or run commands show a preview and require confirmation. Saved routines require
confirmation every time they run. File tools stay inside the chosen workspace;
copy/move and screenshots do not overwrite existing destinations. Parent
folders for copies/moves must already exist. Read supports UTF-8 files up to 1 MB.

Raw commands run with your account's permissions, **not in a security sandbox**.
On Windows, `run` and routines use `cmd.exe`, including shell operators. On Linux
and macOS, they accept a program and arguments using shell-style quoting without
interpreting pipes or redirections. Review commands before approving them.
Commands time out after 60 seconds; descendant processes may survive a timeout.
Only one desktop action runs at a time; command output appears after completion.
AI requests have a 120-second timeout. Always-on wake words, autonomous AI tool
execution and unattended background service installation are not implemented.

## Development and validation

```sh
python -m unittest discover -s tests -v
python havie.py --data-dir /tmp/havie-data
```

Linux/macOS support the portable tools and optional AI chat. The desktop requires
Tk and a graphical display. Windows-specific features are unavailable there.
The optional mobile browser smoke requires Playwright plus Chromium:

```sh
python -m pip install playwright
python -m playwright install chromium
python tests/mobile_smoke.py
```

This exercises pairing, shared personal tools, cancel/confirm, disabled PC
controls, safe rendering and layouts at 320, 390 and 768 pixels. It supplements
the standard-library HTTP integration tests in the main test suite.

See [research sources](docs/research.md) for the documentation used in development.
