#!/usr/bin/env python3
"""Secure Office Suite: Phase 9 cross-application functional and format
regression test of EuroOffice Writer, Sheet, Presentation and PDF.

    run_regression.py [--out DIR] [--only functional|formats] [--apps writer,sheet,...]

Runs against the installed Ubuntu package on an X display with a window
manager. It drives the real applications: start pages and editors through
the DevTools protocol (enabled for the test user only, see cdp.py), native
GTK file pickers and windows through xdotool. Every result is written to
DIR/results.json and DIR/results.md (feature x application and
format x render/edit/save/reopen), with what was checked and how.

Statuses: PASS, FAIL, NA (the engine has no such capability; the reason
is given), SKIP (not run because an earlier step failed).
"""

import argparse
import json
import os
import shutil
import stat
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cdp  # noqa: E402
import check  # noqa: E402
import sos  # noqa: E402
from sos import APPS, log  # noqa: E402

RESULTS = []
MARK = 'SOSQA%d' % (int(time.time()) % 100000)


def record(area, item, app, status, detail=''):
    RESULTS.append(dict(area=area, item=item, app=app, status=status, detail=str(detail)[:600]))
    log('%-4s %s / %s / %s: %s' % (status, area, item, app, str(detail)[:300]))


def result(area, item, app):
    return next((r for r in RESULTS if r['area'] == area and r['item'] == item and r['app'] == app), None)


def guarded(area, item, app):
    """decorator-free guard: with guard(...) as g: ...; exceptions become FAIL"""
    class G:
        def __enter__(self):
            return self

        def __exit__(self, et, ev, tb):
            if et is None:
                return False
            record(area, item, app, 'FAIL', 'exception: %s' % ''.join(traceback.format_exception_only(et, ev)).strip())
            log(''.join(traceback.format_exception(et, ev, tb)))
            sos.screenshot('error-%s-%s' % (app, item.replace(' ', '_')))
            return True
    return G()


# -- shared steps -----------------------------------------------------------------

def start_app(app, secs=120):
    """launch the application without documents; its start page"""
    t0 = time.time()
    sos.launch(app)
    t = sos.wait_target(lambda t: sos.is_start(t, app), secs)
    if not t:
        return None, time.time() - t0
    sp = sos.StartPage(t)
    end = time.time() + 60
    while time.time() < end and not sp.js("!!(window.SOS && SOS.recents && SOS.recents.ready())"):
        time.sleep(0.5)
    return sp, time.time() - t0


def open_direct(app, path, secs=150):
    """launch the application with a document; the document's editor"""
    before = sos.doc_ids()
    sos.launch(app, path)
    t = sos.wait_target(sos.is_doc, secs, exclude=before)
    if not t:
        return None
    ed = sos.Editor(t, app)
    ed.ready = ed.wait_ready()
    return ed


def new_doc_from(click, app, secs=120):
    """run click(); the new document tab it opens"""
    before = sos.doc_ids()
    how = click()
    t = sos.wait_target(sos.is_doc, secs, exclude=before)
    if not t:
        return None, how
    ed = sos.Editor(t, app)
    ed.ready = ed.wait_ready()
    return ed, how


def edit(ed, app, marker):
    """change the document the way a user does; returns (ok, how)"""
    if app == 'writer':
        ed.focus_canvas()
        ed.page.key('End', 'End', 35, modifiers=2)
        ed.page.type_text(' ' + marker)
        time.sleep(1.5)
        if ed.modified():
            return True, 'typed at the end of the document'
        ed.js("api.asc_AddText(' %s')" % marker)
        time.sleep(1)
        return bool(ed.modified()), 'keyboard input not taken; added through the editor API'
    if app == 'sheet':
        ed.focus_canvas()
        ed.page.key('Home', 'Home', 36, modifiers=2)
        for _ in range(3):
            ed.page.key('ArrowRight', 'ArrowRight', 39)
        ed.page.type_text(marker)
        ed.page.key('Enter', 'Enter', 13, text='\r')
        time.sleep(1.5)
        if ed.modified():
            return True, 'typed into cell D1'
        return False, 'typing into a cell did not change the workbook'
    if app == 'presentation':
        n0 = ed.js('return api.getCountPages()')
        ed.click('.ribtab > a[data-tab="home"]')
        time.sleep(0.5)
        how = ed.click('#id-toolbar-btn-add-slide')
        time.sleep(2)
        n1 = ed.js('return api.getCountPages()')
        if n0 is not None and n1 == n0 + 1:
            ed.slides = n1
            return True, 'Add Slide on the ribbon (%s click): %s -> %s slides' % (how, n0, n1)
        ed.js('api.AddSlide()')
        time.sleep(1)
        n1 = ed.js('return api.getCountPages()')
        ed.slides = n1
        return (n0 is not None and n1 == n0 + 1), 'ribbon Add Slide did not add one; API AddSlide: %s -> %s' % (n0, n1)
    if app == 'pdf':
        r = ed.js("var d=new Asc.asc_CCommentDataWord(null);d.asc_putText(%s);d.asc_putUserName('QA');"
                  "d.asc_putTime(''+Date.now());return api.asc_addComment(d)" % json.dumps(marker))
        time.sleep(1.5)
        return bool(ed.modified()), 'comment annotation added through the editor (id %s)' % r
    return False, 'no edit step'


def verify_in_editor(ed, app, marker, slides=None):
    """is the change there after reopening? (ok, detail)"""
    if app == 'writer':
        t = ed.js("var d=api.WordControl.m_oLogicDocument;d.SelectAll();var t=api.asc_GetSelectedText();"
                  "d.RemoveSelection();return t") or ''
        return marker in t, 'document text has the marker' if marker in t else 'text: %r' % t[:120]
    if app == 'sheet':
        v = ed.js("var ws=api.wbModel.getWorksheet(0),out=[];for(var r=0;r<20;r++)for(var c=0;c<10;c++){"
                  "var x=ws.getCell3(r,c).getValueWithoutFormat();if(x)out.push(x)}return out") or []
        return marker in v, 'cell values: %s' % v[:12]
    if app == 'presentation':
        n = ed.js('return api.getCountPages()')
        return (slides is not None and n == slides), '%s slides (expected %s)' % (n, slides)
    if app == 'pdf':
        v = ed.js("var d=api.getPDFDoc();return (d.annots||[]).concat(d.GetAllComments?[]:[]).map(function(a){"
                  "try{return a.GetContents()}catch(e){return ''}})") or []
        ok = any(marker in (x or '') for x in v)
        return ok, 'annotations: %s' % v[:6]
    return False, ''


def save(ed, app, picker_path, how='ctrl+s', secs=120):
    """save the open document. Answers the native picker with picker_path
    and the editor's own prompts. Returns dict(picker, prompts, path)."""
    info = {'picker': None, 'prompts': [], 'path': None}
    t0 = time.time() - 1
    if how == 'ctrl+s':
        ed.page.shortcut('s')
    elif how == 'menu':
        ed.open_file_menu()
        ed.click('#fm-btn-save')
    elif how == 'saveas':
        ed.open_file_menu()
        ed.click('#fm-btn-save-desktop')
    end = time.time() + secs
    while time.time() < end:
        w = sos.wait_window(sos.DIALOG_RX, 1)
        if w:
            info['picker'] = sos.file_dialog(picker_path, 'save')
            continue
        al = ed.alerts()
        if al:
            info['prompts'].append(al[0])
            ed.answer_alert()
            time.sleep(1)
            continue
        # done when the editor has nothing left unsaved and a file was written
        if not ed.modified():
            for p in [picker_path] + [picker_path + '.' + e for e in ('docx', 'xlsx', 'pptx', 'pdf')] + \
                     ([ed.path] if getattr(ed, 'path', None) else []):
                try:
                    if p and os.stat(p).st_mtime >= t0 and os.path.getsize(p) > 0:
                        info['path'] = p
                        break
                except OSError:
                    pass
            if info['path']:
                time.sleep(1.5)
                break
        time.sleep(1)
    return info


# -- functional tests ---------------------------------------------------------------

def functional(app, docs):
    A = 'functional'
    d = APPS[app]
    os.makedirs(docs, exist_ok=True)
    sos.kill_all()
    sp = None

    # 1 + 17 launch (offline: the whole run has no network, see the workflow)
    with guarded(A, '01 Launch', app):
        sp, secs = start_app(app)
        w = sos.main_window(app)
        if sp and w:
            record(A, '01 Launch', app, 'PASS', 'start page in %.0f s, window "%s", pid %s, own process (--app=%s)'
                   % (secs, w[1], w[2], app))
        else:
            record(A, '01 Launch', app, 'FAIL', 'no start page after %.0f s; windows: %s' % (secs, sos.windows()))
            return
    sos.screenshot('%s-01-start' % app)

    # 2 start page
    with guarded(A, '02 Start page', app):
        info = sp.js("""({app: SOS.currentApp().id, name: (document.querySelector('.sos-app-header__name')||{}).textContent,
            blank: document.querySelectorAll('.sos-card--blank').length,
            templates: document.querySelectorAll('.sos-card--template').length,
            open: document.querySelectorAll('.sos-card--open').length,
            recent: !!document.querySelector('#box-recent'),
            title: document.title})""") or {}
        ok = info.get('app') == app and info.get('recent') and (info.get('blank') or info.get('open')) and info.get('templates', 0) > 0
        record(A, '02 Start page', app, 'PASS' if ok else 'FAIL',
               'app=%(app)s, header "%(name)s", %(blank)s blank + %(templates)s template cards, %(open)s open cards, recent list %(recent)s' % dict(
                   {'app': '?', 'name': '?', 'blank': 0, 'templates': 0, 'open': 0, 'recent': False}, **info))

    saved = {}
    # 3 blank document, 12 save, 6 registration
    if d['blank']:
        with guarded(A, '03 Blank document', app):
            ed, how = new_doc_from(lambda: sp.click('.sos-card[data-key="blank:%s"]' % d['blank']), app)
            if not ed or not ed.ready:
                record(A, '03 Blank document', app, 'FAIL', 'no editor (%s click); alerts %s' % (how, ed and ed.alerts()))
            else:
                record(A, '03 Blank document', app, 'PASS', 'blank card (%s click) opened "%s" in %s'
                       % (how, ed.title(), ed.editor_kind().split('/apps/')[-1]))
                saved['editor'] = ed
    else:
        record(A, '03 Blank document', app, 'NA', 'EuroOffice PDF has no blank document; its first card is Open PDF (by design, Phase 3)')

    ed = saved.get('editor')
    if ed:
        with guarded(A, '12 Save', app):
            ok, how = edit(ed, app, MARK)
            target = os.path.join(docs, '%s-blank.%s' % (app, d['ext']))
            info = save(ed, app, target)
            p = info['path']
            good = p and check.contains(p, MARK) if app != 'presentation' else p and check.slides(p) == getattr(ed, 'slides', None)
            ed.path = p
            record(A, '12 Save', app, 'PASS' if good else 'FAIL',
                   'edit: %s; Ctrl+S on the new document -> picker "%s"; prompts %s; saved %s (%s); change in file: %s'
                   % (how, info['picker'], info['prompts'], p, p and check.describe(p), bool(good)))
            saved['blank'] = p
        with guarded(A, '06 Recent registration', app):
            time.sleep(2)
            e = saved.get('blank') and sos.recent_entry(app, saved['blank'])
            shown = sp.wait_recents(app, lambda l: any(x['path'] == saved.get('blank') for x in l), 15) or []
            ok = bool(e) and any(x['path'] == saved.get('blank') for x in shown)
            record(A, '06 Recent registration', app, 'PASS' if ok else 'FAIL',
                   'sos-recents.json: %s; on the start page: %s' % (e and {k: e.get(k) for k in ('origin', 'app', 'status')}, ok))

        # 13 Save As (same format, new name) and Export
        with guarded(A, '13 Save As', app):
            ed.edit2 = edit(ed, app, MARK + 'B')
            target = os.path.join(docs, '%s-saveas.%s' % (app, d['ext']))
            info = save(ed, app, target, how='saveas')
            p = info['path']
            ok = p == target and os.path.exists(target)
            time.sleep(2)
            e = sos.recent_entry(app, target)
            record(A, '13 Save As', app, 'PASS' if ok else 'FAIL',
                   'File > Save As -> picker "%s"; prompts %s; wrote %s (%s); recent entry origin %s; title now "%s"'
                   % (info['picker'], info['prompts'], p, p and check.describe(p), e and e.get('origin'), ed.title()))

        # 14 File menu
        with guarded(A, '14 File menu', app):
            notes = []
            opened = ed.open_file_menu()
            items = ed.page.try_eval("Array.from(document.querySelectorAll('#file-menu-panel .panel-menu li.fm-btn')).filter(e=>e.offsetParent!==null).map(e=>e.id.replace('fm-btn-','')+':'+e.innerText.trim())", ed.frame, default=[])
            notes.append('items: ' + ', '.join(items or []))
            checks = {}
            for item, panel, expect in (('info', '#panel-info', None), ('recent', '#panel-recentfiles', os.path.basename(saved.get('blank') or 'x')),
                                        ('sos-about', '#panel-sos-about', 'Secure Office Suite'), ('sos-export', '#panel-sos-export', 'PDF'),
                                        ('sos-new', '#panel-sos-new', None)):
                if not ed.visible('#fm-btn-' + item):
                    checks[item] = 'missing'
                    continue
                ed.click('#fm-btn-' + item)
                time.sleep(1.2)
                txt = ed.page.try_eval("(document.querySelector(%s)||{}).innerText||''" % json.dumps(panel), ed.frame, default='') or ''
                checks[item] = 'ok' if txt and (expect is None or expect in txt) else 'panel %s: %r' % (panel, txt[:80])
            # Export a PDF copy from the File menu
            exp = os.path.join(docs, '%s-export.pdf' % app)
            if app != 'pdf' and ed.visible('#fm-btn-sos-export'):
                ed.click('#fm-btn-sos-export')
                time.sleep(1)
                btn = ed.page.try_eval("(function(){var b=Array.from(document.querySelectorAll('#panel-sos-export .sos-bs-format')).find(b=>/^PDF$/i.test(b.querySelector('.sos-bs-ext').innerText.trim()));if(!b)return null;b.setAttribute('data-qa','pdf');return true})()", ed.frame)
                if btn:
                    t0 = time.time()
                    ed.click('#panel-sos-export .sos-bs-format[data-qa="pdf"]')
                    pk = sos.file_dialog(exp, 'save')
                    ok = sos.wait_file(exp, t0 - 1, 60)
                    checks['export-pdf'] = 'ok (%s pages)' % check.pdf_pages(exp) if ok and check.kind(exp) == 'pdf' else 'picker %s, file %s' % (pk, ok)
            ed.close_file_menu()
            bad = {k: v for k, v in checks.items() if not v.startswith('ok')}
            record(A, '14 File menu', app, 'PASS' if opened and not bad else 'FAIL',
                   'menu opened: %s; %s; panels: %s' % (opened, notes[0], checks))

        # 15 ribbon
        with guarded(A, '15 Ribbon commands', app):
            tabs = ed.page.try_eval("Array.from(document.querySelectorAll('.ribtab > a[data-tab]')).filter(a=>a.offsetParent!==null).map(a=>a.getAttribute('data-tab'))", ed.frame, default=[]) or []
            switched = []
            for t in tabs:
                if t == 'file':
                    continue
                ed.click('.ribtab > a[data-tab="%s"]' % t)
                time.sleep(0.4)
                act = ed.page.try_eval("!!document.querySelector('section.panel[data-tab=\"%s\"].active')" % t, ed.frame)
                switched.append(t if act else t + '(!)')
            ed.click('.ribtab > a[data-tab="home"]')
            cmd = ''
            ok_cmd = False
            if app in ('writer', 'sheet'):
                ed.focus_canvas()
                if app == 'writer':
                    ed.js("api.WordControl.m_oLogicDocument.SelectAll()")
                b0 = ed.page.try_eval("document.querySelector('#id-toolbar-btn-bold button, #id-toolbar-btn-bold').classList.contains('active')", ed.frame)
                ed.click('#id-toolbar-btn-bold')
                time.sleep(1)
                b1 = ed.page.try_eval("(function(){var b=document.querySelector('#id-toolbar-btn-bold');var x=b.querySelector('button')||b;return x.classList.contains('active')})()", ed.frame)
                ok_cmd = b0 != b1 and bool(ed.modified())
                cmd = 'Bold: pressed %s -> %s, document modified %s' % (b0, b1, ed.modified())
                ed.page.shortcut('z')
            elif app == 'presentation':
                ok_cmd, cmd = edit(ed, app, MARK)
            switched_ok = tabs and not [s for s in switched if s.endswith('(!)')]
            record(A, '15 Ribbon commands', app, 'PASS' if switched_ok and ok_cmd else 'FAIL',
                   'tabs %s; %s' % (switched, cmd))
        sos.screenshot('%s-15-ribbon' % app)

    # 4 + 5 template
    with guarded(A, '04 Template selection', app):
        sp.click('.sos-card--template')
        time.sleep(1.5)
        prev = sp.js("(function(){var d=document.querySelector('.sos-dlg-preview');return d&&d.open?{name:(d.querySelector('.sos-preview__name')||{}).textContent,meta:(d.querySelector('.sos-preview__meta')||{}).innerText}:null})()")
        record(A, '04 Template selection', app, 'PASS' if prev else 'FAIL', 'first template card opened the preview: %s' % prev)
    with guarded(A, '05 Document from template', app):
        tpl, how = new_doc_from(lambda: sp.click('.sos-dlg-preview .sos-preview__create'), app)
        if not tpl or not tpl.ready:
            record(A, '05 Document from template', app, 'FAIL', 'Create did not open an editor (%s); alerts %s' % (how, tpl and tpl.alerts()))
        else:
            content = {'writer': "return api.getCountPages()+' pages'",
                       'sheet': "return api.asc_getWorksheetsCount()+' sheets'",
                       'presentation': "return api.getCountPages()+' slides'",
                       'pdf': "return api.getCountPages()+' pages'"}[app]
            c = tpl.js(content)
            target = os.path.join(docs, '%s-template.%s' % (app, d['ext']))
            info = save(tpl, app, target)
            time.sleep(2)
            e = info['path'] and sos.recent_entry(app, info['path'])
            ok = info['path'] and e and e.get('origin') == 'template'
            record(A, '05 Document from template', app, 'PASS' if ok else 'FAIL',
                   'untitled "%s" with %s; saved via picker "%s" to %s; recent origin %s, template %s'
                   % (tpl.title(), c, info['picker'], info['path'], e and e.get('origin'), e and e.get('template')))
            saved['template'] = info['path']

    # 11 native Open dialog (from the start page)
    with guarded(A, '11 Native Open dialog', app):
        src = sos.fresh_copy(os.path.join(sos.samples_dir(), 'Sample.' + d['formats'][0 if app != 'writer' else 1]),
                             docs, 'Opened-%s.%s' % (app, d['formats'][0 if app != 'writer' else 1]))
        def click_open():
            return sp.click('#sos-btn-open-other') if sp.rect('#sos-btn-open-other') else sp.click('.sos-card--open')
        before = sos.doc_ids()
        how = click_open()
        title = sos.file_dialog(src, 'open')
        t = sos.wait_target(sos.is_doc, 90, exclude=before)
        ed2 = sos.Editor(t, app) if t else None
        ok = ed2 and ed2.wait_ready()
        record(A, '11 Native Open dialog', app, 'PASS' if ok else 'FAIL',
               '"Open other" (%s click) -> picker "%s" -> %s opened: %s' % (how, title, os.path.basename(src), ed2 and ed2.title()))

    # 16 restart (closing the window the way a user does)
    with guarded(A, '16 Application restart', app):
        closed = sos.close_window(app)
        for w in sos.windows():
            if 'EuroOffice' in w[1] and w[1] != sos.main_window(app):
                pass
        if not closed:
            # unsaved-changes question from the Qt shell: answer "don't save"
            sos.screenshot('%s-16-close-question' % app)
            sos.kill_all()
        sp.close()
        sp, secs = start_app(app)
        lst = sp and sp.recents(app) or []
        have = [os.path.basename(x['path']) for x in lst]
        ok = closed and sp and saved.get('blank', 'x') and any(x['path'] == saved.get('blank') for x in lst) if d['blank'] else bool(sp)
        record(A, '16 Application restart', app, 'PASS' if ok else 'FAIL',
               'closed by Alt+F4: %s; restarted in %.0f s; recent list after restart: %s' % (closed, secs, have))

    # 7 open from recents, 8 pin/unpin, 9 remove, 10 clear
    lst = sp.recents(app) or []
    if lst:
        first = lst[0]
        with guarded(A, '07 Recent-document opening', app):
            rid = sp.row_id(first['path'])
            before = sos.doc_ids()
            how = sp.click('#%s .col-name' % rid) if rid else None
            t = sos.wait_target(sos.is_doc, 90, exclude=before)
            ed3 = sos.Editor(t, app) if t else None
            ok = ed3 and ed3.wait_ready()
            record(A, '07 Recent-document opening', app, 'PASS' if ok else 'FAIL',
                   'clicked row %s (%s) -> "%s"' % (os.path.basename(first['path']), how, ed3 and ed3.title()))
        with guarded(A, '08 Pin and unpin', app):
            target = lst[-1]
            rid = sp.row_id(target['path'])
            sp.click('#%s-pin-btn' % rid)
            l1 = sp.wait_recents(app, lambda l: any(x['path'] == target['path'] and x.get('pinned') for x in l))
            e1 = sos.recent_entry(app, target['path'])
            top = (l1 or [{}])[0].get('path') == target['path']
            rid = sp.row_id(target['path'])
            sp.click('#%s-pin-btn' % rid)
            sp.wait_recents(app, lambda l: any(x['path'] == target['path'] and not x.get('pinned') for x in l))
            e2 = sos.recent_entry(app, target['path'])
            ok = e1 and e1.get('pinned') and top and e2 and not e2.get('pinned')
            record(A, '08 Pin and unpin', app, 'PASS' if ok else 'FAIL',
                   'pin: saved %s, moved to top %s; unpin: saved %s' % (e1 and e1.get('pinned'), top, e2 and e2.get('pinned')))
            # pin again for the clear test
            sp.click('#%s-pin-btn' % sp.row_id(target['path']))
            sp.wait_recents(app, lambda l: any(x['path'] == target['path'] and x.get('pinned') for x in l))
            pinned = target['path']
        with guarded(A, '09 Remove recent entry', app):
            lst = sp.recents(app) or []
            victim = next((x for x in lst if not x.get('pinned')), None)
            if not victim:
                record(A, '09 Remove recent entry', app, 'SKIP', 'only pinned entries left')
            else:
                rid = sp.row_id(victim['path'])
                sp.click('#%s-more-btn' % rid)
                time.sleep(0.7)
                sp.js("(function(){var a=Array.from(document.querySelectorAll('#pp-menu-files a.dd-item')).find(a=>a.innerText.trim()===utils.Lang.menuRemoveModel);a&&a.setAttribute('data-qa','remove')})()")
                sp.click('#pp-menu-files a[data-qa="remove"]')
                l2 = sp.wait_recents(app, lambda l: all(x['path'] != victim['path'] for x in l))
                gone = all(x['path'] != victim['path'] for x in (l2 or [])) and not sos.recent_entry(app, victim['path'])
                still = os.path.exists(victim['path'])
                record(A, '09 Remove recent entry', app, 'PASS' if gone and still else 'FAIL',
                       'More > Remove from list: entry gone %s, document still on disk %s' % (gone, still))
        with guarded(A, '10 Clear history', app):
            rid = sp.row_id(pinned)
            sp.click('#%s-more-btn' % rid)
            time.sleep(0.7)
            sp.js("(function(){var a=Array.from(document.querySelectorAll('#pp-menu-files a.dd-item')).find(a=>a.innerText.trim()===utils.Lang.menuClear);a&&a.setAttribute('data-qa','clear')})()")
            sp.click('#pp-menu-files a[data-qa="clear"]')
            time.sleep(0.8)
            had_check = sp.js("!!document.querySelector('.dlg-sos-recent .sos-dlg__check input')")
            sp.click('.dlg-sos-recent .sos-dlg__buttons .btn[data-index="0"]')
            l3 = sp.wait_recents(app, lambda l: all(x.get('pinned') for x in l))
            keep = [x['path'] for x in (l3 or [])]
            ok1 = keep == [pinned]
            # clear again, now with "also pinned"
            sp.click('#%s-more-btn' % sp.row_id(pinned))
            time.sleep(0.7)
            sp.js("(function(){var a=Array.from(document.querySelectorAll('#pp-menu-files a.dd-item')).find(a=>a.innerText.trim()===utils.Lang.menuClear);a&&a.setAttribute('data-qa','clear')})()")
            sp.click('#pp-menu-files a[data-qa="clear"]')
            time.sleep(0.8)
            sp.js("(function(){var c=document.querySelector('.dlg-sos-recent .sos-dlg__check input');c&&(c.checked=true)})()")
            sp.click('.dlg-sos-recent .sos-dlg__buttons .btn[data-index="0"]')
            l4 = sp.wait_recents(app, lambda l: not l)
            files_kept = all(os.path.exists(p) for p in [pinned] + [v for v in saved.values() if isinstance(v, str)])
            ok = ok1 and l4 == [] and files_kept
            record(A, '10 Clear history', app, 'PASS' if ok else 'FAIL',
                   'Clear: pinned kept %s (dialog offered "also pinned": %s); Clear with pinned: list empty %s; documents untouched %s'
                   % (keep, had_check, l4 == [], files_kept))
            # other applications' lists are not touched
            others = {a: len(v) for a, v in sos.read_recents().get('lists', {}).items() if a != app}
            record(A, '10 Clear history (other apps untouched)', app, 'PASS' if all(others.values()) or not others else 'FAIL',
                   'other lists after clearing %s: %s' % (app, others))
    else:
        for it in ('07 Recent-document opening', '08 Pin and unpin', '09 Remove recent entry', '10 Clear history'):
            record(A, it, app, 'SKIP', 'recent list empty after restart')

    # 20 missing and inaccessible files
    with guarded(A, '20 Missing file in recents', app):
        ext = d['formats'][0 if app != 'writer' else 1]
        p = sos.fresh_copy(os.path.join(sos.samples_dir(), 'Sample.' + ext), docs, 'Vanishing-%s.%s' % (app, ext))
        ed4 = open_direct(app, p)
        ok_open = ed4 and ed4.ready
        time.sleep(2)
        os.remove(p)
        sp.page.send('Page.reload')
        time.sleep(4)
        sp.js("SOS.recents.check()")
        lst = sp.wait_recents(app, lambda l: any(x['path'] == p and x.get('status') == 'missing' for x in l), 30) or []
        e = next((x for x in lst if x['path'] == p), None)
        rid = sp.row_id(p)
        before = sos.doc_ids()
        sp.click('#%s .col-name' % rid) if rid else None
        time.sleep(3)
        dlg = sp.js("(function(){var d=document.querySelector('.dlg-sos-recent');return d?d.innerText.slice(0,200):null})()")
        opened = bool(sos.doc_ids() - before)
        if dlg:
            sp.js("(function(){var b=Array.from(document.querySelectorAll('.dlg-sos-recent .sos-dlg__buttons .btn')).find(b=>b.innerText.trim()===utils.Lang.sosRecentRemove);b&&b.setAttribute('data-qa','rm')})()")
            sp.click('.dlg-sos-recent .btn[data-qa="rm"]')
        l2 = sp.wait_recents(app, lambda l: all(x['path'] != p for x in l), 15) or []
        removed = all(x['path'] != p for x in l2)
        alive = bool(sos.app_pids(app))
        ok = ok_open and e and e.get('status') == 'missing' and dlg and not opened and removed and alive
        record(A, '20 Missing file in recents', app, 'PASS' if ok else 'FAIL',
               'opened then deleted; row status %s; click -> dialog %r; no editor opened %s; Remove from list worked %s; app running %s'
               % (e and e.get('status'), dlg, not opened, removed, alive))
    with guarded(A, '20 Inaccessible file', app):
        ext = d['formats'][0 if app != 'writer' else 1]
        p = sos.fresh_copy(os.path.join(sos.samples_dir(), 'Sample.' + ext), docs, 'Locked-%s.%s' % (app, ext))
        os.chmod(p, 0)
        before = sos.doc_ids()
        sos.launch(app, p)
        time.sleep(12)
        new = sos.doc_ids() - before
        msgs = []
        for t in [x for x in cdp.targets() if x['id'] in new]:
            e5 = sos.Editor(t, app)
            msgs += e5.alerts()
            e5.close()
        qt = [w[1] for w in sos.windows() if 'EuroOffice' not in w[1] and w[1]]
        alive = bool(sos.app_pids(app))
        sos.screenshot('%s-20-inaccessible' % app)
        record(A, '20 Inaccessible file', app, 'PASS' if alive else 'FAIL',
               'no read permission: new tabs %d, editor messages %s, other windows %s, application still running %s'
               % (len(new), msgs, qt, alive))
        sos.close_stray_dialogs()
        os.chmod(p, stat.S_IRUSR | stat.S_IWUSR)
    with guarded(A, '20 Nonexistent path on the command line', app):
        before = sos.doc_ids()
        sos.launch(app, os.path.join(docs, 'does-not-exist.' + d['formats'][0]))
        time.sleep(10)
        alive = bool(sos.app_pids(app))
        new = sos.doc_ids() - before
        record(A, '20 Nonexistent path on the command line', app, 'PASS' if alive else 'FAIL',
               'application still running %s; tabs opened %d; windows %s' % (alive, len(new), [w[1] for w in sos.windows()]))
        sos.close_stray_dialogs()
    sos.screenshot('%s-20-end' % app)
    sos.kill_all()


# -- format regression ----------------------------------------------------------------

NOT_WRITABLE = {'doc', 'xls', 'ppt'}   # x2t reads these binary formats but has no writer


def formats(docs):
    A = 'formats'
    os.makedirs(docs, exist_ok=True)
    for app, d in APPS.items():
        for ext in d['formats']:
            sos.kill_all()
            src = sos.fresh_copy(os.path.join(sos.samples_dir(), 'Sample.' + ext), docs, 'Fmt-%s.%s' % (ext, ext))
            # render (= 18 direct document opening)
            ed = None
            with guarded(A, 'render', ext):
                ed = open_direct(app, src)
                if not ed or not ed.ready:
                    record(A, 'render', ext, 'FAIL', 'did not load: %s' % (ed and ed.alerts()))
                    ed = None
                else:
                    size = ed.js({'writer': "return api.getCountPages()+' page(s)'", 'sheet': "return api.asc_getWorksheetsCount()+' sheet(s)'",
                                  'presentation': "return api.getCountPages()+' slide(s)'", 'pdf': "return api.getCountPages()+' page(s)'"}[app])
                    record(A, 'render', ext, 'PASS', 'opened directly in %s: "%s", %s, no error message %s'
                           % (d['name'], ed.title(), size, ed.alerts() == []))
                    sos.screenshot('fmt-%s-render' % ext)
            if not ed:
                for it in ('edit', 'save', 'reopen'):
                    record(A, it, ext, 'SKIP', 'not loaded')
                continue
            ed.path = src
            with guarded(A, 'edit', ext):
                ok, how = edit(ed, app, MARK)
                record(A, 'edit', ext, 'PASS' if ok else 'FAIL', how)
            saved_path = None
            with guarded(A, 'save', ext):
                target = os.path.join(docs, 'Fmt-%s-saved.%s' % (ext, d['ext'] if ext in NOT_WRITABLE else ext))
                info = save(ed, app, target)
                p = info['path']
                if not p:
                    record(A, 'save', ext, 'FAIL', 'nothing written; picker %s; prompts %s; alerts %s' % (info['picker'], info['prompts'], ed.alerts()))
                else:
                    has = check.contains(p, MARK) if app != 'presentation' else check.slides(p) == getattr(ed, 'slides', -1)
                    k = check.kind(p)
                    in_place = os.path.abspath(p) == os.path.abspath(src)
                    note = ('saved in place as %s' % ext.upper()) if in_place else \
                           ('Ctrl+S asked where to save: picker "%s" -> %s' % (info['picker'], os.path.basename(p)))
                    if ext in NOT_WRITABLE and not in_place:
                        note += ' (the engine cannot write %s; it offers %s, as upstream)' % (ext.upper(), d['ext'].upper())
                    exp_kind = check.EXPECTED_KIND[p.rsplit('.', 1)[-1].lower()]
                    good = has and k == exp_kind
                    record(A, 'save', ext, 'PASS' if good else 'FAIL', '%s; prompts %s; file %s; change in file %s'
                           % (note, info['prompts'], check.describe(p), has))
                    saved_path = p if good else None
            if not saved_path:
                record(A, 'reopen', ext, 'SKIP', 'not saved')
                continue
            with guarded(A, 'reopen', ext):
                slides = getattr(ed, 'slides', None)
                ed.close()
                sos.kill_all()
                ed2 = open_direct(app, saved_path)
                if not ed2 or not ed2.ready:
                    record(A, 'reopen', ext, 'FAIL', 'saved file did not load: %s' % (ed2 and ed2.alerts()))
                    continue
                ok, det = verify_in_editor(ed2, app, MARK, slides)
                record(A, 'reopen', ext, 'PASS' if ok else 'FAIL', 'reopened %s: %s' % (os.path.basename(saved_path), det))
                ed2.close()
    sos.kill_all()


# -- report -------------------------------------------------------------------------

def report(out):
    with open(os.path.join(out, 'results.json'), 'w') as f:
        json.dump({'marker': MARK, 'results': RESULTS}, f, indent=1)
    icon = {'PASS': 'PASS', 'FAIL': '**FAIL**', 'NA': 'n/a', 'SKIP': 'skipped'}
    lines = ['# Phase 9 regression results (Ubuntu)', '']
    fn = [r for r in RESULTS if r['area'] == 'functional']
    if fn:
        apps = [a for a in APPS if any(r['app'] == a for r in fn)]
        items = []
        for r in fn:
            if r['item'] not in items:
                items.append(r['item'])
        lines += ['## Functional (feature x application)', '', '| Feature | ' + ' | '.join(APPS[a]['name'] for a in apps) + ' |',
                  '|---|' + '---|' * len(apps)]
        for it in items:
            cells = []
            for a in apps:
                r = result('functional', it, a)
                cells.append(icon[r['status']] if r else '')
            lines.append('| %s | %s |' % (it, ' | '.join(cells)))
        lines.append('')
    fm = [r for r in RESULTS if r['area'] == 'formats']
    if fm:
        lines += ['## Formats (render / edit / save / reopen)', '', '| Format | App | Render | Edit | Save | Reopen |', '|---|---|---|---|---|---|']
        for app, d in APPS.items():
            for ext in d['formats']:
                cells = [icon[result('formats', s, ext)['status']] if result('formats', s, ext) else '' for s in ('render', 'edit', 'save', 'reopen')]
                lines.append('| %s | %s | %s |' % (ext.upper(), d['name'].split()[-1], ' | '.join(cells)))
        lines.append('')
    lines += ['## Details', '']
    for r in RESULTS:
        lines.append('- %s %s / %s / %s: %s' % (r['status'], r['area'], r['item'], r['app'], r['detail'].replace('\n', ' ')))
    with open(os.path.join(out, 'results.md'), 'w') as f:
        f.write('\n'.join(lines) + '\n')
    fails = [r for r in RESULTS if r['status'] == 'FAIL']
    log('%d results, %d failures' % (len(RESULTS), len(fails)))
    return fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=sos.OUT)
    ap.add_argument('--only', choices=['functional', 'formats'])
    ap.add_argument('--apps', default='writer,sheet,presentation,pdf')
    a = ap.parse_args()
    sos.OUT = a.out
    os.makedirs(a.out, exist_ok=True)
    docs = os.path.join(os.path.expanduser('~/Documents'), 'sos-regression')
    shutil.rmtree(docs, ignore_errors=True)
    os.makedirs(docs)
    log('DevTools switch in', sos.enable_devtools(), '; marker', MARK)
    try:
        if a.only in (None, 'functional'):
            for app in a.apps.split(','):
                functional(app, os.path.join(docs, app))
        if a.only in (None, 'formats'):
            formats(os.path.join(docs, 'formats'))
    finally:
        sos.kill_all()
        fails = report(a.out)
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
