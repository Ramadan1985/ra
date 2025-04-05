{
    'name': "Archive Management",
    'version': '1.0',
    'summary': "Manage and archive documents",
    'description': """  
        This module allows you to manage and archive documents.  

        Features:  
        - Manage incoming, outgoing and internal documents  
        - Track document status and priority  
        - Categorize documents with tags and categories  
        - Link related documents  
        - Extract and search text from PDF files  
        - Dashboard with document statistics and status  
    """,
    'author': "Your Name",
    'website': "http://www.example.com",
    'category': 'Document Management',
    'license': 'AGPL-3',
    'depends': [
        'base',
        'mail',
        'web',  # إضافة إعتماد على وحدة web للدعم الكامل للواجهة
        'portal',  # إضافة لدعم بعض ميزات البوابة
    ],
    'data': [
        'security/archive_security.xml',
        'security/ir.model.access.csv',
        'data/archive_sequence.xml',
        'data/archive_category_data.xml',

        # تحميل الإجراءات أولاً
        'views/archive_actions.xml',

        # ثم العروض
        'views/archive_dashboard_stats_view.xml',
        'views/archive_dashboard_views.xml',
        'views/archive_management_views.xml',
        'views/archive_directed_to_views.xml',
        'views/archive_sent_by_views.xml',
        'views/archive_contact_views.xml',
        'views/archive_category_views.xml',
        'views/archive_tag_views.xml',
        'reports/archive_report_templates.xml',
        # ثم القوائم أخيراً
        'views/archive_menu.xml',
        'views/archive_dashboard_menu.xml',
        'views/archive_search_wizard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # ملفات CSS
            'mfz_archive/static/src/scss/archive_document_summary.scss',
            #'mfz_archive/static/src/css/dashboard_fix.css',  # إضافة ملف الإصلاح الجديد

            # تحميل Chart.js
            'mfz_archive/static/lib/chart.umd.min.js',
            'mfz_archive/static/src/xml/boolean_button.xml',
            # ملفات JavaScript

            'mfz_archive/static/src/js/archive_rtl_helper.js',
            'mfz_archive/static/src/js/archive_management.js',  # للتحكم في أزرار الإنشاء
            'mfz_archive/static/src/js/archive_dashboard.js',  # الملف الموحد للوحة معلومات Kanban
            'mfz_archive/static/src/components/dashboard.js',  # لوحة المعلومات المتقدمة باستخدام OWL
            'mfz_archive/static/src/js/scanner_action.js',

            'mfz_archive/static/src/scss/archive_rtl.scss',
            'mfz_archive/static/src/scss/archive_management.scss',
            'mfz_archive/static/src/css/dashboard.css',
            # تم استبعاد الملفين المتعارضين
            # 'mfz_archive/static/src/js/kanban_dashboard_view.js',
            # 'mfz_archive/static/src/charts/dashboard_charts.js',
            # إضافة ملف لإصلاح مشاكل الأدوات
            'mfz_archive/static/src/js/widget_compatibility.js',

        ],
        # إضافة أصول البريد لدعم ميزات الرسائل
        'mail.assets_messaging': [
            'mfz_archive/static/src/js/messaging_fixes.js',
        ],

        # إضافة دعم أصول التقرير
        'web.report_assets_common': [
            'mfz_archive/static/src/css/report_styles.css',
        ],
    },
    'application': True,
    'installable': True,
    'auto_install': False,
    'sequence': 1,
}