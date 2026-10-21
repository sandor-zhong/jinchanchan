"""Local, user-operated SSH login. Credentials remain in process memory only.

This helper uses stdin/stdout for deployment commands after the user logs in.
It does not expose a listening socket or create remote authorized_keys entries.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
from pathlib import Path
import sys
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import paramiko

ROOT = Path(__file__).resolve().parents[2]
KNOWN_HOSTS = Path(__file__).with_name('known_hosts')
HOST = '47.107.143.148'
logging.getLogger('paramiko').addHandler(logging.NullHandler())
logging.getLogger('paramiko').propagate = False


def emit(event: str, **values):
    print(json.dumps({'event': event, **values}, ensure_ascii=True), flush=True)


class AskHostKey(paramiko.MissingHostKeyPolicy):
    def __init__(self, window):
        self.window = window

    def missing_host_key(self, client, hostname, key):
        fingerprint = base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=')
        accepted = messagebox.askyesno(
            '首次 SSH 连接：核对服务器指纹',
            f'服务器：{hostname}\n密钥类型：{key.get_name()}\n\nSHA256:{fingerprint}\n\n'
            '这是此工具首次连接该服务器。可与云控制台中的 SSH 主机指纹核对。\n是否信任此主机密钥并继续登录？',
            parent=self.window,
        )
        if not accepted:
            raise paramiko.SSHException('Host key was not accepted')
        client.get_host_keys().add(hostname, key.get_name(), key)
        client.save_host_keys(str(KNOWN_HOSTS))


def login():
    window = tk.Tk()
    window.title('金铲铲助手 · 服务器登录')
    window.resizable(False, False)
    frame = ttk.Frame(window, padding=24)
    frame.grid(sticky='nsew')
    ttk.Label(frame, text='登录你的云服务器', font=('Microsoft YaHei UI', 14, 'bold')).grid(row=0, column=0, columnspan=3, sticky='w', pady=(0, 16))
    ttk.Label(frame, text='服务器').grid(row=1, column=0, sticky='w', pady=6)
    ttk.Label(frame, text=HOST).grid(row=1, column=1, columnspan=2, sticky='w')
    ttk.Label(frame, text='SSH 用户名').grid(row=2, column=0, sticky='w', pady=6)
    username = ttk.Entry(frame, width=36)
    username.insert(0, 'root')
    username.grid(row=2, column=1, columnspan=2, sticky='ew')
    ttk.Label(frame, text='SSH 端口').grid(row=3, column=0, sticky='w', pady=6)
    port = ttk.Entry(frame, width=36)
    port.insert(0, '22')
    port.grid(row=3, column=1, columnspan=2, sticky='ew')
    ttk.Label(frame, text='登录方式').grid(row=4, column=0, sticky='w', pady=6)
    mode = ttk.Combobox(frame, values=['密码登录', '本机私钥'], state='readonly', width=34)
    mode.set('密码登录')
    mode.grid(row=4, column=1, columnspan=2, sticky='ew')
    ttk.Label(frame, text='密码 / 密钥口令').grid(row=5, column=0, sticky='w', pady=6)
    password = ttk.Entry(frame, show='●', width=36)
    password.grid(row=5, column=1, columnspan=2, sticky='ew')
    ttk.Label(frame, text='私钥文件（可选）').grid(row=6, column=0, sticky='w', pady=6)
    key_path = ttk.Entry(frame, width=27)
    key_path.grid(row=6, column=1, sticky='ew')
    def choose_key():
        selected = filedialog.askopenfilename(parent=window, title='选择本机 SSH 私钥')
        if selected:
            key_path.delete(0, tk.END)
            key_path.insert(0, selected)
            mode.set('本机私钥')
    ttk.Button(frame, text='选择…', command=choose_key).grid(row=6, column=2, padx=(6, 0))
    status = tk.StringVar(value='凭据只交给 SSH 连接，不保存到文件，也不传入聊天。')
    ttk.Label(frame, textvariable=status, wraplength=410).grid(row=7, column=0, columnspan=3, sticky='w', pady=(16, 12))
    result = {}

    def connect():
        user = username.get().strip()
        secret = password.get()
        path = key_path.get().strip()
        try:
            selected_port = int(port.get())
            if not user or not 1 <= selected_port <= 65535:
                raise ValueError()
        except ValueError:
            status.set('请检查 SSH 用户名和端口。')
            return
        if mode.get() == '密码登录' and not secret:
            status.set('请在密码框中输入服务器密码。')
            password.focus_set()
            return
        if mode.get() == '本机私钥' and not Path(path).is_file():
            status.set('请选择存在的 SSH 私钥文件。')
            return
        password.delete(0, tk.END)
        button.state(['disabled'])
        status.set('正在建立加密连接…')
        window.update_idletasks()
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        if KNOWN_HOSTS.exists():
            client.load_host_keys(str(KNOWN_HOSTS))
        client.set_missing_host_key_policy(AskHostKey(window))
        try:
            client.connect(
                HOST, port=selected_port, username=user,
                password=secret if mode.get() == '密码登录' else None,
                key_filename=path if mode.get() == '本机私钥' else None,
                passphrase=secret if mode.get() == '本机私钥' else None,
                allow_agent=False, look_for_keys=False,
                timeout=12, banner_timeout=15, auth_timeout=30,
            )
            client.get_transport().set_keepalive(20)
            result.update(client=client, username=user, port=selected_port)
            window.destroy()
        except paramiko.AuthenticationException:
            client.close()
            status.set('认证失败。请检查 SSH 用户名、密码或私钥后再试。')
            password.focus_set()
        except paramiko.BadHostKeyException:
            client.close()
            status.set('服务器指纹与已信任记录不一致，已停止连接。请先核对云控制台。')
        except Exception as exc:
            client.close()
            status.set(f'连接未完成（{type(exc).__name__}）。请检查端口、网络或主机指纹。')
        finally:
            secret = None
            if not result and window.winfo_exists():
                button.state(['!disabled'])

    button = ttk.Button(frame, text='登录并交给助手继续部署', command=connect)
    button.grid(row=8, column=0, columnspan=3, sticky='ew', pady=(4, 0))
    window.bind('<Return>', lambda event: connect())
    window.update_idletasks()
    width, height = window.winfo_reqwidth(), window.winfo_reqheight()
    window.geometry(f'+{(window.winfo_screenwidth()-width)//2}+{(window.winfo_screenheight()-height)//2}')
    window.attributes('-topmost', True)
    window.after(1500, lambda: window.attributes('-topmost', False) if window.winfo_exists() else None)
    password.focus_set()
    emit('login_window_open', host=HOST)
    window.mainloop()
    return result


def run_command(client, request):
    channel = client.get_transport().open_session(timeout=20)
    channel.exec_command(request['command'])
    channel.shutdown_write()
    deadline = time.monotonic() + min(900, max(5, int(request.get('timeout', 120))))
    output_bytes = 0
    limit = 1_000_000
    while True:
        for stream, ready, receive in [('stdout', channel.recv_ready, channel.recv), ('stderr', channel.recv_stderr_ready, channel.recv_stderr)]:
            while ready():
                chunk = receive(32768)
                if not chunk:
                    break
                output_bytes += len(chunk)
                if output_bytes <= limit:
                    emit(stream, id=request.get('id'), text=chunk.decode('utf-8', errors='replace'))
        if channel.exit_status_ready() and not channel.recv_ready() and not channel.recv_stderr_ready():
            break
        if time.monotonic() > deadline:
            channel.close()
            emit('done', id=request.get('id'), exit_code=-1, error='Remote command timeout')
            return
        time.sleep(.1)
    code = channel.recv_exit_status()
    channel.close()
    emit('done', id=request.get('id'), exit_code=code, truncated=output_bytes > limit)


def main():
    result = login()
    if not result:
        emit('login_cancelled')
        return
    client = result['client']
    emit('connected', host=HOST, username=result['username'], port=result['port'])
    try:
        for line in sys.stdin:
            if not line.strip():
                continue
            request = json.loads(line)
            try:
                if request['action'] == 'exec':
                    run_command(client, request)
                elif request['action'] == 'put':
                    local = Path(request['local']).resolve()
                    local.relative_to(ROOT)
                    if not local.is_file():
                        raise ValueError('Missing local file')
                    with client.open_sftp() as sftp:
                        sftp.put(str(local), request['remote'])
                    emit('uploaded', id=request.get('id'), remote=request['remote'], size=local.stat().st_size)
                elif request['action'] == 'close':
                    break
                else:
                    raise ValueError('Unsupported action')
            except Exception as exc:
                emit('error', id=request.get('id'), error=type(exc).__name__, message=str(exc))
    finally:
        client.close()
        emit('disconnected')


if __name__ == '__main__':
    main()
