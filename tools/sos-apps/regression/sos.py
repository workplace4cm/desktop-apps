"""Helpers that drive the installed Secure Office Suite applications on X11.

Processes and windows go through xdotool, the pages (start pages and the
editors) through the DevTools protocol (cdp.py), native GTK file pickers by
keyboard. Used by run_regression.py.
"""

import glob
import json
import os
import re
import shutil
import subprocess
import time

import cdp

PREFIX = os.environ.get('SOS_PREFIX', 'secure-office-suite-desktopeditors')
BASE = re.sub(r'-desktopeditors$', '', PREFIX)
APP_DIR = '/opt/%s/desktopeditors' % BASE
DATA = os.path.expanduser('~/.local/share/%s/desktopeditors' % BASE)
RECENTS = os.path.join(DATA, 'sos-recents.json')
OUT = os.environ.get('SOS_OUT', '/tmp/sos-regression')

APPS = {
    'writer': dict(name='EuroOffice Writer', editor='documenteditor', ext='docx', blank='word',
                   formats=['doc', 'docx', 'odt', 'rtf', 'txt']),
    'sheet': dict(name='EuroOffice Sheet', editor='spreadsheeteditor', ext='xlsx', blank='cell',
                  formats=['xls', 'xlsx', 'ods', 'csv']),
    'presentation': dict(name='EuroOffice Presentation', editor='presentationeditor', ext='pptx', blank='slide',
                         formats=['ppt', 'pptx', 'odp']),
    'pdf': dict(name='EuroOffice PDF', editor='pdfeditor', ext='pdf', blank=None, formats=['pdf']),
}


def owner(path):
    ext = path.rsplit('.', 1)[-1].lower()
    for a, d in APPS.items():
        if ext in d['formats']:
            return a
    return None


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


# -- X11 ------------------------------------------------------------------------

def sh(*args, timeout=30):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout).stdout
    except Exception:
        return ''


def windows():
    """visible top-level windows: [(wid, title, pid)]"""
    out = []
    for w in sh('xdotool', 'search', '--onlyvisible', '--name', '.').split():
        name = sh('xdotool', 'getwindowname', w).strip()
        pid = sh('xdotool', 'getwindowpid', w).strip()
        out.append((w, name, pid))
    return out


def wait_window(regex, secs=60, exclude=()):
    end = time.time() + secs
    rx = re.compile(regex)
    while time.time() < end:
        for w in windows():
            if w[0] not in exclude and rx.search(w[1]):
                return w
        time.sleep(0.5)
    return None


def screenshot(name):
    os.makedirs(os.path.join(OUT, 'shots'), exist_ok=True)
    sh('import', '-window', 'root', os.path.join(OUT, 'shots', name + '.png'), timeout=20)


def key(*keys, wid=None):
    if wid:
        sh('xdotool', 'windowactivate', '--sync', wid, timeout=10)
    sh('xdotool', 'key', '--clearmodifiers', *keys)


def xtype(text):
    sh('xdotool', 'type', '--delay', '20', '--clearmodifiers', text, timeout=60)


DIALOG_RX = r'^(Open|Save|Export|Choose|Select|Find|Open Document|Save As|Save Copy)'


def file_dialog(path, mode, secs=40):
    """answer a native GTK file picker: mode 'open' or 'save'. Returns the
    dialog's title, or None when no picker showed up."""
    w = wait_window(DIALOG_RX, secs)
    if not w:
        return None
    wid, title, _ = w
    time.sleep(1.0)
    sh('xdotool', 'windowactivate', '--sync', wid, timeout=10)
    if mode == 'open':
        key('ctrl+l')
        time.sleep(0.5)
        key('ctrl+a')
        xtype(path)
        time.sleep(0.6)
        key('Return')
    else:
        key('ctrl+a')
        xtype(path)
        time.sleep(0.6)
        key('Return')
    # a picker may stay open when it did not take the path
    for _ in range(20):
        if wid not in [x[0] for x in windows()]:
            break
        time.sleep(0.5)
    else:
        screenshot('dialog-stuck-' + re.sub(r'\W+', '_', title))
        key('Escape', wid=wid)
        return title + ' (did not close)'
    return title


def close_stray_dialogs():
    for wid, title, _ in windows():
        if re.search(DIALOG_RX, title):
            key('Escape', wid=wid)


# -- processes ----------------------------------------------------------------

def app_pids(app=None):
    pat = '%s/DesktopEditors' % APP_DIR + (' --app=%s' % app if app else '')
    out = sh('pgrep', '-u', str(os.getuid()), '-f', '--', pat).split()
    return [p for p in out if p]


def kill_all(secs=20):
    sh('pkill', '-u', str(os.getuid()), '-f', '--', '%s/DesktopEditors' % APP_DIR)
    end = time.time() + secs
    while time.time() < end and app_pids():
        time.sleep(0.5)
    if app_pids():
        sh('pkill', '-9', '-u', str(os.getuid()), '-f', '--', '%s/DesktopEditors' % APP_DIR)
        time.sleep(2)
    # the DevTools port is gone with the browser process
    end = time.time() + 15
    while time.time() < end and cdp.targets():
        time.sleep(0.5)


def launch(app, *args):
    os.makedirs(os.path.join(OUT, 'logs'), exist_ok=True)
    # Release builds never open the DevTools port themselves (desktop-sdk
    # ENABLE_REMOTE_DEBUGGING_PORT); Chromium's own command-line switch does.
    cmd = [PREFIX + ('-' + app if app else ''), '--remote-debugging-port=%d' % cdp.PORT,
           '--remote-allow-origins=*'] + list(args)
    logf = open(os.path.join(OUT, 'logs', (app or 'suite') + '.log'), 'a')
    logf.write('\n$ %s\n' % ' '.join(cmd))
    logf.flush()
    return subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT, start_new_session=True)


def main_window(app):
    rx = re.compile(r'(^| - )%s$' % re.escape(APPS[app]['name']))
    for w in windows():
        if rx.search(w[1]):
            return w
    return None


def close_window(app, secs=40):
    """close the application the way a user does (Alt+F4 on its window);
    True when its process ended"""
    w = main_window(app)
    if w:
        key('alt+F4', wid=w[0])
    end = time.time() + secs
    while time.time() < end:
        if not app_pids(app):
            return True
        time.sleep(0.5)
    return False


# -- pages ----------------------------------------------------------------------

def is_start(t, app=None):
    u = t.get('url', '')
    return '/apps/api/documents/' not in u and 'index.html' in u and \
        (app is None or ('app=' + app) in u)


def is_doc(t):
    return '/apps/api/documents/' in t.get('url', '')


def wait_target(pred, secs=90, exclude=()):
    end = time.time() + secs
    while time.time() < end:
        for t in cdp.targets():
            if t['id'] not in exclude and pred(t):
                return t
        time.sleep(0.5)
    return None


def doc_ids():
    return {t['id'] for t in cdp.targets() if is_doc(t)}


API = ("(function(){var g=window.PDFE||window.SSE||window.PE||window.DE;"
       "try{return g&&g.getController('Main').api}catch(e){}"
       "return window.editor||(window.Asc&&Asc.editor)})()")


class Editor:
    """a document tab"""

    def __init__(self, target, app):
        self.app = app
        self.page = cdp.Page(target)
        self.frame = '/apps/%s/' % APPS[app]['editor']

    def js(self, body, default=None, **kw):
        return self.page.try_eval('(function(){var api=%s;%s})()' % (API, body),
                                  self.frame, default=default, **kw)

    def js_strict(self, body, **kw):
        return self.page.eval('(function(){var api=%s;%s})()' % (API, body), self.frame, **kw)

    def editor_kind(self):
        try:
            return next((f['url'] for f in self.page.frames() if '/apps/' in f['url'] and '/main/' in f['url']), '')
        except Exception:
            return ''

    def wait_ready(self, secs=150):
        end = time.time() + secs
        while time.time() < end:
            st = self.js("return api ? !!api.isDocumentLoadComplete : null")
            if st:
                time.sleep(1.5)
                return True
            err = self.alerts()
            if err:
                return False
            time.sleep(1)
        return False

    def alerts(self):
        """texts of visible modal windows in the editor"""
        return self.page.try_eval(
            "Array.from(document.querySelectorAll('.asc-window')).filter(e=>e.offsetParent!==null&&getComputedStyle(e).display!=='none')"
            ".map(e=>(e.querySelector('.title')||{}).textContent+': '+((e.querySelector('.body')||e).innerText||'').trim().slice(0,300))",
            self.frame, default=[]) or []

    def answer_alert(self, prefer=('OK', 'Yes', 'Save', 'Continue')):
        """press a button of the visible modal window; returns its text"""
        return self.page.try_eval("""(function(prefer){
            var w=Array.from(document.querySelectorAll('.asc-window')).filter(e=>e.offsetParent!==null)[0];
            if(!w) return null;
            var bs=Array.from(w.querySelectorAll('.footer button, button.btn')).filter(b=>b.offsetParent!==null);
            var b=null;
            for (var p of prefer){ b=bs.find(x=>x.innerText.trim().toLowerCase()===p.toLowerCase()); if(b) break; }
            b=b||bs.find(x=>x.classList.contains('primary'))||bs[0];
            if(!b) return null; var t=b.innerText.trim(); b.click(); return t;})(%s)""" % json.dumps(list(prefer)),
            self.frame)

    def modified(self):
        return self.js("return api.isDocumentModified ? api.isDocumentModified() : api.asc_isDocumentModified()")

    def title(self):
        return self.page.try_eval('document.title', default='')

    # -- real mouse clicks on elements of the editor frame -------------------
    def rect(self, selector):
        off = self.page.try_eval("(function(){var f=document.querySelector('iframe');if(!f)return [0,0];"
                                 "var r=f.getBoundingClientRect();return [r.left,r.top]})()", default=[0, 0]) or [0, 0]
        r = self.page.try_eval("(function(s){var e=document.querySelector(s);if(!e||e.offsetParent===null)return null;"
                               "var r=e.getBoundingClientRect();return [r.left,r.top,r.width,r.height]})(%s)" % json.dumps(selector),
                               self.frame)
        if not r or r[2] == 0:
            return None
        return off[0] + r[0] + r[2] / 2, off[1] + r[1] + r[3] / 2

    def click(self, selector, secs=10):
        """mouse click on the element's centre; falls back to a DOM click.
        Returns 'mouse', 'dom' or None (no such visible element)."""
        end = time.time() + secs
        while time.time() < end:
            c = self.rect(selector)
            if c:
                self.page.click_xy(*c)
                return 'mouse'
            time.sleep(0.5)
        ok = self.page.try_eval("(function(s){var e=document.querySelector(s);if(!e)return false;e.click();return true})(%s)"
                                % json.dumps(selector), self.frame)
        return 'dom' if ok else None

    def visible(self, selector):
        return bool(self.page.try_eval("(function(s){var e=document.querySelector(s);return !!e&&e.offsetParent!==null})(%s)"
                                       % json.dumps(selector), self.frame))

    def focus_canvas(self):
        for sel in ('#id_main_view', '#editor_sdk', '#ws-canvas-outer', '#id_viewer', '#id_main'):
            c = self.rect(sel)
            if c:
                self.page.click_xy(*c)
                time.sleep(0.5)
                return sel
        return None

    def open_file_menu(self):
        how = self.click('.ribtab > a[data-tab="file"]') or self.click('#file')
        time.sleep(1.0)
        return how and self.visible('#file-menu-panel')

    def close_file_menu(self):
        if self.visible('#file-menu-panel'):
            self.click('#fm-btn-return') if self.visible('#fm-btn-return') else self.page.key('Escape', 'Escape', 27)
            time.sleep(0.6)
        if self.visible('#file-menu-panel'):
            self.page.key('Escape', 'Escape', 27)
            time.sleep(0.6)

    def close(self):
        self.page.close()


class StartPage:
    def __init__(self, target):
        self.page = cdp.Page(target)

    def js(self, expr, default=None):
        return self.page.try_eval(expr, default=default)

    def rect(self, selector):
        return self.page.try_eval("(function(s){var e=document.querySelector(s);if(!e||e.offsetParent===null)return null;"
                                  "e.scrollIntoView({block:'center'});"
                                  "var r=e.getBoundingClientRect();return [r.left+r.width/2,r.top+r.height/2,r.width]})(%s)"
                                  % json.dumps(selector))

    def click(self, selector, secs=10):
        end = time.time() + secs
        while time.time() < end:
            r = self.rect(selector)
            if r and r[2] > 0:
                self.page.click_xy(r[0], r[1])
                return 'mouse'
            time.sleep(0.5)
        ok = self.page.try_eval("(function(s){var e=document.querySelector(s);if(!e)return false;e.click();return true})(%s)"
                                % json.dumps(selector))
        return 'dom' if ok else None

    def recents(self, app):
        return self.js("SOS.recents.ready() ? SOS.recents.list(%s) : null" % json.dumps(app))

    def wait_recents(self, app, pred, secs=20):
        end = time.time() + secs
        last = None
        while time.time() < end:
            last = self.recents(app)
            if last is not None and pred(last):
                return last
            time.sleep(0.5)
        return last

    def row_id(self, path):
        """DOM id of the recent-list row of path"""
        return self.js("""(function(p){var rows=document.querySelectorAll('#box-recent .file-list-body .row');
            for (var r of rows){ var n=r.querySelector('.col-location'); var nm=r.querySelector('.name');
              var full=(r.querySelector('.col-name')||{}).title||'';
              if ((full && p.endsWith(full)) || (n && nm && p.indexOf((n.title||'').split(' · ').pop())===0 && p.endsWith(nm.innerText.replace(/\\s+/g,'')))) return r.id; }
            return null;})(%s)""" % json.dumps(path))

    def rows(self):
        return self.js("Array.from(document.querySelectorAll('#box-recent .file-list-body .row')).map(r=>({id:r.id,name:(r.querySelector('.col-name')||{}).title||'',loc:(r.querySelector('.col-location')||{}).title||''}))", default=[])

    def close(self):
        self.page.close()


def read_recents():
    try:
        with open(RECENTS) as f:
            return json.load(f)
    except Exception:
        return {}


def recent_entry(app, path):
    for e in read_recents().get('lists', {}).get(app, []):
        if e.get('path') == path:
            return e
    return None


def enable_devtools():
    """CEF's developer switch: DevTools on 127.0.0.1:8080 (tests only)"""
    d = os.path.join(DATA, 'data')
    os.makedirs(d, exist_ok=True)
    f = os.path.join(d, 'settings.xml')
    xml = ''
    if os.path.exists(f):
        xml = open(f).read()
    if 'ascdesktop-support-debug-info-keep' not in xml:
        if '<Settings>' in xml:
            xml = xml.replace('<Settings>', '<Settings><ascdesktop-support-debug-info-keep>1</ascdesktop-support-debug-info-keep>')
        else:
            xml = '<Settings><ascdesktop-support-debug-info-keep>1</ascdesktop-support-debug-info-keep></Settings>'
        open(f, 'w').write(xml)
    return f


def samples_dir():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(here), 'samples')


def fresh_copy(src, dst_dir, name=None):
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, name or os.path.basename(src))
    shutil.copyfile(src, dst)
    return dst


def wait_file(path, since=0, secs=60, min_size=1):
    end = time.time() + secs
    while time.time() < end:
        try:
            st = os.stat(path)
            if st.st_mtime >= since and st.st_size >= min_size:
                time.sleep(1.0)
                return True
        except OSError:
            pass
        time.sleep(0.5)
    return False
