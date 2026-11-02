"""Minimal Chrome DevTools Protocol client for the Secure Office Suite tests.

The editors run in CEF. When the user's settings.xml holds
<ascdesktop-support-debug-info-keep>1</...>, CEF listens on 127.0.0.1:8080
(developer switch, off in a normal install). Each start page and each
document tab is one page target; the editor itself runs in an iframe of the
document page, so evaluation picks the frame's execution context.
"""

import json
import time
import urllib.request

import websocket  # websocket-client

PORT = 8080


def targets(port=PORT):
    try:
        with urllib.request.urlopen('http://127.0.0.1:%d/json/list' % port, timeout=3) as r:
            return [t for t in json.loads(r.read().decode()) if t.get('type') == 'page']
    except Exception:
        return []


class CDPError(Exception):
    pass


class Page:
    """One page target (a start page or a document tab)."""

    def __init__(self, target):
        self.target = target
        self.id = target['id']
        self.url = target.get('url', '')
        self.ws = websocket.create_connection(target['webSocketDebuggerUrl'], timeout=60,
                                              suppress_origin=True)
        self._id = 0
        self.events = []
        self.contexts = {}          # context id -> {frameId, origin, name, default}
        self.send('Runtime.enable')
        self.send('Page.enable')

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass

    def _read(self, timeout):
        self.ws.settimeout(timeout)
        msg = json.loads(self.ws.recv())
        if 'method' in msg:
            m, p = msg['method'], msg.get('params', {})
            if m == 'Runtime.executionContextCreated':
                c = p['context']
                aux = c.get('auxData', {})
                self.contexts[c['id']] = {'frameId': aux.get('frameId'), 'origin': c.get('origin'),
                                          'name': c.get('name'), 'default': aux.get('isDefault')}
            elif m == 'Runtime.executionContextDestroyed':
                self.contexts.pop(p.get('executionContextId'), None)
            elif m == 'Runtime.executionContextsCleared':
                self.contexts.clear()
            else:
                self.events.append(msg)
                del self.events[:-500]
        return msg

    def send(self, method, params=None, timeout=60):
        self._id += 1
        mid = self._id
        self.ws.send(json.dumps({'id': mid, 'method': method, 'params': params or {}}))
        end = time.time() + timeout
        while True:
            left = end - time.time()
            if left <= 0:
                raise CDPError('%s timed out' % method)
            try:
                msg = self._read(left)
            except websocket.WebSocketTimeoutException:
                raise CDPError('%s timed out' % method)
            if msg.get('id') == mid:
                if 'error' in msg:
                    raise CDPError('%s: %s' % (method, msg['error'].get('message')))
                return msg.get('result', {})

    def pump(self, secs=0.2):
        end = time.time() + secs
        while time.time() < end:
            try:
                self._read(max(0.01, end - time.time()))
            except websocket.WebSocketTimeoutException:
                break
            except Exception:
                break

    # -- frames and evaluation -------------------------------------------------
    def frames(self):
        tree = self.send('Page.getFrameTree')['frameTree']
        out = []

        def walk(node):
            out.append(node['frame'])
            for ch in node.get('childFrames', []):
                walk(ch)
        walk(tree)
        return out

    def context_for(self, url_part=None):
        """default execution context of the first frame whose URL has url_part
        (None = main frame)"""
        self.pump(0.05)
        frames = self.frames()
        frame = frames[0] if url_part is None else next((f for f in frames if url_part in f.get('url', '')), None)
        if frame is None:
            return None
        for cid, c in self.contexts.items():
            if c['frameId'] == frame['id'] and c['default']:
                return cid
        # contexts are reported on Runtime.enable; re-enable to refresh
        self.send('Runtime.disable')
        self.contexts.clear()
        self.send('Runtime.enable')
        self.pump(0.3)
        for cid, c in self.contexts.items():
            if c['frameId'] == frame['id'] and c['default']:
                return cid
        return None

    def eval(self, expr, frame=None, timeout=60, await_promise=False):
        """evaluate expr (in the frame whose URL contains `frame`) and return
        its JSON value; raises CDPError on exceptions"""
        params = {'expression': expr, 'returnByValue': True, 'awaitPromise': await_promise}
        if frame is not None:
            cid = self.context_for(frame)
            if cid is None:
                raise CDPError('no frame matching %r' % frame)
            params['contextId'] = cid
        r = self.send('Runtime.evaluate', params, timeout=timeout)
        if 'exceptionDetails' in r:
            d = r['exceptionDetails']
            raise CDPError('JS: %s' % (d.get('exception', {}).get('description') or d.get('text')))
        return r.get('result', {}).get('value')

    def try_eval(self, expr, frame=None, default=None, **kw):
        try:
            return self.eval(expr, frame, **kw)
        except Exception:
            return default

    # -- input -----------------------------------------------------------------
    def click_xy(self, x, y, count=1):
        for t in ('mouseMoved', 'mousePressed', 'mouseReleased'):
            p = {'type': t, 'x': x, 'y': y}
            if t != 'mouseMoved':
                p.update(button='left', clickCount=count)
            self.send('Input.dispatchMouseEvent', p)

    def key(self, key, code=None, keycode=0, modifiers=0, text=None):
        base = {'key': key, 'code': code or key, 'windowsVirtualKeyCode': keycode,
                'nativeVirtualKeyCode': keycode, 'modifiers': modifiers}
        down = dict(base, type='keyDown' if text else 'rawKeyDown')
        if text:
            down.update(text=text, unmodifiedText=text)
        self.send('Input.dispatchKeyEvent', down)
        self.send('Input.dispatchKeyEvent', dict(base, type='keyUp'))

    def type_text(self, s):
        for ch in s:
            if ch == '\n':
                self.key('Enter', 'Enter', 13, text='\r')
            else:
                code = ord(ch.upper()) if ch.isalnum() else 0
                self.key(ch, None, code, text=ch)

    def shortcut(self, letter, ctrl=True, shift=False):
        mods = (2 if ctrl else 0) | (8 if shift else 0)
        self.key(letter.lower(), 'Key' + letter.upper(), ord(letter.upper()), modifiers=mods)

    def screenshot(self, path):
        try:
            import base64
            data = self.send('Page.captureScreenshot', {'format': 'png'}, timeout=20)['data']
            with open(path, 'wb') as f:
                f.write(base64.b64decode(data))
        except Exception:
            pass
