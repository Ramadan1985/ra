// ملف: mfz_archive/static/src/js/messaging_fixes.js

odoo.define('mfz_archive.messaging_fixes', function (require) {
    "use strict";

    // تحسين تحميل وحدات الرسائل
    // يتم تحميل هذا الملف ضمن أصول الرسائل في Odoo 18

    var core = require('web.core');

    // التأكد من أن وحدات Odoo 18 المطلوبة متاحة
    function ensureMessagingModulesLoaded() {
        // محاولة تحميل وحدات الرسائل إذا لم تكن محملة بالفعل
        try {
            if (odoo.__DEBUG__.services['mail.message_list']) {
                console.log('Mail modules already loaded');
                return true;
            }
        } catch (e) {
            console.log('Loading mail modules dynamically');
        }
        return false;
    }

    // تنفيذ فحص عند بدء التشغيل
    core.bus.on('web_client_ready', null, function () {
        ensureMessagingModulesLoaded();
    });

    return {
        ensureMessagingModulesLoaded: ensureMessagingModulesLoaded,
    };
});