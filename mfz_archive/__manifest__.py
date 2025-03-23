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
    """,
    'author': "Your Name",
    'website': "http://www.example.com",
    'category': 'Document Management',
    'license': 'AGPL-3',
    'depends': [
        'base',
        'mail',
    ],
    'data': [
        # الأمان
        'security/archive_security.xml',
        'security/ir.model.access.csv',

        # البيانات الأساسية
        'data/archive_sequence.xml',
        'data/archive_category_data.xml',

        # الواجهات والنماذج (دون القوائم)
        'views/archive_management_views.xml',
        'views/archive_directed_to_views.xml',
        'views/archive_sent_by_views.xml',
        'views/archive_contact_views.xml',
        'views/archive_category_views.xml',
        'views/archive_tag_views.xml',
        'views/archive_dashboard_views.xml',

        # القوائم - تجميع كافة القوائم في ملف واحد
        'views/archive_menu.xml',

        # المعالجات - بعد تعريف القوائم
        'views/archive_search_wizard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'mfz_archive/static/src/components/dashboard.js',
            'mfz_archive/static/src/dashboard.xml',
            'mfz_archive/static/src/scss/archive_management.scss',
        ],
    },
    'application': True,
    'installable': True,
    'auto_install': False,
}