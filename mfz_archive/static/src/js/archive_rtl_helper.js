/** @odoo-module **/

import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";

/**
 * خدمة دعم RTL للتطبيق في موديول الأرشيف
 */
export const archiveRtlHelperService = {
    dependencies: ["ui"],
    start(env, { ui }) {
        // التحقق من لغة المستخدم من الـ HTML
        const checkRtl = () => {
            // طريقة أكثر أمانًا للحصول على اللغة في Odoo 18
            const htmlElement = document.documentElement;
            const lang = htmlElement.getAttribute('lang') || '';
            const isRtl = lang.startsWith('ar_');

            if (isRtl) {
                // تطبيق RTL على العناصر
                applyRtlToArchiveElements();
            }
        };

        const applyRtlToArchiveElements = () => {
            setTimeout(() => {
                console.log("تطبيق RTL على عناصر الأرشيف");
                document.querySelectorAll('.o_form_view.archive-management-form:not(.o_rtl), .o_list_view:not(.o_rtl), .o_kanban_view:not(.o_rtl)')
                    .forEach(el => el.classList.add('o_rtl'));
            }, 100);
        };

        // تطبيق أولي
        checkRtl();

        // استماع للتغييرات
        ui.bus.addEventListener('ROUTE_CHANGED', applyRtlToArchiveElements);

        return () => {
            ui.bus.removeEventListener('ROUTE_CHANGED', applyRtlToArchiveElements);
        };
    }
};

// تسجيل الخدمة
registry.category("services").add("archive_rtl_helper", archiveRtlHelperService);

export default archiveRtlHelperService;