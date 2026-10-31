/*
 * Secure Office Suite: the local template library.
 *
 * Installed with the application as converter/templates/sos/manifest.js and
 * loaded by every start page. Nothing here is fetched from the network: the
 * files sit next to this manifest, so the gallery works on offline PCs.
 *
 * The block between the sos-templates markers is strict JSON, so tools (the
 * CI check, tools/sos-templates/verify_templates.py) read the same list the
 * start page shows. Each entry:
 *   id           stable, unique id: <app>.<name>
 *   app          writer | sheet | presentation | pdf
 *   name         card title
 *   description  one line under the title and in the preview
 *   category     groups the cards on the New page
 *   file         template file, relative to this folder
 *   format       utils.defines.FileFormat key of the file
 *   thumb        preview image (304x264 PNG), relative to this folder
 *   keywords     optional search words
 *
 * To add a template: put the file under writer/, sheet/ or presentation/,
 * its thumbnail under thumbs/, and add an entry. CI opens every listed file
 * with the suite's own converter, so a broken template fails the build.
 * People can also add their own templates without changing the
 * installation: see README.md in this folder ("My templates").
 *
 * Selecting a card opens a new, untitled document made from a copy of the
 * file; the template itself is never written to.
 *
 * The suite's own templates come from tools/sos-templates/make_templates.py
 * in desktop-apps; the en-* entries reuse the templates in ../EN.
 */

(function () {
    'use strict';

    var manifest = /* sos-templates:begin */ {
    "schema": 1,
    "templates": [
        {"id": "writer.business-letter", "app": "writer", "name": "Business letter", "description": "Formal letter with letterhead", "category": "Business", "file": "writer/business-letter.dotx", "format": "FILE_DOCUMENT_DOTX", "thumb": "thumbs/writer-business-letter.png", "keywords": ["letter", "formal", "correspondence"]},
        {"id": "writer.resume", "app": "writer", "name": "Resume", "description": "Clean one-page resume", "category": "Personal", "file": "writer/resume.dotx", "format": "FILE_DOCUMENT_DOTX", "thumb": "thumbs/writer-resume.png", "keywords": ["cv", "job", "career"]},
        {"id": "writer.report", "app": "writer", "name": "Report", "description": "Structured report with headings and tables", "category": "Business", "file": "writer/report.dotx", "format": "FILE_DOCUMENT_DOTX", "thumb": "thumbs/writer-report.png", "keywords": ["analysis", "findings"]},
        {"id": "writer.meeting-notes", "app": "writer", "name": "Meeting notes", "description": "Agenda, decisions and action items", "category": "Business", "file": "writer/meeting-notes.dotx", "format": "FILE_DOCUMENT_DOTX", "thumb": "thumbs/writer-meeting-notes.png", "keywords": ["minutes", "actions"]},
        {"id": "writer.memo", "app": "writer", "name": "Memo", "description": "Internal memorandum", "category": "Business", "file": "writer/memo.dotx", "format": "FILE_DOCUMENT_DOTX", "thumb": "thumbs/writer-memo.png", "keywords": ["memorandum", "internal"]},
        {"id": "writer.cover-letter", "app": "writer", "name": "Cover letter", "description": "Job application letter to go with a resume", "category": "Personal", "file": "writer/cover-letter.dotx", "format": "FILE_DOCUMENT_DOTX", "thumb": "thumbs/writer-cover-letter.png", "keywords": ["job", "application", "letter"]},
        {"id": "writer.project-proposal", "app": "writer", "name": "Project proposal", "description": "Objectives, scope, timeline, budget and approval", "category": "Business", "file": "writer/project-proposal.dotx", "format": "FILE_DOCUMENT_DOTX", "thumb": "thumbs/writer-project-proposal.png", "keywords": ["plan", "budget", "scope"]},
        {"id": "writer.agenda", "app": "writer", "name": "Meeting agenda", "description": "Timed agenda items with leads and outcomes", "category": "Business", "file": "writer/agenda.dotx", "format": "FILE_DOCUMENT_DOTX", "thumb": "thumbs/writer-agenda.png", "keywords": ["meeting", "schedule"]},
        {"id": "writer.en-resume-sky-blue", "app": "writer", "name": "Resume (sky blue)", "description": "Two-column resume with photo", "category": "Personal", "file": "../EN/Documents/[32]KJSXG5LNMUQCQ43LPEQGE3DVMUUQ====.dotx", "format": "FILE_DOCUMENT_DOTX", "thumb": "thumbs/en-resume-sky-blue.png"},
        {"id": "writer.en-sop", "app": "writer", "name": "Standard operating procedure", "description": "Process document with steps", "category": "Business", "file": "../EN/Documents/[32]KN2GC3TEMFZGIICPOBSXEYLUNFXGOICQOJXWGZLEOVZGK===.dotx", "format": "FILE_DOCUMENT_DOTX", "thumb": "thumbs/en-sop.png"},
        {"id": "writer.en-checklist", "app": "writer", "name": "Checklist", "description": "Task checklist, official style", "category": "Business", "file": "../EN/Documents/[32]INUGKY3LNRUXG5BAN5TGM2LDNFQWYIDTOR4WYZI=.dotx", "format": "FILE_DOCUMENT_DOTX", "thumb": "thumbs/en-checklist.png"},
        {"id": "writer.en-purchase-order", "app": "writer", "name": "Purchase order", "description": "Order form with item table", "category": "Business", "file": "../EN/Documents/[32]KB2XEY3IMFZWKIDPOJSGK4RAORSW24DMMF2GK===.dotx", "format": "FILE_DOCUMENT_DOTX", "thumb": "thumbs/en-purchase-order.png"},
        {"id": "writer.en-certificate", "app": "writer", "name": "Certificate", "description": "Certificate of participation", "category": "Personal", "file": "../EN/Documents/[32]INSXE5DJMZUWGYLUMU======.dotx", "format": "FILE_DOCUMENT_DOTX", "thumb": "thumbs/en-certificate.png"},
        {"id": "sheet.budget", "app": "sheet", "name": "Budget", "description": "Monthly budget, planned against actual", "category": "Finance", "file": "sheet/budget.xltx", "format": "FILE_SPREADSHEET_XLTX", "thumb": "thumbs/sheet-budget.png", "keywords": ["money", "household", "expenses"]},
        {"id": "sheet.calendar", "app": "sheet", "name": "Calendar", "description": "Year calendar, change the year to update", "category": "Planning", "file": "sheet/calendar.xltx", "format": "FILE_SPREADSHEET_XLTX", "thumb": "thumbs/sheet-calendar.png", "keywords": ["year", "dates"]},
        {"id": "sheet.invoice", "app": "sheet", "name": "Invoice", "description": "Invoice with totals and tax", "category": "Finance", "file": "sheet/invoice.xltx", "format": "FILE_SPREADSHEET_XLTX", "thumb": "thumbs/sheet-invoice.png", "keywords": ["bill", "billing", "tax"]},
        {"id": "sheet.financial-report", "app": "sheet", "name": "Financial report", "description": "Quarterly income statement and ratios", "category": "Finance", "file": "sheet/financial-report.xltx", "format": "FILE_SPREADSHEET_XLTX", "thumb": "thumbs/sheet-financial-report.png", "keywords": ["income statement", "profit", "quarterly"]},
        {"id": "sheet.expense-report", "app": "sheet", "name": "Expense report", "description": "Expenses with VAT, advance and amount due", "category": "Finance", "file": "sheet/expense-report.xltx", "format": "FILE_SPREADSHEET_XLTX", "thumb": "thumbs/sheet-expense-report.png", "keywords": ["expenses", "claim", "vat", "reimbursement"]},
        {"id": "sheet.timesheet", "app": "sheet", "name": "Timesheet", "description": "Weekly hours, overtime and gross pay", "category": "Planning", "file": "sheet/timesheet.xltx", "format": "FILE_SPREADSHEET_XLTX", "thumb": "thumbs/sheet-timesheet.png", "keywords": ["hours", "time", "payroll"]},
        {"id": "sheet.project-tracker", "app": "sheet", "name": "Project tracker", "description": "Tasks with owners, dates, status and progress", "category": "Planning", "file": "sheet/project-tracker.xltx", "format": "FILE_SPREADSHEET_XLTX", "thumb": "thumbs/sheet-project-tracker.png", "keywords": ["tasks", "status", "todo"]},
        {"id": "sheet.en-gantt", "app": "sheet", "name": "Gantt chart", "description": "Project tasks on a timeline", "category": "Planning", "file": "../EN/Spreadsheet/[32]I5QW45DUEBRWQYLSOQ======.xltx", "format": "FILE_SPREADSHEET_XLTX", "thumb": "thumbs/en-gantt.png", "keywords": ["schedule", "timeline"]},
        {"id": "sheet.en-profit-loss", "app": "sheet", "name": "Profit and loss statement", "description": "Budget against actual by category", "category": "Finance", "file": "../EN/Spreadsheet/[32]KBZG6ZTJOQQGC3TEEBWG643TEBZXIYLUMVWWK3TU.xltx", "format": "FILE_SPREADSHEET_XLTX", "thumb": "thumbs/en-profit-loss.png"},
        {"id": "sheet.en-amortization", "app": "sheet", "name": "Amortization schedule", "description": "Loan repayment plan", "category": "Finance", "file": "../EN/Spreadsheet/[32]IFWW64TUNF5GC5DJN5XCA43DNBSWI5LMMU======.xltx", "format": "FILE_SPREADSHEET_XLTX", "thumb": "thumbs/en-amortization.png"},
        {"id": "sheet.en-staff-schedule", "app": "sheet", "name": "Staff schedule", "description": "Weekly shifts per employee", "category": "Planning", "file": "../EN/Spreadsheet/[32]KN2GCZTGEBZWG2DFMR2WYZI=.xltx", "format": "FILE_SPREADSHEET_XLTX", "thumb": "thumbs/en-staff-schedule.png"},
        {"id": "sheet.en-sales-pipeline", "app": "sheet", "name": "Sales pipeline", "description": "Deals by stage", "category": "Business", "file": "../EN/Spreadsheet/[32]KNQWYZLTEBYGS4DFNRUW4ZI=.xltx", "format": "FILE_SPREADSHEET_XLTX", "thumb": "thumbs/en-sales-pipeline.png"},
        {"id": "presentation.business", "app": "presentation", "name": "Business presentation", "description": "Company overview, results and plan", "category": "Business", "file": "presentation/business.potx", "format": "FILE_PRESENTATION_POTX", "thumb": "thumbs/presentation-business.png", "keywords": ["company", "pitch", "overview"]},
        {"id": "presentation.project", "app": "presentation", "name": "Project presentation", "description": "Scope, timeline, team and risks", "category": "Business", "file": "presentation/project.potx", "format": "FILE_PRESENTATION_POTX", "thumb": "thumbs/presentation-project.png", "keywords": ["plan", "status", "team"]},
        {"id": "presentation.education", "app": "presentation", "name": "Education presentation", "description": "Lesson with objectives and activities", "category": "Education", "file": "presentation/education.potx", "format": "FILE_PRESENTATION_POTX", "thumb": "thumbs/presentation-education.png", "keywords": ["lesson", "class", "teaching"]},
        {"id": "presentation.status-report", "app": "presentation", "name": "Status report", "description": "Milestones, budget, issues and decisions", "category": "Business", "file": "presentation/status-report.potx", "format": "FILE_PRESENTATION_POTX", "thumb": "thumbs/presentation-status-report.png", "keywords": ["progress", "milestones"]},
        {"id": "presentation.training", "app": "presentation", "name": "Training workshop", "description": "Workshop programme, modules and exercises", "category": "Education", "file": "presentation/training.potx", "format": "FILE_PRESENTATION_POTX", "thumb": "thumbs/presentation-training.png", "keywords": ["course", "lesson", "workshop"]},
        {"id": "presentation.en-agenda", "app": "presentation", "name": "Agenda", "description": "Meeting agenda slides", "category": "Business", "file": "../EN/Presentation/[32]IFTWK3TEMEQA====.potx", "format": "FILE_PRESENTATION_POTX", "thumb": "thumbs/en-agenda.png"},
        {"id": "presentation.en-executive-summary", "app": "presentation", "name": "Executive summary", "description": "Key facts and milestones", "category": "Business", "file": "../EN/Presentation/[32]IV4GKY3VORUXMZJAON2W23LBOJ4Q====.potx", "format": "FILE_PRESENTATION_POTX", "thumb": "thumbs/en-executive-summary.png"},
        {"id": "presentation.en-timeline", "app": "presentation", "name": "Timeline", "description": "Events on a timeline", "category": "Business", "file": "../EN/Presentation/[32]KRUW2ZLMNFXGK===.potx", "format": "FILE_PRESENTATION_POTX", "thumb": "thumbs/en-timeline.png"},
        {"id": "presentation.en-swot", "app": "presentation", "name": "SWOT analysis", "description": "Strengths, weaknesses, opportunities, threats", "category": "Business", "file": "../EN/Presentation/[32]KNUW24DMMUQHG53POQQGC3TBNR4XG2LT.potx", "format": "FILE_PRESENTATION_POTX", "thumb": "thumbs/en-swot.png"},
        {"id": "presentation.en-org-chart", "app": "presentation", "name": "Organization chart", "description": "Team structure", "category": "Business", "file": "../EN/Presentation/[32]J5ZGOIDDNBQXE5A=.potx", "format": "FILE_PRESENTATION_POTX", "thumb": "thumbs/en-org-chart.png"},
        {"id": "pdf.en-invoice-form", "app": "pdf", "name": "Invoice form", "description": "Fillable PDF invoice", "category": "Forms", "file": "../EN/Forms/[32]I5SW4ZLSMFWCA2LOOZXWSY3F.pdf", "format": "FILE_DOCUMENT_OFORM_PDF", "thumb": "thumbs/en-invoice-form.png", "keywords": ["bill", "fillable"]},
        {"id": "pdf.en-job-proposal", "app": "pdf", "name": "Job proposal", "description": "Fillable PDF proposal", "category": "Forms", "file": "../EN/Forms/[32]JJXWEIDQOJXXA33TMFWA====.pdf", "format": "FILE_DOCUMENT_OFORM_PDF", "thumb": "thumbs/en-job-proposal.png"},
        {"id": "pdf.en-license-agreement", "app": "pdf", "name": "License agreement", "description": "Fillable PDF agreement", "category": "Forms", "file": "../EN/Forms/[32]JRUWGZLOONSSAYLHOJSWK3LFNZ2A====.pdf", "format": "FILE_DOCUMENT_OFORM_PDF", "thumb": "thumbs/en-license-agreement.png"},
        {"id": "pdf.en-weekly-planner", "app": "pdf", "name": "Weekly planner", "description": "Fillable PDF planner", "category": "Forms", "file": "../EN/Forms/[32]K5SWK23MPEQHA3DBNZXGK4Q=.pdf", "format": "FILE_DOCUMENT_OFORM_PDF", "thumb": "thumbs/en-weekly-planner.png"},
        {"id": "pdf.en-travel-planner", "app": "pdf", "name": "Travel planner", "description": "Fillable PDF planner", "category": "Forms", "file": "../EN/Forms/[32]KRZGC5TFNQQHA3DBNZXGK4Q=.pdf", "format": "FILE_DOCUMENT_OFORM_PDF", "thumb": "thumbs/en-travel-planner.png"}
    ]
} /* sos-templates:end */;

    if ( window.SOS && SOS.templates && SOS.templates.registerFrom )
        SOS.templates.registerFrom(document.currentScript && document.currentScript.src, manifest);
})();
