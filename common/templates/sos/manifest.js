/*
 * Secure Office Suite: templates of the start page galleries.
 *
 * Installed next to the start page as converter/templates/sos/manifest.js and
 * loaded by it. Paths are relative to this file. Everything is local: no
 * template is fetched from the network.
 *
 * To add a template, put the file under writer/, sheet/ or presentation/ (a
 * thumbnail under thumbs/ is optional) and add an entry below:
 *   app          writer | sheet | presentation | pdf
 *   file         template file, relative to this folder
 *   format       utils.defines.FileFormat key of the file
 *   category     groups the cards on the New page
 *   thumb        image, relative to this folder
 * Selecting a card opens a new, untitled document from a copy of the file;
 * the template itself is never changed.
 *
 * The suite's own templates come from tools/sos-templates/make_templates.py
 * in desktop-apps; the en-* entries reuse the templates in ../EN.
 */

(function () {
    'use strict';

    if ( !window.SOS || !SOS.templates || !SOS.templates.registerFrom ) return;

    var DOTX = 'FILE_DOCUMENT_DOTX',
        XLTX = 'FILE_SPREADSHEET_XLTX',
        POTX = 'FILE_PRESENTATION_POTX',
        FORM = 'FILE_DOCUMENT_OFORM_PDF';

    SOS.templates.registerFrom(document.currentScript && document.currentScript.src, [
        // EuroOffice Writer
        {app: 'writer', name: 'Business letter', description: 'Formal letter with letterhead', category: 'Business',
            file: 'writer/business-letter.dotx', format: DOTX, thumb: 'thumbs/writer-business-letter.png'},
        {app: 'writer', name: 'Resume', description: 'Clean one-page resume', category: 'Personal',
            file: 'writer/resume.dotx', format: DOTX, thumb: 'thumbs/writer-resume.png'},
        {app: 'writer', name: 'Report', description: 'Structured report with headings and tables', category: 'Business',
            file: 'writer/report.dotx', format: DOTX, thumb: 'thumbs/writer-report.png'},
        {app: 'writer', name: 'Meeting notes', description: 'Agenda, decisions and action items', category: 'Business',
            file: 'writer/meeting-notes.dotx', format: DOTX, thumb: 'thumbs/writer-meeting-notes.png'},
        {app: 'writer', name: 'Memo', description: 'Internal memorandum', category: 'Business',
            file: 'writer/memo.dotx', format: DOTX, thumb: 'thumbs/writer-memo.png'},
        {app: 'writer', name: 'Resume (sky blue)', description: 'Two-column resume with photo', category: 'Personal',
            file: '../EN/Documents/[32]KJSXG5LNMUQCQ43LPEQGE3DVMUUQ====.dotx', format: DOTX, thumb: 'thumbs/en-resume-sky-blue.png'},
        {app: 'writer', name: 'Standard operating procedure', description: 'Process document with steps', category: 'Business',
            file: '../EN/Documents/[32]KN2GC3TEMFZGIICPOBSXEYLUNFXGOICQOJXWGZLEOVZGK===.dotx', format: DOTX, thumb: 'thumbs/en-sop.png'},
        {app: 'writer', name: 'Checklist', description: 'Task checklist, official style', category: 'Business',
            file: '../EN/Documents/[32]INUGKY3LNRUXG5BAN5TGM2LDNFQWYIDTOR4WYZI=.dotx', format: DOTX, thumb: 'thumbs/en-checklist.png'},
        {app: 'writer', name: 'Purchase order', description: 'Order form with item table', category: 'Business',
            file: '../EN/Documents/[32]KB2XEY3IMFZWKIDPOJSGK4RAORSW24DMMF2GK===.dotx', format: DOTX, thumb: 'thumbs/en-purchase-order.png'},
        {app: 'writer', name: 'Certificate', description: 'Certificate of participation', category: 'Personal',
            file: '../EN/Documents/[32]INSXE5DJMZUWGYLUMU======.dotx', format: DOTX, thumb: 'thumbs/en-certificate.png'},

        // EuroOffice Sheet
        {app: 'sheet', name: 'Budget', description: 'Monthly budget, planned against actual', category: 'Finance',
            file: 'sheet/budget.xltx', format: XLTX, thumb: 'thumbs/sheet-budget.png'},
        {app: 'sheet', name: 'Calendar', description: 'Year calendar, change the year to update', category: 'Planning',
            file: 'sheet/calendar.xltx', format: XLTX, thumb: 'thumbs/sheet-calendar.png'},
        {app: 'sheet', name: 'Invoice', description: 'Invoice with totals and tax', category: 'Finance',
            file: 'sheet/invoice.xltx', format: XLTX, thumb: 'thumbs/sheet-invoice.png'},
        {app: 'sheet', name: 'Financial report', description: 'Quarterly income statement and ratios', category: 'Finance',
            file: 'sheet/financial-report.xltx', format: XLTX, thumb: 'thumbs/sheet-financial-report.png'},
        {app: 'sheet', name: 'Gantt chart', description: 'Project tasks on a timeline', category: 'Planning',
            file: '../EN/Spreadsheet/[32]I5QW45DUEBRWQYLSOQ======.xltx', format: XLTX, thumb: 'thumbs/en-gantt.png'},
        {app: 'sheet', name: 'Profit and loss statement', description: 'Budget against actual by category', category: 'Finance',
            file: '../EN/Spreadsheet/[32]KBZG6ZTJOQQGC3TEEBWG643TEBZXIYLUMVWWK3TU.xltx', format: XLTX, thumb: 'thumbs/en-profit-loss.png'},
        {app: 'sheet', name: 'Amortization schedule', description: 'Loan repayment plan', category: 'Finance',
            file: '../EN/Spreadsheet/[32]IFWW64TUNF5GC5DJN5XCA43DNBSWI5LMMU======.xltx', format: XLTX, thumb: 'thumbs/en-amortization.png'},
        {app: 'sheet', name: 'Staff schedule', description: 'Weekly shifts per employee', category: 'Planning',
            file: '../EN/Spreadsheet/[32]KN2GCZTGEBZWG2DFMR2WYZI=.xltx', format: XLTX, thumb: 'thumbs/en-staff-schedule.png'},
        {app: 'sheet', name: 'Sales pipeline', description: 'Deals by stage', category: 'Business',
            file: '../EN/Spreadsheet/[32]KNQWYZLTEBYGS4DFNRUW4ZI=.xltx', format: XLTX, thumb: 'thumbs/en-sales-pipeline.png'},

        // EuroOffice Presentation
        {app: 'presentation', name: 'Business presentation', description: 'Company overview, results and plan', category: 'Business',
            file: 'presentation/business.potx', format: POTX, thumb: 'thumbs/presentation-business.png'},
        {app: 'presentation', name: 'Project presentation', description: 'Scope, timeline, team and risks', category: 'Business',
            file: 'presentation/project.potx', format: POTX, thumb: 'thumbs/presentation-project.png'},
        {app: 'presentation', name: 'Education presentation', description: 'Lesson with objectives and activities', category: 'Education',
            file: 'presentation/education.potx', format: POTX, thumb: 'thumbs/presentation-education.png'},
        {app: 'presentation', name: 'Agenda', description: 'Meeting agenda slides', category: 'Business',
            file: '../EN/Presentation/[32]IFTWK3TEMEQA====.potx', format: POTX, thumb: 'thumbs/en-agenda.png'},
        {app: 'presentation', name: 'Executive summary', description: 'Key facts and milestones', category: 'Business',
            file: '../EN/Presentation/[32]IV4GKY3VORUXMZJAON2W23LBOJ4Q====.potx', format: POTX, thumb: 'thumbs/en-executive-summary.png'},
        {app: 'presentation', name: 'Timeline', description: 'Events on a timeline', category: 'Business',
            file: '../EN/Presentation/[32]KRUW2ZLMNFXGK===.potx', format: POTX, thumb: 'thumbs/en-timeline.png'},
        {app: 'presentation', name: 'SWOT analysis', description: 'Strengths, weaknesses, opportunities, threats', category: 'Business',
            file: '../EN/Presentation/[32]KNUW24DMMUQHG53POQQGC3TBNR4XG2LT.potx', format: POTX, thumb: 'thumbs/en-swot.png'},
        {app: 'presentation', name: 'Organization chart', description: 'Team structure', category: 'Business',
            file: '../EN/Presentation/[32]J5ZGOIDDNBQXE5A=.potx', format: POTX, thumb: 'thumbs/en-org-chart.png'},

        // EuroOffice PDF: fillable PDF forms
        {app: 'pdf', name: 'Invoice form', description: 'Fillable PDF invoice', category: 'Forms',
            file: '../EN/Forms/[32]I5SW4ZLSMFWCA2LOOZXWSY3F.pdf', format: FORM, thumb: 'thumbs/en-invoice-form.png'},
        {app: 'pdf', name: 'Job proposal', description: 'Fillable PDF proposal', category: 'Forms',
            file: '../EN/Forms/[32]JJXWEIDQOJXXA33TMFWA====.pdf', format: FORM, thumb: 'thumbs/en-job-proposal.png'},
        {app: 'pdf', name: 'License agreement', description: 'Fillable PDF agreement', category: 'Forms',
            file: '../EN/Forms/[32]JRUWGZLOONSSAYLHOJSWK3LFNZ2A====.pdf', format: FORM, thumb: 'thumbs/en-license-agreement.png'},
        {app: 'pdf', name: 'Weekly planner', description: 'Fillable PDF planner', category: 'Forms',
            file: '../EN/Forms/[32]K5SWK23MPEQHA3DBNZXGK4Q=.pdf', format: FORM, thumb: 'thumbs/en-weekly-planner.png'},
        {app: 'pdf', name: 'Travel planner', description: 'Fillable PDF planner', category: 'Forms',
            file: '../EN/Forms/[32]KRZGC5TFNQQHA3DBNZXGK4Q=.pdf', format: FORM, thumb: 'thumbs/en-travel-planner.png'},
    ]);
})();
