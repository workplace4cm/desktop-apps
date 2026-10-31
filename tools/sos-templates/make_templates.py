#!/usr/bin/env python3
"""
Secure Office Suite: builds the start-page templates of EuroOffice Writer,
Sheet and Presentation.

    python3 make_templates.py [OUT_DIR]

OUT_DIR defaults to common/templates/sos. The script writes
    writer/*.dotx  sheet/*.xltx  presentation/*.potx
from python-docx, openpyxl and python-pptx, then thumbnails (thumbs/*.png)
with LibreOffice and pdftoppm. The thumbnails of the PDF starter templates
come from the PDF forms already shipped in common/templates/EN/Forms.

manifest.js, which lists the templates for the start page, is kept by hand.
Requirements: python-docx, openpyxl, python-pptx, Pillow, LibreOffice (soffice),
poppler-utils (pdftoppm).
"""

import datetime
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.properties import PageSetupProperties

from pptx import Presentation
from pptx.dml.color import RGBColor as PRGB
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Emu, Inches, Pt as PPt

from PIL import Image, ImageChops

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
OUT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(ROOT, 'common', 'templates', 'sos')

FONT = 'Calibri'
INK = '262626'
MUTED = '595959'
LINE = 'BFBFBF'

# Application accents (tokens.less)
WRITER = '2D5AA6'
SHEET = '1F7A4D'
PRES = 'B9482A'

# Thumbnail box of the start-page cards, at 2x
THUMB_W, THUMB_H = 304, 264


def hexrgb(h):
    return RGBColor.from_string(h)


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------

def writer_base(margins_cm=2.2):
    doc = Document()
    sec = doc.sections[0]
    # A4
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    for side in ('left_margin', 'right_margin', 'top_margin', 'bottom_margin'):
        setattr(sec, side, Cm(margins_cm))

    st = doc.styles
    normal = st['Normal']
    normal.font.name = FONT
    normal.font.size = Pt(11)
    normal.font.color.rgb = hexrgb(INK)
    normal.element.rPr.rFonts.set(qn('w:eastAsia'), FONT)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.15

    for name, size, color, before, after in (('Title', 26, WRITER, 0, 4),
                                             ('Subtitle', 13, MUTED, 0, 12),
                                             ('Heading 1', 16, WRITER, 18, 6),
                                             ('Heading 2', 13, WRITER, 12, 4),
                                             ('Heading 3', 11.5, INK, 10, 2)):
        s = st[name]
        s.font.name = FONT
        s.font.size = Pt(size)
        s.font.color.rgb = hexrgb(color)
        s.font.bold = name.startswith('Heading') or name == 'Title'
        s.font.italic = False
        rpr = s.element.get_or_add_rPr()
        rf = rpr.find(qn('w:rFonts'))
        if rf is None:
            rf = OxmlElement('w:rFonts')
            rpr.insert(0, rf)
        for a in ('w:ascii', 'w:hAnsi', 'w:eastAsia', 'w:cs'):
            rf.set(qn(a), FONT)
        for a in ('w:asciiTheme', 'w:hAnsiTheme', 'w:eastAsiaTheme', 'w:cstheme'):
            if rf.get(qn(a)) is not None:
                del rf.attrib[qn(a)]
        s.paragraph_format.space_before = Pt(before)
        s.paragraph_format.space_after = Pt(after)
    # Title without the theme's bottom border
    tppr = st['Title'].element.find(qn('w:pPr'))
    if tppr is not None and tppr.find(qn('w:pBdr')) is not None:
        tppr.remove(tppr.find(qn('w:pBdr')))
    return doc


def para(doc, text='', style=None, bold=False, size=None, color=None, align=None, after=None, before=None, italic=False):
    p = doc.add_paragraph(style=style)
    if text:
        r = p.add_run(text)
        r.bold = bold
        r.italic = italic
        if size:
            r.font.size = Pt(size)
        if color:
            r.font.color.rgb = hexrgb(color)
    if align is not None:
        p.alignment = align
    if after is not None:
        p.paragraph_format.space_after = Pt(after)
    if before is not None:
        p.paragraph_format.space_before = Pt(before)
    return p


def rule(p, color=WRITER, size=12, side='bottom', space=4):
    ppr = p._p.get_or_add_pPr()
    bdr = ppr.find(qn('w:pBdr'))
    if bdr is None:
        bdr = OxmlElement('w:pBdr')
        ppr.append(bdr)
    el = OxmlElement('w:' + side)
    el.set(qn('w:val'), 'single')
    el.set(qn('w:sz'), str(size))
    el.set(qn('w:space'), str(space))
    el.set(qn('w:color'), color)
    bdr.append(el)


def shade(cell, fill):
    tcpr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), fill)
    tcpr.append(shd)


def table(doc, rows, header=True, widths=None, fill=WRITER, zebra='F2F5FA'):
    t = doc.add_table(rows=len(rows), cols=len(rows[0]))
    t.style = doc.styles['Table Grid']
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            c = t.cell(i, j)
            c.text = ''
            p = c.paragraphs[0]
            p.paragraph_format.space_after = Pt(2)
            r = p.add_run(val)
            if header and i == 0:
                r.bold = True
                r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
                shade(c, fill)
            elif zebra and i % 2 == 0:
                shade(c, zebra)
            if widths:
                c.width = Cm(widths[j])
    # light borders
    tblpr = t._tbl.tblPr
    borders = OxmlElement('w:tblBorders')
    for edge in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        e = OxmlElement('w:' + edge)
        e.set(qn('w:val'), 'single')
        e.set(qn('w:sz'), '4')
        e.set(qn('w:color'), LINE)
        borders.append(e)
    tblpr.append(borders)
    return t


def bullets(doc, items, style='List Bullet'):
    for it in items:
        p = doc.add_paragraph(style=style)
        p.add_run(it)
        p.paragraph_format.space_after = Pt(3)


def footer_page_numbers(doc, label):
    sec = doc.sections[0]
    p = sec.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r = p.add_run(label + '  |  Page ')
    r.font.size = Pt(9)
    r.font.color.rgb = hexrgb(MUTED)
    for kind, txt in (('begin', None), (None, 'PAGE'), ('end', None)):
        run = p.add_run()
        run.font.size = Pt(9)
        run.font.color.rgb = hexrgb(MUTED)
        if kind:
            fc = OxmlElement('w:fldChar')
            fc.set(qn('w:fldCharType'), kind)
            run._r.append(fc)
        else:
            it = OxmlElement('w:instrText')
            it.set(qn('xml:space'), 'preserve')
            it.text = txt
            run._r.append(it)


def business_letter(path):
    doc = writer_base(2.5)
    p = para(doc, '[Your Company Name]', bold=True, size=20, color=WRITER, after=0)
    p = para(doc, '[Street Address]  ·  [City, Postcode]  ·  [Phone]  ·  [Email]', size=9.5, color=MUTED, after=2)
    rule(p, WRITER, 12)
    para(doc, '', after=18)
    para(doc, '[Date]', after=18)
    for line in ('[Recipient Name]', '[Title]', '[Company Name]', '[Street Address]', '[City, Postcode]'):
        para(doc, line, after=0)
    para(doc, '', after=12)
    para(doc, 'Subject: [Letter subject]', bold=True, after=12)
    para(doc, 'Dear [Recipient Name],', after=10)
    para(doc, 'Thank you for [the reason you are writing]. In this first paragraph, state the purpose of '
              'the letter clearly and briefly so that the reader knows at once why you are writing.')
    para(doc, 'Use the second paragraph to give the details: background, facts, figures and anything the '
              'reader needs to act on your request. Keep sentences short and focused on the reader.')
    para(doc, 'Close by stating the next step you expect, such as a reply, a meeting or a decision, and '
              'by thanking the reader for their time.')
    para(doc, '', after=6)
    para(doc, 'Yours sincerely,', after=36)
    para(doc, '[Your Name]', bold=True, after=0)
    para(doc, '[Your Title]', color=MUTED, after=0)
    doc.save(path)


def report(path):
    doc = writer_base(2.2)
    footer_page_numbers(doc, '[Report title]')
    p = para(doc, 'REPORT', bold=True, size=10, color=MUTED, after=2)
    doc.add_paragraph('[Report Title]', style='Title')
    doc.add_paragraph('[Subtitle or short description of the report]', style='Subtitle')
    t = table(doc, [['Prepared by', '[Name, Department]'],
                    ['Prepared for', '[Audience]'],
                    ['Date', '[Date]'],
                    ['Version', '1.0']], header=False, widths=[4, 12.6], zebra=None)
    for r in t.rows:
        r.cells[0].paragraphs[0].runs[0].bold = True
        shade(r.cells[0], 'EAF0F8')
    doc.add_paragraph('Executive summary', style='Heading 1')
    para(doc, 'Summarise the purpose of the report, the main findings and the recommendations in a few '
              'sentences. A reader who only reads this section should understand the outcome.')
    doc.add_paragraph('1. Introduction', style='Heading 1')
    para(doc, 'Describe the background, the scope of the work and the questions the report answers.')
    doc.add_paragraph('2. Method', style='Heading 1')
    para(doc, 'Explain how the information was gathered and analysed.')
    doc.add_paragraph('3. Findings', style='Heading 1')
    doc.add_paragraph('3.1 Key results', style='Heading 2')
    para(doc, 'Present the results in a logical order. Use tables for figures:')
    table(doc, [['Measure', 'Target', 'Result', 'Status'],
                ['[Measure 1]', '[Value]', '[Value]', 'On track'],
                ['[Measure 2]', '[Value]', '[Value]', 'At risk'],
                ['[Measure 3]', '[Value]', '[Value]', 'On track']], widths=[6.6, 3.3, 3.3, 3.4])
    doc.add_paragraph('3.2 Discussion', style='Heading 2')
    para(doc, 'Interpret the results and explain what they mean for the organisation.')
    doc.add_paragraph('4. Recommendations', style='Heading 1')
    bullets(doc, ['[Recommendation 1 with owner and date]',
                  '[Recommendation 2 with owner and date]',
                  '[Recommendation 3 with owner and date]'], 'List Number')
    doc.add_paragraph('5. Conclusion', style='Heading 1')
    para(doc, 'Restate the main message and the decisions you ask the reader to take.')
    doc.save(path)


def meeting_notes(path):
    doc = writer_base(2.0)
    p = para(doc, 'MEETING NOTES', bold=True, size=10, color=MUTED, after=2)
    doc.add_paragraph('[Meeting title]', style='Title')
    t = table(doc, [['Date', '[Date]', 'Time', '[Start – End]'],
                    ['Location', '[Room or call]', 'Facilitator', '[Name]'],
                    ['Note taker', '[Name]', 'Next meeting', '[Date]']], header=False,
              widths=[3, 5.5, 3, 5.5], zebra=None)
    for r in t.rows:
        for j in (0, 2):
            r.cells[j].paragraphs[0].runs[0].bold = True
            shade(r.cells[j], 'EAF0F8')
    doc.add_paragraph('Attendees', style='Heading 2')
    para(doc, '[Name], [Name], [Name]')
    doc.add_paragraph('Absent', style='Heading 2')
    para(doc, '[Name]')
    doc.add_paragraph('Agenda', style='Heading 1')
    bullets(doc, ['[Topic 1]', '[Topic 2]', '[Topic 3]'], 'List Number')
    doc.add_paragraph('Discussion', style='Heading 1')
    for i in (1, 2, 3):
        doc.add_paragraph('[Topic %d]' % i, style='Heading 3')
        para(doc, '[Summary of the discussion and the points raised.]')
    doc.add_paragraph('Decisions', style='Heading 1')
    bullets(doc, ['[Decision 1]', '[Decision 2]'])
    doc.add_paragraph('Action items', style='Heading 1')
    table(doc, [['#', 'Action', 'Owner', 'Due date', 'Status'],
                ['1', '[Action]', '[Name]', '[Date]', 'Open'],
                ['2', '[Action]', '[Name]', '[Date]', 'Open'],
                ['3', '[Action]', '[Name]', '[Date]', 'Open']], widths=[1, 7.4, 3, 3, 2.6])
    doc.save(path)


def resume(path):
    doc = writer_base(2.0)
    para(doc, '[YOUR NAME]', bold=True, size=28, color=WRITER, after=0)
    para(doc, '[Professional title]', size=13, color=MUTED, after=4)
    p = para(doc, '[City, Country]  ·  [Phone]  ·  [Email]  ·  [Website or profile]', size=9.5, color=MUTED, after=8)
    rule(p, WRITER, 12)

    def section(title):
        p = doc.add_paragraph(title.upper(), style='Heading 2')
        p.paragraph_format.space_before = Pt(14)
        rule(p, LINE, 6, space=2)

    section('Profile')
    para(doc, 'Two or three sentences about who you are, the value you bring and the kind of role you are '
              'looking for. Mention your strongest skills and achievements.')
    section('Experience')
    for job in (('[Job title]', '[Company], [City]', '[Month Year] – Present'),
                ('[Job title]', '[Company], [City]', '[Month Year] – [Month Year]')):
        p = para(doc, job[0], bold=True, after=0)
        r = p.add_run('   ' + job[2])
        r.font.color.rgb = hexrgb(MUTED)
        r.bold = False
        para(doc, job[1], italic=True, color=MUTED, after=2)
        bullets(doc, ['[Achievement with a measurable result]',
                      '[Responsibility or project you led]',
                      '[Skill you used and what it changed]'])
    section('Education')
    p = para(doc, '[Degree, Subject]', bold=True, after=0)
    para(doc, '[University], [Year]', italic=True, color=MUTED)
    section('Skills')
    t = table(doc, [['[Skill]', '[Skill]', '[Skill]'], ['[Skill]', '[Skill]', '[Skill]']], header=False,
              widths=[5.6, 5.6, 5.6], zebra=None)
    section('Languages')
    para(doc, '[Language] – [Level]   ·   [Language] – [Level]')
    doc.save(path)


def memo(path):
    doc = writer_base(2.5)
    para(doc, 'MEMORANDUM', bold=True, size=24, color=WRITER, after=10)
    t = table(doc, [['To:', '[Recipients]'], ['From:', '[Your name]'], ['CC:', '[Names]'],
                    ['Date:', '[Date]'], ['Subject:', '[Subject]']], header=False, widths=[2.6, 13.4], zebra=None)
    for r in t.rows:
        r.cells[0].paragraphs[0].runs[0].bold = True
    # memo header without grid lines
    tblpr = t._tbl.tblPr
    for b in tblpr.findall(qn('w:tblBorders')):
        tblpr.remove(b)
    borders = OxmlElement('w:tblBorders')
    for edge in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        e = OxmlElement('w:' + edge)
        e.set(qn('w:val'), 'nil')
        borders.append(e)
    tblpr.append(borders)
    p = para(doc, '', after=12)
    rule(p, WRITER, 12)
    para(doc, 'State the purpose of the memo in the first sentence.')
    para(doc, 'Give the background and the details the readers need. Keep each paragraph to one idea.')
    para(doc, 'End with the action you need from the readers and the date it is due.')
    doc.save(path)


def cover_letter(path):
    doc = writer_base(2.5)
    para(doc, '[Your Name]', bold=True, size=22, color=WRITER, after=0)
    p = para(doc, '[Street Address], [City, Postcode]  ·  [Phone]  ·  [Email]', size=9.5, color=MUTED, after=2)
    rule(p, WRITER, 12)
    para(doc, '', after=14)
    para(doc, '[Date]', after=14)
    for line in ('[Hiring Manager Name]', '[Company Name]', '[Street Address]', '[City, Postcode]'):
        para(doc, line, after=0)
    para(doc, '', after=12)
    para(doc, 'Application for the position of [Job Title], reference [Reference]', bold=True, after=12)
    para(doc, 'Dear [Hiring Manager Name],', after=10)
    para(doc, 'I am writing to apply for the position of [Job Title] advertised on [where you saw it]. '
              'With [number] years of experience in [field], I am confident that I can contribute to '
              '[Company Name] from my first day.')
    para(doc, 'In my current role at [Current Employer], I [main achievement with a measurable result]. '
              'I have also [second achievement or responsibility that matches the job description].')
    para(doc, 'What attracts me to [Company Name] is [a specific reason: product, values, project]. '
              'I would welcome the opportunity to discuss how my skills in [skill], [skill] and [skill] '
              'can support your team.')
    para(doc, 'Thank you for considering my application. I look forward to hearing from you.')
    para(doc, '', after=6)
    para(doc, 'Yours sincerely,', after=36)
    para(doc, '[Your Name]', bold=True, after=0)
    para(doc, 'Enclosure: Resume', color=MUTED, size=9.5, after=0)
    doc.save(path)


def project_proposal(path):
    doc = writer_base(2.2)
    footer_page_numbers(doc, '[Project name] proposal')
    para(doc, 'PROJECT PROPOSAL', bold=True, size=10, color=MUTED, after=2)
    doc.add_paragraph('[Project Name]', style='Title')
    doc.add_paragraph('[One sentence that says what the project will achieve]', style='Subtitle')
    t = table(doc, [['Submitted by', '[Name, Department]'],
                    ['Submitted to', '[Sponsor or committee]'],
                    ['Date', '[Date]'],
                    ['Requested budget', '[Amount]']], header=False, widths=[4, 12.6], zebra=None)
    for r in t.rows:
        r.cells[0].paragraphs[0].runs[0].bold = True
        shade(r.cells[0], 'EAF0F8')
    doc.add_paragraph('1. Background', style='Heading 1')
    para(doc, 'Describe the situation today and the problem or opportunity the project addresses. '
              'Give the facts and figures that show why it matters.')
    doc.add_paragraph('2. Objectives', style='Heading 1')
    bullets(doc, ['[Specific, measurable objective]', '[Specific, measurable objective]',
                  '[Specific, measurable objective]'], 'List Number')
    doc.add_paragraph('3. Scope and deliverables', style='Heading 1')
    table(doc, [['Deliverable', 'Description', 'Due'],
                ['[Deliverable 1]', '[What will be delivered]', '[Date]'],
                ['[Deliverable 2]', '[What will be delivered]', '[Date]'],
                ['[Deliverable 3]', '[What will be delivered]', '[Date]']], widths=[4.5, 9, 3.1])
    para(doc, 'Out of scope: [what the project will not do].', italic=True, color=MUTED, before=6)
    doc.add_paragraph('4. Approach and timeline', style='Heading 1')
    table(doc, [['Phase', 'Activities', 'Start', 'End'],
                ['Initiation', '[Activities]', '[Date]', '[Date]'],
                ['Planning', '[Activities]', '[Date]', '[Date]'],
                ['Delivery', '[Activities]', '[Date]', '[Date]'],
                ['Closure', '[Activities]', '[Date]', '[Date]']], widths=[3.4, 8.2, 2.5, 2.5])
    doc.add_paragraph('5. Budget', style='Heading 1')
    table(doc, [['Item', 'Cost'], ['Staff', '[Amount]'], ['Equipment and software', '[Amount]'],
                ['External services', '[Amount]'], ['Contingency (10%)', '[Amount]'], ['Total', '[Amount]']],
          widths=[11.6, 5])
    doc.add_paragraph('6. Risks', style='Heading 1')
    bullets(doc, ['[Risk] – [how it will be reduced]', '[Risk] – [how it will be reduced]'])
    doc.add_paragraph('7. Approval', style='Heading 1')
    table(doc, [['Name', 'Role', 'Signature', 'Date'], ['', '', '', ''], ['', '', '', '']],
          widths=[4.6, 4, 5, 3])
    doc.save(path)


def agenda(path):
    doc = writer_base(2.2)
    para(doc, 'MEETING AGENDA', bold=True, size=10, color=MUTED, after=2)
    doc.add_paragraph('[Meeting title]', style='Title')
    t = table(doc, [['Date', '[Date]', 'Time', '[Start – End]'],
                    ['Location', '[Room or call link]', 'Chair', '[Name]']], header=False,
              widths=[3, 5.5, 3, 5.1], zebra=None)
    for r in t.rows:
        for j in (0, 2):
            r.cells[j].paragraphs[0].runs[0].bold = True
            shade(r.cells[j], 'EAF0F8')
    doc.add_paragraph('Purpose', style='Heading 2')
    para(doc, '[What the meeting must decide or produce.]')
    doc.add_paragraph('Invited', style='Heading 2')
    para(doc, '[Name], [Name], [Name]')
    doc.add_paragraph('Agenda', style='Heading 1')
    table(doc, [['Time', 'Item', 'Lead', 'Outcome'],
                ['[09:00]', 'Welcome and review of previous actions', '[Name]', 'Information'],
                ['[09:10]', '[Topic 1]', '[Name]', 'Decision'],
                ['[09:30]', '[Topic 2]', '[Name]', 'Discussion'],
                ['[09:50]', '[Topic 3]', '[Name]', 'Information'],
                ['[10:05]', 'Actions and next meeting', '[Name]', 'Agreement']], widths=[2.2, 8, 3, 3.4])
    doc.add_paragraph('Preparation', style='Heading 2')
    bullets(doc, ['[Document to read before the meeting]', '[Data to bring]'])
    doc.save(path)


# ---------------------------------------------------------------------------
# Sheet
# ---------------------------------------------------------------------------

THIN = Side(style='thin', color=LINE)
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
MONEY = '#,##0.00'


def fill(h):
    return PatternFill('solid', fgColor=h)


def xl_title(ws, title, subtitle=None, color=SHEET, width_cols=6):
    ws['A1'] = title
    ws['A1'].font = Font(name=FONT, size=20, bold=True, color=color)
    if subtitle:
        ws['A2'] = subtitle
        ws['A2'].font = Font(name=FONT, size=11, color=MUTED)
    ws.row_dimensions[1].height = 32
    ws.sheet_view.showGridLines = False


def xl_header(ws, row, col, values, color=SHEET):
    for i, v in enumerate(values):
        c = ws.cell(row=row, column=col + i, value=v)
        c.font = Font(name=FONT, bold=True, color='FFFFFF')
        c.fill = fill(color)
        c.alignment = Alignment(horizontal='center' if i else 'left', vertical='center')
        c.border = BOX


def xl_cell(ws, row, col, value, fmt=None, bold=False, bg=None, color=INK, align=None):
    c = ws.cell(row=row, column=col, value=value)
    c.font = Font(name=FONT, bold=bold, color=color)
    c.border = BOX
    if fmt:
        c.number_format = fmt
    if bg:
        c.fill = fill(bg)
    if align:
        c.alignment = Alignment(horizontal=align)
    return c


def xl_defaults(wb):
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if c.font is None or c.font.name != FONT:
                    f = c.font
                    c.font = Font(name=FONT, size=f.size if f and f.size else 11, bold=f.bold if f else False,
                                  italic=f.italic if f else False, color=f.color if f else None)
        ws.page_setup.orientation = 'portrait'
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)


def budget(path):
    wb = Workbook()
    ws = wb.active
    ws.title = 'Monthly budget'
    xl_title(ws, 'Monthly Budget', '[Month Year]  ·  Enter your planned and actual amounts in the white cells.')
    widths = [30, 16, 16, 16, 4, 26, 16]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # Income
    ws['A4'] = 'Income'
    ws['A4'].font = Font(name=FONT, size=13, bold=True, color=SHEET)
    xl_header(ws, 5, 1, ['Source', 'Planned', 'Actual', 'Difference'])
    income = [('Salary', 4200, 4200), ('Other income', 300, 250), ('[Source]', 0, 0)]
    r = 6
    for name, plan, act in income:
        xl_cell(ws, r, 1, name)
        xl_cell(ws, r, 2, plan, MONEY)
        xl_cell(ws, r, 3, act, MONEY)
        xl_cell(ws, r, 4, '=C%d-B%d' % (r, r), MONEY, bg='F2F2F2')
        r += 1
    inc_first, inc_last = 6, r - 1
    xl_cell(ws, r, 1, 'Total income', bold=True, bg='E2EFE8')
    for col in 'BCD':
        xl_cell(ws, r, ' BCD'.index(col) + 1, '=SUM(%s%d:%s%d)' % (col, inc_first, col, inc_last), MONEY, True, 'E2EFE8')
    inc_total = r

    # Expenses
    r += 2
    ws.cell(row=r, column=1, value='Expenses').font = Font(name=FONT, size=13, bold=True, color=SHEET)
    r += 1
    xl_header(ws, r, 1, ['Category', 'Planned', 'Actual', 'Difference'])
    r += 1
    expenses = [('Housing', 1400, 1400), ('Utilities', 220, 236), ('Groceries', 520, 548), ('Transport', 260, 231),
                ('Insurance', 180, 180), ('Health', 90, 45), ('Phone and internet', 75, 75),
                ('Entertainment', 150, 182), ('Savings', 600, 600), ('[Category]', 0, 0)]
    exp_first = r
    for name, plan, act in expenses:
        xl_cell(ws, r, 1, name)
        xl_cell(ws, r, 2, plan, MONEY)
        xl_cell(ws, r, 3, act, MONEY)
        xl_cell(ws, r, 4, '=B%d-C%d' % (r, r), MONEY, bg='F2F2F2')
        r += 1
    exp_last = r - 1
    xl_cell(ws, r, 1, 'Total expenses', bold=True, bg='E2EFE8')
    for col in 'BCD':
        xl_cell(ws, r, ' BCD'.index(col) + 1, '=SUM(%s%d:%s%d)' % (col, exp_first, col, exp_last), MONEY, True, 'E2EFE8')
    exp_total = r

    # Summary
    ws['F4'] = 'Summary'
    ws['F4'].font = Font(name=FONT, size=13, bold=True, color=SHEET)
    xl_header(ws, 5, 6, ['', 'Actual'])
    # savings rate = (planned savings + what is left) / income
    sav_row = exp_first + [e[0] for e in expenses].index('Savings')
    rows = [('Total income', '=C%d' % inc_total), ('Total expenses', '=C%d' % exp_total),
            ('Balance', '=G6-G7'), ('Savings rate', '=IF(G6=0,0,(C%d+G8)/G6)' % sav_row)]
    for i, (k, f) in enumerate(rows):
        xl_cell(ws, 6 + i, 6, k, bold=(k == 'Balance'))
        xl_cell(ws, 6 + i, 7, f, '0.0%' if k == 'Savings rate' else MONEY, bold=(k == 'Balance'), bg='F2F2F2')
    ws['F11'] = 'Positive difference on expenses = under budget.'
    ws['F11'].font = Font(name=FONT, size=9, italic=True, color=MUTED)
    ws.freeze_panes = 'A4'
    xl_defaults(wb)
    wb.save(path)


def calendar(path):
    wb = Workbook()
    ws = wb.active
    ws.title = 'Calendar'
    ws.sheet_view.showGridLines = False
    year = datetime.date.today().year + 1
    ws['A1'] = 'Calendar'
    ws['A1'].font = Font(name=FONT, size=22, bold=True, color=SHEET)
    ws['H1'] = 'Year'
    ws['H1'].font = Font(name=FONT, size=11, color=MUTED)
    ws['H1'].alignment = Alignment(horizontal='right', vertical='center')
    ws['I1'] = year
    ws['I1'].font = Font(name=FONT, size=20, bold=True, color=SHEET)
    ws['I1'].alignment = Alignment(horizontal='left', vertical='center')
    ws.merge_cells('I1:K1')
    ws['M1'] = 'Change the year in I1 to update every month. Week starts on Monday.'
    ws['M1'].font = Font(name=FONT, size=9, italic=True, color=MUTED)
    ws.row_dimensions[1].height = 34

    months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August',
              'September', 'October', 'November', 'December']
    days = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su']
    # 3 months per band, 7 columns each + 1 spacer column
    for col in range(1, 3 * 8):
        ws.column_dimensions[get_column_letter(col)].width = 1.6 if col % 8 == 0 else 4.6
    for m in range(12):
        band, pos = divmod(m, 3)
        top = 3 + band * 10
        left = 1 + pos * 8
        c = ws.cell(row=top, column=left, value=months[m])
        c.font = Font(name=FONT, size=12, bold=True, color='FFFFFF')
        for k in range(7):
            ws.cell(row=top, column=left + k).fill = fill(SHEET)
        ws.merge_cells(start_row=top, start_column=left, end_row=top, end_column=left + 6)
        c.alignment = Alignment(horizontal='center')
        for k, d in enumerate(days):
            h = ws.cell(row=top + 1, column=left + k, value=d)
            h.font = Font(name=FONT, size=9, bold=True, color=SHEET if k < 5 else PRES)
            h.alignment = Alignment(horizontal='center')
            h.border = Border(bottom=THIN)
        first = 'DATE($I$1,%d,1)' % (m + 1)
        for w in range(6):
            for k in range(7):
                n = w * 7 + k
                # Monday of the first week, then day n
                expr = '%s-WEEKDAY(%s,2)+1+%d' % (first, first, n)
                f = '=IF(MONTH(%s)=%d,DAY(%s),"")' % (expr, m + 1, expr)
                cell = ws.cell(row=top + 2 + w, column=left + k, value=f)
                cell.alignment = Alignment(horizontal='center')
                cell.font = Font(name=FONT, size=10, color=INK if k < 5 else PRES)
    ws.page_setup.orientation = 'landscape'
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1
    ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    wb.save(path)


def invoice(path):
    wb = Workbook()
    ws = wb.active
    ws.title = 'Invoice'
    ws.sheet_view.showGridLines = False
    for col, w in zip('ABCDEF', (6, 40, 10, 14, 16, 2)):
        ws.column_dimensions[col].width = w
    ws['A1'] = '[Your Company Name]'
    ws['A1'].font = Font(name=FONT, size=16, bold=True, color=SHEET)
    for i, line in enumerate(('[Street Address]', '[City, Postcode]', '[Phone]  ·  [Email]'), 2):
        ws.cell(row=i, column=1, value=line).font = Font(name=FONT, size=10, color=MUTED)
    ws['E1'] = 'INVOICE'
    ws['E1'].font = Font(name=FONT, size=24, bold=True, color=SHEET)
    ws['E1'].alignment = Alignment(horizontal='right')
    for i, (k, v) in enumerate((('Invoice no.', 'INV-0001'), ('Date', None), ('Due date', '=IF(E4="","",E4+30)')), 2):
        ws.cell(row=i + 1, column=4, value=k).font = Font(name=FONT, size=10, bold=True, color=MUTED)
        c = ws.cell(row=i + 1, column=5, value=v)
        c.alignment = Alignment(horizontal='right')
        c.font = Font(name=FONT, size=10)
        if k != 'Invoice no.':
            c.number_format = 'yyyy-mm-dd'
    ws['A7'] = 'BILL TO'
    ws['A7'].font = Font(name=FONT, size=10, bold=True, color=SHEET)
    for i, line in enumerate(('[Customer Name]', '[Company]', '[Street Address]', '[City, Postcode]'), 8):
        ws.cell(row=i, column=1, value=line).font = Font(name=FONT, size=11)
    xl_header(ws, 13, 1, ['#', 'Description', 'Qty', 'Unit price', 'Amount'])
    items = [('[Product or service]', 2, 150), ('[Product or service]', 1, 480), ('[Product or service]', 5, 24)]
    first = 14
    for i in range(10):
        r = first + i
        bg = 'F3F8F5' if i % 2 else None
        xl_cell(ws, r, 1, i + 1, align='center', bg=bg)
        if i < len(items):
            xl_cell(ws, r, 2, items[i][0], bg=bg)
            xl_cell(ws, r, 3, items[i][1], '0', bg=bg, align='center')
            xl_cell(ws, r, 4, items[i][2], MONEY, bg=bg)
        else:
            xl_cell(ws, r, 2, None, bg=bg)
            xl_cell(ws, r, 3, None, '0', bg=bg, align='center')
            xl_cell(ws, r, 4, None, MONEY, bg=bg)
        xl_cell(ws, r, 5, '=IF(C%d="","",C%d*D%d)' % (r, r, r), MONEY, bg=bg)
    last = first + 9
    r = last + 2
    for k, f, fmt in (('Subtotal', '=SUM(E%d:E%d)' % (first, last), MONEY),
                      ('Tax rate', 0.2, '0%'),
                      ('Tax', '=E%d*E%d' % (r, r + 1), MONEY),
                      ('Total due', '=E%d+E%d' % (r, r + 2), MONEY)):
        ws.cell(row=r, column=4, value=k).font = Font(name=FONT, bold=True, color=SHEET if k == 'Total due' else INK)
        c = ws.cell(row=r, column=5, value=f)
        c.number_format = fmt
        c.font = Font(name=FONT, bold=k == 'Total due', size=13 if k == 'Total due' else 11)
        c.border = Border(bottom=THIN)
        if k == 'Total due':
            c.fill = fill('E2EFE8')
        r += 1
    ws.cell(row=r + 1, column=1, value='Payment terms: 30 days. Bank: [Bank name]  ·  IBAN: [IBAN]').font = \
        Font(name=FONT, size=9, italic=True, color=MUTED)
    ws.cell(row=r + 2, column=1, value='Thank you for your business.').font = Font(name=FONT, size=10, bold=True, color=SHEET)
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1
    ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    wb.save(path)


def financial_report(path):
    wb = Workbook()
    ws = wb.active
    ws.title = 'Income statement'
    xl_title(ws, 'Financial Report', '[Company name]  ·  Income statement for the year [Year]  ·  Amounts in [currency]')
    ws.column_dimensions['A'].width = 34
    for col in 'BCDEFG':
        ws.column_dimensions[col].width = 14
    xl_header(ws, 4, 1, ['', 'Q1', 'Q2', 'Q3', 'Q4', 'Year', '% of revenue'])
    lines = [
        ('Revenue', None, 'h'),
        ('Product sales', [182000, 195500, 201300, 238900], 'v'),
        ('Services', [41000, 43800, 45200, 52100], 'v'),
        ('Total revenue', 'sum:6:7', 't'),
        ('Cost of sales', [96500, 102400, 104900, 121600], 'v'),
        ('Gross profit', '=B8-B9', 't'),
        ('Operating expenses', None, 'h'),
        ('Salaries and benefits', [48200, 48900, 49700, 51300], 'v'),
        ('Rent and utilities', [12600, 12600, 12900, 12900], 'v'),
        ('Marketing', [8200, 9600, 7900, 14300], 'v'),
        ('General and administrative', [6900, 7100, 7300, 7600], 'v'),
        ('Depreciation', [3100, 3100, 3100, 3100], 'v'),
        ('Total operating expenses', 'sum:12:16', 't'),
        ('Operating profit (EBIT)', '=B10-B17', 't'),
        ('Interest expense', [1400, 1400, 1300, 1300], 'v'),
        ('Profit before tax', '=B18-B19', 't'),
        ('Income tax', '=B20*0.25', 'f'),
        ('Net profit', '=B20-B21', 'T'),
    ]
    r = 5
    for name, val, kind in lines:
        if kind == 'h':
            c = ws.cell(row=r, column=1, value=name)
            c.font = Font(name=FONT, bold=True, color=SHEET)
            r += 1
            continue
        bold = kind in ('t', 'T')
        bg = 'E2EFE8' if kind == 'T' else ('F2F2F2' if kind == 't' else None)
        xl_cell(ws, r, 1, name, bold=bold, bg=bg)
        for q in range(4):
            col = get_column_letter(2 + q)
            if isinstance(val, list):
                v = val[q]
            elif isinstance(val, str) and val.startswith('sum:'):
                a, b = val[4:].split(':')
                v = '=SUM(%s%s:%s%s)' % (col, a, col, b)
            else:
                v = val.replace('B', col)
            xl_cell(ws, r, 2 + q, v, '#,##0;[Red]-#,##0', bold, bg)
        xl_cell(ws, r, 6, '=SUM(B%d:E%d)' % (r, r), '#,##0;[Red]-#,##0', True, bg or 'F7F7F7')
        xl_cell(ws, r, 7, '=IF($F$8=0,0,F%d/$F$8)' % r, '0.0%', bold, bg, MUTED)
        r += 1
    r += 1
    ws.cell(row=r, column=1, value='Key ratios').font = Font(name=FONT, size=13, bold=True, color=SHEET)
    r += 1
    xl_header(ws, r, 1, ['', 'Q1', 'Q2', 'Q3', 'Q4', 'Year'])
    r += 1
    for name, num in (('Gross margin', 10), ('Operating margin', 18), ('Net margin', 22)):
        xl_cell(ws, r, 1, name)
        for q in range(5):
            col = get_column_letter(2 + q)
            xl_cell(ws, r, 2 + q, '=IF(%s8=0,0,%s%d/%s8)' % (col, col, num, col), '0.0%')
        r += 1
    ws.freeze_panes = 'B5'
    ws.page_setup.orientation = 'landscape'
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1
    ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    wb.save(path)


def expense_report(path):
    wb = Workbook()
    ws = wb.active
    ws.title = 'Expense report'
    xl_title(ws, 'Expense Report', 'Fill in the white cells. Totals update automatically.')
    for col, w in zip('ABCDEFG', (13, 34, 18, 14, 12, 14, 2)):
        ws.column_dimensions[col].width = w
    info = (('Employee', '[Name]'), ('Department', '[Department]'), ('Manager', '[Name]'),
            ('Period', '[From – To]'), ('Purpose', '[Business purpose]'))
    for i, (k, v) in enumerate(info, 4):
        ws.cell(row=i, column=1, value=k).font = Font(name=FONT, bold=True, color=MUTED)
        c = ws.cell(row=i, column=2, value=v)
        c.border = Border(bottom=THIN)
    xl_header(ws, 10, 1, ['Date', 'Description', 'Category', 'Amount', 'VAT %', 'Total'])
    rows = [('Taxi to client site', 'Travel', 38.50, 0.1), ('Hotel, 1 night', 'Lodging', 129, 0.1),
            ('Client lunch', 'Meals', 64.20, 0.1), ('Printer paper', 'Office supplies', 18.90, 0.2)]
    first = 11
    for i in range(12):
        r = first + i
        bg = 'F3F8F5' if i % 2 else None
        if i < len(rows):
            d, cat, amt, vat = rows[i]
            xl_cell(ws, r, 1, datetime.date(datetime.date.today().year + 1, 1, 8 + i), 'yyyy-mm-dd', bg=bg)
            xl_cell(ws, r, 2, d, bg=bg)
            xl_cell(ws, r, 3, cat, bg=bg)
            xl_cell(ws, r, 4, amt, MONEY, bg=bg)
            xl_cell(ws, r, 5, vat, '0%', bg=bg, align='center')
        else:
            xl_cell(ws, r, 1, None, 'yyyy-mm-dd', bg=bg)
            for c in (2, 3):
                xl_cell(ws, r, c, None, bg=bg)
            xl_cell(ws, r, 4, None, MONEY, bg=bg)
            xl_cell(ws, r, 5, None, '0%', bg=bg, align='center')
        xl_cell(ws, r, 6, '=IF(D%d="","",D%d*(1+E%d))' % (r, r, r), MONEY, bg=bg or 'F7F7F7')
    last = first + 11
    r = last + 2
    for k, f in (('Subtotal', '=SUM(D%d:D%d)' % (first, last)),
                 ('VAT', '=SUM(F%d:F%d)-E%d' % (first, last, r)),
                 ('Total claimed', '=E%d+E%d' % (r, r + 1)),
                 ('Advance received', 0),
                 ('Amount due to employee', '=E%d-E%d' % (r + 2, r + 3))):
        ws.cell(row=r, column=4, value=k).font = Font(name=FONT, bold=True,
                                                       color=SHEET if k.startswith('Amount') else INK)
        ws.cell(row=r, column=4).alignment = Alignment(horizontal='right')
        c = ws.cell(row=r, column=5, value=f)
        c.number_format = MONEY
        c.font = Font(name=FONT, bold=k.startswith(('Total', 'Amount')))
        c.border = Border(bottom=THIN)
        ws.merge_cells(start_row=r, start_column=5, end_row=r, end_column=6)
        if k.startswith('Amount'):
            c.fill = fill('E2EFE8')
        r += 1
    r += 1
    for k in ('Employee signature', 'Approved by'):
        ws.cell(row=r, column=1, value=k).font = Font(name=FONT, size=10, color=MUTED)
        for col in range(2, 4):
            ws.cell(row=r, column=col).border = Border(bottom=THIN)
        r += 2
    ws.freeze_panes = 'A11'
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1
    ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    wb.save(path)


def timesheet(path):
    wb = Workbook()
    ws = wb.active
    ws.title = 'Timesheet'
    xl_title(ws, 'Weekly Timesheet', 'Enter start, end and break for each day; hours are calculated.')
    for col, w in zip('ABCDEFGH', (14, 13, 12, 12, 12, 12, 30, 2)):
        ws.column_dimensions[col].width = w
    for i, (k, v) in enumerate((('Employee', '[Name]'), ('Week starting', None), ('Hourly rate', 25)), 4):
        ws.cell(row=i, column=1, value=k).font = Font(name=FONT, bold=True, color=MUTED)
        c = ws.cell(row=i, column=2, value=v)
        c.border = Border(bottom=THIN)
        if k == 'Week starting':
            # next Monday after 1 January of next year
            y = datetime.date.today().year + 1
            d = datetime.date(y, 1, 1)
            c.value = d + datetime.timedelta(days=(7 - d.weekday()) % 7)
            c.number_format = 'yyyy-mm-dd'
        if k == 'Hourly rate':
            c.number_format = MONEY
    xl_header(ws, 8, 1, ['Day', 'Date', 'Start', 'End', 'Break (h)', 'Hours', 'Notes'])
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    for i, d in enumerate(days):
        r = 9 + i
        bg = 'F3F8F5' if i % 2 else None
        xl_cell(ws, r, 1, d, bold=True, bg=bg)
        xl_cell(ws, r, 2, '=$B$5+%d' % i, 'ddd dd mmm', bg=bg or 'F7F7F7')
        work = i < 5
        xl_cell(ws, r, 3, datetime.time(9, 0) if work else None, 'hh:mm', bg=bg, align='center')
        xl_cell(ws, r, 4, datetime.time(17, 30) if work else None, 'hh:mm', bg=bg, align='center')
        xl_cell(ws, r, 5, 0.5 if work else None, '0.00', bg=bg, align='center')
        xl_cell(ws, r, 6, '=IF(OR(C%d="",D%d=""),0,MAX(0,(D%d-C%d)*24-E%d))' % (r, r, r, r, r), '0.00',
                True, bg or 'F7F7F7')
        xl_cell(ws, r, 7, None, bg=bg)
    r = 17
    for k, f, fmt in (('Total hours', '=SUM(F9:F15)', '0.00'),
                      ('Regular (up to 40 h)', '=MIN(40,F17)', '0.00'),
                      ('Overtime', '=MAX(0,F17-40)', '0.00'),
                      ('Gross pay (overtime at 1.5x)', '=F18*B6+F19*B6*1.5', MONEY)):
        c = ws.cell(row=r, column=5, value=k)
        c.font = Font(name=FONT, bold=True, color=SHEET if k.startswith('Gross') else INK)
        c.alignment = Alignment(horizontal='right')
        v = ws.cell(row=r, column=6, value=f)
        v.number_format = fmt
        v.font = Font(name=FONT, bold=True)
        v.border = Border(bottom=THIN)
        if k.startswith('Gross'):
            v.fill = fill('E2EFE8')
        r += 1
    ws.freeze_panes = 'A9'
    ws.page_setup.orientation = 'landscape'
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1
    ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    wb.save(path)


def project_tracker(path):
    wb = Workbook()
    ws = wb.active
    ws.title = 'Tasks'
    xl_title(ws, 'Project Tracker', '[Project name]  ·  Status: Not started, In progress, Done, Blocked')
    for col, w in zip('ABCDEFGHI', (6, 36, 16, 13, 13, 14, 12, 30, 2)):
        ws.column_dimensions[col].width = w
    xl_header(ws, 4, 1, ['#', 'Task', 'Owner', 'Start', 'Due', 'Status', '% done', 'Notes'])
    y = datetime.date.today().year + 1
    tasks = [('Kick-off meeting', 'Done', 1.0), ('Gather requirements', 'Done', 1.0),
             ('Design', 'In progress', 0.6), ('Build', 'Not started', 0), ('Test', 'Not started', 0),
             ('Launch', 'Not started', 0)]
    dv = DataValidation(type='list', formula1='"Not started,In progress,Done,Blocked"', allow_blank=True)
    ws.add_data_validation(dv)
    for i in range(15):
        r = 5 + i
        bg = 'F3F8F5' if i % 2 else None
        xl_cell(ws, r, 1, i + 1, align='center', bg=bg)
        if i < len(tasks):
            name, st, pct = tasks[i]
            start = datetime.date(y, 1, 5) + datetime.timedelta(days=14 * i)
            xl_cell(ws, r, 2, name, bg=bg)
            xl_cell(ws, r, 3, '[Owner]', bg=bg)
            xl_cell(ws, r, 4, start, 'yyyy-mm-dd', bg=bg)
            xl_cell(ws, r, 5, start + datetime.timedelta(days=12), 'yyyy-mm-dd', bg=bg)
            xl_cell(ws, r, 6, st, bg=bg, align='center')
            xl_cell(ws, r, 7, pct, '0%', bg=bg, align='center')
        else:
            for c, fmt in ((2, None), (3, None), (4, 'yyyy-mm-dd'), (5, 'yyyy-mm-dd'), (6, None), (7, '0%')):
                xl_cell(ws, r, c, None, fmt, bg=bg)
        xl_cell(ws, r, 8, None, bg=bg)
        dv.add('F%d' % r)
    ws['B21'] = 'Summary'
    ws['B21'].font = Font(name=FONT, size=13, bold=True, color=SHEET)
    for i, (k, f, fmt) in enumerate((('Tasks', '=COUNTA(B5:B19)', '0'),
                                     ('Done', '=COUNTIF(F5:F19,"Done")', '0'),
                                     ('In progress', '=COUNTIF(F5:F19,"In progress")', '0'),
                                     ('Blocked', '=COUNTIF(F5:F19,"Blocked")', '0'),
                                     ('Overall progress', '=IF(COUNTA(B5:B19)=0,0,SUM(G5:G19)/COUNTA(B5:B19))', '0%'))):
        xl_cell(ws, 22 + i, 2, k, bold=k.startswith('Overall'))
        xl_cell(ws, 22 + i, 3, f, fmt, bold=k.startswith('Overall'), bg='E2EFE8' if k.startswith('Overall') else 'F7F7F7')
    ws.freeze_panes = 'A5'
    ws.page_setup.orientation = 'landscape'
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    wb.save(path)


# ---------------------------------------------------------------------------
# Presentation
# ---------------------------------------------------------------------------

def prgb(h):
    return PRGB.from_string(h)


class Deck:
    """16:9 deck from python-pptx's default master, rescaled and recoloured."""

    W, H = Emu(12192000), Emu(6858000)

    def __init__(self, accent, dark, light='FFFFFF'):
        self.prs = Presentation()
        old_w = self.prs.slide_width
        self.prs.slide_width, self.prs.slide_height = self.W, self.H
        k = self.W / old_w
        for shapes in [self.prs.slide_master.shapes] + [l.shapes for l in self.prs.slide_layouts]:
            for sh in shapes:
                if sh.left is not None:
                    sh.left = int(sh.left * k)
                    sh.width = int(sh.width * k)
        self.accent, self.dark, self.light = accent, dark, light
        self._theme_colors()
        self._master_fonts()

    def _theme_colors(self):
        master = self.prs.slide_master
        for rel in master.part.rels.values():
            if rel.reltype.endswith('/theme'):
                part = rel.target_part
                xml = part.blob.decode('utf-8')
                xml = re.sub(r'(<a:accent1>\s*<a:srgbClr val=")[0-9A-Fa-f]{6}', r'\g<1>' + self.accent, xml)
                xml = re.sub(r'(<a:dk2>\s*<a:srgbClr val=")[0-9A-Fa-f]{6}', r'\g<1>' + self.dark, xml)
                xml = re.sub(r'(<a:latin typeface=")[^"]*(")', r'\g<1>' + FONT + r'\g<2>', xml)
                part._blob = xml.encode('utf-8')

    def _master_fonts(self):
        master = self.prs.slide_master
        for sh in master.placeholders:
            if sh.placeholder_format.type is not None and 'TITLE' in str(sh.placeholder_format.type):
                for p in sh.text_frame.paragraphs:
                    for r in p.runs:
                        r.font.color.rgb = prgb(self.dark)

    def layout(self, name):
        for l in self.prs.slide_layouts:
            if l.name == name:
                return l
        return self.prs.slide_layouts[6]

    def rect(self, slide, x, y, w, h, color, shape=MSO_SHAPE.RECTANGLE):
        s = slide.shapes.add_shape(shape, x, y, w, h)
        s.fill.solid()
        s.fill.fore_color.rgb = prgb(color)
        s.line.fill.background()
        s.shadow.inherit = False
        return s

    def text(self, slide, x, y, w, h, txt, size=18, color=INK, bold=False, align=PP_ALIGN.LEFT,
             anchor=MSO_ANCHOR.TOP):
        tb = slide.shapes.add_textbox(x, y, w, h)
        tf = tb.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = anchor
        lines = txt if isinstance(txt, list) else [txt]
        for i, line in enumerate(lines):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = align
            r = p.add_run()
            r.text = line
            r.font.size = PPt(size)
            r.font.bold = bold
            r.font.name = FONT
            r.font.color.rgb = prgb(color)
        return tb

    def style_title(self, shape, color=None, size=34):
        for p in shape.text_frame.paragraphs:
            p.alignment = PP_ALIGN.LEFT
            for r in p.runs:
                r.font.color.rgb = prgb(color or self.dark)
                r.font.bold = True
                r.font.size = PPt(size)
                r.font.name = FONT

    def title_slide(self, title, subtitle, kicker):
        s = self.prs.slides.add_slide(self.layout('Title Slide'))
        self.rect(s, 0, 0, self.W, self.H, self.dark)
        self.rect(s, 0, int(self.H * 0.72), self.W, int(self.H * 0.28), self.accent)
        self.rect(s, Inches(0.8), Inches(1.55), Inches(1.2), Inches(0.08), self.accent)
        t, sub = s.shapes.title, s.placeholders[1]
        t.left, t.top, t.width, t.height = Inches(0.8), Inches(1.8), Inches(11), Inches(1.6)
        t.text = title
        self.style_title(t, 'FFFFFF', 44)
        t.text_frame.vertical_anchor = MSO_ANCHOR.TOP
        sub.left, sub.top, sub.width, sub.height = Inches(0.8), Inches(3.4), Inches(11), Inches(0.9)
        sub.text = subtitle
        for p in sub.text_frame.paragraphs:
            p.alignment = PP_ALIGN.LEFT
            for r in p.runs:
                r.font.color.rgb = prgb('E6E6E6')
                r.font.size = PPt(20)
        # draw the background shapes behind the placeholders
        sp = s.shapes._spTree
        for el in reversed([x._element for x in s.shapes if not x.is_placeholder]):
            sp.remove(el)
            sp.insert(2, el)
        self.text(s, Inches(0.8), Inches(1.0), Inches(8), Inches(0.5), kicker.upper(), 14, 'FFFFFF', True)
        self.text(s, Inches(0.8), Inches(5.9), Inches(8), Inches(0.6), '[Presenter name]  ·  [Date]', 16, 'FFFFFF')
        return s

    def content(self, title, bullets_=None):
        s = self.prs.slides.add_slide(self.layout('Title and Content'))
        self.rect(s, 0, 0, Inches(0.18), self.H, self.accent)
        t = s.shapes.title
        t.left, t.top, t.width, t.height = Inches(0.7), Inches(0.4), Inches(11.8), Inches(1.0)
        t.text = title
        self.style_title(t)
        body = s.placeholders[1]
        body.left, body.top, body.width, body.height = Inches(0.7), Inches(1.6), Inches(11.8), Inches(5.2)
        if bullets_:
            body.text_frame.text = bullets_[0]
            for b in bullets_[1:]:
                level = 0
                if b.startswith('  '):
                    level, b = 1, b.strip()
                p = body.text_frame.add_paragraph()
                p.text = b
                p.level = level
            for p in body.text_frame.paragraphs:
                for r in p.runs:
                    r.font.size = PPt(22 if p.level == 0 else 18)
                    r.font.color.rgb = prgb(INK if p.level == 0 else MUTED)
        else:
            body._element.getparent().remove(body._element)
        return s

    def columns(self, title, cols):
        s = self.content(title)
        n = len(cols)
        gap = Inches(0.35)
        w = int((Inches(11.8) - gap * (n - 1)) / n)
        for i, (head, txt) in enumerate(cols):
            x = Inches(0.7) + i * (w + gap)
            self.rect(s, x, Inches(1.8), w, Inches(4.6), 'F4F4F4')
            self.rect(s, x, Inches(1.8), w, Inches(0.12), self.accent)
            self.text(s, x + Inches(0.3), Inches(2.2), w - Inches(0.6), Inches(0.7), head, 22, self.dark, True)
            self.text(s, x + Inches(0.3), Inches(3.0), w - Inches(0.6), Inches(3.2), txt, 16, MUTED)
        return s

    def table(self, title, rows, col_w=None):
        s = self.content(title)
        nrows, ncols = len(rows), len(rows[0])
        gt = s.shapes.add_table(nrows, ncols, Inches(0.7), Inches(1.8), Inches(11.8), Inches(0.55) * nrows)
        tbl = gt.table
        for i, row in enumerate(rows):
            for j, val in enumerate(row):
                c = tbl.cell(i, j)
                c.text = val
                c.fill.solid()
                c.fill.fore_color.rgb = prgb(self.dark if i == 0 else ('F4F4F4' if i % 2 else 'FFFFFF'))
                for p in c.text_frame.paragraphs:
                    for r in p.runs:
                        r.font.size = PPt(16)
                        r.font.name = FONT
                        r.font.bold = i == 0
                        r.font.color.rgb = prgb('FFFFFF' if i == 0 else INK)
        if col_w:
            for j, w in enumerate(col_w):
                tbl.columns[j].width = Inches(w)
        return s

    def timeline(self, title, steps):
        s = self.content(title)
        y = Inches(3.6)
        self.rect(s, Inches(0.9), y, Inches(11.4), Inches(0.08), 'BFBFBF')
        n = len(steps)
        step_w = Inches(11.4) / n
        for i, (when, what) in enumerate(steps):
            cx = int(Inches(0.9) + step_w * i + step_w / 2)
            self.rect(s, cx - Inches(0.22), y - Inches(0.18), Inches(0.44), Inches(0.44), self.accent, MSO_SHAPE.OVAL)
            self.text(s, int(cx - step_w / 2), Inches(2.4), int(step_w), Inches(0.9), when, 18, self.dark, True,
                      PP_ALIGN.CENTER, MSO_ANCHOR.BOTTOM)
            self.text(s, int(cx - step_w / 2) + Inches(0.1), Inches(4.2), int(step_w) - Inches(0.2), Inches(1.6),
                      what, 14, MUTED, False, PP_ALIGN.CENTER)
        return s

    def closing(self, title, sub):
        s = self.prs.slides.add_slide(self.layout('Blank'))
        self.rect(s, 0, 0, self.W, self.H, self.dark)
        self.rect(s, Inches(0.8), Inches(2.9), Inches(1.2), Inches(0.08), self.accent)
        self.text(s, Inches(0.8), Inches(3.1), Inches(11), Inches(1.2), title, 44, 'FFFFFF', True)
        self.text(s, Inches(0.8), Inches(4.2), Inches(11), Inches(0.8), sub, 20, 'E6E6E6')
        return s

    def save(self, path):
        self.prs.save(path)


def business_presentation(path):
    d = Deck(PRES, '3A2E2A')
    d.title_slide('[Company Name]\nBusiness Overview', '[One-line description of the presentation]', 'Business presentation')
    d.content('Agenda', ['Who we are', 'Market opportunity', 'Our solution', 'Results so far', 'Plan and next steps'])
    d.columns('Who we are', [('Mission', '[What the company does and for whom, in one or two sentences.]'),
                             ('Vision', '[Where the company wants to be in five years.]'),
                             ('Values', '[Three values that guide how you work.]')])
    d.content('Market opportunity', ['[Size of the market and its growth]', '[The problem customers have today]',
                                     '  [Evidence: survey, data or quote]', '[Why now]'])
    d.columns('Our solution', [('[Product 1]', '[Benefit for the customer]'), ('[Product 2]', '[Benefit for the customer]'),
                               ('[Service]', '[Benefit for the customer]')])
    d.table('Results so far', [['Indicator', 'Last year', 'This year', 'Change'],
                               ['Revenue', '[Value]', '[Value]', '[+%]'],
                               ['Customers', '[Value]', '[Value]', '[+%]'],
                               ['Employees', '[Value]', '[Value]', '[+%]']], [4.4, 2.5, 2.5, 2.4])
    d.timeline('Plan', [('Q1', '[Milestone]'), ('Q2', '[Milestone]'), ('Q3', '[Milestone]'), ('Q4', '[Milestone]')])
    d.content('Next steps', ['[Decision we ask for today]', '[Owner and date for each action]', '[How we report progress]'])
    d.closing('Thank you', '[Name]  ·  [Email]  ·  [Phone]')
    d.save(path)


def project_presentation(path):
    d = Deck('2D5AA6', '1F2A44')
    d.title_slide('[Project Name]', 'Project status and plan', 'Project presentation')
    d.content('Project overview', ['[Why the project exists: the problem or opportunity]', '[Sponsor and stakeholders]',
                                   '[Budget and duration]'])
    d.columns('Objectives', [('Objective 1', '[Specific, measurable goal]'), ('Objective 2', '[Specific, measurable goal]'),
                             ('Objective 3', '[Specific, measurable goal]')])
    d.columns('Scope', [('In scope', '[What the project will deliver]'), ('Out of scope', '[What it will not deliver]')])
    d.timeline('Timeline', [('[Month]', 'Initiation'), ('[Month]', 'Planning'), ('[Month]', 'Execution'),
                            ('[Month]', 'Testing'), ('[Month]', 'Launch')])
    d.table('Team', [['Role', 'Name', 'Responsibility'], ['Project manager', '[Name]', '[Responsibility]'],
                     ['Lead', '[Name]', '[Responsibility]'], ['Member', '[Name]', '[Responsibility]']], [3.4, 3.4, 5.0])
    d.table('Risks and mitigation', [['Risk', 'Impact', 'Likelihood', 'Mitigation'],
                                     ['[Risk 1]', 'High', 'Medium', '[Action]'], ['[Risk 2]', 'Medium', 'Low', '[Action]'],
                                     ['[Risk 3]', 'Low', 'Medium', '[Action]']], [3.6, 1.8, 1.8, 4.6])
    d.table('Status', [['Workstream', 'Status', 'Comment'], ['[Workstream 1]', 'On track', '[Comment]'],
                       ['[Workstream 2]', 'At risk', '[Comment]'], ['[Workstream 3]', 'Done', '[Comment]']], [3.8, 2.2, 5.8])
    d.content('Next steps', ['[Action, owner, date]', '[Action, owner, date]', '[Decisions needed from the sponsor]'])
    d.closing('Questions?', '[Project manager]  ·  [Email]')
    d.save(path)


def education_presentation(path):
    d = Deck('1F7A4D', '17352A')
    d.title_slide('[Lesson Title]', '[Course name]  ·  [Class or group]', 'Lesson')
    d.content('Learning objectives', ['By the end of this lesson you will be able to:', '  [Objective 1]',
                                      '  [Objective 2]', '  [Objective 3]'])
    d.content('What you already know', ['[Question to connect with the previous lesson]', '[Short warm-up activity]'])
    d.columns('Key concepts', [('[Concept 1]', '[Definition in plain words]'), ('[Concept 2]', '[Definition in plain words]'),
                               ('[Concept 3]', '[Definition in plain words]')])
    d.content('Worked example', ['[Step 1]', '[Step 2]', '[Step 3]', '[Result and why it matters]'])
    d.columns('Activity', [('Task', '[What students do]'), ('Time', '[Minutes]'), ('Output', '[What they hand in or present]')])
    d.content('Check your understanding', ['1. [Question]', '2. [Question]', '3. [Question]'])
    d.content('Summary', ['[Key point 1]', '[Key point 2]', '[Key point 3]', 'Homework: [task and due date]'])
    d.closing('Questions?', '[Teacher name]  ·  [Contact]')
    d.save(path)


def status_report_presentation(path):
    d = Deck('2D5AA6', '1F2A44')
    d.title_slide('Status Report\n[Project or Team]', 'Reporting period: [From – To]', 'Status report')
    d.columns('Summary', [('Overall', '[On track / At risk / Off track] – [one-line reason]'),
                          ('Done this period', '[Main achievements]'),
                          ('Next period', '[Main planned work]')])
    d.table('Milestones', [['Milestone', 'Planned', 'Forecast', 'Status'],
                           ['[Milestone 1]', '[Date]', '[Date]', 'Done'],
                           ['[Milestone 2]', '[Date]', '[Date]', 'On track'],
                           ['[Milestone 3]', '[Date]', '[Date]', 'At risk']], [4.6, 2.4, 2.4, 2.4])
    d.table('Budget', [['Item', 'Budget', 'Spent', 'Remaining'], ['[Item]', '[Value]', '[Value]', '[Value]'],
                       ['[Item]', '[Value]', '[Value]', '[Value]'], ['Total', '[Value]', '[Value]', '[Value]']],
            [4.6, 2.4, 2.4, 2.4])
    d.table('Issues and risks', [['Issue or risk', 'Impact', 'Owner', 'Action'],
                                 ['[Issue]', 'High', '[Name]', '[Action and date]'],
                                 ['[Risk]', 'Medium', '[Name]', '[Action and date]']], [4.0, 1.8, 2.2, 3.8])
    d.content('Decisions needed', ['[Decision 1, by when]', '[Decision 2, by when]'])
    d.closing('Thank you', '[Name]  ·  [Email]')
    d.save(path)


def training_presentation(path):
    d = Deck('7A4FA3', '2E2140')
    d.title_slide('[Workshop Title]', '[Trainer name]  ·  [Date]  ·  [Duration]', 'Training workshop')
    d.content('Welcome', ['Introductions: name, role, what you expect from today', 'Practical information',
                          '  Breaks, materials, how to ask questions'])
    d.content('Today\'s goals', ['After this workshop you will be able to:', '  [Skill 1]', '  [Skill 2]', '  [Skill 3]'])
    d.table('Programme', [['Time', 'Session', 'Format'], ['[09:00]', '[Topic]', 'Presentation'],
                          ['[10:00]', '[Topic]', 'Hands-on exercise'], ['[11:15]', '[Topic]', 'Group work'],
                          ['[12:00]', 'Wrap-up and feedback', 'Discussion']], [2.4, 6.0, 3.4])
    d.columns('Module 1: [Topic]', [('Why it matters', '[Context]'), ('How it works', '[Explanation]'),
                                    ('Try it', '[Short exercise]')])
    d.content('Exercise', ['[Instructions, step by step]', '[Time available]', '[What to share at the end]'])
    d.content('Key takeaways', ['[Takeaway 1]', '[Takeaway 2]', '[Takeaway 3]', 'Resources: [where to find more]'])
    d.closing('Thank you', 'Please share your feedback: [how]')
    d.save(path)


# ---------------------------------------------------------------------------
# Templates, thumbnails
# ---------------------------------------------------------------------------

TEMPLATE_TYPES = {
    '.dotx': ('word/document.xml',
              'application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml',
              'application/vnd.openxmlformats-officedocument.wordprocessingml.template.main+xml'),
    '.xltx': ('xl/workbook.xml',
              'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml',
              'application/vnd.openxmlformats-officedocument.spreadsheetml.template.main+xml'),
    '.potx': ('ppt/presentation.xml',
              'application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml',
              'application/vnd.openxmlformats-officedocument.presentationml.template.main+xml'),
}

FIXED_TIME = (2026, 1, 1, 0, 0, 0)


def to_template(src, dst):
    """Rewrites the main part's content type, which is all that separates a
    template from a document in OOXML. Entries get a fixed time so rebuilds
    are byte-identical."""
    ext = os.path.splitext(dst)[1]
    _, doc_ct, tpl_ct = TEMPLATE_TYPES[ext]
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == '[Content_Types].xml':
                data = data.replace(doc_ct.encode(), tpl_ct.encode())
            if item.filename == 'docProps/core.xml':
                data = re.sub(rb'<dcterms:(created|modified)([^>]*)>[^<]*<',
                              rb'<dcterms:\1\2>2026-01-01T00:00:00Z<', data)
                data = re.sub(rb'<dc:creator>[^<]*<', b'<dc:creator>Secure Office Suite<', data)
                data = re.sub(rb'<cp:lastModifiedBy>[^<]*<', b'<cp:lastModifiedBy>Secure Office Suite<', data)
            zi = zipfile.ZipInfo(item.filename, FIXED_TIME)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zout.writestr(zi, data)


def soffice(src, fmt, outdir):
    subprocess.run(['soffice', '--headless', '--norestore', '--convert-to', fmt, '--outdir', outdir, src],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=240)
    return os.path.join(outdir, os.path.splitext(os.path.basename(src))[0] + '.' + fmt.split(':')[0])


def recalc_xlsx(src, tmp):
    """Formula results cached by LibreOffice, so the first view of a new
    workbook shows numbers before the editor recalculates."""
    out = os.path.join(tmp, 'recalc')
    os.makedirs(out, exist_ok=True)
    return soffice(src, 'xlsx:Calc MS Excel 2007 XML', out)


def pdf_page_png(pdf, out_png, width=THUMB_W * 2):
    base = out_png[:-4] + '-raw'
    subprocess.run(['pdftoppm', '-png', '-singlefile', '-f', '1', '-l', '1', '-scale-to-x', str(width),
                    '-scale-to-y', '-1', pdf, base], check=True)
    return base + '.png'


def compose_thumb(raw, out, mode):
    """Fits a rendered first page into the card's thumbnail box."""
    im = Image.open(raw).convert('RGB')
    box = Image.new('RGB', (THUMB_W, THUMB_H), (255, 255, 255))
    if mode in ('page', 'sheet'):
        # drop the page margins so the content reads at card size
        bbox = ImageChops.difference(im, Image.new('RGB', im.size, (255, 255, 255))).getbbox()
        if bbox:
            pad = int(im.width * 0.03)
            im = im.crop((max(0, bbox[0] - pad), max(0, bbox[1] - pad),
                          min(im.width, bbox[2] + pad), im.height))
        # top of the page, full width (a sheet keeps a readable scale)
        target = THUMB_W if mode == 'page' else max(THUMB_W, int(im.width * THUMB_W / 900))
        k = target / im.width
        im = im.resize((target, max(1, int(im.height * k))), Image.LANCZOS)
        box.paste(im.crop((0, 0, THUMB_W, min(THUMB_H, im.height))), (0, 0))
    else:                       # whole slide, centred
        box = Image.new('RGB', (THUMB_W, THUMB_H), (240, 240, 240))
        k = min((THUMB_W - 24) / im.width, (THUMB_H - 24) / im.height)
        im = im.resize((int(im.width * k), int(im.height * k)), Image.LANCZOS)
        box.paste(im, ((THUMB_W - im.width) // 2, (THUMB_H - im.height) // 2))
    box.save(out, optimize=True)
    os.remove(raw)


def page_box_for_pdf_form(raw, out):
    compose_thumb(raw, out, 'page')


BUILDERS = [
    ('writer', 'business-letter.dotx', business_letter, 'page'),
    ('writer', 'resume.dotx', resume, 'page'),
    ('writer', 'report.dotx', report, 'page'),
    ('writer', 'meeting-notes.dotx', meeting_notes, 'page'),
    ('writer', 'memo.dotx', memo, 'page'),
    ('writer', 'cover-letter.dotx', cover_letter, 'page'),
    ('writer', 'project-proposal.dotx', project_proposal, 'page'),
    ('writer', 'agenda.dotx', agenda, 'page'),
    ('sheet', 'budget.xltx', budget, 'sheet'),
    ('sheet', 'calendar.xltx', calendar, 'sheet'),
    ('sheet', 'invoice.xltx', invoice, 'sheet'),
    ('sheet', 'financial-report.xltx', financial_report, 'sheet'),
    ('sheet', 'expense-report.xltx', expense_report, 'sheet'),
    ('sheet', 'timesheet.xltx', timesheet, 'sheet'),
    ('sheet', 'project-tracker.xltx', project_tracker, 'sheet'),
    ('presentation', 'business.potx', business_presentation, 'slide'),
    ('presentation', 'project.potx', project_presentation, 'slide'),
    ('presentation', 'education.potx', education_presentation, 'slide'),
    ('presentation', 'status-report.potx', status_report_presentation, 'slide'),
    ('presentation', 'training.potx', training_presentation, 'slide'),
]

# Templates that already ship with the suite (common/templates/EN) and get a
# card too. Thumbnail name -> file, relative to common/templates.
SHIPPED = {
    'en-resume-sky-blue': ('EN/Documents/[32]KJSXG5LNMUQCQ43LPEQGE3DVMUUQ====.dotx', 'page'),
    'en-sop': ('EN/Documents/[32]KN2GC3TEMFZGIICPOBSXEYLUNFXGOICQOJXWGZLEOVZGK===.dotx', 'page'),
    'en-checklist': ('EN/Documents/[32]INUGKY3LNRUXG5BAN5TGM2LDNFQWYIDTOR4WYZI=.dotx', 'page'),
    'en-purchase-order': ('EN/Documents/[32]KB2XEY3IMFZWKIDPOJSGK4RAORSW24DMMF2GK===.dotx', 'page'),
    'en-certificate': ('EN/Documents/[32]INSXE5DJMZUWGYLUMU======.dotx', 'page'),
    'en-gantt': ('EN/Spreadsheet/[32]I5QW45DUEBRWQYLSOQ======.xltx', 'sheet'),
    'en-profit-loss': ('EN/Spreadsheet/[32]KBZG6ZTJOQQGC3TEEBWG643TEBZXIYLUMVWWK3TU.xltx', 'sheet'),
    'en-amortization': ('EN/Spreadsheet/[32]IFWW64TUNF5GC5DJN5XCA43DNBSWI5LMMU======.xltx', 'sheet'),
    'en-staff-schedule': ('EN/Spreadsheet/[32]KN2GCZTGEBZWG2DFMR2WYZI=.xltx', 'sheet'),
    'en-sales-pipeline': ('EN/Spreadsheet/[32]KNQWYZLTEBYGS4DFNRUW4ZI=.xltx', 'sheet'),
    'en-agenda': ('EN/Presentation/[32]IFTWK3TEMEQA====.potx', 'slide'),
    'en-executive-summary': ('EN/Presentation/[32]IV4GKY3VORUXMZJAON2W23LBOJ4Q====.potx', 'slide'),
    'en-timeline': ('EN/Presentation/[32]KRUW2ZLMNFXGK===.potx', 'slide'),
    'en-swot': ('EN/Presentation/[32]KNUW24DMMUQHG53POQQGC3TBNR4XG2LT.potx', 'slide'),
    'en-org-chart': ('EN/Presentation/[32]J5ZGOIDDNBQXE5A=.potx', 'slide'),
    'en-invoice-form': ('EN/Forms/[32]I5SW4ZLSMFWCA2LOOZXWSY3F.pdf', 'page'),
    'en-job-proposal': ('EN/Forms/[32]JJXWEIDQOJXXA33TMFWA====.pdf', 'page'),
    'en-weekly-planner': ('EN/Forms/[32]K5SWK23MPEQHA3DBNZXGK4Q=.pdf', 'page'),
    'en-travel-planner': ('EN/Forms/[32]KRZGC5TFNQQHA3DBNZXGK4Q=.pdf', 'page'),
    'en-license-agreement': ('EN/Forms/[32]JRUWGZLOONSSAYLHOJSWK3LFNZ2A====.pdf', 'page'),
}


def main():
    thumbs = os.path.join(OUT, 'thumbs')
    for d in ('writer', 'sheet', 'presentation', 'thumbs'):
        os.makedirs(os.path.join(OUT, d), exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        for app, name, build, mode in BUILDERS:
            stem, ext = os.path.splitext(name)
            doc_ext = {'.dotx': '.docx', '.xltx': '.xlsx', '.potx': '.pptx'}[ext]
            src = os.path.join(tmp, stem + doc_ext)
            build(src)
            if ext == '.xltx':
                src = recalc_xlsx(src, tmp)
            dst = os.path.join(OUT, app, name)
            to_template(src, dst)
            pdf = soffice(src, 'pdf', tmp)
            compose_thumb(pdf_page_png(pdf, os.path.join(thumbs, stem + '.png')),
                          os.path.join(thumbs, '%s-%s.png' % (app, stem)), mode)
            print('built', os.path.relpath(dst, ROOT))

        tpl_root = os.path.join(ROOT, 'common', 'templates')
        for key, (rel, mode) in SHIPPED.items():
            src = os.path.join(tpl_root, rel)
            if not src.endswith('.pdf'):
                # LibreOffice opens a template as a new document; copy to a
                # plain name so the PDF lands where we expect it
                plain = os.path.join(tmp, key + os.path.splitext(src)[1])
                shutil.copy(src, plain)
                pdf = soffice(plain, 'pdf', tmp)
            else:
                pdf = src
            compose_thumb(pdf_page_png(pdf, os.path.join(thumbs, key + '.png')),
                          os.path.join(thumbs, key + '.png'), mode)
            print('thumb', key)


if __name__ == '__main__':
    main()
