# -*- coding: utf-8 -*-
from odoo import api, fields, models
import re
from difflib import SequenceMatcher
import logging

_logger = logging.getLogger(__name__)


class ArchiveContentSearchWizard(models.TransientModel):
    _name = 'archive.content.search.wizard'
    _description = 'Advanced Content Search Wizard'

    search_term = fields.Char('نص البحث', required=True)
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
        """معالجة النص العربي وتوحيد شكل الحروف"""
        if not text:
            return ""

        try:
            # إزالة التشكيل والحركات
            text = re.sub(r'[\u064B-\u065F\u0670]', '', text)

            # توحيد أشكال الألف
            text = re.sub(r'[إأآا]', 'ا', text)

            # توحيد التاء المربوطة والهاء
            text = text.replace('ة', 'ه')

            # توحيد الهمزات
            text = text.replace('ؤ', 'و')
            text = text.replace('ئ', 'ي')
            text = text.replace('ء', '')

            # إزالة المسافات المتعددة
            text = re.sub(r'\s+', ' ', text)

            return text.strip()
        except Exception as e:
            _logger.error(f"خطأ أثناء معالجة النص العربي: {e}")
            return text.strip() if text else ""

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

            # جذر الكلمة إذا كانت ميزة الجذور مفعلة
            if self.use_stemming:
                stem = self.get_arabic_stem(normalized)
                if stem and stem != normalized and len(stem) >= 2:
                    variations.add(stem)

                    # الكلمة معكوسة
            if self.search_reversed:
                variations.add(self.reverse_word(normalized))

                # جذر الكلمة المعكوسة إذا كانت ميزة الجذور مفعلة
                if self.use_stemming:
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
                elif normalized.endswith('ه') or normalized.endswith('ت'):
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

    def action_search(self):
        self.ensure_one()
        search_fields = []

        # تحديد حقول البحث
        if self.search_in_name:
            search_fields.append('name')
        if self.search_in_description:
            search_fields.append('description')
        if self.search_in_content:
            search_fields.append('indexed_content_2')

        if not search_fields:
            return {'type': 'ir.actions.act_window_close'}

            # تقسيم البحث إلى كلمات وإزالة الكلمات الفارغة
        search_terms = [term for term in self.search_term.split() if term.strip()]

        if not search_terms:
            return {'type': 'ir.actions.act_window_close'}

            # استرجاع جميع السجلات التي قد تحتوي على النص المطلوب
        model_obj = self.env[self.model]

        try:
            # إنشاء مجال بحث أولي واسع لاسترجاع المرشحين المحتملين
            domain = []

            # إذا كان البحث بسيطًا (غير مرن وبدون خيارات متقدمة)، استخدم البحث التقليدي
            if not self.fuzzy_search and not self.search_reversed and not self.use_stemming and not self.semantic_search:
                for field in search_fields:
                    for term in search_terms:
                        domain.append((field, 'ilike', term))

                        # تطبيق OR بشكل صحيح
                if len(domain) > 1:
                    final_domain = ['|'] + domain[:2]
                    for d in domain[2:]:
                        final_domain = ['|'] + final_domain + [d]
                    domain = final_domain
            else:
                # للبحث المتقدم، نسترجع مجموعة أوسع من السجلات ثم نصفيها
                prelim_domain = []

                # إنشاء مجال أولي للبحث عن أي سجلات تحتوي على أجزاء من مصطلحات البحث
                for field in search_fields:
                    field_domain = []
                    for term in search_terms:
                        # استخدام أول 3 أحرف من كل كلمة للحصول على نتائج أوسع
                        if len(term) >= 3:
                            field_domain.append((field, 'ilike', term[:3]))

                            # إضافة البحث عن الكلمة المعكوسة أيضًا
                            if self.search_reversed:
                                reversed_term = self.reverse_word(term)
                                if len(reversed_term) >= 3:
                                    field_domain.append((field, 'ilike', reversed_term[:3]))

                                    # إضافة البحث عن جذر الكلمة
                            if self.use_stemming:
                                stem = self.get_arabic_stem(term)
                                if stem and len(stem) >= 3 and stem != term[:3]:
                                    field_domain.append((field, 'ilike', stem[:3]))

                                    # وجذر الكلمة المعكوسة أيضًا
                                    if self.search_reversed:
                                        reversed_stem = self.reverse_word(stem)
                                        if len(reversed_stem) >= 3:
                                            field_domain.append((field, 'ilike', reversed_stem[:3]))

                                            # تطبيق OR على كل حقل
                    if field_domain:
                        if len(field_domain) > 1:
                            field_or_domain = ['|'] + field_domain[:2]
                            for d in field_domain[2:]:
                                field_or_domain = ['|'] + field_or_domain + [d]
                            prelim_domain.append(field_or_domain)
                        else:
                            prelim_domain.append(field_domain[0])

                            # تطبيق OR بين الحقول
                if len(prelim_domain) > 1:
                    domain = ['|'] + prelim_domain[:2]
                    for d in prelim_domain[2:]:
                        domain = ['|'] + domain + [d]
                elif len(prelim_domain) == 1:
                    domain = prelim_domain
                else:
                    # إذا لم يتم إنشاء مجال، استخدم مجال عام للحصول على جميع السجلات التي تحتوي على محتوى
                    for field in search_fields:
                        domain.append((field, '!=', False))

                    if len(search_fields) > 1:
                        domain = ['|'] * (len(search_fields) - 1) + domain

                        # استرجاع السجلات المرشحة
            _logger.info(f"مجال البحث الأولي: {domain}")
            records = model_obj.search(domain)
            _logger.info(f"تم العثور على {len(records)} سجل مرشح للبحث")

            # تصفية النتائج باستخدام الخوارزمية المخصصة للبحث
            matching_ids = []
            matched_fields = {}  # لتتبع الحقول التي تحتوي على تطابق

            for record in records:
                matched = False
                record_matched_fields = []

                for field in search_fields:
                    field_value = getattr(record, field, '')
                    if not field_value:
                        continue

                        # تحويل القيمة إلى نص
                    field_value = str(field_value)

                    # البحث عن التطابق باستخدام الخوارزمية المحسنة
                    if self.find_matches_in_text(field_value, search_terms):
                        matched = True
                        record_matched_fields.append(field)

                if matched:
                    matching_ids.append(record.id)
                    matched_fields[record.id] = record_matched_fields

            _logger.info(f"تم العثور على {len(matching_ids)} سجل مطابق بعد التصفية")

            # إنشاء مجال نهائي باستخدام الهويات المطابقة
            final_domain = [('id', 'in', matching_ids)]

            # إذا لم يتم العثور على نتائج، عرض رسالة للمستخدم
            if not matching_ids:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'لا توجد نتائج',
                        'message': f'لم يتم العثور على أي مستند يطابق البحث: {self.search_term}',
                        'sticky': False,
                        'type': 'warning',
                    }
                }

                # عرض نتائج البحث
            return {
                'name': f'نتائج البحث: {self.search_term} ({len(matching_ids)})',
                'type': 'ir.actions.act_window',
                'res_model': self.model,
                'view_mode': 'list,form',
                'domain': final_domain,
                'context': {
                    'search_default_active': 1,
                    'search_term': self.search_term,
                    'matched_fields': matched_fields,
                },
                'target': 'current',
            }
        except Exception as e:
            _logger.error(f"خطأ أثناء عملية البحث: {e}")
            # في حالة حدوث خطأ، نعرض رسالة ونغلق النافذة
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'خطأ في البحث',
                    'message': f'حدث خطأ أثناء عملية البحث: {e}',
                    'sticky': False,
                    'type': 'danger',
                }
            }

    def action_search_similar(self):
        """البحث عن مستندات مشابهة"""
        self.ensure_one()
        search_fields = []

        # تحديد حقول البحث
        if self.search_in_name:
            search_fields.append('name')
        if self.search_in_description:
            search_fields.append('description')
        if self.search_in_content:
            search_fields.append('indexed_content_2')

        if not search_fields:
            return {'type': 'ir.actions.act_window_close'}

            # تقسيم البحث إلى كلمات وإزالة الكلمات الفارغة والقصيرة جدًا
        search_terms = [term for term in self.search_term.split() if len(term.strip()) > 2]

        if not search_terms:
            return {'type': 'ir.actions.act_window_close'}

        try:
            # استخدام منطق مختلف للبحث عن مستندات مشابهة - البحث عن أي كلمة من كلمات البحث
            model_obj = self.env[self.model]

            # بناء مجال للبحث عن أي كلمة من كلمات البحث
            domain = []

            # للبحث عن مستندات مشابهة، نبحث عن أي كلمة من كلمات البحث
            for field in search_fields:
                for term in search_terms:
                    normalized_term = self.normalize_arabic_text(term)
                    if len(normalized_term) >= 3:
                        # البحث عن الكلمة العادية
                        domain.append((field, 'ilike', normalized_term))

                        # البحث عن جذر الكلمة إذا كانت طويلة بما يكفي
                        if len(normalized_term) > 4:
                            domain.append((field, 'ilike', normalized_term[:-1]))  # بدون الحرف الأخير

                        # البحث عن جذر الكلمة إذا كانت ميزة الجذور مفعلة
                        if self.use_stemming:
                            stem = self.get_arabic_stem(normalized_term)
                            if stem and stem != normalized_term and len(stem) >= 3:
                                domain.append((field, 'ilike', stem))

                                # البحث عن الكلمة المعكوسة
                        if self.search_reversed:
                            reversed_term = self.reverse_word(normalized_term)
                            domain.append((field, 'ilike', reversed_term))

                            # بحث عن جذر الكلمة المعكوسة
                            if self.use_stemming:
                                reversed_stem = self.reverse_word(stem) if stem else ""
                                if reversed_stem and len(reversed_stem) >= 3:
                                    domain.append((field, 'ilike', reversed_stem))

                                    # تطبيق OR بشكل صحيح
            if len(domain) > 1:
                final_domain = ['|'] + domain[:2]
                for d in domain[2:]:
                    final_domain = ['|'] + final_domain + [d]
                domain = final_domain

            if not domain:
                return {'type': 'ir.actions.act_window_close'}

            _logger.info(f"مجال البحث للمستندات المشابهة: {domain}")

            # عرض نتائج البحث
            return {
                'name': f'مستندات مشابهة لـ: {self.search_term}',
                'type': 'ir.actions.act_window',
                'res_model': self.model,
                'view_mode': 'list,form',
                'domain': domain,
                'context': {'search_default_active': 1},
                'target': 'current',
            }
        except Exception as e:
            _logger.error(f"خطأ أثناء البحث عن مستندات مشابهة: {e}")
            # في حالة حدوث خطأ، نعرض رسالة ونغلق النافذة
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'خطأ في البحث',
                    'message': f'حدث خطأ أثناء البحث عن مستندات مشابهة: {e}',
                    'sticky': False,
                    'type': 'danger',
                }
            }