# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ArchiveContact(models.Model):
    _name = 'archive.contact'
    _description = 'Archive Contact'

    name = fields.Char(string='Name', required=True)
    title = fields.Char(string='Title')
    company = fields.Char(string='Company')
    email = fields.Char(string='Email')
    phone = fields.Char(string='Phone')

    # العلاقات مع النماذج الأخرى
    directed_to_id = fields.Many2one('archive.directed.to', string='Directed To Contact')
    sent_by_id = fields.Many2one('archive.sent.by', string='Sent By Contact')

    # دالة تحويل جهة اتصال إلى جهة مستقبلة
    def action_convert_to_directed_to(self):
        self.ensure_one()
        if not self.directed_to_id:
            directed_to = self.env['archive.directed.to'].create({
                'name': self.name,
                'title': self.title,
                'company': self.company,
                'email': self.email,
                'phone': self.phone,
            })
            self.directed_to_id = directed_to.id
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'archive.directed.to',
            'res_id': self.directed_to_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

        # دالة تحويل جهة اتصال إلى جهة مرسلة

    def action_convert_to_sent_by(self):
        self.ensure_one()
        if not self.sent_by_id:
            sent_by = self.env['archive.sent.by'].create({
                'name': self.name,
                'title': self.title,
                'company': self.company,
                'email': self.email,
                'phone': self.phone,
            })
            self.sent_by_id = sent_by.id
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'archive.sent.by',
            'res_id': self.sent_by_id.id,
            'view_mode': 'form',
            'target': 'current',
        }