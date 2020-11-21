from odoo import fields,api,models,_

class AccountMoveInherit(models.Model):
    _inherit = 'account.move'

    # trading_order = fields.Boolean('Trading')
    # service_order = fields.Boolean('Service')
    so_type = fields.Selection([
        ('trading', 'Trading'),
        ('service', 'Service')], string='Type')

    po_number_customer = fields.Char('P/O Number')

    project_ids = fields.Many2many('project.project', string='Project')
