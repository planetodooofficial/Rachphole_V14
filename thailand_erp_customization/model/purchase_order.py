from odoo import api, fields, models, _, SUPERUSER_ID
from odoo.tools.float_utils import float_compare
from dateutil import relativedelta
from odoo.exceptions import UserError, ValidationError

from odoo.addons.purchase.models.purchase import PurchaseOrder as Purchase


class PurchaseOrderInherit(models.Model):

    _inherit = 'purchase.order'

    outsource = fields.Boolean('Outsource')
    approved_by_engineer = fields.Boolean('Approved By Engineer')
    discount = fields.Float('Discount')
    project_id = fields.Many2one('project.project', 'Project')
    project_ids = fields.Many2many('project.project', string='Project')

    def button_confirm(self):
        res = super(PurchaseOrderInherit, self).button_confirm()
        # update the project in receipts
        if self.project_ids:
            for do_pick in self.picking_ids:
                do_pick.write({'project_ids': [(6,0, self.project_ids.ids)]})

        return res

    def action_view_invoice(self):
        res = super(PurchaseOrderInherit, self).action_view_invoice()
        project_list = []
        # update projects in invoice
        if self.project_ids:
            for rec in self.project_ids:
                project_list.append(rec.id)

        if project_list:
            res['context']['default_project_ids'] = [(6,0, project_list)]
            # res['project_ids'] = [(6,0, project_list)]
            # res.update({'project_ids': [(6,0, project_list)]})

        return res


    @api.onchange('partner_id')
    def summarize_purchase_order(self):
        if self.partner_id:
            search_po_ids = self.env['purchase.order'].search([('partner_id', '=', self.partner_id.id)])
            if search_po_ids and self.partner_id.summarize_purchase_order:
                for rec in search_po_ids:
                    if rec.state in ['draft', 'sent']:
                        raise ValidationError('There is another purchase order in open state.')

    @api.depends('order_line.price_total', 'discount')
    def _amount_all(self):
        for order in self:
            amount_untaxed = amount_tax = total_untaxed_amt = 0.0
            for line in order.order_line:
                amount_untaxed += line.price_subtotal
                total_untaxed_amt += line.price_subtotal
                amount_tax += line.price_tax

            if order.discount:
                amount_untaxed = total_untaxed_amt - order.discount
            order.update({
                'amount_untaxed': order.currency_id.round(amount_untaxed),
                'amount_tax': order.currency_id.round(amount_tax),
                'amount_total': amount_untaxed + amount_tax,
            })

    @api.model
    def _prepare_picking(self):
        if not self.group_id:
            self.group_id = self.group_id.create({
                'name': self.name,
                'partner_id': self.partner_id.id
            })
        if not self.partner_id.property_stock_supplier.id:
            raise UserError(_("You must set a Vendor Location for this partner %s") % self.partner_id.name)
        locatn = []
        for line in self.order_line:
            if line.destination_location not in locatn:
                locatn.append(line.destination_location)
        vals1 = []
        for loc in locatn:
            vals1.append({
                'picking_type_id': self.picking_type_id.id,
                'partner_id': self.partner_id.id,
                'user_id': False,
                'date': self.date_order,
                'origin': self.name,
                'location_dest_id': loc.id,
                # self._get_destination_location()
                'location_id': self.partner_id.property_stock_supplier.id,
                'company_id': self.company_id.id,
            })
        # return {
        #     'picking_type_id': self.picking_type_id.id,
        #     'partner_id': self.partner_id.id,
        #     'user_id': False,
        #     'date': self.date_order,
        #     'origin': self.name,
        #     'location_dest_id': self._get_destination_location(),
        #     'location_id': self.partner_id.property_stock_supplier.id,
        #     'company_id': self.company_id.id,
        # }
        return vals1

    def _create_picking(self):
        StockPicking = self.env['stock.picking']
        for order in self:
            if any([ptype in ['product', 'consu'] for ptype in order.order_line.mapped('product_id.type')]):
                order = order.with_company(order.company_id)
                pickings = order.picking_ids.filtered(lambda x: x.state not in ('done', 'cancel'))
                if not pickings:
                    res = order._prepare_picking()
                    picking_cust_ids=[]
                    for re in res:
                        picking = StockPicking.with_user(SUPERUSER_ID).create(re)
                        picking_cust_ids.append(picking)
                        lines = order.order_line.filtered(lambda l: l.destination_location.id == re.get('location_dest_id'))

                        moves = lines._create_stock_moves(picking)
                        moves = moves.filtered(lambda x: x.state not in ('done', 'cancel'))._action_confirm()
                        seq = 0
                        for move in sorted(moves, key=lambda move: move.date):
                            seq += 5
                            move.sequence = seq
                        moves._action_assign()
                        picking.message_post_with_view('mail.message_origin_link',
                                                       values={'self': picking, 'origin': order},
                                                       subtype_id=self.env.ref('mail.mt_note').id)
                else:
                    picking = pickings[0]

                    moves = order.order_line._create_stock_moves(picking)
                    moves = moves.filtered(lambda x: x.state not in ('done', 'cancel'))._action_confirm()
                    seq = 0
                    for move in sorted(moves, key=lambda move: move.date):
                        seq += 5
                        move.sequence = seq
                    moves._action_assign()
                    picking.message_post_with_view('mail.message_origin_link',
                        values={'self': picking, 'origin': order},
                        subtype_id=self.env.ref('mail.mt_note').id)
        return True


#
class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    sale_order_id=fields.Many2one('sale.order', 'SO No.')
    project_id = fields.Many2one('project.project', 'Project')
    destination_location=fields.Many2one('stock.location','Destination Loc')


    def _find_candidate(self, product_id, product_qty, product_uom, location_id, name, origin, company_id, values):
        """ Return the record in self where the procument with values passed as
        args can be merged. If it returns an empty record then a new line will
        be created.
        """
        lines = self.filtered(lambda l: l.project_id == values['project_id'] and l.sale_order_id == values['sale_order_id'] and l.price_unit == values['after_disc_prod_price'] and l.propagate_date == values['propagate_date'] and l.propagate_date_minimum_delta == values['propagate_date_minimum_delta'] and l.propagate_cancel == values['propagate_cancel'])
        return lines and lines[0] or self.env['purchase.order.line']

    def _prepare_stock_moves(self, picking):
        """ Prepare the stock moves data for one order line. This function returns a list of
        dictionary ready to be used in stock.move's create()
        """
        res = super(PurchaseOrderLine, self)._prepare_stock_moves(picking)
        print(res)
        res[0]['location_dest_id']=self.destination_location.id
        # self.ensure_one()
        # res = []
        # if self.product_id.type not in ['product', 'consu']:
        #     return res
        # qty = 0.0
        # price_unit = self._get_stock_move_price_unit()
        # outgoing_moves, incoming_moves = self._get_outgoing_incoming_moves()
        # for move in outgoing_moves:
        #     qty -= move.product_uom._compute_quantity(move.product_uom_qty, self.product_uom, rounding_method='HALF-UP')
        # for move in incoming_moves:
        #     qty += move.product_uom._compute_quantity(move.product_uom_qty, self.product_uom, rounding_method='HALF-UP')
        # description_picking = self.product_id.with_context(
        #     lang=self.order_id.dest_address_id.lang or self.env.user.lang)._get_description(
        #     self.order_id.picking_type_id)
        # template = {
        #     # truncate to 2000 to avoid triggering index limit error
        #     # TODO: remove index in master?
        #     'name': (self.name or '')[:2000],
        #     'product_id': self.product_id.id,
        #     'product_uom': self.product_uom.id,
        #     'date': self.order_id.date_order,
        #     'date_expected': self.date_planned,
        #     'location_id': self.order_id.partner_id.property_stock_supplier.id,
        #     'location_dest_id': self.destination_location.id,
        #     # 'location_dest_id': self.order_id._get_destination_location(),
        #     'picking_id': picking.id,
        #     'partner_id': self.order_id.dest_address_id.id,
        #     'move_dest_ids': [(4, x) for x in self.move_dest_ids.ids],
        #     'state': 'draft',
        #     'purchase_line_id': self.id,
        #     'company_id': self.order_id.company_id.id,
        #     'price_unit': price_unit,
        #     'picking_type_id': self.order_id.picking_type_id.id,
        #     'group_id': self.order_id.group_id.id,
        #     'origin': self.order_id.name,
        #     'propagate_date': self.propagate_date,
        #     'propagate_date_minimum_delta': self.propagate_date_minimum_delta,
        #     'description_picking': description_picking,
        #     'propagate_cancel': self.propagate_cancel,
        #     'route_ids': self.order_id.picking_type_id.warehouse_id and [
        #         (6, 0, [x.id for x in self.order_id.picking_type_id.warehouse_id.route_ids])] or [],
        #     'warehouse_id': self.order_id.picking_type_id.warehouse_id.id,
        # }
        # diff_quantity = self.product_qty - qty
        # if float_compare(diff_quantity, 0.0, precision_rounding=self.product_uom.rounding) > 0:
        #     po_line_uom = self.product_uom
        #     quant_uom = self.product_id.uom_id
        #     product_uom_qty, product_uom = po_line_uom._adjust_uom_quantities(diff_quantity, quant_uom)
        #     template['product_uom_qty'] = product_uom_qty
        #     template['product_uom'] = product_uom.id
        #     res.append(template)
        return res
#
#     discount = fields.Float(string="Discount (%)", digits="Discount")
#
#     @api.depends('product_qty', 'price_unit', 'taxes_id', 'discount')
#     def _compute_amount(self):
#         for line in self:
#             taxes = line.taxes_id.compute_all(line.price_unit, line.order_id.currency_id, line.product_qty,
#                                               product=line.product_id, partner=line.order_id.partner_id)
#             if line.discount:
#                 discount = (line.price_unit * line.discount * line.product_qty) / 100
#                 line.update({
#                     'price_tax': taxes['total_included'] - taxes['total_excluded'],
#                     'price_total': taxes['total_included'],
#                     'price_subtotal': taxes['total_excluded'] - discount,
#                 })
#             else:
#                 line.update({
#                     'price_tax': taxes['total_included'] - taxes['total_excluded'],
#                     'price_total': taxes['total_included'],
#                     'price_subtotal': taxes['total_excluded'],
#                 })
#
#     def _prepare_account_move_line(self, move):
#         vals = super(PurchaseOrderLine, self)._prepare_account_move_line(move)
#         vals["discount"] = self.discount
#         return vals