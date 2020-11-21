from odoo import fields,models,api
import logging
_logger = logging.getLogger(__name__)

class MrpBOMLineInherit(models.Model):

    _inherit = 'mrp.bom.line'

    function = fields.Char('Function')
    product_sales_price = fields.Float('Price')

    @api.onchange('function')
    def update_function(self):
        for line in self:
            if line.function:
                search_boq_id = self.env['bom.details'].search([('reference','=',line.bom_id.code),
                                                                ('product_id','=',line.product_id.id)])
                if search_boq_id:
                    for rec in search_boq_id:
                        rec.write({'function': line.function})

    @api.onchange('product_id', 'product_qty')
    def get_sale_price(self):
        for line in self:
            if line.product_id:
                try:
                    line.product_sales_price = line.product_id.lst_price * line.product_qty

                except Exception as e:
                    _logger.info('------------------The error in sale price for BoM------------%s', e)


class MrpBOMInherit(models.Model):

    _inherit = 'mrp.bom'

    total_price = fields.Float('Total Price', compute='get_total_price')

    @api.depends('bom_line_ids.product_id', 'bom_line_ids.product_qty', 'bom_line_ids.product_sales_price')
    def get_total_price(self):
        for bom in self:
            total_amt = 0.0
            for line in bom.bom_line_ids:
                total_amt += line.product_sales_price
            bom.update({
                'total_price': total_amt
            })