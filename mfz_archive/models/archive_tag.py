# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ArchiveTag(models.Model):
    _name = 'archive.tag'
    _description = 'Document Tag'

    name = fields.Char(string='Name', required=True)
    color = fields.Integer(string='Color')
    active = fields.Boolean(default=True)  # إضافة حقل active للأرشفة

    # العلاقة مع المستندات
    document_ids = fields.Many2many('archive.management', string='Documents')
    document_count = fields.Integer(string='Document Count', compute='_compute_document_count')

    # حساب عدد الوثائق
    @api.depends('document_ids')
    def _compute_document_count(self):
        for record in self:
            record.document_count = len(record.document_ids)

            # عرض الوثائق المرتبطة بالوسم

    def action_view_documents(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Documents',
            'res_model': 'archive.management',
            'view_mode': 'list,form',
            'domain': [('tag_ids', 'in', self.id)],
            'context': {'default_tag_ids': [(4, self.id)]}
        }