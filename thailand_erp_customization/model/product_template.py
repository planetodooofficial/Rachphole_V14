from odoo import fields,models

class ProductTemplate(models.Model):

    _inherit = 'product.template'

    manufacturing = fields.Char('Manufacturing')
    created_from_boq = fields.Boolean(default=False)