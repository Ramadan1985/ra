# -*- coding: utf-8 -*-
from odoo import models, fields, api, _, Command
from odoo.exceptions import UserError, ValidationError, AccessError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# مكتبات معالجة النص
import unicodedata
import logging
import re
import base64
from io import BytesIO
import unidecode  # إضافة مكتبة معالجة الأحرف

# محاولة استيراد مكتبات معالجة النص العربي
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    ARABIC_SUPPORT = True
except ImportError:
    ARABIC_SUPPORT = False
    # تسجيل تحذير فقط، لا نريد أن يتوقف النظام
    logging.getLogger(__name__).warning("المكتبات arabic_reshaper و python-bidi غير مثبتة. يرجى تثبيتها باستخدام: pip install arabic-reshaper python-bidi")

# محاولة استيراد مكتبات معالجة PDF
try:
    import PyPDF2
    import pdfplumber
    PDF_LIBRARIES_AVAILABLE = True
except ImportError:
    PDF_LIBRARIES_AVAILABLE = False
    logging.getLogger(__name__).warning("مكتبات PyPDF2 و pdfplumber غير مثبتة. يرجى تثبيتها باستخدام: pip install PyPDF2 pdfplumber")

# إنشاء logger للتتبع
_logger = logging.getLogger(__name__)

class ArchiveManagement(models.Model):
    _name = 'archive.management'
    _description = 'نظام إدارة الأرشيف'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    # الحقول الأساسية
    name = fields.Char(string='Name', required=True, tracking=True)
    reference = fields.Char(string='Reference', tracking=True, readonly=True, copy=False)
    date = fields.Date(string='Date', default=fields.Date.context_today, tracking=True, required=True)
    deadline = fields.Date(string='Deadline', tracking=True)
    description = fields.Html(string='Description')
    notes = fields.Text(string='Notes')
    # إضافة حقل لتاريخ التلخيص (للتتبع فقط)
    summary_date = fields.Datetime(string='تاريخ التلخيص', readonly=True)
    document_type = fields.Selection([
        ('incoming', 'Incoming'),
        ('outgoing', 'Outgoing'),
        ('memo', 'Memo'),
    ], string='Document Type', required=True, default='incoming', tracking=True)
    # الحقل الإضافي لتحديد ما إذا كان السجل جديدًا
    is_new_record = fields.Boolean(default=True, copy=False)
    # باقي الحقول
    file = fields.Binary("PDF File", attachment=True)
    file_name = fields.Char("File Name")
    attachment_id = fields.Many2one('ir.attachment', string="Main Attachment", ondelete='cascade', auto_join=True,
                                    copy=False)
    indexed_content = fields.Text("Extracted Text", related="attachment_id.index_content", store=True)
    indexed_content_2 = fields.Text("Normalized Text", compute='_normalize_arabic_text', store=True)
    sent_by = fields.Many2one('archive.sent.by', string='Sent By', tracking=True)
    directed_to = fields.Many2one('archive.directed.to', string='Directed To', tracking=True)
    user_id = fields.Many2one('res.users', string='Assigned To',
                              default=lambda self: self.env.user.id, tracking=True)
    category_id = fields.Many2one('archive.category', string='Category', tracking=True)
    tag_ids = fields.Many2many('archive.tag', string='Tags')
    attachment_ids = fields.Many2many('ir.attachment', 'archive_attachment_rel', 'archive_id', 'attachment_id',
                                      string='Attachments')
    related_document_ids = fields.Many2many('archive.management', 'archive_related_rel',
                                            'document_id', 'related_id',
                                            string='Related Documents')

    state = fields.Selection([
        ('pending', 'طلب اعتماد'),
        ('approved', 'معتمدة')
    ], string='Status', default='pending', tracking=True, copy=False)

    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Normal'),
        ('2', 'High'),
        ('3', 'Urgent')
    ], string='Priority', default='1', tracking=True)

    confidentiality = fields.Selection([
        ('public', 'Public'),
        ('internal', 'Internal'),
        ('confidential', 'Confidential'),
        ('restricted', 'Restricted')
    ], string='Confidentiality', default='internal', tracking=True)

    image = fields.Binary("Document Image", attachment=True)
    active = fields.Boolean(default=True, string='Active')
    # حقول إحصائيات الأنشطة
    activity_overdue_count = fields.Integer(compute='_compute_activity_count', string="عدد الأنشطة المتأخرة")
    activity_today_count = fields.Integer(compute='_compute_activity_count', string="عدد أنشطة اليوم")
    activity_planned_count = fields.Integer(compute='_compute_activity_count', string="عدد الأنشطة المخططة")

    # ***************** دالة معالجة النص العربي المحدثة *****************
    def action_approve(self):
        # التأكد من وجود صلاحية الاعتماد
        if not self.env.user.has_group('mfz_archive.group_archive_approver'):
            raise UserError("ليس لديك صلاحية اعتماد المستندات")
        self.write({'state': 'approved'})



    def action_reset_to_pending(self):
        for record in self:
            if record.state == 'approved':
                record.state = 'pending'

    @api.depends('indexed_content')
    def _normalize_arabic_text(self):
        for rec in self:
            rec.indexed_content_2 = ''
            if rec.indexed_content:
                try:
                    # 1. تطبيع النص باستخدام unicodedata
                    normalized_text = unicodedata.normalize("NFKC", rec.indexed_content)

                    # قاموس التصحيحات الخاصة
                    corrections = {
                        'الأمن والسالمة': 'الأمن والسلامة',
                        'السالم ة المهنية': 'السلامة المهنية',
                        'موظفبإنشاء': 'موظف بإنشاء',
                        'رئيسقسمه': 'رئيس قسمه',
                        'بعض الملاحظات والتعديلات العامة': 'بعض الملاحظات والتعديلات العامة',
                        'تمالإشارة': 'تم الإشارة',
                        'عيه': 'عليه'
                    }

                    # تطبيق التصحيحات
                    for original, corrected in corrections.items():
                        normalized_text = normalized_text.replace(original, corrected)

                        # 2. معالجة المسافات والفراغات الزائدة
                    normalized_text = re.sub(r'\s+', ' ', normalized_text)

                    # 3. إعادة توزيع المسافات حول علامات الترقيم
                    normalized_text = re.sub(r'([^\w\s])(\w)', r'\1 \2', normalized_text)
                    normalized_text = re.sub(r'(\w)([^\w\s])', r'\1 \2', normalized_text)

                    # 4. معالجة الكلمات المندمجة
                    words = normalized_text.split()
                    corrected_words = []

                    for word in words:
                        # معالجة الكلمات العربية الطويلة
                        if len(word) > 15 and all('\u0600' <= c <= '\u06FF' for c in word):
                            split_words = re.findall(r'[أ-ي]{2,}', word)
                            corrected_words.extend(split_words)
                        else:
                            corrected_words.append(word)

                            # إعادة بناء النص
                    normalized_text = ' '.join(corrected_words)

                    # 5. تنظيف الأحرف غير المرغوب فيها
                    normalized_text = re.sub(r'[^\w\s\u0600-\u06FF.،؟!:()٠-٩-]', '', normalized_text)

                    # 6. تحويل الأرقام العربية إلى إنجليزية
                    for ar_digit, en_digit in self.ar_to_en_digits.items():
                        normalized_text = normalized_text.replace(ar_digit, en_digit)

                        # 7. معالجة الأقواس المربعة
                    normalized_text = re.sub(r'^\[(\d+)\]', r'[\1] ', normalized_text, flags=re.MULTILINE)

                    # 8. الحفاظ على التنسيق العام
                    normalized_text = normalized_text.replace('  ', ' ').strip()

                    rec.indexed_content_2 = normalized_text
                except Exception as e:
                    _logger.error(f"خطأ في معالجة النص العربي: {e}")
                    rec.indexed_content_2 = rec.indexed_content or ''
    ar_to_en_digits = {
        '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
        '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9'
    }
    def advanced_arabic_text_extraction(self):
        """
        استخراج وتنظيف متقدم للنص العربي
        """
        try:
            # استخراج النص من الملف المرفق
            binary_data = base64.b64decode(self.attachment_id.datas)

            # محاولة استخراج النص باستخدام مكتبات متعددة
            extracted_texts = []

            # محاولة PyPDF2
            try:
                pdf_reader = PyPDF2.PdfReader(BytesIO(binary_data))
                for page in pdf_reader.pages:
                    page_text = page.extract_text() or ""
                    extracted_texts.append(page_text)
            except Exception as e1:
                _logger.warning(f"فشل استخراج النص بـ PyPDF2: {e1}")

                # محاولة pdfplumber إذا فشل PyPDF2
            if not extracted_texts:
                try:
                    with pdfplumber.open(BytesIO(binary_data)) as pdf:
                        for page in pdf.pages:
                            page_text = page.extract_text() or ""
                            extracted_texts.append(page_text)
                except Exception as e2:
                    _logger.warning(f"فشل استخراج النص بـ pdfplumber: {e2}")

                    # تجميع النص
            full_text = "\n".join(extracted_texts)

            # معالجات متقدمة للنص
            def advanced_text_cleaning(text):
                # قاموس التصحيحات
                corrections = {
                    'الأمن والسالمة': 'الأمن والسلامة',
                    'السالم ة المهنية': 'السلامة المهنية',
                    'موظفبإنشاء': 'موظف بإنشاء',
                    'رئيسقسمه': 'رئيس قسمه',
                    'الح وادث': 'الحوادث',
                    'عي ه': 'عليه',
                    'خال ل': 'خلال',
                    'المراس الت': 'المراسلات',
                    'تفاصيل الحادثة': 'تفاصيل الحادثة',
                    'بإمكانه': 'بإمكانه',
                    'المشار ألقسامهم': 'المشار لأقسامهم'
                }

                # تطبيق التصحيحات
                for original, corrected in corrections.items():
                    text = text.replace(original, corrected)

                    # معالجة المسافات والفراغات
                text = re.sub(r'\s+', ' ', text)

                # تنظيف علامات الترقيم
                text = re.sub(r'\s*([،.؟!:])\s*', r'\1 ', text)

                # معالجة الأرقام العربية
                ar_to_en_digits = {
                    '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
                    '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9'
                }
                for ar_digit, en_digit in ar_to_en_digits.items():
                    text = text.replace(ar_digit, en_digit)

                    # إزالة الأحرف غير المرغوب فيها
                text = re.sub(r'[^\w\s\u0600-\u06FF.،؟!:()٠-٩-]', '', text)

                return text.strip()

                # تنظيف النص النهائي

            cleaned_text = advanced_text_cleaning(full_text)

            # تحديث حقول النص
            self.write({
                'indexed_content': cleaned_text,
                'indexed_content_2': cleaned_text
            })

            return cleaned_text

        except Exception as e:
            _logger.error(f"خطأ في معالجة النص: {e}")
            return False
    def additional_text_cleaning(self, text):
        """
        دالة إضافية للتنظيف النهائي للنص
        """
        # معالجة الفقرات والعناوين
        text = re.sub(r'\n{2,}', '\n', text)

        # التأكد من وجود مسافات بين الكلمات والعلامات
        text = re.sub(r'([أ-ي])([A-Za-z0-9])', r'\1 \2', text)
        text = re.sub(r'([A-Za-z0-9])([أ-ي])', r'\1 \2', text)

        # معالجة العلامات
        text = re.sub(r'\s*([،.؟!])\s*', r'\1 ', text)

        return text.strip()
    def improve_arabic_extraction(self):
        """تحسين استخراج النص العربي من ملفات PDF مع معالجة متقدمة"""
        self.ensure_one()

        if not self.attachment_id:
            raise UserError("لا يوجد ملف مرفق لهذا المستند")

        try:
            import PyPDF2
            import pdfplumber  # إضافة مكتبة أخرى للاستخراج
        except ImportError:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'تحذير',
                    'message': 'المكتبات PyPDF2 و pdfplumber غير مثبتة. يرجى تثبيتها',
                    'sticky': True,
                    'type': 'warning',
                }
            }

        try:
            # الحصول على محتوى الملف
            binary_data = base64.b64decode(self.attachment_id.datas)
            pdf_file = BytesIO(binary_data)

            # محاولة استخراج النص باستخدام مكتبتين
            text = ""

            # المحاولة الأولى باستخدام PyPDF2
            try:
                reader = PyPDF2.PdfReader(pdf_file)
                for page_num in range(len(reader.pages)):
                    try:
                        page = reader.pages[page_num]
                        page_text = page.extract_text() or ""
                        text += page_text + "\n\n"
                    except Exception as page_error:
                        _logger.warning(f"خطأ في استخراج النص من الصفحة {page_num} بواسطة PyPDF2: {page_error}")

            except Exception as e:
                _logger.warning(f"فشل استخراج النص بواسطة PyPDF2: {e}")

                # إعادة فتح الملف للمحاولة الثانية
            if not text.strip():
                try:
                    with pdfplumber.open(pdf_file) as pdf:
                        for page in pdf.pages:
                            page_text = page.extract_text() or ""
                            text += page_text + "\n\n"
                except Exception as e:
                    _logger.warning(f"فشل استخراج النص بواسطة pdfplumber: {e}")

                    # التحقق من وجود نص
            if not text.strip():
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'تنبيه',
                        'message': 'لم يتم العثور على نص قابل للاستخراج. قد يحتاج المستند إلى معالجة OCR.',
                        'sticky': True,
                        'type': 'warning',
                    }
                }

                # تحديث محتوى المرفق
            self.attachment_id.write({
                'index_content': text
            })

            # إعادة معالجة النص
            self._normalize_arabic_text()

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'نجاح',
                    'message': 'تم تحسين استخراج النص العربي بنجاح.',
                    'sticky': False,
                    'type': 'success',
                }
            }

        except Exception as e:
            _logger.error(f"خطأ في استخراج النص من PDF: {e}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'خطأ',
                    'message': f'حدث خطأ أثناء معالجة الملف: {str(e)}',
                    'sticky': True,
                    'type': 'danger',
                }
            }

            # قاموس تحويل الأرقام العربية إلى الإنجليزية
    def final_text_validation(self, text):
        """التحقق النهائي وتنقية النص"""
        # إزالة السطور الفارغة
        text = re.sub(r'\n{2,}', '\n', text)

        # التأكد من وجود مسافات بين الكلمات
        text = re.sub(r'([أ-ي])([A-Za-z0-9])', r'\1 \2', text)
        text = re.sub(r'([A-Za-z0-9])([أ-ي])', r'\1 \2', text)

        return text.strip()
    def advanced_arabic_text_cleanup(self, text):
        """
        معالجة متقدمة للنص العربي مع معالجة التحديات المحددة
        """
        # 1. إزالة الأسطر الفارغة والمسافات الزائدة
        text = re.sub(r'\n+', '\n', text).strip()

        # 2. معالجة الكلمات الشائعة
        corrections = {
            'الأمن والسالمة': 'الأمن والسلامة',
            'السالم ة المهنية': 'السلامة المهنية',
            'موظفبإنشاء': 'موظف بإنشاء',
            'رئيسقسمه': 'رئيس قسمه',
            'الح وادث': 'الحوادث',
        }

        for original, corrected in corrections.items():
            text = text.replace(original, corrected)

            # 3. تنظيف المسافات حول علامات الترقيم
        text = re.sub(r'\s*([،.؟!:])\s*', r'\1 ', text)

        # 4. معالجة الأقواس المربعة
        text = re.sub(r'\[\s*(\d+)\s*\]', r'[\1]', text)

        # 5. توحيد المسافات بين الكلمات
        text = re.sub(r'\s+', ' ', text)

        # 6. معالجة الهمزات والألفاظ المركبة
        text = unidecode(text)

        return text.strip()
    def process_document_text(self):
        """
        معالجة النص المستخرج بشكل شامل
        """
        try:
            # استخراج النص من المرفق
            extracted_text = self._extract_pdf_text()

            # تنظيف النص
            cleaned_text = self.advanced_arabic_text_cleanup(extracted_text)

            # تحديث حقول النص
            self.write({
                'indexed_content': cleaned_text,
                'indexed_content_2': cleaned_text
            })

            return cleaned_text

        except Exception as e:
            _logger.error(f"خطأ في معالجة النص: {e}")
            return False
    def generate_summary(self):
        """دالة توليد ملخص للنص المستخرج من الملف مع تحسين التعامل مع اللغة العربية"""
        self.ensure_one()

        if not self.indexed_content_2 and not self.indexed_content:
            raise UserError("لا يوجد نص مستخرج لتلخيصه. تأكد من أن المستند تم فهرسته بشكل صحيح.")

            # استخدام النص المعالج إن وجد، وإلا استخدام النص الأصلي
        text_to_summarize = self.indexed_content_2 or self.indexed_content

        try:
            # تنظيف النص
            cleaned_text = text_to_summarize

            # تقسيم النص إلى جمل - استخدام علامات الترقيم العربية والإنجليزية
            sentences = re.split(r'[.!?؟;،:\n]', cleaned_text)
            sentences = [s.strip() for s in sentences if len(s.strip()) > 10]

            if not sentences:
                raise UserError("لم يتم العثور على جمل كافية للتلخيص في النص.")

                # إعداد الكلمات المفتاحية الهامة التي يجب الانتباه لها في النص
            important_keywords = [
                "تقرير", "ملاحظات", "تعديلات", "الأمن", "السلامة",
                "مهم", "اعتماد", "بلاغات", "تدريب", "نظام", "إضافة",
                "تغيير", "سجل", "قسم", "وزارة", "شركة", "يجب", "ضرورة"
            ]

            # 1. حساب تكرار الكلمات
            word_freq = {}
            for sentence in sentences:
                words = sentence.split()
                for word in words:
                    word = word.lower()
                    if len(word) > 2:  # تجاهل الكلمات القصيرة
                        word_freq[word] = word_freq.get(word, 0) + 1

                        # 2. اختيار الكلمات المهمة (الأكثر تكرارًا)
            top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:30]
            important_words = [word for word, _ in top_words]

            # إضافة الكلمات المفتاحية المحددة مسبقاً إلى قائمة الكلمات المهمة
            for keyword in important_keywords:
                if keyword.lower() not in important_words:
                    important_words.append(keyword.lower())

                    # 3. حساب أهمية كل جملة
            sentence_scores = {}
            for i, sentence in enumerate(sentences):
                # إعطاء وزن أكبر للجمل الأولى والأخيرة
                position_score = 0
                if i < min(3, len(sentences)):
                    position_score = 3  # أهمية أكبر للجمل الأولى
                elif i >= len(sentences) - 3:
                    position_score = 1  # أهمية متوسطة للجمل الأخيرة

                # حساب نقاط الكلمات المهمة
                words = sentence.split()
                word_score = 0
                for word in words:
                    word = word.lower()
                    if word in important_words:
                        word_score += 1
                        # نقاط إضافية للكلمات المفتاحية المحددة مسبقاً
                    if word in important_keywords:
                        word_score += 2

                        # نقاط إضافية للجمل ذات الطول المناسب
                length_score = 0
                if 10 <= len(words) <= 25:
                    length_score = 2

                    # الدرجة النهائية هي مجموع الدرجات المختلفة
                sentence_scores[i] = position_score + word_score + length_score

                # 4. اختيار أفضل الجمل
            # عدد الجمل يعتمد على طول النص: 20% من الجمل بحد أدنى 3 وحد أقصى 8
            num_sentences = min(max(3, len(sentences) // 5), 8)

            top_sentences = sorted(sentence_scores.items(), key=lambda x: x[1], reverse=True)[:num_sentences]
            top_sentences = sorted([idx for idx, _ in top_sentences])  # ترتيب الجمل حسب الترتيب الأصلي

            # 5. بناء الملخص
            summary_sentences = []
            for idx in top_sentences:
                if idx < len(sentences):
                    summary_sentences.append(sentences[idx])

            summary = '. '.join(summary_sentences)

            # معالجة النص العربي للعرض في واجهة المستخدم
            if ARABIC_SUPPORT:
                try:
                    # تنسيق النص بشكل صحيح للعرض
                    summary = re.sub(r'\s+', ' ', summary).strip()
                except Exception as e:
                    _logger.error(f"خطأ في معالجة النص العربي النهائي: {e}")

                    # إنشاء ملخص منسق مع دعم RTL
            formatted_summary = f"""<div dir="rtl" class="document-summary" style="text-align: right; line-height: 1.6; font-family: 'Arial', sans-serif;">  
                <p><strong>ملخص المستند:</strong></p>  
                <p>{summary}</p>  
                <hr/>  
                <p><small>تم إنشاء هذا الملخص تلقائيًا بتاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}</small></p>  
            </div>"""

            # حفظ الملخص في حقل الوصف
            self.write({
                'description': formatted_summary,
                'summary_date': fields.Datetime.now()
            })

            # تسجيل نشاط في سجل المستند
            self.message_post(
                body="تم توليد ملخص للمستند تلقائيًا.",
                message_type='comment'
            )

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'تم التلخيص بنجاح',
                    'message': 'تم توليد ملخص للمستند بنجاح وحفظه في وصف المستند.',
                    'sticky': False,
                    'type': 'success',
                }
            }

        except Exception as e:
            _logger.error(f"Error generating summary: {e}")
            raise UserError(f"حدث خطأ أثناء تلخيص المستند: {str(e)}")

            # ***************** نهاية دالة تلخيص النص *****************
    @api.model
    def _check_document_type_access(self, doc_type):
        """
        التحقق من صلاحية الوصول إلى نوع معين من المستندات
        """
        user = self.env.user

        # المدير لديه صلاحية على كل شيء
        if user.has_group('mfz_archive.group_archive_manager'):
            return True

            # مسؤول المستندات الواردة
        if doc_type == 'incoming' and user.has_group('mfz_archive.group_archive_incoming_manager'):
            return True

            # مسؤول المستندات الصادرة
        if doc_type == 'outgoing' and user.has_group('mfz_archive.group_archive_outgoing_manager'):
            return True

            # مسؤول المذكرات الداخلية
        if doc_type == 'memo' and user.has_group('mfz_archive.group_archive_memo_manager'):
            return True

            # المستخدمون العاديون يمكنهم فقط رؤية مستنداتهم الخاصة (تتم معالجة هذا في قواعد الأمان)
        return user.has_group('mfz_archive.group_archive_user')
    def check_access_rights(self, operation, raise_exception=True):
        """
        التحقق من صلاحيات الوصول العامة
        """
        result = super(ArchiveManagement, self).check_access_rights(operation, raise_exception=False)

        # إذا كان لدى المستخدم صلاحيات عامة، عد النتيجة
        if result:
            return True

            # خلاف ذلك، تحقق من الصلاحيات المخصصة
        user = self.env.user
        if operation == 'write' or operation == 'unlink':
            # تحقق مما إذا كان المستخدم مديرًا أو مسؤولاً عن نوع المستند
            if user.has_group('mfz_archive.group_archive_manager'):
                return True
            if operation == 'write':
                # السماح للمستخدمين بتعديل مستنداتهم الخاصة فقط
                if not self.ids:  # حالة check_access_rights العامة
                    return True

                    # إذا لم يتم العثور على صلاحيات ورفع الاستثناءات مطلوب
        if not result and raise_exception:
            raise AccessError("ليس لديك الصلاحيات اللازمة لتنفيذ هذه العملية!")

        return result
    def check_access_rule(self, operation):
        """
        التحقق من قواعد الوصول لسجلات محددة
        """
        # السماح بالوصول الكامل للمدير
        if self.env.user.has_group('mfz_archive.group_archive_manager'):
            return

            # التحقق من قواعد الوصول القياسية أولاً
        super(ArchiveManagement, self).check_access_rule(operation)

        # قواعد إضافية خاصة بأنواع المستندات
        if operation in ('write', 'unlink'):
            # التحقق من كل سجل
            for record in self:
                # المستخدمون العاديون يمكنهم تعديل مستنداتهم الخاصة فقط
                if self.env.user.id == record.user_id.id or self.env.user.id == record.create_uid.id:
                    continue

                    # المسؤولون المتخصصون يمكنهم تعديل المستندات من نوعهم
                doc_type = record.document_type
                if doc_type == 'incoming' and self.env.user.has_group('mfz_archive.group_archive_incoming_manager'):
                    continue
                if doc_type == 'outgoing' and self.env.user.has_group('mfz_archive.group_archive_outgoing_manager'):
                    continue
                if doc_type == 'memo' and self.env.user.has_group('mfz_archive.group_archive_memo_manager'):
                    continue

                    # إذا وصلنا إلى هنا، فليس لدى المستخدم صلاحيات كافية
                raise AccessError(
                    f"لا يُسمح لك بتنفيذ عملية {operation} على مستند {dict(self._fields['document_type'].selection).get(doc_type)}. "
                    "فقط منشئه أو المستخدم المعين أو مدير نوع المستند المعني يمكنه القيام بذلك."
                )

    def action_reset_to_pending(self):
        """
        تعديل دالة إعادة التعيين للتحقق من الصلاحيات
        """
        for record in self:
            # التحقق من صلاحيات إعادة التعيين - فقط مدير النظام يمكنه ذلك
            if not self.env.user.has_group('mfz_archive.group_archive_manager'):
                raise AccessError("يمكن لمديري النظام فقط إعادة تعيين اعتماد المستند.")

            if record.state == 'approved':
                record.state = 'pending'
                record.message_post(body=f"تمت إعادة المستند إلى حالة طلب الاعتماد بواسطة {self.env.user.name}.")
    @api.model
    def _check_create_permissions(self, vals):
        """
        التحقق من صلاحيات إنشاء مستند جديد
        """
        doc_type = vals.get('document_type', 'incoming')
        user = self.env.user

        # المدير يمكنه إنشاء أي نوع من المستندات
        if user.has_group('mfz_archive.group_archive_manager'):
            return True

            # التحقق من صلاحيات المستخدمين المتخصصين
        if doc_type == 'incoming' and not user.has_group(
                'mfz_archive.group_archive_incoming_manager') and not user.has_group('mfz_archive.group_archive_user'):
            raise AccessError("ليس لديك إذن لإنشاء مستندات واردة.")

        if doc_type == 'outgoing' and not user.has_group(
                'mfz_archive.group_archive_outgoing_manager') and not user.has_group('mfz_archive.group_archive_user'):
            raise AccessError("ليس لديك إذن لإنشاء مستندات صادرة.")

        if doc_type == 'memo' and not user.has_group('mfz_archive.group_archive_memo_manager') and not user.has_group(
                'mfz_archive.group_archive_user'):
            raise AccessError("ليس لديك إذن لإنشاء مذكرات داخلية.")

            # تعيين المستخدم الحالي كمسؤول إذا لم يتم تحديد ذلك
        if not vals.get('user_id'):
            vals['user_id'] = user.id

        return True

        # ---- نهاية الدوال الجديدة للصلاحيات ----
    # دالة حساب عدد الأنشطة
    def _compute_activity_count(self):
        for record in self:
            record.activity_overdue_count = self.env['mail.activity'].search_count([
                ('res_model', '=', 'archive.management'),
                ('res_id', '=', record.id),
                ('date_deadline', '<', fields.Date.today())
            ])
            record.activity_today_count = self.env['mail.activity'].search_count([
                ('res_model', '=', 'archive.management'),
                ('res_id', '=', record.id),
                ('date_deadline', '=', fields.Date.today())
            ])
            record.activity_planned_count = self.env['mail.activity'].search_count([
                ('res_model', '=', 'archive.management'),
                ('res_id', '=', record.id),
                ('date_deadline', '>', fields.Date.today())
            ])

            # دالة لعرض الأنشطة
    def action_view_activities(self):
        self.ensure_one()
        return {
            'name': "أنشطة المستند",
            'type': 'ir.actions.act_window',
            'res_model': 'mail.activity',
            'view_mode': 'tree,form',
            'domain': [('res_model', '=', 'archive.management'), ('res_id', '=', self.id)],
            'context': {'default_res_model': 'archive.management', 'default_res_id': self.id},
            'target': 'new',
        }

        # دالة لعرض ملخص المستند
    def action_view_full_summary(self):
        self.ensure_one()
        return {
            'name': "ملخص المستند",
            'type': 'ir.actions.act_window',
            'res_model': 'archive.management',
            'view_mode': 'form',
            'res_id': self.id,
            'view_id': self.env.ref('mfz_archive.view_archive_document_summary').id,
            'target': 'new',
        }

        # دالة إعادة معالجة النص
    def action_reprocess_text(self):
        """إعادة معالجة النص المستخرج من ملف PDF"""
        for record in self:
            if record.attachment_id:
                # تحديث النص المستخرج من الملف
                if hasattr(record.attachment_id, '_index_content'):
                    record.attachment_id._index_content()
                    # إعادة حساب النص المعالج
                record._normalize_arabic_text()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': "تمت إعادة المعالجة",
                'message': "تمت إعادة معالجة النص المستخرج من الملف بنجاح.",
                'sticky': False,
                'type': 'success',
            }
        }
    @api.constrains('document_type')
    def _check_document_type_change(self):
        for record in self:
            if not record.is_new_record and record._origin and record._origin.document_type != record.document_type:
                raise ValidationError("لا يمكنك تغيير نوع المستند بعد الإنشاء.")

    def write(self, vals):
        # التحقق من صلاحية التعديل على المستندات المعتمدة
        for record in self:
            # السماح بإعادة الحالة للاعتماد للمستخدمين المصرح لهم
            if record.state == 'approved' and vals.get('state') == 'pending':
                if not self.env.user.has_group('mfz_archive.group_archive_approver'):
                    raise UserError("ليس لديك صلاحية إعادة المستند للاعتماد")

                    # منع التعديل على المستندات المعتمدة ما لم يكن هناك استثناء
            elif record.state == 'approved' and any(
                    key not in ['state', 'message_follower_ids', 'activity_ids', 'message_ids'] for key in vals):
                raise UserError("لا يمكن تعديل المستند المعتمد")

                # إذا كان السجل جديدًا وتمت كتابته، ضع is_new_record إلى False
        if self.is_new_record:
            vals['is_new_record'] = False

            # معالجة ملف PDF إذا تم تحديثه
        if 'file' in vals and vals.get('file'):
            for record in self:
                attachment = self.env['ir.attachment'].create({
                    'name': vals.get('file_name', record.file_name or 'document.pdf'),
                    'datas': vals['file'],
                    'res_model': 'archive.management',
                    'res_id': record.id,
                    'mimetype': 'application/pdf',
                })
                vals['attachment_id'] = attachment.id

                # إذا تم تفعيل التلخيص التلقائي، قم بتلخيص المستند تلقائياً
                auto_summary = self.env['ir.config_parameter'].sudo().get_param('archive_management.auto_summary',
                                                                                'False')
                if auto_summary == 'True':
                    # جدولة تلخيص بعد الفهرسة
                    self.env.cr.commit()  # حفظ التغييرات الحالية قبل المعالجة

                    # جدولة نشاط للتلخيص
                    record.activity_schedule(
                        'mail.mail_activity_data_todo',
                        summary="تلخيص المستند تلقائيًا",
                        note="تم جدولة تلخيص تلقائي للمستند بعد رفع الملف.",
                        user_id=self.env.user.id,
                        date_deadline=fields.Date.today()
                    )

        return super(ArchiveManagement, self).write(vals)
    def action_view_history(self):
        self.ensure_one()
        return {
            'name': "سجل المستند",
            'type': 'ir.actions.act_window',
            'res_model': 'mail.message',
            'view_mode': 'tree,form',
            'domain': [('model', '=', 'archive.management'), ('res_id', '=', self.id)],
            'context': {'default_model': 'archive.management', 'default_res_id': self.id},
            'target': 'new',
        }
    def action_open_attachment(self):
        self.ensure_one()
        if self.attachment_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'ir.attachment',
                'res_id': self.attachment_id.id,
                'view_mode': 'form',
                'target': 'current',
                'name': "المرفق",
            }
        else:
            return False

    def unlink(self):
        # التحقق من الصلاحيات قبل الحذف
        for record in self:
            # فحص الصلاحية الجديدة للحذف
            can_delete_by_group = (
                self.env.user.has_group('mfz_archive.group_archive_deleter')
            )

            # الصلاحيات الحالية
            can_delete_by_role = (
                    self.env.user.has_group('mfz_archive.group_archive_manager') or
                    (record.document_type == 'incoming' and self.env.user.has_group(
                        'mfz_archive.group_archive_incoming_manager')) or
                    (record.document_type == 'outgoing' and self.env.user.has_group(
                        'mfz_archive.group_archive_outgoing_manager')) or
                    (record.document_type == 'memo' and self.env.user.has_group(
                        'mfz_archive.group_archive_memo_manager'))
            )

            # التحقق من الصلاحية (إما المجموعة الجديدة أو الصلاحيات الحالية)
            if not (can_delete_by_group or can_delete_by_role):
                raise AccessError("ليس لديك إذن لحذف هذا المستند.")

                # التحقق من الحالة
            if record.state != 'pending':
                raise UserError("يمكنك فقط حذف المستندات في حالة طلب الاعتماد.")

                # حذف المرفق المرتبط إن وجد
            if record.attachment_id:
                try:
                    record.attachment_id.unlink()
                except Exception as e:
                    _logger.warning(f"خطأ في حذف المرفق المرتبط: {e}")

        return super(ArchiveManagement, self).unlink()
        # دوال مساعدة للحصول على آخر رقم مستخدم وتعديل نظام التسلسل
    @api.model
    def _get_last_used_sequence(self, sequence_code, current_year, doc_type_code, field='name'):
        """
        الحصول على آخر رقم مستخدم فعليًا في النظام
        """
        # نمط للمطابقة استنادًا إلى نوع الحقل
        if field == 'name':
            # نمط مثل: mfz/2025/1/0001
            pattern = f"mfz/{current_year}/{doc_type_code}/([0-9]+)"
        else:
            # للمرجع، يمكننا استخدام أي رقم في نهاية السلسلة
            pattern = f".*?([0-9]+)$"

            # البحث عن آخر سجل بناءً على نوع المستند والسنة
        domain = [
            ('document_type', '=', self._get_document_type_from_code(doc_type_code)),
            (field, '=ilike', f"%{current_year}%")
        ]

        # البحث عن أحدث السجلات أولاً
        last_records = self.search(domain, order='id desc', limit=20)

        highest_seq = 0
        # استخراج الأرقام من الأسماء المطابقة للنمط
        for record in last_records:
            value = getattr(record, field, '')
            if value:
                match = re.search(pattern, value)
                if match:
                    try:
                        seq = int(match.group(1))
                        if seq > highest_seq:
                            highest_seq = seq
                    except ValueError:
                        continue

                        # Eliminar la línea que utiliza _logger
        # if highest_seq > 0:
        #     _logger.info(f"Found highest used sequence number: {highest_seq} for {field}")
        # else:
        #     _logger.info(f"No existing sequence found for {field}, starting from 1")

        if highest_seq > 0:
            return highest_seq
        else:
            return 0  # سنبدأ من 1
    @api.model
    def _get_document_type_from_code(self, doc_type_code):
        """تحويل رمز نوع المستند إلى نوع المستند"""
        if doc_type_code == 1:
            return 'incoming'
        elif doc_type_code == 2:
            return 'outgoing'
        elif doc_type_code == 3:
            return 'memo'
        else:
            return 'incoming'  # افتراضي
    @api.model
    def _get_next_sequence_for_year(self, doc_type, current_year, field='name'):
        """
        الحصول على الرقم التسلسلي التالي بناءً على آخر رقم مستخدم + 1
        """
        # الحصول على رمز نوع المستند
        if doc_type == 'incoming':
            doc_type_code = 1
        elif doc_type == 'outgoing':
            doc_type_code = 2
        elif doc_type == 'memo':
            doc_type_code = 3
        else:
            doc_type_code = 0

            # الحصول على آخر رقم مستخدم
        last_seq = self._get_last_used_sequence(doc_type, current_year, doc_type_code, field)

        # زيادة الرقم بواحد
        next_seq = last_seq + 1

        # تنسيق الرقم مع تعبئة أصفار
        return f"{next_seq:04d}"

        # دالة إنشاء السجلات مع النظام الجديد للترقيم
    @api.model_create_multi
    def create(self, vals_list):
        result = []
        for vals in vals_list:
            # التحقق من الصلاحيات
            self._check_create_permissions(vals)

            # الحصول على السنة الحالية للتسلسلات
            current_year = datetime.now().year

            # تعيين is_new_record إلى True لجميع السجلات الجديدة
            vals['is_new_record'] = True

            # التحقق من نوع المستند والتأكد من وجوده
            doc_type = vals.get('document_type', 'incoming')
            if doc_type not in ['incoming', 'outgoing', 'memo']:
                doc_type = 'incoming'
                vals['document_type'] = doc_type

                # إنشاء المرجع التسلسلي
            if not vals.get('reference'):
                next_number = self._get_next_sequence_for_year(doc_type, current_year, 'reference')
                vals['reference'] = f"{doc_type[:3]}/{current_year}/{next_number}"
                _logger.info(f"تم تعيين المرجع إلى '{vals['reference']}' للسجل الجديد")

                # إنشاء الاسم إذا لم يتم توفيره
            if not vals.get('name'):
                document_type_code = self._get_document_type_code_from_type(doc_type)
                next_sequence = self._get_next_sequence_for_year(doc_type, current_year, 'name')
                vals['name'] = f"mfz/{current_year}/{document_type_code}/{next_sequence}"
                _logger.info(f"تم تعيين الاسم إلى '{vals['name']}' للسجل الجديد")

                # التأكد من وجود المستخدم المعين
            if not vals.get('user_id'):
                vals['user_id'] = self.env.user.id

                # إنشاء السجل
            record = super(ArchiveManagement, self.with_context(mail_create_nosubscribe=True)).create([vals])[0]
            result.append(record.id)

            # معالجة ملف PDF
            if record.file and record.file_name:
                try:
                    attachment = self.env['ir.attachment'].create({
                        'name': record.file_name,
                        'datas': record.file,
                        'res_model': 'archive.management',
                        'res_id': record.id,
                        'mimetype': 'application/pdf',
                    })
                    record.attachment_id = attachment.id
                except Exception as e:
                    _logger.error(f"خطأ في إنشاء المرفق: {e}")

        return self.browse(result)

        # دالة مساعدة لاستخراج رمز نوع المستند من نوع المستند
    def _get_document_type_code_from_type(self, doc_type):
        if doc_type == 'incoming':
            return 1
        elif doc_type == 'outgoing':
            return 2
        elif doc_type == 'memo':
            return 3
        else:
            return 0

            # تحديث دالة _onchange_document_type
    @api.onchange('document_type')
    def _onchange_document_type(self):
        # تحقق مما إذا كان هذا سجل جديد - إذا لم يكن كذلك، لا تسمح بتغيير نوع المستند
        if not self.is_new_record and self.id:
            return {
                'warning': {
                    'title': "تحذير",
                    'message': "لا يمكنك تغيير نوع المستند بعد الإنشاء."
                }
            }

        if not self.name or not self.name.startswith('mfz/'):
            # إذا لم يكن هناك اسم أو كان بتنسيق غير متوقع، ننشئ واحداً جديداً
            current_year = datetime.now().year
            document_type_code = self._get_document_type_code()

            # الحصول على الرقم التسلسلي التالي باستخدام الدالة الجديدة
            next_sequence = self._get_next_sequence_for_year(self.document_type or 'incoming', current_year, 'name')
            self.name = f"mfz/{current_year}/{document_type_code}/{next_sequence}"
        elif self.name.startswith('mfz/'):
            # إذا كان للاسم التنسيق المتوقع، نقوم بتحديث رمز النوع فقط
            document_type_code = self._get_document_type_code()

            if '/' in self.name:
                parts = self.name.split('/')
                if len(parts) >= 4:
                    parts[2] = str(document_type_code)
                    self.name = '/'.join(parts)
                else:
                    # إذا لم تكن هناك الأجزاء المتوقعة، نقوم بإعادة إنشاء الاسم
                    current_year = datetime.now().year
                    next_sequence = self._get_next_sequence_for_year(self.document_type or 'incoming', current_year,
                                                                     'name')
                    self.name = f"mfz/{current_year}/{document_type_code}/{next_sequence}"

                    # دالة _get_document_type_code الحالية
    def _get_document_type_code(self):
        if self.document_type == 'incoming':
            return 1
        elif self.document_type == 'outgoing':
            return 2
        elif self.document_type == 'memo':
            return 3
        else:
            return 0

            # باقي الدوال
    def copy(self, default=None):
        default = dict(default or {})
        default['name'] = f"نسخة من {self.name}"
        default['reference'] = False  # لكي يتم إنشاء رقم جديد
        default['is_new_record'] = True  # تمكين تعديل نوع المستند في النسخة الجديدة

        new_record = super(ArchiveManagement, self).copy(default)

        # نسخ المرفق الرئيسي إذا كان موجوداً
        if self.attachment_id:
            attachment_data = self.attachment_id.copy_data()[0]
            attachment_data.update({
                'res_model': 'archive.management',
                'res_id': new_record.id,
            })
            new_attachment = self.env['ir.attachment'].create(attachment_data)
            new_record.attachment_id = new_attachment.id

        return new_record
    def _check_duplicates(self):
        """البحث عن النسخ المحتملة بناءً على الاسم أو المرجع أو المحتوى"""
        self.ensure_one()
        duplicates = self.search([
            '|', '|',
            ('name', '=ilike', self.name),
            ('reference', '=ilike', self.reference),
            ('indexed_content_2', '=ilike', self.indexed_content_2),
            ('id', '!=', self.id)
        ], limit=5)

        return duplicates
    def action_check_duplicates(self):
        """عمل للبحث وعرض النسخ المحتملة"""
        self.ensure_one()
        duplicates = self._check_duplicates()

        if not duplicates:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': "لم يتم العثور على تكرارات",
                    'message': "لم يتم العثور على مستندات مكررة محتملة.",
                    'sticky': False,
                    'type': 'success',
                }
            }

        return {
            'name': "التكرارات المحتملة",
            'type': 'ir.actions.act_window',
            'res_model': 'archive.management',
            'view_mode': 'list,form',
            'domain': [('id', 'in', duplicates.ids)],
            'target': 'new',
        }
    @api.model
    def get_dashboard_data(self, options=None):
        """
        الحصول على بيانات لوحة المعلومات
        :param options: خيارات التصفية مثل الفترة الزمنية (اليوم، الأسبوع، الشهر، السنة)
        :return: قاموس يحتوي على إحصائيات المستندات
        """
        if not options:
            options = {}

            # تحديد نطاق التاريخ بناءً على الفترة المحددة
        period = options.get('period', 'month')

        today = fields.Date.today()
        date_from = today

        if period == 'today':
            date_from = today
        elif period == 'week':
            date_from = today - timedelta(days=7)
        elif period == 'month':
            date_from = today.replace(day=1)
        elif period == 'year':
            date_from = today.replace(month=1, day=1)

            # مجال التاريخ للاستعلام
        date_domain = [('date', '>=', date_from), ('date', '<=', today)]

        # الإحصائيات الأساسية
        stats = {
            'incoming': self.search_count([('document_type', '=', 'incoming')] + date_domain),
            'outgoing': self.search_count([('document_type', '=', 'outgoing')] + date_domain),
            'memo': self.search_count([('document_type', '=', 'memo')] + date_domain),
            'pending': self.search_count([('state', '=', 'pending')] + date_domain),
            'approved': self.search_count([('state', '=', 'approved')] + date_domain),
            'confidential': self.search_count(
                [('confidentiality', 'in', ['confidential', 'restricted'])] + date_domain),
        }

        # إجمالي المستندات
        stats['total'] = stats['incoming'] + stats['outgoing'] + stats['memo']

        # توزيع المستندات حسب التصنيف
        categories = self.env['archive.category'].search([])
        category_stats = []

        for category in categories:
            count = self.search_count([('category_id', '=', category.id)] + date_domain)
            if count > 0:  # إضافة فقط التصنيفات التي لديها مستندات
                category_stats.append({
                    'id': category.id,
                    'name': category.name,
                    'count': count,
                })

                # ترتيب حسب العدد تنازلياً
        category_stats = sorted(category_stats, key=lambda x: x['count'], reverse=True)
        stats['by_category'] = category_stats[:7]  # أخذ أعلى 7 تصنيفات فقط

        # الاتجاهات الشهرية
        if period in ['month', 'year']:
            # تحديد عدد الأشهر للعرض
            num_months = 12 if period == 'year' else 6
            monthly_trends = []

            for i in range(num_months - 1, -1, -1):
                month_start = today.replace(day=1) - relativedelta(months=i)
                month_end = (month_start + relativedelta(months=1)) - timedelta(days=1)

                month_domain = [('date', '>=', month_start), ('date', '<=', month_end)]

                month_stats = {
                    'month': month_start.strftime('%B'),  # اسم الشهر
                    'incoming': self.search_count([('document_type', '=', 'incoming')] + month_domain),
                    'outgoing': self.search_count([('document_type', '=', 'outgoing')] + month_domain),
                    'memo': self.search_count([('document_type', '=', 'memo')] + month_domain),
                }

                monthly_trends.append(month_stats)

            stats['monthly_trends'] = monthly_trends

        return stats
    @api.model
    def get_recent_documents(self, options=None):
        """
        الحصول على المستندات الأخيرة
        :param options: خيارات مثل الحد الأقصى للمستندات
        :return: قائمة المستندات الأخيرة
        """
        if not options:
            options = {}

        limit = options.get('limit', 5)

        documents = self.search([
            ('active', '=', True),
        ], order='date desc, id desc', limit=limit)

        result = []
        for doc in documents:
            result.append({
                'id': doc.id,
                'name': doc.name,
                'date': doc.date,
                'document_type': doc.document_type,
                'state': doc.state,
            })

        return result
    @api.model
    def get_pending_actions(self):
        """
        الحصول على الإجراءات المعلقة للمستخدم الحالي
        :return: قائمة الإجراءات المعلقة
        """
        # جلب المستندات التي تحتاج إلى معالجة من قبل المستخدم الحالي
        user_id = self.env.user.id

        # استخدام user_id فقط بدل الاستعلام المركب
        documents = self.search([
            ('state', '=', 'pending'),
            ('user_id', '=', user_id)
        ], limit=10)

        result = []
        for doc in documents:
            result.append({
                'id': doc.id,
                'document_id': doc.id,
                'name': doc.name,
                'description': f"مستند {dict(self._fields['document_type'].selection).get(doc.document_type)} بحاجة للمراجعة",
            })

        return result
    @api.model
    def get_top_contactors(self, options=None):
        """
        الحصول على الجهات الأكثر تفاعلاً
        :param options: خيارات مثل الحد الأقصى للجهات
        :return: قائمة الجهات الأكثر تفاعلاً
        """
        if not options:
            options = {}

        limit = options.get('limit', 5)

        # الحصول على الجهات التي تم توجيه أكبر عدد من المستندات إليها
        query = """  
        SELECT directed_to_id, COUNT(*) as document_count  
        FROM archive_management  
        WHERE directed_to_id IS NOT NULL  
        GROUP BY directed_to_id  
        ORDER BY document_count DESC  
        LIMIT %s  
        """

        self.env.cr.execute(query, (limit,))
        directed_to_results = self.env.cr.fetchall()

        result = []
        for directed_to_id, count in directed_to_results:
            directed_to = self.env['archive.directed.to'].browse(directed_to_id)
            if directed_to.exists():
                result.append({
                    'id': directed_to.id,
                    'model': 'archive.directed.to',
                    'name': directed_to.name,
                    'company': directed_to.company,
                    'count': count,
                })

                # إذا كنا نريد إضافة جهات مرسلة أيضاً...
        if len(result) < limit:
            remaining = limit - len(result)
            query = """  
            SELECT sent_by_id, COUNT(*) as document_count  
            FROM archive_management  
            WHERE sent_by_id IS NOT NULL  
            GROUP BY sent_by_id  
            ORDER BY document_count DESC  
            LIMIT %s  
            """

            self.env.cr.execute(query, (remaining,))
            sent_by_results = self.env.cr.fetchall()

            for sent_by_id, count in sent_by_results:
                sent_by = self.env['archive.sent.by'].browse(sent_by_id)
                if sent_by.exists():
                    result.append({
                        'id': sent_by.id,
                        'model': 'archive.sent.by',
                        'name': sent_by.name,
                        'company': sent_by.company,
                        'count': count,
                    })

        return result
    def action_open_scanner(self):
        """فتح مربع حوار يوجه المستخدم لاستخدام الماسح الضوئي"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'استخدام الماسح الضوئي',
                'message': 'يرجى استخدام برنامج المسح الضوئي المثبت على جهازك، ثم قم بحفظ الملف ورفعه في النظام.',
                'sticky': True,
                'type': 'info',
                'links': [{
                    'label': 'فتح تطبيق المسح الضوئي',
                    'url': 'scanner://'
                }]
            }
        }
    def _check_potential_duplicates(self):
        """
        البحث عن المستندات المكررة المحتملة بطرق متعددة
        :return: قائمة المستندات المكررة
        """
        self.ensure_one()

        # البحث باستخدام معايير متعددة
        potential_duplicates = self.search([
            '|', '|', '|', '|',
            ('name', '=ilike', self.name),  # اسم متطابق
            ('reference', '=ilike', self.reference),  # مرجع متطابق
            ('indexed_content_2', '=ilike', self.indexed_content_2),  # محتوى متشابه
            ('description', '=ilike', self.description),  # وصف متشابه
            ('id', '!=', self.id)  # استبعاد السجل الحالي
        ], limit=10)

        return potential_duplicates
    def action_check_potential_duplicates(self):
        """
        إجراء للبحث عن التكرارات المحتملة وعرضها
        """
        self.ensure_one()
        duplicates = self._check_potential_duplicates()

        if not duplicates:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': "لم يتم العثور على تكرارات",
                    'message': "لم يتم العثور على مستندات مكررة محتملة.",
                    'sticky': False,
                    'type': 'success',
                }
            }

        return {
            'name': "التكرارات المحتملة",
            'type': 'ir.actions.act_window',
            'res_model': 'archive.management',
            'view_mode': 'list,form',
            'domain': [('id', 'in', duplicates.ids)],
            'target': 'new',
        }
    def action_search_content(self):
        return {
            'name': "بحث متقدم في النص",
            'type': 'ir.actions.act_window',
            'res_model': 'archive.content.search.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_model': 'archive.management'},
        }
    def action_content_search(self):
        return {
            'name': "بحث متقدم في النص",
            'type': 'ir.actions.act_window',
            'res_model': 'archive.content.search.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_model': 'archive.management'},
        }
    @api.model
    # يضاف في نموذج archive.management

    def search(self, domain, offset=0, limit=None, order=None, count=False):
        """
        تخصيص عملية البحث للتأكد من تطابق جميع الكلمات
        """
        # الحصول على كلمات البحث من السياق
        search_terms = self.env.context.get('advanced_search_terms', [])
        search_method = self.env.context.get('advanced_search_method', '')
        search_fields = self.env.context.get('advanced_search_fields', [])

        # إجراء البحث الأساسي مع التأكد من توافق التوقيع
        if count:
            return super().search(domain, offset=offset, limit=limit, order=order, count=count)

        base_records = super().search(domain, offset=offset, limit=limit, order=order)

        # إذا لم يكن بحث متقدم
        if not search_terms or search_method != 'strict_sequence_match':
            return base_records

            # تصفية السجلات
        filtered_records = self.env[self._name]

        for record in base_records:
            record_matched = False

            # فحص كل الحقول
            for field in search_fields:
                # استخراج محتوى الحقل
                content = getattr(record, field, '')
                if not content:
                    continue

                    # تطبيع محتوى الحقل
                normalized_content = self.env['archive.content.search.wizard'].normalize_arabic_text(content)

                # التحقق من وجود كل الكلمات
                all_terms_found = all(
                    self.env['archive.content.search.wizard'].normalize_arabic_text(term) in normalized_content
                    for term in search_terms
                )

                # إذا وجدت كل الكلمات
                if all_terms_found:
                    # التحقق من التتابع
                    current_index = 0
                    terms_in_sequence = True

                    for term in search_terms:
                        normalized_term = self.env['archive.content.search.wizard'].normalize_arabic_text(term)
                        term_index = normalized_content.find(normalized_term, current_index)

                        # إذا لم يتم العثور على الكلمة أو وجدت قبل الفهرسة السابقة
                        if term_index == -1 or term_index < current_index:
                            terms_in_sequence = False
                            break

                            # تحديث الفهرسة للبحث عن الكلمة التالية
                        current_index = term_index + len(normalized_term)

                        # إذا كانت الكلمات متتابعة
                    if terms_in_sequence:
                        filtered_records |= record
                        record_matched = True
                        break

                        # تسجيل السجلات المستبعدة
            if not record_matched:
                _logger.info(f"تم استبعاد السجل {record.id} لعدم تطابق كامل")

        return filtered_records