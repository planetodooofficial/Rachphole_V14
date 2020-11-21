from odoo import api, fields, models

class ResPartner(models.Model):

    _inherit = 'res.partner'

    summarize_purchase_order = fields.Boolean('Summarize Purchase Order')