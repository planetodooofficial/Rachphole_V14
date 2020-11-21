from odoo import fields, models, api
from odoo.exceptions import UserError


class ConfirmSaleOrder(models.TransientModel):

    _name = 'confirm.sale.order.wiz'

    so_ids = fields.One2many('sale.order.wiz.line', 'confirm_so_id', 'Sale Order')

    @api.model
    def default_get(self, field):
        res = super(ConfirmSaleOrder, self).default_get(field)
        active_ids = self.env['sale.order'].browse(self._context.get('active_ids'))
        value = []
        if active_ids:
            for rec in active_ids:
                if rec.state in ('draft', 'sent'):
                    line_vals = (0, 0, {
                        'so_id': rec.id,
                        'so_state': rec.state
                    })
                    value.append(line_vals)
                else:
                    raise UserError('Selected Sale Orders Have Already Been Confirmed.')
            res['so_ids'] = value
        return res

    def confirm_sale_order(self):
        active_ids = self.env['sale.order'].browse(self._context.get('active_ids'))
        if active_ids:
            for line in active_ids:
                line.write({'state': 'sale'})

class SaleOrderWizLine(models.TransientModel):

    _name = 'sale.order.wiz.line'

    confirm_so_id = fields.Many2one('confirm.sale.order.wiz')
    so_id = fields.Many2one('sale.order', 'Quotation Number')
    so_state = fields.Selection([
        ('draft', 'Quotation'),
        ('sent', 'Quotation Sent'),
        ('sale', 'Sales Order'),
        ('done', 'Locked'),
        ('cancel', 'Cancelled'),
    ], string='Status')

class SaleOrderLocWiz(models.TransientModel):

    _name = 'sale.order.loc.wiz'

    location_id=fields.Many2one("stock.location","WH Location")
    sale_order_id=fields.Many2one("sale.order","Sale order")

    def confirm_sale_order(self):
        if self.location_id:
            self.sale_order_id.write({'wh_location':self.location_id.id})
            self.sale_order_id.action_confirm()