"""File-level checks of what the applications saved (no office engine needed)."""

import re
import zipfile

MAGIC = [
    (b'PK\x03\x04', 'zip'),
    (b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1', 'ole'),
    (b'%PDF', 'pdf'),
    (b'{\\rtf', 'rtf'),
]


def kind(path):
    """container of the file: ooxml-docx/xlsx/pptx, odf-odt/ods/odp, ole, pdf, rtf, text"""
    with open(path, 'rb') as f:
        head = f.read(8)
    k = next((k for m, k in MAGIC if head.startswith(m)), 'text')
    if k != 'zip':
        return k
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        if 'mimetype' in names:
            mt = z.read('mimetype').decode(errors='replace')
            return {'application/vnd.oasis.opendocument.text': 'odf-odt',
                    'application/vnd.oasis.opendocument.spreadsheet': 'odf-ods',
                    'application/vnd.oasis.opendocument.presentation': 'odf-odp'}.get(mt, 'odf?' + mt)
        if any(n.startswith('word/') for n in names):
            return 'ooxml-docx'
        if any(n.startswith('xl/') for n in names):
            return 'ooxml-xlsx'
        if any(n.startswith('ppt/') for n in names):
            return 'ooxml-pptx'
    return 'zip'


EXPECTED_KIND = {'docx': 'ooxml-docx', 'xlsx': 'ooxml-xlsx', 'pptx': 'ooxml-pptx',
                 'odt': 'odf-odt', 'ods': 'odf-ods', 'odp': 'odf-odp',
                 'doc': 'ole', 'xls': 'ole', 'ppt': 'ole', 'pdf': 'pdf', 'rtf': 'rtf',
                 'txt': 'text', 'csv': 'text'}


def contains(path, marker):
    """is marker in the saved document's text?"""
    k = kind(path)
    m = marker.encode()
    if k.startswith('ooxml') or k.startswith('odf'):
        with zipfile.ZipFile(path) as z:
            for n in z.namelist():
                if n.endswith('.xml') and m in z.read(n):
                    return True
        return False
    if k == 'pdf':
        try:
            import pypdf
            r = pypdf.PdfReader(path)
            for p in r.pages:
                for a in (p.get('/Annots') or []):
                    a = a.get_object()
                    if marker in str(a.get('/Contents', '')) or marker in str(a.get('/RC', '')):
                        return True
                if marker in (p.extract_text() or ''):
                    return True
        except Exception:
            pass
        with open(path, 'rb') as f:
            return m in f.read()
    with open(path, 'rb') as f:
        data = f.read()
    if k == 'rtf':
        return marker in rtf_text(data.decode('latin-1'))
    return m in data or marker.encode('utf-16-le') in data


def rtf_text(rtf):
    """the visible text of an RTF document, roughly: escapes decoded,
    control words and groups' braces dropped"""
    rtf = re.sub(r'\\u(-?\d+)\??', lambda m: chr(int(m.group(1)) % 65536), rtf)
    rtf = re.sub(r"\\'([0-9a-fA-F]{2})", lambda m: chr(int(m.group(1), 16)), rtf)
    rtf = re.sub(r'\\[a-zA-Z]+-?\d* ?', '', rtf)
    return re.sub(r'[{}\r\n]', '', rtf)


def slides(path):
    k = kind(path)
    if k == 'ooxml-pptx':
        with zipfile.ZipFile(path) as z:
            return len([n for n in z.namelist() if re.match(r'ppt/slides/slide\d+\.xml$', n)])
    if k == 'odf-odp':
        with zipfile.ZipFile(path) as z:
            return z.read('content.xml').count(b'<draw:page ')
    return None


def pdf_pages(path):
    try:
        import pypdf
        return len(pypdf.PdfReader(path).pages)
    except Exception:
        return None


def describe(path):
    try:
        import os
        return '%s, %d bytes' % (kind(path), os.path.getsize(path))
    except Exception as e:
        return str(e)
