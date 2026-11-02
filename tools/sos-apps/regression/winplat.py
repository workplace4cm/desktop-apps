"""Windows side of sos.py: windows, keyboard, processes and paths.

sos.py imports these over its X11 helpers when it runs on Windows, so the
tests themselves don't change. Needs pywinauto, psutil and Pillow.
"""

import os
import re
import subprocess
import time

import psutil
from pywinauto import keyboard
import win32con
import win32gui
import win32process

import cdp

APP_DIR = os.path.join(os.environ.get('ProgramFiles', r'C:\Program Files'), 'Secure Office Suite', 'DesktopEditors')
EXE = os.path.join(APP_DIR, 'DesktopEditors.exe')
DATA = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Secure Office Suite', 'DesktopEditors')
# Windows keeps the profile one level down (main.cpp: <user path>/data)
RECENTS_CANDIDATES = [os.path.join(DATA, 'data', 'sos-recents.json'), os.path.join(DATA, 'sos-recents.json')]


def windows():
    out = []

    def cb(h, _):
        if win32gui.IsWindowVisible(h):
            t = win32gui.GetWindowText(h)
            if t:
                out.append((str(h), t, str(win32process.GetWindowThreadProcessId(h)[1])))
        return True
    win32gui.EnumWindows(cb, None)
    return out


def activate(wid):
    try:
        h = int(wid)
        keyboard.send_keys('%')          # lets a background process take the foreground
        win32gui.ShowWindow(h, win32con.SW_SHOW)
        win32gui.SetForegroundWindow(h)
        time.sleep(0.4)
    except Exception:
        pass


KEYS = {'Return': '{ENTER}', 'Escape': '{ESC}', 'Tab': '{TAB}', 'F4': '{F4}'}


def _keyspec(k):
    mods = ''
    parts = k.split('+')
    for m in parts[:-1]:
        mods += {'ctrl': '^', 'alt': '%', 'shift': '+'}[m.lower()]
    last = parts[-1]
    return mods + KEYS.get(last, last)


def key(*keys, wid=None):
    if wid:
        activate(wid)
    for k in keys:
        keyboard.send_keys(_keyspec(k))


def xtype(text):
    esc = re.sub(r'([+^%~(){}\[\]])', r'{\1}', text)
    keyboard.send_keys(esc, with_spaces=True, pause=0.02)


def screenshot(name, OUT=None):
    import sos
    os.makedirs(os.path.join(sos.OUT, 'shots'), exist_ok=True)
    f = os.path.join(sos.OUT, 'shots', name + '.png')
    try:
        from PIL import ImageGrab
        ImageGrab.grab().save(f)
    except Exception:
        pass
    return f


def screen_text(name):
    screenshot(name)
    # message boxes: their own text, read from the window
    texts = []
    for wid, title, _ in windows():
        try:
            h = int(wid)
            if win32gui.GetClassName(h) == '#32770':
                parts = []

                def cb(c, _):
                    t = win32gui.GetWindowText(c)
                    if t:
                        parts.append(t)
                    return True
                win32gui.EnumChildWindows(h, cb, None)
                texts.append('%s: %s' % (title, ' | '.join(parts)))
        except Exception:
            pass
    return '; '.join(texts)[:400]


def _procs(app=None):
    out = []
    for p in psutil.process_iter(['name', 'cmdline']):
        try:
            if (p.info['name'] or '').lower() != 'desktopeditors.exe':
                continue
            cl = ' '.join(p.info['cmdline'] or [])
            if '--type=' in cl:
                continue
            if app and not re.search(r'--app=%s( |$)' % app, cl):
                continue
            out.append(p)
        except Exception:
            pass
    return out


def app_pids(app=None):
    return [str(p.pid) for p in _procs(app)]


def kill_all(secs=20):
    for p in psutil.process_iter(['name']):
        try:
            if (p.info['name'] or '').lower() in ('desktopeditors.exe', 'editors_helper.exe'):
                p.kill()
        except Exception:
            pass
    end = time.time() + secs
    while time.time() < end and (app_pids() or cdp.targets()):
        time.sleep(0.5)


def launch(app, *args):
    import sos
    os.makedirs(os.path.join(sos.OUT, 'logs'), exist_ok=True)
    cmd = [EXE] + (['--app=' + app] if app else []) + ['--remote-debugging-port=%d' % cdp.PORT,
                                                        '--remote-allow-origins=*'] + list(args)
    logf = open(os.path.join(sos.OUT, 'logs', (app or 'suite') + '.log'), 'a')
    logf.write('\n$ %s\n' % ' '.join(cmd))
    logf.flush()
    return subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT)


def close_window(app, secs=40):
    """WM_CLOSE on the application's window: what the title bar's X does"""
    import sos
    w = sos.main_window(app)
    if w:
        win32gui.PostMessage(int(w[0]), win32con.WM_CLOSE, 0, 0)
    end = time.time() + secs
    seen = ''
    while time.time() < end:
        if not app_pids(app):
            return True, seen
        if not seen and time.time() > end - secs + 6:
            seen = 'windows %s; message boxes: %s' % ([x[1] for x in windows()], screen_text('close-%s' % app))
            if re.search(r'(?i)close the window anyway', seen):
                for wid, _t, _p in windows():
                    if win32gui.GetClassName(int(wid)) == '#32770':
                        key('y', wid=wid)
                seen = 'answered Yes to "More than one document is open. Close the window anyway?"'
        time.sleep(0.5)
    return False, seen


def file_dialog(path, mode, secs=40):
    """the Windows file picker: type the full path into "File name" """
    import sos
    w = sos.wait_window(sos.DIALOG_RX, secs)
    if not w:
        return None
    wid, title, _ = w
    time.sleep(1.0)
    activate(wid)
    key('alt+n')
    time.sleep(0.3)
    key('ctrl+a')
    xtype(path)
    time.sleep(0.5)
    key('Return')
    for _ in range(20):
        if wid not in [x[0] for x in windows()]:
            break
        time.sleep(0.5)
    else:
        key('Escape', wid=wid)
        return title + ' (did not close)'
    return title


def deny_read(path):
    subprocess.run(['icacls', path, '/deny', '%s:(R)' % os.environ.get('USERNAME', '')], capture_output=True)


def allow_read(path):
    subprocess.run(['icacls', path, '/remove:d', os.environ.get('USERNAME', '')], capture_output=True)
