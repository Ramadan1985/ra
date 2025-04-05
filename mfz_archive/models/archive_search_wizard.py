# -*- coding: utf-8 -*-
from odoo import api, fields, models
import re
from difflib import SequenceMatcher
from collections import Counter  # تم إضافة استيراد Counter هنا
import logging

_logger = logging.getLogger(__name__)


class ArchiveContentSearchWizard(models.TransientModel):
    _name = 'archive.content.search.wizard'
    _description = 'Advanced Content Search Wizard'

    search_term = fields.Char('نص البحث', required=True)
    date_from = fields.Date(string='من تاريخ', default=lambda self: fields.Date.today().replace(day=1))
    date_to = fields.Date(string='إلى تاريخ', default=fields.Date.today())
    # حقل جديد لنوع المستند
    document_type = fields.Selection([
        ('all', 'الكل'),
        ('incoming', 'وارد'),
        ('outgoing', 'صادر'),
        ('internal_memo', 'مذكرات داخلية')
    ], string='نوع المستند', default='all', required=True)
    model = fields.Char(default='archive.management')

    # خيارات البحث
    search_in_name = fields.Boolean('البحث في الاسم', default=True)
    search_in_description = fields.Boolean('البحث في الوصف', default=True)
    search_in_content = fields.Boolean('البحث في المحتوى المستخرج', default=True)
    case_sensitive = fields.Boolean('مطابقة حالة الأحرف', default=False)
    whole_word = fields.Boolean('كلمات كاملة فقط', default=False)
    fuzzy_search = fields.Boolean('بحث مرن', default=True)  # تفعيل بشكل افتراضي
    fuzzy_threshold = fields.Integer('مستوى التشابه', default=2, help="1 = تشابه أكثر مرونة، 5 = دقة أعلى")
    search_reversed = fields.Boolean('البحث في النص المعكوس', default=True)  # خيار جديد للبحث في النص المعكوس
    use_stemming = fields.Boolean('استخدام جذور الكلمات', default=True)  # إضافة جديدة
    semantic_search = fields.Boolean('بحث دلالي', default=False)  # إضافة جديدة

    # تم إضافة دالة بحث بسيطة للاختبار

    def enhanced_arabic_preprocessing(self, text):
        """معالجة متقدمة للنص العربي"""
        if not text:
            return ""

        try:
            # التطبيع الأساسي
            text = self.normalize_arabic_text(text)

            # معالجة فراغات الكتابة العربية غير القياسية
            text = re.sub(r'(\w)\s+(\w)', r'\1 \2', text)

            # توحيد أشكال الواو والياء
            text = text.replace('ؤ', 'و')
            text = text.replace('ئ', 'ي')

            # إزالة علامات الترقيم
            text = re.sub(r'[^\w\s]', ' ', text)

            # إزالة تكرار الحروف (مثل: مررررحبا)
            text = re.sub(r'(.)\1{2,}', r'\1\1', text)

            # توحيد المسافات
            text = re.sub(r'\s+', ' ', text)

            return text.strip()
        except Exception as e:
            _logger.error(f"خطأ في المعالجة المتقدمة للنص العربي: {e}")
            return text if text else ""

    def normalize_arabic_text(self, text):
        """
        معالجة النص العربي وتوحيد شكل الحروف
        مع معالجة متقدمة للتنويعات
        """
        if not text:
            return ""

        try:
            # إزالة التشكيل والحركات
            text = re.sub(r'[\u064B-\u065F\u0670]', '', text)

            # توحيد أشكال الألف والهمزات
            text = re.sub(r'[إأآا]', 'ا', text)  # توحيد الألف
            text = text.replace('ؤ', 'و')  # توحيد واو الهمزة
            text = text.replace('ئ', 'ي')  # توحيد ياء الهمزة
            text = text.replace('ء', '')  # إزالة الهمزة المنفردة

            # توحيد التاء المفتوحة والمربوطة
            text = text.replace('ة', 'ه')

            # توحيد واو والياء
            text = text.replace('ى', 'ي')
            text = text.replace('و', 'و')
            text = text.replace('د', 'د')
            text = text.replace('ذ', 'ذ')

            # إزالة المسافات المتعددة والفراغات الزائدة
            text = re.sub(r'\s+', ' ', text)

            return text.strip().lower()  # تحويل للحروف الصغيرة للمطابقة الكاملة
        except Exception as e:
            _logger.error(f"خطأ أثناء معالجة النص العربي: {e}")
            return text.strip().lower() if text else ""

    def reverse_text(self, text):
        """عكس ترتيب الكلمات في النص"""
        if not text:
            return ""
        try:
            words = text.split()
            return " ".join(words[::-1])
        except Exception as e:
            _logger.error(f"خطأ أثناء عكس النص: {e}")
            return text

    def reverse_word(self, word):
        """عكس ترتيب الأحرف في الكلمة"""
        if not word:
            return ""
        try:
            return word[::-1]
        except Exception as e:
            _logger.error(f"خطأ أثناء عكس الكلمة: {e}")
            return word

    def get_arabic_stem(self, word):
        """استخراج جذر الكلمة العربية (تبسيط للجذور)"""
        if not word or len(word) < 3:
            return word

        try:
            # إزالة البادئات الشائعة
            prefixes = ['ال', 'لل', 'بال', 'كال', 'فال', 'وال', 'بال', 'لل', 'ولل']
            for prefix in prefixes:
                if word.startswith(prefix) and len(word) > len(prefix) + 2:
                    word = word[len(prefix):]
                    break

                    # إزالة اللواحق الشائعة
            suffixes = ['ون', 'ات', 'ين', 'ان', 'تي', 'هم', 'هن', 'ها', 'ية', 'تك', 'نا', 'كم', 'تن', 'ني']
            for suffix in suffixes:
                if word.endswith(suffix) and len(word) > len(suffix) + 2:
                    word = word[:-len(suffix)]
                    break

                    # حد أدنى للطول
            return word if len(word) >= 2 else word
        except Exception as e:
            _logger.error(f"خطأ في استخراج جذر الكلمة: {e}")
            return word

    def generate_variations(self, word):
        """توليد تنويعات مختلفة للكلمة للبحث"""
        variations = set()

        if not word:
            return variations

        try:
            # الكلمة الأصلية
            normalized = self.normalize_arabic_text(word)
            variations.add(normalized)

            # إضافة النص بعد المعالجة المتقدمة
            variations.add(self.enhanced_arabic_preprocessing(word))

            # معالجة التاء المربوطة - إضافة صيغ بديلة
            if normalized.endswith('ة'):
                # إضافة نسخة بدون التاء المربوطة
                variations.add(normalized[:-1])
                # إضافة نسخة بهاء بدلاً من التاء المربوطة
                variations.add(normalized[:-1] + 'ه')
            elif normalized.endswith('ه'):
                # إضافة نسخة بتاء مربوطة بدلاً من الهاء
                variations.add(normalized[:-1] + 'ة')
            else:
                # إضافة نسخة مع تاء مربوطة للكلمات العربية التي قد تكون اختصاراً
                ar_letters = 'ابتثجحخدذرزسشصضطظعغفقكلمنهويءإأآ'
                if len(normalized) >= 3 and any(c in ar_letters for c in normalized[-3:]):
                    variations.add(normalized + 'ة')
                    variations.add(normalized + 'ه')

                    # جذر الكلمة إذا كانت ميزة الجذور مفعلة
            if self.use_stemming:
                stem = self.get_arabic_stem(normalized)
                if stem and stem != normalized and len(stem) >= 2:
                    variations.add(stem)
                    # إضافة صيغ بديلة للجذر أيضاً
                    if stem.endswith('ة'):
                        variations.add(stem[:-1])
                        variations.add(stem[:-1] + 'ه')
                    elif stem.endswith('ه'):
                        variations.add(stem[:-1] + 'ة')

                        # الكلمة معكوسة
            if self.search_reversed:
                variations.add(self.reverse_word(normalized))

                # جذر الكلمة المعكوسة إذا كانت ميزة الجذور مفعلة
                if self.use_stemming and 'stem' in locals():
                    variations.add(self.reverse_word(stem))

                    # إزالة ال التعريف إذا كانت موجودة
            if len(normalized) > 3 and normalized.startswith('ال'):
                without_al = normalized[2:]
                variations.add(without_al)
                if self.search_reversed:
                    variations.add(self.reverse_word(without_al))

                    # إضافة جذر الكلمة (بدون لاحقة التاء المربوطة أو الألف والتاء)
            if len(normalized) > 3:
                if normalized.endswith('ات'):
                    root = normalized[:-2]
                    variations.add(root)
                    if self.search_reversed:
                        variations.add(self.reverse_word(root))
                elif normalized.endswith('ة') or normalized.endswith('ه') or normalized.endswith('ت'):
                    root = normalized[:-1]
                    variations.add(root)
                    if self.search_reversed:
                        variations.add(self.reverse_word(root))

                        # إزالة العناصر الفارغة من المجموعة
            variations = {v for v in variations if v}

            return variations
        except Exception as e:
            _logger.error(f"خطأ أثناء توليد تنويعات الكلمة: {e}")
            return {word} if word else set()

    def is_similar(self, a, b, max_distance=2):
        """تحديد ما إذا كانت الكلمتان متشابهتان"""
        # إذا كانت إحدى السلسلتين فارغة
        if not a or not b:
            return False

        try:
            # إذا كانت السلاسل متطابقة
            if a == b:
                return True

                # لتحسين الأداء، نتجاهل الكلمات القصيرة جدًا
            if len(a) < 2 or len(b) < 2:
                return a == b

                # إذا كانت الكلمة الأولى موجودة في الثانية
            if a in b or b in a:
                return True

                # إذا كانت الكلمتان مختلفتين جدًا في الطول
            if abs(len(a) - len(b)) > max_distance + 1:
                return False

                # كلا السلسلتين بنفس الطول تقريباً - تحقق إذا كانت نفس الحروف بترتيب مختلف
            if abs(len(a) - len(b)) <= 1 and sorted(a) == sorted(b):
                return True

                # تحقق من وجود كمية كبيرة من الحروف المشتركة
            common_chars = set(a) & set(b)
            if len(common_chars) >= min(len(a), len(b)) * 0.7:
                return True

                # مقارنة التشابه باستخدام خوارزمية سلسلة متتابعة أطول مشتركة
            matcher = SequenceMatcher(None, a, b)
            similarity = matcher.ratio()
            threshold = 0.7 - (0.1 * max_distance)  # أكثر تسامحًا مع زيادة max_distance

            return similarity >= threshold
        except Exception as e:
            _logger.error(f"خطأ أثناء مقارنة التشابه بين الكلمات: {e}")
            return False

    def calc_text_similarity(self, text1, text2):
        """حساب التشابه بين نصين باستخدام Vector Space Model"""
        if not text1 or not text2:
            return 0

        try:
            # تقسيم النصوص إلى كلمات
            words1 = self.normalize_arabic_text(text1).split()
            words2 = self.normalize_arabic_text(text2).split()

            # تحويل القوائم إلى مجموعات للتقاطع
            set1 = set(words1)
            set2 = set(words2)

            # حساب تقاطع ووحدة المجموعتين
            intersection = set1.intersection(set2)
            union = set1.union(set2)

            # حساب معامل جاكارد للتشابه
            if not union:
                return 0
            jaccard = len(intersection) / len(union)

            # تحليل تكرار الكلمات
            counter1 = Counter(words1)
            counter2 = Counter(words2)

            # حساب تداخل المتجهات (عدد الكلمات المشتركة مع الأخذ في الاعتبار تكرارها)
            vector_overlap = sum((counter1 & counter2).values())

            # حساب المجموع الكلي للكلمات
            total_words = sum(counter1.values()) + sum(counter2.values())

            # مزج الطريقتين للحصول على نتيجة أفضل
            if total_words == 0:
                return 0

            vector_sim = vector_overlap / total_words

            # دمج المقاييس مع ترجيح
            return (jaccard * 0.5) + (vector_sim * 0.5)
        except Exception as e:
            _logger.error(f"خطأ في حساب تشابه النصوص: {e}")
            return 0

    def find_matches_in_text(self, text, search_words):
        """البحث عن الكلمات في النص مع مراعاة الاختلافات"""
        if not text or not search_words:
            return False

        try:
            # البحث عن النص الكامل أولاً
            full_search_term = " ".join(search_words)
            normalized_text = self.normalize_arabic_text(text)

            # البحث الدلالي إذا كان مفعلاً
            if self.semantic_search and len(normalized_text) > 10 and len(full_search_term) > 5:
                similarity = self.calc_text_similarity(full_search_term, normalized_text)
                if similarity > 0.6:  # حد أدنى للتشابه الدلالي
                    return True

                    # البحث المباشر عن العبارة الكاملة
            if full_search_term in normalized_text:
                return True

                # البحث عن العبارة في النص المعكوس
            if self.search_reversed:
                # عكس حروف العبارة
                reversed_term = "".join([self.reverse_word(word) for word in search_words])
                if reversed_term in normalized_text:
                    return True

                    # عكس ترتيب الكلمات
                reversed_order = self.reverse_text(full_search_term)
                if reversed_order in normalized_text:
                    return True

                    # عكس ترتيب الكلمات وحروف كل كلمة
                reversed_both = " ".join([self.reverse_word(word) for word in reversed_order.split()])
                if reversed_both in normalized_text:
                    return True

                    # تحويل النص إلى قائمة من الكلمات
            text_words = normalized_text.split()

            # إضافة نسخ إضافية من النص للبحث
            all_text_formats = [normalized_text]
            all_text_words = list(text_words)

            # مجموعة من الكلمات المعكوسة للتحقق منها أيضًا
            if self.search_reversed:
                # 1. نص مع عكس ترتيب الأحرف في كل كلمة
                reversed_char_text = " ".join([self.reverse_word(word) for word in text_words])
                all_text_formats.append(reversed_char_text)
                all_text_words.extend(reversed_char_text.split())

                # 2. نص بعد عكس ترتيب الكلمات
                reversed_word_order = self.reverse_text(normalized_text)
                all_text_formats.append(reversed_word_order)
                all_text_words.extend(reversed_word_order.split())

                # 3. نص بعد عكس ترتيب الكلمات ثم عكس الأحرف في كل كلمة
                reversed_both = " ".join([self.reverse_word(word) for word in reversed_word_order.split()])
                all_text_formats.append(reversed_both)
                all_text_words.extend(reversed_both.split())

                # تتبع الكلمات التي تم العثور عليها
            found_words = set()
            found_scores = {}  # لتتبع نقاط الدقة لكل كلمة

            # البحث عن كل كلمة من كلمات البحث
            for search_word in search_words:
                # توليد تنويعات البحث
                search_variations = self.generate_variations(search_word)

                # البحث عن تطابق
                word_found = False
                best_score = 0  # أفضل نقاط دقة

                # 1. البحث المباشر في النص الكامل (أكثر أهمية)
                for text_format in all_text_formats:
                    for variation in search_variations:
                        if variation in text_format:
                            word_found = True
                            best_score = 1.0  # تطابق كامل
                            break
                    if word_found:
                        break

                        # 2. البحث في كلمات النص الفردية مع البحث المرن
                if not word_found and self.fuzzy_search:
                    max_distance = 6 - self.fuzzy_threshold
                    for variation in search_variations:
                        for text_word in all_text_words:
                            if self.is_similar(variation, text_word, max_distance):
                                word_found = True
                                # حساب درجة التشابه كنقاط دقة
                                matcher = SequenceMatcher(None, variation, text_word)
                                sim_score = matcher.ratio()
                                if sim_score > best_score:
                                    best_score = sim_score
                                if best_score > 0.9:  # إذا كان التطابق ممتازًا، توقف عن البحث
                                    break
                        if word_found and best_score > 0.9:
                            break

                if word_found:
                    found_words.add(search_word)
                    found_scores[search_word] = best_score

                    # حساب النتيجة النهائية مع الأخذ في الاعتبار درجة التطابق
            if not found_words:
                return False

                # حساب متوسط نقاط الدقة للكلمات التي تم العثور عليها
            avg_score = sum(found_scores.values()) / len(found_scores) if found_scores else 0

            # معايير النجاح محسنة:
            # 1. وجدت جميع كلمات البحث
            if len(found_words) == len(search_words):
                return True

                # 2. وجدت أكثر من 70% من الكلمات مع درجة تطابق عالية
            if len(search_words) > 1 and len(found_words) >= len(search_words) * 0.7 and avg_score > 0.7:
                return True

                # 3. وجدت كلمة واحدة على الأقل (مع درجة تطابق ممتازة) وكان البحث عن كلمة واحدة فقط
            if len(search_words) == 1 and len(found_words) == 1 and avg_score > 0.8:
                return True

                # 4. النص قصير جدًا والبحث عن كلمة واحدة على الأقل
            if len(text_words) < 20 and len(found_words) > 0 and avg_score > 0.9:
                return True

                # 5. للنصوص الطويلة، نكون أكثر تسامحًا
            if len(text_words) > 100 and len(found_words) > max(1, len(search_words) * 0.5):
                return True

            return False
        except Exception as e:
            _logger.error(f"خطأ أثناء البحث عن تطابقات في النص: {e}")
            return False


    def action_view_records(self):
        """
        دالة مخصصة لعرض السجلات مع التصفية
        """
        # الحصول على السجلات
        records = self.search([])

        # التصفية باستخدام post_search_filter
        filtered_records = records.post_search_filter()

        # عرض النتائج
        return {
            'name': 'السجلات المفلترة',
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'tree,form',
            'domain': [('id', 'in', filtered_records.ids)],
            'target': 'current',
        }


    def post_search_filter(self):
        """
        تصفية نتائج البحث للتأكد من:
        1. وجود جميع كلمات البحث
        2. تتابع الكلمات
        3. في نفس السجل
        """
        # استخراج كلمات البحث من السياق
        search_terms = self.env.context.get('advanced_search_terms', [])
        search_method = self.env.context.get('advanced_search_method', '')

        # التأكد من وجود كلمات البحث وطريقة البحث
        if not search_terms or search_method != 'strict_sequence_match':
            return self

            # تصفية السجلات
        filtered_records = self.env[self._name]

        for record in self:
            # فحص الحقول المختلفة
            search_fields = ['name', 'description', 'indexed_content', 'indexed_content_2']
            record_matched = False

            for field in search_fields:
                content = getattr(record, field, '')
                if not content:
                    continue

                    # تطبيع النص
                normalized_content = self.env['archive.content.search.wizard'].normalize_arabic_text(content)

                # التحقق من وجود كل الكلمات
                all_terms_found = all(
                    self.env['archive.content.search.wizard'].normalize_arabic_text(term) in normalized_content
                    for term in search_terms
                )

                # التحقق من وجود الكلمات بالترتيب
                if all_terms_found:
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

                        # إذا لم يتم العثور على الكلمات في أي حقل
            if not record_matched:
                _logger.info(f"تم استبعاد السجل {record.id} لعدم تطابق كامل")

        return filtered_records

    def action_search_similar(self):
        """
        بحث متقدم مع التأكد من:
        1. وجود جميع الكلمات
        2. في نفس المستند
        3. بدون اعتبار الترتيب
        4. البحث فقط في indexed_content_2
        5. تصفية حسب التاريخ ونوع المستند
        """
        # تقسيم كلمات البحث
        search_terms = [term.strip() for term in self.search_term.split() if len(term.strip()) > 2]

        if not search_terms:
            return {'type': 'ir.actions.act_window_close'}

        try:
            # إنشاء دومين للبحث
            domain = [
                ('date', '>=', self.date_from),
                ('date', '<=', self.date_to)
            ]

            # إضافة تصفية نوع المستند إذا لم يكن 'الكل'
            if self.document_type != 'all':
                domain.append(('document_type', '=', self.document_type))

                # البحث الأولي مع تصفية التاريخ ونوع المستند
            initial_records = self.env['archive.management'].search(domain)

            # باقي الكود كما هو (عملية البحث في المحتوى)
            filtered_records = self.env['archive.management']

            for record in initial_records:
                # مصفوفة للتتبع
                terms_found = [False] * len(search_terms)

                # فحص حقل indexed_content_2
                content = record.indexed_content_2
                if not content:
                    continue

                    # تطبيع محتوى الحقل
                normalized_content = self.normalize_arabic_text(content)

                # التحقق من وجود كل الكلمات
                for i, term in enumerate(search_terms):
                    normalized_term = self.normalize_arabic_text(term)
                    if normalized_term in normalized_content:
                        terms_found[i] = True

                        # التأكد من وجود كل الكلمات
                if all(terms_found):
                    filtered_records |= record

                    # إذا لم توجد نتائج
            if not filtered_records:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'نتائج البحث',
                        'message': 'لم يتم العثور على مستندات مطابقة للبحث',
                        'sticky': False,
                        'type': 'warning'
                    }
                }

                # عرض النتائج
            return {
                'name': f'مستندات مشابهة لـ: {self.search_term}',
                'type': 'ir.actions.act_window',
                'res_model': 'archive.management',
                'view_mode': 'list,form',
                'domain': [('id', 'in', filtered_records.ids)],
                'target': 'current',
                'context': {
                    'search_default_date_range': 1,
                    'date_from': self.date_from,
                    'date_to': self.date_to
                }
            }

        except Exception as e:
            _logger.error(f"خطأ أثناء البحث: {e}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'خطأ في البحث',
                    'message': f'حدث خطأ أثناء البحث: {e}',
                    'sticky': False,
                    'type': 'danger'
                }
            }