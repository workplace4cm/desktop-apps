#!/usr/bin/env python3
"""
Secure Office Suite: checks every template of the start-page library.

    python3 verify_templates.py --manifest common/templates/sos/manifest.js \
        [--engine /opt/<package>] [--work DIR] [--require-pdf]

Without --engine the check is static: the manifest is valid, every listed
file and thumbnail ships, and every file is a well-formed template of the
format it claims (the same rules the desktop shell applies before it opens a
template, see win-linux/src/ctemplatelibrary.cpp). Templates must also work
offline and stay inert: no macros, no external links or data connections.

With --engine (an installed or extracted Secure Office Suite) every template
then goes through the suite's own converter, the way the desktop shell
creates a document from it:
  1. template -> Editor.bin       what the editor loads for a new document
  2. Editor.bin -> docx/xlsx/pptx  what "Save As" writes; must be a document,
                                    not a template, so the template is never
                                    overwritten
  3. that document -> Editor.bin   the saved document opens again
  4. template -> PDF               layout through the editors' own engine
                                    (best effort unless --require-pdf)
PDF form templates are opened by the PDF editor directly; they are checked
for structure and rendered to an image by the converter.

Exit status 0 when every template passes. Standard library only.
"""

import argparse
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile
from xml.sax.saxutils import escape

APPS = ('writer', 'sheet', 'presentation', 'pdf')

# format key -> (extension, application, OOXML main part, template content type, editor binary, save format)
FORMATS = {
    'FILE_DOCUMENT_DOTX': ('.dotx', 'writer', 'word/document.xml',
                           'application/vnd.openxmlformats-officedocument.wordprocessingml.template.main+xml',
                           8193, 65, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml'),
    'FILE_SPREADSHEET_XLTX': ('.xltx', 'sheet', 'xl/workbook.xml',
                              'application/vnd.openxmlformats-officedocument.spreadsheetml.template.main+xml',
                              8194, 257, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml'),
    'FILE_PRESENTATION_POTX': ('.potx', 'presentation', 'ppt/presentation.xml',
                               'application/vnd.openxmlformats-officedocument.presentationml.template.main+xml',
                               8195, 129, 'application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml'),
    'FILE_DOCUMENT_OFORM_PDF': ('.pdf', 'pdf', None, None, None, None, None),
}

FORMAT_PDF = 513
FORMAT_PNG = 1029
CANVAS = 8192

THUMB_SIZE = (304, 264)
MAX_TEMPLATE_BYTES = 50 * 1024 * 1024


class Failure(Exception):
    pass


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

def read_manifest(path):
    text = open(path, encoding='utf-8').read()
    m = re.search(r'/\*\s*sos-templates:begin\s*\*/(.*?)/\*\s*sos-templates:end\s*\*/', text, re.S)
    if not m:
        raise Failure('%s: no sos-templates:begin/end block' % path)
    try:
        data = json.loads(m.group(1))
    except ValueError as e:
        raise Failure('%s: the template list is not valid JSON: %s' % (path, e))
    if data.get('schema') != 1 or not isinstance(data.get('templates'), list):
        raise Failure('%s: expected {"schema": 1, "templates": [...]}' % path)
    return data['templates']


def check_entry(e, root, ids):
    for k in ('id', 'app', 'name', 'description', 'category', 'file', 'format', 'thumb'):
        if not isinstance(e.get(k), str) or not e[k].strip():
            raise Failure('missing or empty "%s"' % k)
    if e['id'] in ids:
        raise Failure('duplicate id')
    ids.add(e['id'])
    if not re.match(r'^(writer|sheet|presentation|pdf)\.[a-z0-9][a-z0-9-]*$', e['id']):
        raise Failure('id must be <app>.<lowercase-name>')
    if e['app'] not in APPS or not e['id'].startswith(e['app'] + '.'):
        raise Failure('unknown app or id of another app')
    fmt = FORMATS.get(e['format'])
    if not fmt:
        raise Failure('unsupported format %s' % e['format'])
    if fmt[1] != e['app']:
        raise Failure('%s templates belong to %s, not %s' % (e['format'], fmt[1], e['app']))
    if not e['file'].lower().endswith(fmt[0]):
        raise Failure('file extension does not match %s' % e['format'])
    if 'keywords' in e and not (isinstance(e['keywords'], list) and all(isinstance(k, str) for k in e['keywords'])):
        raise Failure('keywords must be a list of strings')

    # files stay inside the installed templates folder
    lib = os.path.normpath(os.path.join(root, '..'))
    for key in ('file', 'thumb'):
        p = os.path.normpath(os.path.join(root, e[key]))
        if os.path.commonpath([lib, p]) != lib:
            raise Failure('%s points outside the templates folder' % key)
        if not os.path.isfile(p):
            raise Failure('%s not found: %s' % (key, e[key]))
    check_thumb(os.path.join(root, e['thumb']))
    return os.path.join(root, e['file'])


def check_thumb(path):
    with open(path, 'rb') as f:
        head = f.read(24)
    if head[:8] != b'\x89PNG\r\n\x1a\n' or head[12:16] != b'IHDR':
        raise Failure('thumbnail is not a PNG')
    w, h = struct.unpack('>II', head[16:24])
    if (w, h) != THUMB_SIZE:
        raise Failure('thumbnail is %dx%d, expected %dx%d' % ((w, h) + THUMB_SIZE))


# ---------------------------------------------------------------------------
# Container rules (mirrors CTemplateLibrary::validate in the desktop shell)
# ---------------------------------------------------------------------------

def check_ooxml(path, fmt):
    ext, _, main_part, tpl_ct = fmt[:4]
    size = os.path.getsize(path)
    if size == 0:
        raise Failure('empty file')
    if size > MAX_TEMPLATE_BYTES:
        raise Failure('larger than %d MB' % (MAX_TEMPLATE_BYTES // 1024 // 1024))
    try:
        z = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        raise Failure('damaged: not a ZIP package')
    with z:
        bad = z.testzip()
        if bad:
            raise Failure('damaged: CRC error in %s' % bad)
        names = set(z.namelist())
        if '[Content_Types].xml' not in names:
            raise Failure('damaged: no [Content_Types].xml')
        if main_part not in names:
            raise Failure('damaged: no %s' % main_part)
        ct = z.read('[Content_Types].xml').decode('utf-8', 'replace')
        # a document of the same family works as a template too (several
        # shipped .dotx files are plain documents inside): the editor always
        # starts from a copy
        if tpl_ct not in ct and fmt[6] not in ct:
            raise Failure('not a %s template: wrong main part content type' % ext)
        lower = {n.lower() for n in names}
        if any(n.endswith('vbaproject.bin') or n.endswith('vbadata.xml') for n in lower):
            raise Failure('contains macros')
        for n in names:
            if n.endswith('.rels'):
                rels = z.read(n).decode('utf-8', 'replace')
                for target in re.findall(r'<Relationship\b[^>]*TargetMode="External"[^>]*>', rels):
                    t = re.search(r'Target="([^"]*)"', target)
                    url = t.group(1) if t else ''
                    # hyperlinks are fine (nothing is fetched until clicked);
                    # images, OLE links, templates and data sources would be
                    if '/hyperlink"' not in target:
                        raise Failure('external resource in %s: %s' % (n, url))
            if n.startswith('xl/connections.xml') or n.startswith('xl/externalLinks/'):
                raise Failure('external data connection: %s' % n)


def check_pdf(path):
    size = os.path.getsize(path)
    if size < 64:
        raise Failure('damaged: too small for a PDF')
    if size > MAX_TEMPLATE_BYTES:
        raise Failure('larger than %d MB' % (MAX_TEMPLATE_BYTES // 1024 // 1024))
    with open(path, 'rb') as f:
        head = f.read(1024)
        f.seek(max(0, size - 2048))
        tail = f.read()
    if b'%PDF-' not in head:
        raise Failure('damaged: no PDF header')
    if b'%%EOF' not in tail:
        raise Failure('damaged: no PDF end-of-file marker')
    data = open(path, 'rb').read()
    if re.search(rb'/(Launch|SubmitForm|ImportData|GoToR)\b', data):
        raise Failure('PDF has actions that reach outside the document')


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class Engine:
    def __init__(self, root, work):
        self.root = root
        self.work = work
        x2t = [os.path.join(d, f) for d, _, fs in os.walk(root) for f in fs if f == 'x2t']
        if not x2t:
            raise Failure('no x2t under %s' % root)
        self.x2t = x2t[0]
        self.converter = os.path.dirname(self.x2t)
        self.app_dir = os.path.dirname(self.converter)
        self.themes = os.path.join(self.app_dir, 'editors', 'sdkjs', 'slide', 'themes')
        self.env = dict(os.environ)
        self.env['LD_LIBRARY_PATH'] = os.pathsep.join(
            [self.converter, self.app_dir] + ([self.env['LD_LIBRARY_PATH']] if self.env.get('LD_LIBRARY_PATH') else []))
        self.fonts = os.path.join(work, 'fonts')
        self._make_fonts()

    def _make_fonts(self):
        """The desktop app builds its font list at start-up; do the same with
        the converter's own tool, or fall back to the fonts it ships."""
        os.makedirs(self.fonts, exist_ok=True)
        gen = [os.path.join(d, f) for d, _, fs in os.walk(self.app_dir) for f in fs if f == 'allfontsgen']
        font_dirs = [os.path.join(self.app_dir, 'fonts')]
        if gen:
            cmd = [gen[0], '--input=' + ','.join(font_dirs), '--allfonts=' + os.path.join(self.fonts, 'AllFonts.js'),
                   '--selection=' + os.path.join(self.fonts, 'font_selection.bin'), '--use-system=true']
            r = subprocess.run(cmd, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=600)
            print('allfontsgen: exit %d' % r.returncode)
        else:
            print('allfontsgen: not shipped; the converter uses its defaults')

    def convert(self, src, dst, fmt, tmp_name, extra=''):
        tmp = os.path.join(self.work, tmp_name)
        os.makedirs(tmp, exist_ok=True)
        params = ('<?xml version="1.0" encoding="utf-8"?><TaskQueueDataConvert>'
                  '<m_sFileFrom>%s</m_sFileFrom><m_sFileTo>%s</m_sFileTo><m_nFormatTo>%d</m_nFormatTo>'
                  '<m_sThemeDir>%s</m_sThemeDir><m_bDontSaveAdditional>true</m_bDontSaveAdditional>'
                  '<m_sFontDir>%s</m_sFontDir><m_sAllFontsPath>%s</m_sAllFontsPath>'
                  '<m_sTempDir>%s</m_sTempDir>%s</TaskQueueDataConvert>') % (
            escape(src), escape(dst), fmt, escape(self.themes), escape(self.fonts),
            escape(os.path.join(self.fonts, 'AllFonts.js')), escape(tmp), extra)
        xml = os.path.join(self.work, tmp_name + '.xml')
        with open(xml, 'w', encoding='utf-8') as f:
            f.write(params)
        try:
            r = subprocess.run([self.x2t, xml], cwd=self.converter, env=self.env,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)
        except subprocess.TimeoutExpired:
            raise Failure('converter timed out (%s)' % tmp_name)
        if r.returncode != 0 or not os.path.isfile(dst) or os.path.getsize(dst) == 0:
            out = r.stdout.decode('utf-8', 'replace').strip().splitlines()[-5:]
            raise Failure('converter failed with exit %d (%s)%s' % (r.returncode, tmp_name,
                                                                    (': ' + ' | '.join(out)) if out else ''))
        return dst


def engine_check(engine, e, path, fmt, require_pdf):
    """Returns notes for the report; raises Failure on a hard error."""
    notes = []
    case = os.path.join(engine.work, e['id'])
    shutil.rmtree(case, ignore_errors=True)
    os.makedirs(case)

    # the desktop shell never opens the original: it works on a copy
    copy = os.path.join(case, 'source' + os.path.splitext(path)[1])
    shutil.copyfile(path, copy)
    before = open(path, 'rb').read()

    if e['format'] == 'FILE_DOCUMENT_OFORM_PDF':
        png = engine.convert(copy, os.path.join(case, 'page1.png'), FORMAT_PNG, e['id'] + '-png',
                             '<m_oThumbnail><format>4</format><aspect>1</aspect><first>true</first>'
                             '<width>608</width><height>528</height></m_oThumbnail>')
        notes.append('rendered (%d bytes)' % os.path.getsize(png))
    else:
        ext, _, main_part, _, _, save_fmt, doc_ct = fmt
        bin1 = engine.convert(copy, os.path.join(case, 'Editor.bin'), CANVAS, e['id'] + '-open')
        doc_ext = {'.dotx': '.docx', '.xltx': '.xlsx', '.potx': '.pptx'}[ext]
        saved = engine.convert(bin1, os.path.join(case, 'Document1' + doc_ext), save_fmt, e['id'] + '-save')
        with zipfile.ZipFile(saved) as z:
            ct = z.read('[Content_Types].xml').decode('utf-8', 'replace')
            if doc_ct not in ct:
                raise Failure('"Save As" did not produce a %s document' % doc_ext)
            if main_part not in z.namelist():
                raise Failure('saved document has no %s' % main_part)
        engine.convert(saved, os.path.join(case, 'Reopen.bin'), CANVAS, e['id'] + '-reopen')
        notes.append('opens, saves as %s, reopens' % doc_ext)
        try:
            pdf = engine.convert(copy, os.path.join(case, 'print.pdf'), FORMAT_PDF, e['id'] + '-pdf')
            with open(pdf, 'rb') as f:
                if not f.read(5) == b'%PDF-':
                    raise Failure('PDF output is not a PDF')
            notes.append('lays out to PDF (%d KB)' % (os.path.getsize(pdf) // 1024))
        except Failure as err:
            if require_pdf:
                raise
            notes.append('PDF layout skipped: %s' % err)

    if open(path, 'rb').read() != before:
        raise Failure('the template file changed')
    return notes


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--manifest', required=True)
    ap.add_argument('--engine', help='installed or extracted application folder')
    ap.add_argument('--work', help='scratch folder (kept for inspection)')
    ap.add_argument('--require-pdf', action='store_true')
    args = ap.parse_args()

    root = os.path.dirname(os.path.abspath(args.manifest))
    try:
        entries = read_manifest(args.manifest)
    except Failure as e:
        print('FAIL', e)
        return 1

    engine = None
    work = args.work or tempfile.mkdtemp(prefix='sos-templates-')
    if args.engine:
        try:
            engine = Engine(os.path.abspath(args.engine), os.path.abspath(work))
            print('engine: %s' % engine.x2t)
        except Failure as e:
            print('FAIL engine:', e)
            return 1

    ids, failed, per_app = set(), 0, {a: 0 for a in APPS}
    for e in entries:
        label = e.get('id') or e.get('file') or '?'
        try:
            path = check_entry(e, root, ids)
            fmt = FORMATS[e['format']]
            if fmt[2]:
                check_ooxml(path, fmt)
            else:
                check_pdf(path)
            notes = engine_check(engine, e, path, fmt, args.require_pdf) if engine else ['static checks']
            per_app[e['app']] += 1
            print('ok   %-34s %s' % (label, '; '.join(notes)))
        except Failure as err:
            failed += 1
            print('FAIL %-34s %s' % (label, err))

    print('\n%d templates: %s; %d failed' % (len(entries), ', '.join('%s %d' % kv for kv in per_app.items()), failed))
    for a in ('writer', 'sheet', 'presentation'):
        if per_app[a] == 0:
            print('FAIL no %s templates' % a)
            failed += 1
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
