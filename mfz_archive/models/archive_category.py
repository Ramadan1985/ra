# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ArchiveCategory(models.Model):
    _name = 'archive.category'
    _description = 'Archive Category'
    _parent_store = True
    _order = 'name'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code')
    description = fields.Text(string='Description')
    active = fields.Boolean(default=True)  # إضافة حقل active للأرشفة

    # هيكل التصنيفات الشجري
    parent_id = fields.Many2one('archive.category', string='Parent Category', index=True, ondelete='cascade')
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many('archive.category', 'parent_id', string='Child Categories')

    # العلاقة مع الوثائق
    document_ids = fields.One2many('archive.management', 'category_id', string='Documents')
    document_count = fields.Integer(string='Document Count', compute='_compute_document_count')

    # حساب عدد الوثائق
    @api.depends('document_ids')
    def _compute_document_count(self):
        for record in self:
            record.document_count = len(record.document_ids)

    # التحقق من تكرار الرمز
    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Category code must be unique!')
    ]

    # عرض الوثائق في التصنيف
    def action_view_documents(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Documents',
            'res_model': 'archive.management',
            'view_mode': 'tree,form',
            'domain': [('category_id', '=', self.id)],
            'context': {'default_category_id': self.id}
        }