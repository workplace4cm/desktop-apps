/*
 * Secure Office Suite: "New" page of the start page Backstage.
 * The full template gallery of the current application, with category
 * filters when the templates have several categories.
 */

+function () {
    'use strict';

    var ControllerNew = function (args = {}) {
        args.caption = 'New';
        args.action =
        this.action = 'new';

        this.view = new ViewNew(args);
    };

    ControllerNew.prototype = Object.create(baseController.prototype);
    ControllerNew.prototype.constructor = ControllerNew;

    var ViewNew = function (args) {
        args.tplPage = `
            <div class="action-panel ${args.action}">
                <div class="sos-page">
                    <h1 class="sos-page__title" l10n>${utils.Lang.sosNew}</h1>
                    <div class="sos-page__body"></div>
                </div>
            </div>`;
        args.tplItem = 'nomenuitem';
        args.menu = '.main-column.tool-menu';
        args.field = '.main-column.col-center';

        baseView.prototype.constructor.call(this, args);
    };

    ViewNew.prototype = Object.create(baseView.prototype);
    ViewNew.prototype.constructor = ViewNew;

    utils.fn.extend(ControllerNew.prototype, {
        init: function () {
            baseController.prototype.init.apply(this, arguments);
            this.view.render();

            this.gallery = new SOS.TemplateGallery({categories: true})
                                .render(this.view.$panel.find('.sos-page__body'));
            return this;
        }
    });

    window.ControllerNew = ControllerNew;
}();
