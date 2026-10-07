"""Desktop interface; workers communicate with Tk through a queue."""
import queue
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk


def launch(assistant):
    root = tk.Tk()
    root.title('Havie — Computer Assistant')
    root.geometry('900x660')
    root.configure(bg='#101827')
    ttk.Label(root, text='HAVIE', font=('Segoe UI', 24, 'bold')).pack(pady=(16, 0))
    ttk.Label(root, text=f'Workspace: {assistant.workspace}').pack(pady=6)
    output = scrolledtext.ScrolledText(root, bg='#172337', fg='#e7edf7', insertbackground='white',
                                      font=('Consolas', 11), wrap=tk.WORD, state='disabled')
    output.pack(fill=tk.BOTH, expand=True, padx=16, pady=8)
    entry = ttk.Entry(root, font=('Segoe UI', 12))
    entry.pack(fill=tk.X, padx=16, pady=8)
    bar = ttk.Frame(root)
    bar.pack(fill=tk.X, padx=16, pady=(0, 16))
    events = queue.Queue()
    busy = False

    def append(text):
        output.configure(state='normal')
        output.insert(tk.END, text + '\n\n')
        output.see(tk.END)
        output.configure(state='disabled')

    def submit(event=None):
        nonlocal busy
        if busy:
            return
        request = entry.get().strip()
        if not request:
            return
        try:
            action = assistant.prepare(request)
        except Exception as exc:
            append(f'Havie: {exc}')
            return
        if action.confirm and not messagebox.askyesno('Review action', action.preview + '\n\nProceed? Commands run with your account permissions.'):
            append('Cancelled: ' + action.preview)
            return
        entry.delete(0, tk.END)
        append('You: ' + request)
        busy = True
        send.configure(state='disabled')
        def work():
            try:
                events.put(('result', str(action.run())))
            except Exception as exc:
                events.put(('result', f'Action failed: {exc}'))
        threading.Thread(target=work, daemon=True).start()

    def tick():
        nonlocal busy
        try:
            while True:
                _, text = events.get_nowait()
                append('Havie: ' + text)
                busy = False
                send.configure(state='normal')
        except queue.Empty:
            pass
        try:
            for reminder in assistant.due_reminders():
                append(reminder)
                root.bell()
        except Exception as exc:
            append('Reminder check failed: ' + str(exc))
        root.after(1000, tick)

    send = ttk.Button(bar, text='Send', command=submit)
    send.pack(side=tk.RIGHT)
    for label, request in [('Help', 'help'), ('Files', 'list files'), ('Notes', 'notes'), ('Tasks', 'tasks'), ('Reminders', 'reminders'), ('System', 'system info'), ('Listen', 'listen')]:
        def shortcut(request=request):
            entry.delete(0, tk.END)
            entry.insert(0, request)
            submit()
        ttk.Button(bar, text=label, command=shortcut).pack(side=tk.LEFT, padx=2)
    entry.bind('<Return>', submit)
    entry.focus()
    append('Havie is ready. Type help for features. AI chat: chat <message>. Reminders require Havie to stay open.')
    tick()
    root.mainloop()
