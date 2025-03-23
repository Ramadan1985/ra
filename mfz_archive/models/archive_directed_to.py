# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ArchiveDirectedTo(models.Model):
    _name = 'archive.directed.to'
    _description = 'Document Recipient'

    name = fields.Char(string='Name', required=True)
    title = fields.Char(string='Title')
    company = fields.Char(string='Company')
    email = fields.Char(string='Email')
    phone = fields.Char(string='Phone')
    active = fields.Boolean(default=True)  # إضافة حقل active للأرشفة

    # علاقة عكسية مع المستندات
    document_ids = fields.One2many('archive.management', 'directed_to', string='Documents')
    document_count = fields.Integer(string='Document Count', compute='_compute_document_count')

    # احتساب عدد المستندات
    @api.depends('document_ids')
    def _compute_document_count(self):
        for record in self:
            record.document_count = len(record.document_ids)

    # عرض المستندات
    def action_view_documents(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Documents',
            'res_model': 'archive.management',
            'view_mode': 'list,form',
            'domain': [('directed_to', '=', self.id)],
            'context': {'default_directed_to': self.id}
        }