from odoo import api, SUPERUSER_ID

def fix_mail_demo_data(cr, registry):
    """
    حل مؤقت لمشكلة بيانات العرض التوضيحي في وحدة mail
    """
    with api.Environment.manage():
        env = api.Environment(cr, SUPERUSER_ID, {})
        # تحقق مما إذا كانت القناة موجودة بالفعل وقم بتعديل اسمها إذا لزم الأمر
        channel = env.ref('mail.from_notification_message', False)
        if channel:
            try:
                # محاولة تحديث الاسم فقط بدون تغيير الحقول المشكلة
                channel.write({'name': 'Welcome to the #general channel (fixed)'})
            except Exception as e:
                # تسجيل الخطأ ولكن لا ترفع استثناء
                env.cr.rollback()
                print(f"تم تجاهل خطأ في إصلاح بيانات العرض التوضيحي: {e}")