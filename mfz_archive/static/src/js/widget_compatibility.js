/** @odoo-module **/

import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";

/**
 * إصلاح توافق أدوات Odoo 18
 */
export function setupWidgetCompatibility() {
    // الحصول على سجل الحقول
    const fieldRegistry = registry.category("fields");

    // إنشاء أداة boolean_button قديمة في حالة الحاجة إليها
    if (!fieldRegistry.contains("boolean_button")) {
        console.log("تسجيل أداة boolean_button للتوافق مع الإصدارات السابقة");

        // الحصول على أداة boolean التي ربما حلت محل boolean_button
        const BooleanField = fieldRegistry.get("boolean");

        if (BooleanField) {
            // تسجيل نسخة من boolean كـ boolean_button للتوافق
            fieldRegistry.add("boolean_button", BooleanField);
        }
    }

    // إصلاح أدوات البريد القديمة إذا لزم الأمر
    setupMailWidgetCompatibility();
}

/**
 * إصلاح توافق أدوات البريد
 */
function setupMailWidgetCompatibility() {
    // يمكن إضافة إصلاحات أخرى هنا إذا لزم الأمر
}

// تنفيذ الإصلاحات عند تحميل الملف
setupWidgetCompatibility();

export default { setupWidgetCompatibility };