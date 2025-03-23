# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime
import unicodedata


class ArchiveManagement(models.Model):
    _name = 'archive.management'
    _description = 'Archive Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    # Campos básicos
    name = fields.Char(string='Name', required=True, tracking=True)
    reference = fields.Char(string='Reference', tracking=True, readonly=True, copy=False)
    date = fields.Date(string='Date', default=fields.Date.context_today, tracking=True, required=True)
    deadline = fields.Date(string='Deadline', tracking=True)
    description = fields.Html(string='Description')
    notes = fields.Text(string='Notes')

    # Campos para archivos PDF
    file = fields.Binary("PDF File", attachment=True)
    file_name = fields.Char("File Name")
    attachment_id = fields.Many2one('ir.attachment', string="Main Attachment", ondelete='cascade', auto_join=True,
                                    copy=False)
    indexed_content = fields.Text("Extracted Text", related="attachment_id.index_content", store=True)
    indexed_content_2 = fields.Text("Normalized Text", compute='_normalize_arabic_text', store=True)

    # Campos de clasificación
    document_type = fields.Selection([
        ('incoming', 'Incoming'),
        ('outgoing', 'Outgoing'),
        ('memo', 'Memo'),
    ], string='Document Type', required=True, default='incoming', tracking=True)

    sent_by = fields.Many2one('archive.sent.by', string='Sent By', tracking=True)
    directed_to = fields.Many2one('archive.directed.to', string='Directed To', tracking=True)
    user_id = fields.Many2one('res.users', string='Assigned To',
                              default=lambda self: self.env.user.id, tracking=True)

    category_id = fields.Many2one('archive.category', string='Category', tracking=True)
    tag_ids = fields.Many2many('archive.tag', string='Tags')

    # Adjuntos y relaciones
    attachment_ids = fields.Many2many('ir.attachment', 'archive_attachment_rel', 'archive_id', 'attachment_id',
                                      string='Attachments')
    related_document_ids = fields.Many2many('archive.management', 'archive_related_rel',
                                            'document_id', 'related_id',
                                            string='Related Documents')

    # Estado y atributos
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_review', 'In Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('archived', 'Archived')
    ], string='Status', default='draft', tracking=True, copy=False)

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

    # Método para normalización de texto árabe
    @api.depends('indexed_content')
    def _normalize_arabic_text(self):
        for rec in self:
            rec.indexed_content_2 = ''
            if rec.indexed_content:
                rec.indexed_content_2 = unicodedata.normalize("NFKC", rec.indexed_content)

                # Métodos de flujo de trabajo

    def action_confirm(self):
        for record in self:
            if record.state == 'draft':
                record.state = 'in_review'
                record.message_post(body=_("Document confirmed and sent for review."))

    def action_in_review(self):
        for record in self:
            if record.state in ('draft', 'rejected'):
                record.state = 'in_review'
                record.message_post(body=_("Document sent for review."))

    def action_approve(self):
        for record in self:
            if record.state == 'in_review':
                record.state = 'approved'
                record.message_post(body=_("Document approved."))

    def action_reject(self):
        for record in self:
            if record.state == 'in_review':
                record.state = 'rejected'
                record.message_post(body=_("Document rejected."))

    def action_archive_doc(self):
        for record in self:
            if record.state == 'approved':
                record.state = 'archived'
                record.message_post(body=_("Document archived."))

    def action_draft(self):
        for record in self:
            if record.state != 'draft':
                record.state = 'draft'
                record.message_post(body=_("Document reset to draft."))

                # Historial de documentos

    def action_view_history(self):
        self.ensure_one()
        return {
            'name': _('Document History'),
            'type': 'ir.actions.act_window',
            'res_model': 'mail.message',
            'view_mode': 'tree,form',
            'domain': [('model', '=', 'archive.management'), ('res_id', '=', self.id)],
            'context': {'default_model': 'archive.management', 'default_res_id': self.id},
            'target': 'new',
        }

        # Ver adjunto PDF

    def action_open_attachment(self):
        self.ensure_one()
        if self.attachment_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'ir.attachment',
                'res_id': self.attachment_id.id,
                'view_mode': 'form',
                'target': 'current',
                'name': _('Attachment'),
            }
        else:
            return False

            # Acción para búsqueda avanzada en texto extraído

    def action_search_content(self):
        """Acción para buscar específicamente en el texto extraído"""
        return {
            'name': _('بحث متقدم في النص'),
            'type': 'ir.actions.act_window',
            'res_model': 'archive.content.search.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_model': 'archive.management'},
        }

        # Función nueva para resolver el error de referencia externa

    def action_content_search(self):
        """Acción para abrir el asistente de búsqueda de contenido"""
        return {
            'name': _('بحث متقدم في النص'),
            'type': 'ir.actions.act_window',
            'res_model': 'archive.content.search.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_model': 'archive.management'},
        }

        # Validación antes de eliminación

    def unlink(self):
        for record in self:
            if record.state not in ('draft', 'rejected'):
                raise UserError(_("You can only delete documents in draft or rejected state."))
        return super(ArchiveManagement, self).unlink()

        # Creación con generación de secuencia y procesamiento de PDF

    @api.model_create_multi
    def create(self, vals_list):
        result = []
        for vals in vals_list:
            # Generar referencia secuencial
            if not vals.get('reference'):
                doc_type = vals.get('document_type', 'incoming')
                sequence_code = f'archive.management.{doc_type}'
                vals['reference'] = self.env['ir.sequence'].next_by_code(sequence_code) or '/'

                # Lógica para crear nombre a partir del código de documento si no se proporciona
            if not vals.get('name'):
                current_year = datetime.now().year
                if vals.get('document_type') == 'incoming':
                    sequence_code = 'mfz.archive.in'
                    document_type_code = 1
                elif vals.get('document_type') == 'outgoing':
                    sequence_code = 'mfz.archive.out'
                    document_type_code = 2
                elif vals.get('document_type') == 'memo':
                    sequence_code = 'mfz.archive.memo'
                    document_type_code = 3
                else:
                    sequence_code = 'mfz.archive.generic'
                    document_type_code = 0

                next_sequence = self.env['ir.sequence'].next_by_code(sequence_code) or '0001'
                vals['name'] = f"mfz/{current_year}/{document_type_code}/{next_sequence}"

                # Crear registro
            record = super(ArchiveManagement, self.with_context(mail_create_nosubscribe=True)).create([vals])[0]
            result.append(record.id)

            # Procesar archivo PDF
            if record.file and record.file_name:
                attachment = self.env['ir.attachment'].create({
                    'name': record.file_name,
                    'datas': record.file,
                    'res_model': 'archive.management',
                    'res_id': record.id,
                    'mimetype': 'application/pdf',
                })
                record.attachment_id = attachment.id

        return self.browse(result)

        # Actualización de registros con procesamiento de PDF

    def write(self, vals):
        # Procesar archivo PDF si se actualiza
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

        return super(ArchiveManagement, self).write(vals)

        # Estadísticas para el panel

    @api.model
    def get_dashboard_data(self):
        return {
            'incoming': self.search_count([('document_type', '=', 'incoming')]),
            'outgoing': self.search_count([('document_type', '=', 'outgoing')]),
            'memo': self.search_count([('document_type', '=', 'memo')]),
            'draft': self.search_count([('state', '=', 'draft')]),
            'in_review': self.search_count([('state', '=', 'in_review')]),
            'approved': self.search_count([('state', '=', 'approved')]),
            'rejected': self.search_count([('state', '=', 'rejected')]),
            'archived': self.search_count([('state', '=', 'archived')]),
            'my_documents': self.search_count([('user_id', '=', self.env.user.id)]),
            'high_priority': self.search_count([('priority', '=', '3')]),
            'pending_review': self.search_count([('state', '=', 'in_review')]),
        }

        # Actualizar nombre cuando cambia el tipo de documento

    @api.onchange('document_type')
    def _onchange_document_type(self):
        if not self.name:
            # Si no hay nombre, generamos uno nuevo
            current_year = datetime.now().year
            document_type_code = self._get_document_type_code()
            sequence_code = f'mfz.archive.{self.document_type or "generic"}'
            next_sequence = self.env['ir.sequence'].next_by_code(sequence_code) or '0001'
            self.name = f"mfz/{current_year}/{document_type_code}/{next_sequence}"
        elif isinstance(self.name, str) and self.name.startswith('mfz/'):
            # Si el nombre tiene el formato esperado, actualizamos solo el código de tipo
            current_year = datetime.now().year
            document_type_code = self._get_document_type_code()

            if '/' in self.name:
                parts = self.name.split('/')
                if len(parts) >= 4:
                    parts[2] = str(document_type_code)
                    self.name = '/'.join(parts)
                else:
                    # Si no tiene las partes esperadas, regeneramos
                    sequence_code = f'mfz.archive.{self.document_type or "generic"}'
                    next_sequence = self.env['ir.sequence'].next_by_code(sequence_code) or '0001'
                    self.name = f"mfz/{current_year}/{document_type_code}/{next_sequence}"

                    # Método auxiliar para obtener el código de tipo de documento

    def _get_document_type_code(self):
        if self.document_type == 'incoming':
            return 1
        elif self.document_type == 'outgoing':
            return 2
        elif self.document_type == 'memo':
            return 3
        else:
            return 0

            # Copiar documentos con adjuntos

    def copy(self, default=None):
        default = dict(default or {})
        default['name'] = _('Copy of %s') % self.name
        default['reference'] = False  # Para que se genere un nuevo número

        new_record = super(ArchiveManagement, self).copy(default)

        # Copiar el adjunto principal si existe
        if self.attachment_id:
            attachment_data = self.attachment_id.copy_data()[0]
            attachment_data.update({
                'res_model': 'archive.management',
                'res_id': new_record.id,
            })
            new_attachment = self.env['ir.attachment'].create(attachment_data)
            new_record.attachment_id = new_attachment.id

        return new_record

        # Para detectar duplicados

    def _check_duplicates(self):
        """Busca posibles duplicados basados en nombre, referencia o contenido"""
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
        """Acción para buscar y mostrar posibles duplicados"""
        self.ensure_one()
        duplicates = self._check_duplicates()

        if not duplicates:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No duplicates found'),
                    'message': _('No potential duplicate documents were found.'),
                    'sticky': False,
                    'type': 'success',
                }
            }

        return {
            'name': _('Potential Duplicates'),
            'type': 'ir.actions.act_window',
            'res_model': 'archive.management',
            'view_mode': 'list,form',
            'domain': [('id', 'in', duplicates.ids)],
            'target': 'new',
        }