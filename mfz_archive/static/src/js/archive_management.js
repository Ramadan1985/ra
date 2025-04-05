/** @odoo-module **/

import { registry } from "@web/core/registry";

// خدمة للتحكم في أزرار الأرشيف
const archiveButtonService = {
    dependencies: ["ui"],
    start(env, { ui }) {
        // وظيفة للتحقق من أزرار الإنشاء وتحديث حالتها
        const updateArchiveButtons = () => {
            // البحث عن زر الإنشاء في عرض القائمة
            const listCreateButton = document.querySelector('.o_list_button_add');
            // البحث عن زر الإنشاء في عرض الكانبان
            const kanbanCreateButton = document.querySelector('.o-kanban-button-new, .o_kanban_button_new');

            // التحقق ما إذا كنا في صفحة إدارة الأرشيف
            if (window.location.href.includes('archive.management') ||
                document.querySelector('.breadcrumb, .o_breadcrumb')?.textContent.includes('أرشيف')) {

                // الحصول على السياق الحالي
                const currentAction = env.services?.action?.currentController;
                const context = currentAction?.props?.context || {};
                const canCreate = context.can_create;

                // تطبيق الإخفاء/الإظهار على زر القائمة
                if (listCreateButton) {
                    if (canCreate === false) {
                        listCreateButton.style.display = 'none';
                    } else {
                        listCreateButton.style.display = '';
                    }
                }

                // تطبيق الإخفاء/الإظهار على زر الكانبان
                if (kanbanCreateButton) {
                    if (canCreate === false) {
                        kanbanCreateButton.style.display = 'none';
                    } else {
                        kanbanCreateButton.style.display = '';
                    }
                }
            }
        };

        // تسجيل مستمع لتغييرات واجهة المستخدم
        ui.bus.addEventListener("ROUTE_CHANGED", updateArchiveButtons);
        ui.bus.addEventListener("ACTION_MANAGER:UI-UPDATED", updateArchiveButtons);

        // تشغيل التحقق مرة واحدة عند البدء
        updateArchiveButtons();

        // تنظيف عند انتهاء الخدمة
        return () => {
            ui.bus.removeEventListener("ROUTE_CHANGED", updateArchiveButtons);
            ui.bus.removeEventListener("ACTION_MANAGER:UI-UPDATED", updateArchiveButtons);
        };
    },
};

// تسجيل الخدمة
registry.category("services").add("archive_button_service", archiveButtonService);