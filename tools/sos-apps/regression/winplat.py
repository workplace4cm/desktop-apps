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


def press_button(text, title_rx='.'):
    """click a button of a message box of the application by its text"""
    for wid, title, _ in windows():
        h = int(wid)
        try:
            if win32gui.GetClassName(h) != '#32770' or not re.search(title_rx, title):
                continue
        except Exception:
            continue
        for c in _children(h):
            try:
                if win32gui.GetClassName(c) == 'Button' and win32gui.GetWindowText(c).replace('&', '') == text:
                    win32gui.PostMessage(c, 0x00F5, 0, 0)     # BM_CLICK
                    return True
            except Exception:
                pass
    return False


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
            # the upstream "More than one document is open. Close the window
            # anyway?" question (a Yes / No box of the application): Yes
            if press_button('Yes', title_rx=r'Secure Office Suite'):
                seen = 'answered Yes to the application\'s Yes / No question on closing (%s)' % seen
        time.sleep(0.5)
    return False, seen


def _children(h):
    out = []

    def cb(c, _):
        out.append(c)
        return True
    try:
        win32gui.EnumChildWindows(h, cb, None)
    except Exception:
        pass
    return out


def _name_edit(h):
    """the "File name" box of a common file dialog (control 1148, or 1152 in old ones)"""
    for c in _children(h):
        try:
            if win32gui.GetDlgCtrlID(c) in (1148, 1152):
                if win32gui.GetClassName(c) == 'Edit':
                    return c
                for e in _children(c):
                    if win32gui.GetClassName(e) == 'Edit':
                        return e
        except Exception:
            pass
    return None


def file_dialog(path, mode, secs=40):
    """the Windows file picker: put the full path into "File name" and
    press Save / Open, by window messages so focus doesn't matter"""
    import sos
    w = sos.wait_window(sos.DIALOG_RX, secs)
    if not w:
        return None
    wid, title, _ = w
    h = int(wid)
    time.sleep(1.5)
    path = os.path.normpath(path)
    edit = None
    for _ in range(10):
        edit = _name_edit(h)
        if edit:
            break
        time.sleep(0.5)
    if edit:
        win32gui.SendMessage(edit, win32con.WM_SETTEXT, 0, path)
        time.sleep(0.3)
        win32gui.PostMessage(h, win32con.WM_COMMAND, win32con.IDOK, 0)
    else:
        activate(wid)
        key('alt+n')
        time.sleep(0.3)
        key('ctrl+a')
        xtype(path)
        time.sleep(0.5)
        key('Return')
    for _ in range(30):
        if wid not in [x[0] for x in windows()]:
            break
        time.sleep(0.5)
    else:
        txt = screen_text('picker-stuck')
        win32gui.PostMessage(h, win32con.WM_CLOSE, 0, 0)
        return title + ' (did not close; name box %s; %s)' % (bool(edit), txt)
    return title


def deny_read(path):
    subprocess.run(['icacls', path, '/deny', '%s:(R)' % os.environ.get('USERNAME', '')], capture_output=True)


def allow_read(path):
    subprocess.run(['icacls', path, '/remove:d', os.environ.get('USERNAME', '')], capture_output=True)
