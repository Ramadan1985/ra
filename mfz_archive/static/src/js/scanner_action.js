/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Dialog } from "@web/core/dialog/dialog";
import { Component, useState, xml } from "@odoo/owl";

class ScannerDialog extends Component {
    setup() {
        this.state = useState({
            message: this.props.message || 'سيتم فتح تطبيق المسح الضوئي',
            isScanning: false,
            error: '',
        });
    }

    openScanner() {
        this.state.isScanning = true;

        // محاولة فتح تطبيق المسح الضوئي
        const scannerUrls = [
            'scanner://',      // بروتوكول عام
            'twain://',        // بروتوكول TWAIN (Windows)
            'scanimage://'     // بروتوكول SANE (Linux)
        ];

        // نحاول فتح أحد البروتوكولات
        let opened = false;
        for (const url of scannerUrls) {
            try {
                window.open(url, '_blank');
                opened = true;
                break;
            } catch (e) {
                console.warn(`فشل في فتح البروتوكول: ${url}`, e);
            }
        }

        if (!opened) {
            this.state.error = 'لم نتمكن من فتح تطبيق المسح الضوئي تلقائيًا.';
        }
    }

    close() {
        this.props.close();
    }
}

ScannerDialog.template = xml`
    <Dialog title="المسح الضوئي" size="'md'" close="() => this.close()">
        <div class="p-4">
            <p t-if="!state.error" class="mb-3" t-esc="state.message"/>
            <div t-if="state.error" class="alert alert-warning" role="alert">
                <p t-esc="state.error"></p>
            </div>

            <div class="mt-4">
                <h5>تعليمات المسح الضوئي:</h5>
                <ol>
                    <li>انقر على زر "بدء المسح الضوئي" أدناه</li>
                    <li>سيتم فتح برنامج المسح الضوئي المثبت على جهازك</li>
                    <li>اختر الإعدادات المناسبة وقم بمسح المستند</li>
                    <li>احفظ الملف بتنسيق PDF على جهازك</li>
                    <li>عد إلى هذه الصفحة وانقر على زر "رفع الملف الممسوح"</li>
                </ol>
            </div>

            <div class="d-flex justify-content-between mt-4">
                <button class="btn btn-primary" t-on-click="openScanner" t-att-disabled="state.isScanning">
                    <i class="fa fa-scanner me-2"/>بدء المسح الضوئي
                </button>
                <button class="btn btn-secondary" t-on-click="close">
                    إغلاق
                </button>
            </div>
        </div>
    </Dialog>
`;

// تسجيل إجراء العميل
const scannerAction = async (env, action) => {
    const dialog = env.services.dialog.add(ScannerDialog, action.params);
    return dialog;
};

registry.category("actions").add("scanner_action", scannerAction);