import base64

import xlwt,xlrd
from odoo import fields, models, api, _
from odoo.tools import float_is_zero
from itertools import groupby
from odoo.exceptions import UserError
import logging
import io
from datetime import date, timedelta
from PIL import Image
import os

from datetime import datetime

_logger = logging.getLogger(__name__)


class SaleOrderInherit(models.Model):

    _inherit = 'sale.order'

    total_without_disc = fields.Float('Total')
    disc_perc = fields.Float('Discount%')
    tax_vat_perc = fields.Float('Tax/Vat Rate')
    quote_name = fields.Char('Quotation Name')
    discount_amt = fields.Monetary(string='Discount', store=True, readonly=True, compute='_amount_all')
    add_child_prod = fields.Boolean('Add Child Components')
    show_project = fields.Boolean()
    create_project_id = fields.Boolean('Create Project')
    date = fields.Datetime('Date')
    warranty_period = fields.Integer('Warranty Period', default=1)
    warranty_period_type = fields.Selection([('days', 'Day(s)'), ('weeks', 'Week(s)'),
                                             ('months', 'Month(s)'), ('years', 'Year(s)'), ], string='warranty period',
                                            help="warranty period as days/weeks/months/years", default='years')
    project_id = fields.Many2one('project.project', 'Project')
    revision_no = fields.Char('Quotation Revision No.')
    purchase_order_no = fields.Char('P/O Number')
    so_type = fields.Selection([
        ('trading', 'Trading'),
        ('service', 'Service')], string='Type', default='trading')
    bom_ids = fields.One2many('bill.of.quantities', 'sale_order_id', 'Bill of quantities')
    bom_multiplier = fields.Integer('Profit in (%)', default=100)
    document_ids = fields.One2many('document.sale.order', 'sale_order_id', 'Document')
    engineer_lines = fields.One2many('engineering.line', 'sale_order_id', 'Engineering')
    engineering_multiplier = fields.Integer('Profit in (%)', default=100)
    document_multiplier = fields.Integer('Profit in (%)', default=100)
    show_eng_tax_id = fields.Boolean('Show Taxes')

    show_job_cost = fields.Boolean('Show Job Cost')

    bom_details_id = fields.One2many('bom.details', 'sale_order_id', 'BOQ Details')
    # is_doc = fields.Boolean()
    # new_price_total = fields.Float()

    # commented**************
    avail_purchase_order_id = fields.Many2one('purchase.order', 'Purchase Order')
    payment_term_note = fields.Text('Payment Term Note')
    delivery = fields.Char('Delivery')
    wh_location = fields.Many2one('stock.location', 'Location')

    def _write(self, values):
        if not 'date' in values:
            self.date = fields.Datetime.now()
        return super(SaleOrderInherit, self)._write(values)

    # @api.onchange('project_id')
    # def _get_project_warehouse(self):
    #     if self.project_id:
    #         self.warehouse_id = self.project_id.warehouse_id


    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            seq_date = None
            if 'date_order' in vals:
                seq_date = fields.Datetime.context_timestamp(self, fields.Datetime.to_datetime(vals['date_order']))
            if 'company_id' in vals:
                old_name = self.env['ir.sequence'].with_context(force_company=vals['company_id']).next_by_code(
                    'sale.order.custom', sequence_date=seq_date) or _('New')
                old_name = old_name.replace('QT','')
                new_name = 'QT' + str(datetime.today().strftime('%y%m%d')) + '-' + str(old_name)
                vals['name'] = new_name
                vals['date'] = fields.Datetime.now()
                # vals['show_project'] = True

            else:
                vals['name'] = self.env['ir.sequence'].next_by_code('sale.order.custom', sequence_date=seq_date) or _('New')

        # Makes sure partner_invoice_id', 'partner_shipping_id' and 'pricelist_id' are defined
        if any(f not in vals for f in ['partner_invoice_id', 'partner_shipping_id', 'pricelist_id']):
            partner = self.env['res.partner'].browse(vals.get('partner_id'))
            addr = partner.address_get(['delivery', 'invoice'])
            vals['partner_invoice_id'] = vals.setdefault('partner_invoice_id', addr['invoice'])
            vals['partner_shipping_id'] = vals.setdefault('partner_shipping_id', addr['delivery'])
            vals['pricelist_id'] = vals.setdefault('pricelist_id',
                                                   partner.property_product_pricelist and partner.property_product_pricelist.id)
        result = super(SaleOrderInherit, self).create(vals)
        return result


    # @api.onchange('create_project_id')
    # def create_project(self):
    #     if self.create_project_id and self.show_project:
    #         project_obj = self.env['project.project']
    #         search_project_id = project_obj.search([('name', '=', self.name)])
    #         if not search_project_id:
    #             project_id = project_obj.create({'name': self.name})
    #             self.write({'project_id': project_id.id})


    @api.depends('bom_ids.product_subtotal')
    def _amount_bom_total(self):
        for order in self:
            bom_amount_total = 0.0
            bom_after_disc_total=0.0
            for line in order.bom_ids:
                bom_amount_total += line.product_subtotal
                bom_after_disc_total += line.total_price_after_disc
            order.update({'bom_amount_total': bom_amount_total,'bom_cost_amount_total':bom_after_disc_total })

    @api.depends('amount_total','bom_cost_amount_total','total_overhead_cost')
    def _get_margin_amount(self):
        for line in self:
            cost_amount=line.bom_cost_amount_total + line.total_overhead_cost
            cust_margin=line.amount_untaxed - cost_amount
            line.cust_margin=cust_margin
            if line.cust_margin and line.amount_untaxed:
                line.margin_percent=(cust_margin/line.amount_untaxed)*100

    @api.depends('document_total_cost', 'engineer_total_cost')
    def _get_overhead_amount(self):
        for line in self:
            line.total_overhead_cost=line.document_total_cost + line.engineer_total_cost


    bom_amount_total = fields.Monetary('Total Subtotal Cost', store=True, compute='_amount_bom_total')
    bom_cost_amount_total = fields.Monetary('Total Subtotal After Disc', store=True, compute='_amount_bom_total')
    boq_details_amount_total = fields.Monetary('Total Cost', store=True)
    cust_margin=fields.Monetary('Margin', store=True, compute='_get_margin_amount')
    margin_percent=fields.Float("Margin %", store=True, compute="_get_margin_amount")
    total_overhead_cost=fields.Monetary('Total Overhead Cost', store=True, compute='_get_overhead_amount')

    def get_bom_details(self):
        if self.bom_details_id:
            for rec in self.bom_details_id:
                rec.unlink()

        current_note = ''
        current_note_id = self.env['bom.details']
        last_line = self.env['sale.order.line']
        index = 0
        section_total = 0
        current_line_id = 0
        boq_line_obj = self.env['bill.of.quantities']
        for rec in self.bom_ids:
            # boq_line_id = boq_line_obj.search([('sale_order_id', '=', self.id), ('boq_id', '=', rec.id)],
            #                                            limit=1)
            section_total += rec.product_subtotal

            if rec.display_type == 'line_section':
                self.sudo().write({'bom_details_id': [(0, 0, {
                    'display_type': 'line_section',
                    'name': rec.name,
                    'boq_id': rec.id,
                })]})
                current_note = rec.name

            if current_note:
                for bom_rec in self.bom_details_id:
                    if bom_rec.display_type == 'line_section' and bom_rec.name == current_note and bom_rec.boq_id.id == rec.id:
                        current_note_id = bom_rec

                last_line = self.bom_ids[-1]

                if current_note_id:
                    if rec == last_line or (self.bom_ids[index + 1].display_type == 'line_section'):
                        current_note_id.write({'product_subtotal': section_total})
                        section_total = 0

            if self.add_child_prod:
                if rec.product_id:
                    if rec.product_id.default_code:
                        description = "[" + rec.product_id.default_code + "] " + rec.product_id.name
                    else:
                        description = rec.product_id.name
                    self.sudo().write({'bom_details_id': [(0, 0, {'product_id': rec.product_id.id,
                                                                  'product_qty': rec.product_qty,
                                                                  'product_uom': rec.product_uom.id,
                                                                  'product_cost_price': rec.product_sale_price,
                                                                  'product_subtotal': rec.product_subtotal,
                                                                  'po_location': rec.po_location.id,
                                                                  'name': description,
                                                                  'prod_disc':rec.prod_disc,
                                                                  'after_disc_prod_price':rec.after_disc_prod_price,
                                                                  'total_price_after_disc':rec.total_price_after_disc
                                                                  })]})

            if not self.add_child_prod:
                if rec.bom_product_id:
                    self.sudo().write({'bom_details_id': [(0, 0, {
                        'display_type': 'line_note',
                        'name': rec.name,
                        # 'boq_id': rec.id,
                        'product_subtotal': rec.product_subtotal,
                    })]})
                    search_bom_id = self.env['mrp.bom'].search([('id', '=', rec.bom_product_id.id)])
                    if search_bom_id:
                        for line in search_bom_id.bom_line_ids:
                            if line.product_id.default_code:
                                description = "[" + line.product_id.default_code + "] " + line.product_id.name
                            else:
                                description = line.product_id.name
                            self.sudo().write({'bom_details_id': [(0, 0, {'reference': search_bom_id.code,
                                                                          'product_id': line.product_id.id,
                                                                          'product_qty': line.product_qty * rec.product_qty,
                                                                          'product_uom': line.product_uom_id.id,
                                                                          'product_cost_price': line.product_sales_price,
                                                                          'product_subtotal': line.product_qty * rec.product_qty * line.product_sales_price,
                                                                          'name': description,
                                                                          'po_location': rec.po_location.id,
                                                                          'function': line.function,
                                                                          'prod_disc': rec.prod_disc,
                                                                          'after_disc_prod_price': rec.after_disc_prod_price,
                                                                          'total_price_after_disc': rec.total_price_after_disc

                                                                          })]})
            index += 1

    #
    # @api.onchange('trading_order')
    # def set_trading(self):
    #     if self.trading_order:
    #         self.service_order = False
    #
    # @api.onchange('service_order')
    # def set_service(self):
    #     if self.service_order:
    #         self.trading_order = False

    # # Commented************
    @api.depends('engineer_lines.line_total')
    def _amount_engineering_total(self):
        for order in self:
            engineer_amount_total = 0.0
            engineer_total_cost = 0.0
            for line in order.engineer_lines:
                engineer_amount_total += line.line_total
                engineer_total_cost += line.line_cost_total
            order.update({'engineer_amount_total': engineer_amount_total, 'engineer_total_cost':engineer_total_cost})

    engineer_amount_total = fields.Monetary('Total Engineering Sale Price', store=True, compute='_amount_engineering_total')
    engineer_total_cost = fields.Monetary('Total Engineering Cost', store=True, compute='_amount_engineering_total')

    # Commented*************
    # @api.depends('document_ids.line_total')
    # def _amount_document_total(self):
    #     for order in self:
    #         document_total_amount = 0.0
    #         for line in order.document_ids:
    #             document_total_amount += line.line_total
    #
    #         order.update({'document_total_amount': document_total_amount})

    # Commented***************
    # document_total_amount = fields.Monetary('Total Document Cost', store=True, compute='_amount_document_total')
    @api.depends('document_ids.line_total')
    def _amount_document_total(self):
        for order in self:
            document_total_amount = 0.0
            document_total_cost = 0.0
            for line in order.document_ids:
                document_total_amount += line.line_total
                document_total_cost += line.line_cost_total

            order.update({'document_total_amount': document_total_amount, 'document_total_cost': document_total_cost})

    document_total_amount = fields.Monetary('Total Document sale Price', store=True, compute='_amount_document_total')
    document_total_cost= fields.Monetary('Total Document Cost', store=True, compute='_amount_document_total')

    def add_bom_to_order_lines(self):
        """
        This function will add products from BoM tab as product and take unit price from sale price column in BoM tab
        :return:
        """
        sale_order_line_obj = self.env['sale.order.line']
        section_subtotal = 0
        section_count = 0
        current_section = ''
        index = 0
        unit = self.env['uom.uom']
        for rec in self.order_line:
            if rec.type == 'boq_child' or rec.type == 'boq' or (rec.name == 'BILL OF QUANTITIES' and rec.display_type == 'line_section'):
                rec.unlink()

        if not self.add_child_prod:
            self.sudo().write({'order_line': [(0, 0, {
                'display_type': 'line_section',
                'name': 'BILL OF QUANTITIES' + '  [Subtotal: ' + str(self.bom_amount_total) + ']',
                'type': 'boq',
            })]})

            for line in self.bom_ids:
                if line.display_type == 'line_section':
                    self.sudo().write({'order_line': [(0, 0, {
                        'display_type': 'line_note',
                        'name': line.name,
                        'type': 'boq'
                    })]})
                else:
                    product = [(0, 0, {
                        'product_id': line.bom_product_id.product_tmpl_id.product_variant_id.id,
                        'product_uom_qty': line.product_qty,
                        'product_uom': line.product_uom.id,
                        'price_unit': line.product_sale_price,
                        'after_disc_prod_price':line.after_disc_prod_price,
                        'po_location':line.po_location.id,
                        'name': line.name,
                        'type': 'boq',
                        # 'tax_id': False,
                        'mrp_bom_id': line.bom_product_id.id
                    })]
                    self.sudo().write({'order_line': product})

        else:
            self.sudo().write({'order_line': [(0, 0, {
                'display_type': 'line_section',
                'name': 'Hardware' + '  [Subtotal: ' + str(self.bom_amount_total) + ']',
                'type': 'boq_child',
            })]})

            for line in self.bom_ids:
                if line.display_type == 'line_section':
                    self.sudo().write({'order_line': [(0, 0, {
                        'display_type': 'line_note',
                        'name': line.name,
                        'type': 'boq'
                    })]})
                else:
                    product = [(0, 0, {
                        'product_id': line.product_id.id,
                        'product_uom_qty': line.product_qty,
                        'product_uom': line.product_uom.id,
                        'price_unit': line.product_sale_price,
                        'after_disc_prod_price': line.after_disc_prod_price,
                        'po_location': line.po_location.id,
                        'name': line.name,
                        'type': 'boq_child',
                        'tax_id': False,
                        'mrp_bom_id': False,
                    })]
                    self.sudo().write({'order_line': product})
            # product_id = self.env['product.product']
            # for line in self.bom_ids:
            #     section_subtotal += line.product_subtotal
            #     last_line = self.bom_ids[-1]
            #     if line.display_type == 'line_section':
            #         # last_line = self.bom_ids[-1]
            #         current_section = line.name
            #         section_count += 1
            #         product_id = self.env['product.product'].search([('name', '=', line.name),('created_from_boq','=',True)],limit=1)
            #         if not product_id:
            #             product_id = self.env['product.product'].create({'name': line.name,
            #                                                              'created_from_boq': True})
            #         # self.sudo().write({'order_line': [(0, 0, {
            #         #     'display_type': 'line_note',
            #         #     'name': line.name,
            #         #     'type': 'boq'
            #         # })]})
            #
            #         # self.sudo().write({'order_line': [(0, 0, {
            #         #     'display_type': 'line_note',
            #         #     'name': line.name,
            #         #     'type': 'boq_child',
            #         #     'hide_rows': False
            #         # })]})
            #
            #     if line == last_line or (self.bom_ids[index + 1].display_type == 'line_section'):
            #         if not unit:
            #             unit = self.env['uom.uom'].search([('id','=','1')])
            #         if product_id:
            #             product = [(0, 0, {
            #                 'product_id': product_id.id,
            #                 'product_uom_qty': 1,
            #                 'product_uom': unit.id,
            #                 'price_unit': section_subtotal,
            #                 'after_disc_prod_price': line.after_disc_prod_price,
            #                 'po_location': line.po_location.id,
            #                 'name': product_id.name,
            #                 'type': 'boq_child',
            #                 'tax_id': False,
            #                 'mrp_bom_id': False,
            #             })]
            #             self.sudo().write({'order_line': product})
            #             section_subtotal = 0
            #
            #
            #     else:
            #         if line.product_uom and not unit:
            #             unit = line.product_uom
            #         # product = [(0, 0, {
            #         #     'product_id': line.product_id.id,
            #         #     'product_uom_qty': line.product_qty,
            #         #     'product_uom': line.product_uom.id,
            #         #     'price_unit': line.product_sale_price,
            #         #     'name': line.name,
            #         #     'type': 'boq_child',
            #         #     # 'tax_id': False,
            #         #     'mrp_bom_id': False,
            #         #     'hide_rows': True
            #         # })]
            #         # self.sudo().write({'order_line': product})
            #
            #     index += 1
        self.get_bom_details()
        self.boq_details_amount_total = self.bom_amount_total

    # @api.onchange('project_id')
    # def get_Default_wh_location(self):
    #     if self.project_id:
    #         for line in

    @api.onchange('order_line')
    def get_boq_total(self):
        if not self.add_child_prod:
            self.sudo().write({'bom_details_id': [(5, 0, 0)]})
            total_amount = 0
            subtotal = 0
            current_note = ''
            current_note_id = self.env['bom.details']
            last_line = self.env['sale.order.line']
            index = 0
            section_total = 0
            current_line_id = 0
            for line in self.order_line:
                if line.type == 'boq':
                    total_amount += line.product_uom_qty * line.price_unit
                    subtotal += line.price_subtotal
                    section_total += line.price_subtotal
                    if line.display_type == 'line_note':
                        self.sudo().write({'bom_details_id': [(0, 0, {
                            'display_type': 'line_section',
                            'name': line.name,
                            'boq_id': line.id
                        })]})
                        current_note = line.name
                        current_line_id = line.id

                    if current_note:
                        for bom_rec in self.bom_details_id:
                            if bom_rec.display_type == 'line_section' and bom_rec.name == current_note and bom_rec.boq_id.id == line.id:
                                current_note_id = bom_rec

                        last_line = self.order_line[-1]

                        if current_note_id:
                            if line == last_line or (
                                    self.order_line[index + 1].display_type == 'line_note' or self.order_line[
                                index + 1].display_type == 'line_section'):
                                current_note_id.write({'product_subtotal': section_total})
                                section_total = 0

                    if line.product_id:
                        # if self.add_child_prod:
                        #     if line.product_id.default_code:
                        #         description = "[" + line.product_id.default_code + "] " + line.product_id.name
                        #     else:
                        #         description = line.product_id.name
                        #     self.sudo().write({'bom_details_id': [(0, 0, {'product_id': line.product_id.id,
                        #                                                   'product_qty': line.product_uom_qty,
                        #                                                   'product_uom': line.product_id.product_tmpl_id.uom_id,
                        #                                                   'product_cost_price': line.price_unit,
                        #                                                   'product_subtotal': line.price_subtotal,
                        #                                                   'name': description,
                        #                                                   })]})

                        # if not self.add_child_prod:
                        self.sudo().write({'bom_details_id': [(0, 0, {
                            'display_type': 'line_note',
                            'name': line.name,
                            # 'boq_id': line.id,
                            'product_subtotal': line.price_subtotal
                        })]})
                        search_bom_id = self.env['mrp.bom'].search([('id', '=', line.mrp_bom_id)])
                        if search_bom_id:
                            for sub_line in search_bom_id.bom_line_ids:
                                if sub_line.product_id.default_code:
                                    description = "[" + sub_line.product_id.default_code + "] " + sub_line.product_id.name
                                else:
                                    description = sub_line.product_id.name
                                self.sudo().write({'bom_details_id': [(0, 0, {'reference': search_bom_id.code,
                                                                              'product_id': sub_line.product_id.id,
                                                                              'product_qty': sub_line.product_qty * line.product_uom_qty,
                                                                              'product_uom': sub_line.product_uom_id.id,
                                                                              'product_cost_price': sub_line.product_sales_price,
                                                                              'product_subtotal': sub_line.product_qty * line.product_uom_qty * sub_line.product_sales_price,
                                                                              'name': description,
                                                                              'function': sub_line.function})]})
                index += 1
            for line in self.order_line:
                if line.display_type == 'line_section' and (line.type == 'boq'):
                    line.name = 'BILL OF QUANTITIES  [Subtotal: ' + "{:.2f}".format(total_amount) + ']'

            self.boq_details_amount_total = subtotal

        else:
            total_amount = 0.0
            subtotal = 0.0
            total = 0.0
            sec_count = 0
            boq_sec_count = 0
            for line in self.order_line:
                index = 0
                if line.type == 'boq_child':
                    subtotal += line.price_subtotal
                    total_amount += line.product_uom_qty * line.price_unit
                    if not line.display_type:
                        sec_count += 1
                        for boq_line in self.bom_details_id:
                            last_line = self.bom_details_id[-1]

                            if line.product_id.name == boq_line.name and boq_line.display_type == 'line_section':
                                boq_line.product_subtotal = line.price_subtotal
                                boq_sec_count += 1
                            if boq_line == last_line or (not boq_line.display_type and sec_count == boq_sec_count):
                                total = (boq_line.product_qty * boq_line.product_cost_price)
                                boq_line.product_subtotal =  total - (total * (line.discount/100))

                            index += 1

            for line in self.order_line:
                if line.display_type == 'line_section' and (line.type == 'boq_child'):
                    line.name = 'Hardware  [Subtotal: ' + "{:.2f}".format(total_amount) + ']'

            self.boq_details_amount_total = subtotal


    # def get_subtotal_of_subproducts(self):
    #     current_subtotal = 0.0
    #     line_count = 0
    #     rec_count = 1
    #     line_section = 0
    #     rec_section = 0
    #     for line in self.order_line:
    #         name = line.name
    #         if line.display_type == 'line_note':
    #             line_section += 1
    #             line_count += 1
    #             for rec in self.bom_ids:
    #                 if line.name == rec.name:
    #                     rec_section += 1
    #
    #                 if line_section == rec_section:
    #                     current_subtotal += rec.product_subtotal
    #
    #                 if rec.display_type == 'line_section' and current_subtotal != 0 and line_count == rec_count:
    #                     line.write({'name': name + "  [Subtotal: " + str(current_subtotal) + "]"})
    #                     current_subtotal = 0.0
    #                     rec_count += 1
    #                     continue

    #
    # def add_bom_to_order_lines(self):
    #     """
    #     This function will add products from BoM tab as product and take unit price from sale price column in BoM tab
    #     :return:
    #     """
    #     sale_order_line_obj = self.env['sale.order.line']
    #
    #     for rec in self.order_line:
    #         if rec.type == 'boq' or (rec.name == 'BILL OF QUANTITIES' and rec.display_type == 'line_section'):
    #             rec.unlink()
    #
    #     self.sudo().write({'order_line': [(0, 0, {
    #         'display_type': 'line_section',
    #         'name': 'BILL OF QUANTITIES',
    #     })]})
    #
    #     for line in self.bom_ids:
    #         # order_line_id = sale_order_line_obj.search([('product_id','=',line.product_id.id),('order_id','=',self.id)])
    #         #
    #         # if order_line_id:
    #         #     product = [(1, order_line_id.id, {
    #         #         'product_id': line.product_id.id,
    #         #         'product_uom_qty': line.product_qty,
    #         #         'product_uom': line.product_uom.id,
    #         #         'price_unit': line.product_sale_price,
    #         #         'name': line.product_id.name,
    #         #         'type': 'boq'
    #         #     })]
    #         # else:
    #         product = [(0,0, {
    #             'product_id': line.product_id.id,
    #             'product_uom_qty': line.product_qty,
    #             'product_uom': line.product_uom.id,
    #             'price_unit': line.product_sale_price,
    #             'name': line.product_id.name,
    #             'type': 'boq'
    #         })]
    #         self.sudo().write({'order_line':product})

    # def add_doc_to_order_lines(self):
    #     """
    #     This function will add a sale order line with Document as product and take unit price from document tab
    #     :return:
    #     """
    #     sale_order_line_obj = self.env['sale.order.line']
    #     product_id = self.env.ref('thailand_erp_customization.document_id')
    #     if product_id:
    #         order_line_id = sale_order_line_obj.search([('order_id','=',self.id),('product_id','=',product_id.id)],limit=1)
    #         if order_line_id:
    #             self.sudo().write({'order_line': [(1, order_line_id.id, {'product_id': product_id.id,
    #                                                                      'product_uom': product_id.uom_id.id,
    #                                                                      'price_unit': self.document_total_amount,
    #                                                                      'name': product_id.name, })]})
    #         else:
    #             self.sudo().write({'order_line':[(0,0,{'product_id': product_id.id,
    #                                                    'product_uom_qty': 1,
    #                                                    'product_uom': product_id.uom_id.id,
    #                                                    'price_unit': self.document_total_amount,
    #                                                    'name': product_id.name,})]})

    def add_doc_to_order_lines(self):
        """
        This function will add a sale order line with Document as product and take unit price from document tab
        :return:
        """
        subtotal = 0
        sale_order_line_obj = self.env['sale.order.line']
        parent_product_id = self.env.ref('thailand_erp_customization.document_id')

        for rec in self.order_line:
            if rec.type == 'doc':
                rec.unlink()

        if parent_product_id:
            for line in self.document_ids:
                subtotal += line.line_total

            self.sudo().write({'order_line': [(0, 0, {
                'display_type': 'line_section',
                'name': 'DOCUMENTS  [Subtotal: ' + str(subtotal) + ']',
                'type': 'doc'
            })]})

            order_line_id = sale_order_line_obj.search(
                [('order_id', '=', self.id), ('product_id', '=', parent_product_id.id)],
                limit=1)

            if not order_line_id:
                self.sudo().write({'order_line': [(0, 0, {'product_id': parent_product_id.id,
                                                          'product_uom_qty': 1,
                                                          'product_uom': parent_product_id.uom_id.id,
                                                          'price_unit': self.document_total_amount,
                                                          'name': parent_product_id.name,
                                                          'type': 'doc',
                                                          'tax_id': False})]})
            # self.is_doc = True
            # self.new_price_total = subtotal

    @api.onchange('order_line')
    def get_doc_total(self):
        subtotal = 0
        for line in self.order_line:
            if line.type == 'doc':
                subtotal += line.product_uom_qty * line.price_unit

        for line in self.order_line:
            if line.display_type == 'line_section' and line.type == 'doc':
                line.name = 'DOCUMENTS  [Subtotal: ' + str(subtotal) + ']'

    @api.depends('order_line.price_total')
    def _amount_all(self):
        """
        Compute the total amounts of the SO.
        """
        tax_perc = 0.0
        disc_perc = 0.0
        for order in self:
            # total_without_disc = 0.0
            total_amount = 0.0
            disc_amount = 0.0
            amount_untaxed = amount_tax = 0.0
            for line in order.order_line:
                if line.tax_id and not tax_perc:
                    for tax in line.tax_id:
                        if not tax_perc:
                            tax_perc = tax.amount
                total_amount += (line.product_uom_qty * line.price_unit)
                amount_untaxed += line.price_subtotal
                amount_tax += line.price_tax

            disc_amount = total_amount - amount_untaxed
            if total_amount and disc_amount:
                disc_perc = (disc_amount / total_amount) * 100
            order.update({
                'total_without_disc': total_amount,
                'amount_untaxed': amount_untaxed,
                'amount_tax': amount_tax,
                'tax_vat_perc': tax_perc,
                'disc_perc': disc_perc,
                'amount_total': amount_untaxed + amount_tax,
                'discount_amt':disc_amount
            })

    # def add_engineering_line_to_order_lines(self):
    #     """
    #     checks for the product in sale order line and creates/updates it from engineering tab.
    #     :return:
    #     """
    #     sale_order_line_obj = self.env['sale.order.line']
    #     product_id = self.env.ref('thailand_erp_customization.engineering_id')
    #     if product_id:
    #         order_line_id = sale_order_line_obj.search([('order_id','=',self.id),('product_id','=',product_id.id)],limit=1)
    #
    #         if order_line_id:
    #             self.sudo().write({'order_line': [(1, order_line_id.id, {'product_id': product_id.id,
    #                                                                      'product_uom': product_id.uom_id.id,
    #                                                                      'price_unit': self.engineer_amount_total,
    #                                                                      'name': product_id.name, })]})
    #         else:
    #             self.sudo().write({'order_line': [(0, 0, {'product_id': product_id.id,
    #                                                       'product_uom_qty': 1,
    #                                                       'product_uom': product_id.uom_id.id,
    #                                                       'price_unit': self.engineer_amount_total,
    #                                                       'name': product_id.name, })]})

    def add_engineering_line_to_order_lines(self):
        """
            #     checks for the product in sale order line and creates/updates it from engineering tab.
            #     :return:
            #     """
        subtotal = 0
        tax_id = []
        sale_order_line_obj = self.env['sale.order.line']
        parent_product_id = self.env.ref('thailand_erp_customization.engineering_id')

        for rec in self.order_line:
            if rec.type == 'eng' or (rec.name == 'ENGINEERING' and rec.display_type == 'line_section'):
                rec.unlink()

        if parent_product_id:
            for line in self.engineer_lines:
                subtotal += line.line_total
                if not tax_id and line.tax_id:
                    for tax in line.tax_id:
                        tax_id.append(tax.id)

            self.sudo().write({'order_line': [(0, 0, {
                'display_type': 'line_section',
                'name': 'ENGINEERING  [Subtotal: ' + str(subtotal) + ']',
                'type': 'eng'
            })]})

            order_line_id = sale_order_line_obj.search(
                [('order_id', '=', self.id), ('product_id', '=', parent_product_id.id)],
                limit=1)

            if not order_line_id:
                self.sudo().write({'order_line': [(0, 0, {'product_id': parent_product_id.id,
                                                          'product_uom_qty': 1,
                                                          'product_uom': parent_product_id.uom_id.id,
                                                          'price_unit': self.engineer_amount_total,
                                                          'name': parent_product_id.name,
                                                          'type': 'eng',
                                                          'tax_id': [( 6, 0, tax_id)]})]})

    @api.onchange('order_line')
    def get_eng_total(self):
        subtotal = 0
        for line in self.order_line:
            if line.type == 'eng':
                subtotal += line.product_uom_qty * line.price_unit

        for line in self.order_line:
            if line.display_type == 'line_section' and line.type == 'eng':
                line.name = 'ENGINEERING  [Subtotal: ' + str(subtotal) + ']'

    # def action_confirm(self):
    #     """
    #     This function overrides the sale order confirm function and based on forecasted quantity for products in sale order lines,
    #      a purchase order is triggered if not sufficient quantity is found.
    #     :return:
    #     """
    #     for order in self:
    #         if order.trading_order:
    #             for line in order.order_line:
    #                 self.prepare_purchase_order(line)
    #         if order.service_order:
    #             for line in order.order_line:
    #                 self.prepare_purchase_order(line)
    #             project_obj = self.env['project.project']
    #             job_cost_sheet = self.env['job.cost']
    #             project_id = project_obj.create({'name': 'Service for '+ self.partner_id.name})
    #
    #             job_cost_id = job_cost_sheet.create({'sale_order_id':self.id,
    #                                                  'partner_id':self.partner_id.id,
    #                                                  'project_id':project_id.id,
    #                                                  'analytic_account_id':project_id.analytic_account_id.id if project_id.analytic_account_id else False})
    #
    #     res = super(SaleOrderInherit, self).action_confirm()
    #     return res
    #
    # def prepare_purchase_order(self, line):
    #     order_line_obj = self.env['purchase.order.line']
    #     purchase_obj = self.env['purchase.order']
    #     if line.product_id.type == 'product' and line.product_id.virtual_available < line.product_uom_qty:
    #         # to check forecasted quantity with sale order quantity
    #         vals = {'product_id': line.product_id.id,
    #                 'name': line.name,
    #                 'product_qty': (line.product_uom_qty - line.product_id.virtual_available),
    #                 'product_uom': line.product_uom.id,
    #                 'price_unit': line.product_id.standard_price,
    #                 'date_planned': datetime.now()}
    #         if line.product_id.virtual_available < 0:
    #             vals.update({'product_qty': line.product_uom_qty})
    #
    #         for vendor in line.product_id.seller_ids:
    #             if vendor.name.id == self.partner_id.id:  # to check if the vendor mentioned in product form
    #
    #                 purchase_id = purchase_obj.search([('partner_id', '=', self.partner_id.id),
    #                                                    ('state', 'not in', ['purchase', 'done', 'cancel'])], limit=1)
    #                 if not purchase_id:
    #                     purchase_id = purchase_obj.create({'partner_id': self.partner_id.id})
    #                     vals.update({'order_id': purchase_id.id})
    #                     order_line_obj.create(vals)
    #
    #                 self.avail_purchase_order_id = purchase_id.id

    # Commented******************
    # def _prepare_invoice(self):
    #     invoice_vals = super(SaleOrderInherit, self)._prepare_invoice()
    #     invoice_vals.update({'trading_order':self.trading_order,
    #                          'service_order':self.service_order,
    #                          'po_number_customer': self.purchase_order_no})
    #
    #     return invoice_vals

    def _create_invoices(self, grouped=False, final=False):
        """
        Create the invoice associated to the SO.
        :param grouped: if True, invoices are grouped by SO id. If False, invoices are grouped by
                        (partner_invoice_id, currency)
        :param final: if True, refunds will be generated if necessary
        :returns: list of created invoices
        """
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')

        # 1) Create invoices.
        invoice_vals_list = []
        for order in self:
            pending_section = None
            pending_note_section = None

            # Invoice values.
            invoice_vals = order._prepare_invoice()

            # Invoice line values (keep only necessary sections).
            for line in order.order_line:
                if line.display_type == 'line_section':
                    pending_section = line
                    continue
                if line.display_type == 'line_note':
                    pending_note_section = line
                    continue
                if float_is_zero(line.qty_to_invoice, precision_digits=precision):
                    continue
                if line.qty_to_invoice > 0 or (line.qty_to_invoice < 0 and final):
                    if pending_section:
                        invoice_vals['invoice_line_ids'].append((0, 0, pending_section._prepare_invoice_line()))
                        pending_section = None
                    if pending_note_section:
                        invoice_vals['invoice_line_ids'].append((0, 0, pending_note_section._prepare_invoice_line()))
                        pending_note_section = None
                    invoice_vals['invoice_line_ids'].append((0, 0, line._prepare_invoice_line()))

            if not invoice_vals['invoice_line_ids']:
                raise UserError(_(
                    'There is no invoiceable line. If a product has a Delivered quantities invoicing policy, please make sure that a quantity has been delivered.'))

            invoice_vals_list.append(invoice_vals)

        if not invoice_vals_list:
            raise UserError(_(
                'There is no invoiceable line. If a product has a Delivered quantities invoicing policy, please make sure that a quantity has been delivered.'))

        # 2) Manage 'grouped' parameter: group by (partner_id, currency_id).
        if not grouped:
            new_invoice_vals_list = []
            for grouping_keys, invoices in groupby(invoice_vals_list,
                                                   key=lambda x: (x.get('partner_id'), x.get('currency_id'))):
                origins = set()
                payment_refs = set()
                refs = set()
                ref_invoice_vals = None
                for invoice_vals in invoices:
                    if not ref_invoice_vals:
                        ref_invoice_vals = invoice_vals
                    else:
                        ref_invoice_vals['invoice_line_ids'] += invoice_vals['invoice_line_ids']
                    origins.add(invoice_vals['invoice_origin'])
                    payment_refs.add(invoice_vals['payment_reference'])
                    refs.add(invoice_vals['ref'])
                ref_invoice_vals.update({
                    'ref': ', '.join(refs),
                    'invoice_origin': ', '.join(origins),
                    'payment_reference': len(payment_refs) == 1 and payment_refs.pop() or False,
                })
                new_invoice_vals_list.append(ref_invoice_vals)
            invoice_vals_list = new_invoice_vals_list

        # 3) Manage 'final' parameter: transform out_invoice to out_refund if negative.
        out_invoice_vals_list = []
        refund_invoice_vals_list = []
        if final:
            for invoice_vals in invoice_vals_list:
                if sum(l[2]['quantity'] * l[2]['price_unit'] for l in invoice_vals['invoice_line_ids']) < 0:
                    for l in invoice_vals['invoice_line_ids']:
                        l[2]['quantity'] = -l[2]['quantity']
                    invoice_vals['type'] = 'out_refund'
                    refund_invoice_vals_list.append(invoice_vals)
                else:
                    out_invoice_vals_list.append(invoice_vals)
        else:
            out_invoice_vals_list = invoice_vals_list

        # Create invoices.
        moves = self.env['account.move'].with_context(default_type='out_invoice').create(out_invoice_vals_list)
        moves += self.env['account.move'].with_context(default_type='out_refund').create(refund_invoice_vals_list)
        for move in moves:
            move.message_post_with_view('mail.message_origin_link',
                                        values={'self': move, 'origin': move.line_ids.mapped('sale_line_ids.order_id')},
                                        subtype_id=self.env.ref('mail.mt_note').id
                                        )
        return moves

    def _prepare_invoice(self):
        invoice_vals = super(SaleOrderInherit, self)._prepare_invoice()
        invoice_vals.update({'so_type': self.so_type,
                             'po_number_customer': self.purchase_order_no,
                             })

        if self.so_type == 'service':
            invoice_vals.update({'project_ids': [(4, self.project_id.id)]})

        return invoice_vals
    #
    # def _prepare_purchase_order_data(self, company, company_partner):
    #     """ Generate purchase order values, from the SO (self)
    #         :param company_partner : the partner representing the company of the SO
    #         :rtype company_partner : res.partner record
    #         :param company : the company in which the PO line will be created
    #         :rtype company : res.company record
    #     """
    #     self.ensure_one()
    #     # find location and warehouse, pick warehouse from company object
    #     PurchaseOrder = self.env['purchase.order']
    #     warehouse = company.warehouse_id and company.warehouse_id.company_id.id == company.id and company.warehouse_id or False
    #     if not warehouse:
    #         raise Warning(
    #             _('Configure correct warehouse for company(%s) from Menu: Settings/Users/Companies' % (company.name)))
    #     picking_type_id = self.env['stock.picking.type'].search([
    #         ('code', '=', 'incoming'), ('warehouse_id', '=', warehouse.id)
    #     ], limit=1)
    #     if not picking_type_id:
    #         intercompany_uid = company.intercompany_user_id.id
    #         picking_type_id = PurchaseOrder.with_user(intercompany_uid)._default_picking_type()
    #     purchase_vals = {
    #         'name': self.env['ir.sequence'].sudo().next_by_code('purchase.order'),
    #         'origin': self.name,
    #         'partner_id': company_partner.id,
    #         'picking_type_id': picking_type_id.id,
    #         'date_order': self.date_order,
    #         'company_id': company.id,
    #         'fiscal_position_id': company_partner.property_account_position_id.id,
    #         'payment_term_id': company_partner.property_supplier_payment_term_id.id,
    #         'auto_generated': True,
    #         'auto_sale_order_id': self.id,
    #         'partner_ref': self.name,
    #         'currency_id': self.currency_id.id
    #     }
    #     if self.project_id and self.so_type == 'service':
    #         purchase_vals.update({'project_id': self.project_id})
    #         return purchase_vals
    #
    #     return purchase_vals

    def open_location_wiz(self):
        ctx = dict(self.env.context, default_sale_order_id=self.id)

        view_id = self.env.ref('thailand_erp_customization.confirm_sale_order_loc')
        return {
            'name': _('Location'),
            'res_model': 'sale.order.loc.wiz',
            'target': 'new',
            'type': 'ir.actions.act_window',
            'view_id': view_id.id,
            'view_mode': 'form',
            'context':ctx
        }


    def action_confirm(self):
        if self.so_type == 'service':
            project_obj = self.env['project.project']
            job_cost_sheet = self.env['job.cost']

            search_project_id = project_obj.search([('name', '=', self.name)])
            if not search_project_id and not self.project_id:
                project_id = project_obj.create({'name': self.name})
                self.write({'project_id': project_id.id})

            # project_id = project_obj.create({'name': 'Service for ' + self.partner_id.name})

                job_cost_id = job_cost_sheet.create({'sale_order_id': self.id,
                                                     'partner_id': self.partner_id.id,
                                                     'project_id': self.project_id.id,
                                                     'analytic_account_id': self.project_id.analytic_account_id.id if self.project_id.analytic_account_id else False})
            else:
                if self.project_id:
                    job_id=job_cost_sheet.search([('project_id','=',self.project_id.id)])
                    if job_id:
                        self.env['job.cost.sale.order'].create({'project_id':self.project_id.id,
                                     'sale_order_id':self.id,
                                     'date':self.date_order,
                                     'total_sale_price':float(self.amount_total),
                                    'job_id':job_id.id
                                     })
        self.show_job_cost = True
        res = super(SaleOrderInherit, self).action_confirm()

        if self.so_type == 'service':
            # updating project in DO
            for do_pick in self.picking_ids:
                do_pick.write({'project_ids': [(4, self.project_id.id)]})


            purchase_order_list = []
            search_mrp_ids = self.env['mrp.production'].search([('origin','=',self.name)])
            po_ids = self.env['purchase.order'].search([])
            if search_mrp_ids:
                for mrp_rec in search_mrp_ids:
                    for po in po_ids:
                        if str(po.origin).find(mrp_rec.name) != -1:
                            purchase_order_list.append(po)

            for po in po_ids:
                if str(po.origin).find(self.name) != -1:
                    purchase_order_list.append(po)

            if purchase_order_list and self.project_id:
                for line in purchase_order_list:
                     # line.write({'project_id':self.project_id.id})
                    line.write({'project_ids': [(4, self.project_id.id)]})

        return res

    def show_job_cost_sheet(self):
        return {
            'name': _('Job Cost Sheet'),
            'type': 'ir.actions.act_window',
            'res_model': 'job.cost',
            'view_mode': 'tree,form',
            'target': 'current',
            'domain': [('project_id', '=', self.project_id.id)]
        }

    def show_purchase_order(self):
        purchase_order_list = []
        search_mrp_id = self.env['mrp.production'].search([('origin', '=', self.name)])
        purchase_order_ids = self.env['purchase.order'].search([])
        if search_mrp_id:
            for mrp_rec in search_mrp_id:
                for po in purchase_order_ids:
                    if str(po.origin).find(mrp_rec.name) != -1 :
                        purchase_order_list.append(po.id)

        for po in purchase_order_ids:
            if str(po.origin).find(self.name) != -1:
                purchase_order_list.append(po.id)

        return {
            'name': _('Purchase Order'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'tree,form',
            'target': 'current',
            'domain': [('id', 'in', purchase_order_list)]
        }
        # purchase_order_ids = self.env['purchase.order'].search([])
        # for po in purchase_order_ids:
        #     if self.name in str(po.origin):
        #         self.avail_purchase_order_id = po
        #
        # return {
        #
        #     'name': _('Purchase Order'),
        #     'type': 'ir.actions.act_window',
        #     'res_model': 'purchase.order',
        #     'view_mode': 'tree,form',
        #     'target': 'current',
        #     'domain': [('id', 'in', self.avail_purchase_order_id.ids)]
        # }

    so_excel_file = fields.Binary('Sale Quotation Excel Report')
    so_file_name = fields.Char('Excel File')

    boq_excel_file = fields.Binary('BOQ Excel Report')
    boq_file_name = fields.Char('BOQ Excel File')

    boq_child_excel_file = fields.Binary('BOQ Child Excel Report')
    boq_child_file_name = fields.Char('BOQ Child Excel File')

    def create_sale_excel_report(self):
        self.get_so_report()
        self.get_boq_report()
        self.get_boq_child_report()

        my_file = self.env['so.excel.report'].create({
            'so_excel_file': self.so_excel_file,
            'so_file_name': self.so_file_name,
            'boq_excel_file': self.boq_excel_file,
            'boq_file_name': self.boq_file_name,
            'boq_child_excel_file': self.boq_child_excel_file,
            'boq_child_file_name': self.boq_child_file_name
        })
        view_id = self.env.ref('thailand_erp_customization.get_so_report_wizard_view')
        return {
            'res_id': my_file.id,
            'res_model': 'so.excel.report',
            'target': 'new',
            'type': 'ir.actions.act_window',
            'view_id': view_id.id,
            'view_mode': 'form',
        }

    def get_so_report(self):

        filename = str(self.name) + '.xls'
        workbook = xlwt.Workbook()
        worksheet = workbook.add_sheet('Price Quote')

        if self.company_id.logo:
            fh = open("/tmp/imageToSave.png", "wb")
            fh.write(base64.b64decode(self.company_id.logo))
            fh.close()
            os.chmod("/tmp/imageToSave.png", 0o777)
            # open the image with PIL

            im = Image.open('/tmp/imageToSave.png').convert("RGB")

            file_out = "/tmp/imageTosave.bmp"
            im.save(file_out)
            im_resize = Image.open('/tmp/imageTosave.bmp')
            resize_width, resize_height = im_resize.size
            new_im_reszie = im_resize.resize((60, 55), Image.ANTIALIAS)
            new_im_reszie.save('/tmp/imageTosave.bmp')

            worksheet.insert_bitmap('/tmp/imageTosave.bmp', 2, 4, )

        worksheet.row(0).height = 600
        worksheet.col(0).width = 1880
        worksheet.col(1).width = 4220
        worksheet.col(2).width = 1880
        worksheet.col(3).width = 4220
        worksheet.col(4).width = 5620
        worksheet.col(6).width = 3420
        worksheet.col(7).width = 4620
        worksheet.col(8).width = 4620
        # worksheet.col(9).width = 5420

        first_row = 0

        worksheet.write_merge(first_row, 0, 0, 8, "Quotation", xlwt.easyxf('font: name Arial, bold on,'
                                                                           'color White,height 480; align: vert center;'
                                                                           'pattern: pattern solid, fore_colour Indigo;'))

        if self.company_id:
            comp = self.company_id
            worksheet.write(first_row + 3, 0, str(comp.name), xlwt.easyxf('font: name Arial, bold on,'
                                                                          'height 200; align: vert center; '))
            first_row += 4

            if comp.street:
                worksheet.write(first_row, 0, str(comp.street), xlwt.easyxf('font: name Arial,'
                                                                            'height 200; align: vert center; '))
                first_row += 1

            if comp.street2:
                worksheet.write(first_row, 0, str(comp.street2), xlwt.easyxf('font: name Arial,'
                                                                             'height 200; align: vert center; '))
                first_row += 1

            addr = ''
            if comp.city:
                addr += str(comp.city) + ', '
            if comp.state_id:
                addr += str(comp.state_id.name) + ', '
            if comp.country_id:
                addr += str(comp.country_id.name) + ', '
            if comp.zip:
                addr += str(comp.zip)

            if addr != '':
                worksheet.write(first_row, 0, addr, xlwt.easyxf('font: name Arial,'
                                                                'height 200; align: vert center; '))
                first_row += 1

            if comp.phone:
                worksheet.write(first_row, 0, 'Tel.', xlwt.easyxf('font: name Arial,'
                                                                  'height 180; align: vert center; '))
                worksheet.write(first_row, 1, str(comp.phone), xlwt.easyxf('font: name Arial,'
                                                                           'height 180; align: vert center; '))
                first_row += 1

            xlwt.add_palette_colour("back", 0x16)
            workbook.set_colour_RGB(0x16, 220, 220, 220)

            xlwt.add_palette_colour("fcolour", 0x0C)
            workbook.set_colour_RGB(0x0C, 51, 104, 135)
            if self.user_id.login:
                worksheet.write(first_row, 0, 'Email', xlwt.easyxf('font: name Arial,height 160; align: vert center; '))
                worksheet.write_merge(first_row, first_row, 1, 2, str(self.user_id.login),
                                      xlwt.easyxf('font: name Arial,color fcolour,'
                                                  'underline on,height 160; align: vert center; '
                                                  'pattern: pattern solid, fore_colour back;'))

        first_row = 4

        worksheet.write(first_row, 7, "Date:", xlwt.easyxf('font: name Arial,'
                                                          'height 160; align:horiz right, vert center; '))
        if self.date:
            worksheet.write(first_row, 8, str(self.date.strftime('%d/%m/%Y')),
                            xlwt.easyxf('font: name Arial,height 160; align: vert center; '))
        else:
            worksheet.write(first_row, 8, '')
        first_row += 1

        worksheet.write(first_row, 7, "Validity Date:", xlwt.easyxf('font: name Arial,'
                                                                    'height 160;align: horiz right, vert center; '))
        if self.validity_date:
            worksheet.write(first_row, 8, str(self.validity_date.strftime('%d/%m/%Y')),
                            xlwt.easyxf('font: name Arial,height 160; align: vert center; '))
        else:
            worksheet.write(first_row, 8, '')
        first_row += 1

        worksheet.write(first_row, 7, "Quote No:", xlwt.easyxf('font: name Arial,'
                                                               'height 160; align:horiz right, vert center; '))

        worksheet.write(first_row, 8, str(self.name), xlwt.easyxf('font: name Arial,'
                                                                  'height 160; align: vert center; '))
        first_row += 1
        worksheet.write(first_row, 7, "Quotation Revision No.:", xlwt.easyxf('font: name Arial,'
                                                                            'height 160; align:horiz right, vert center; '))

        if self.revision_no:
            worksheet.write(first_row, 8, str(self.revision_no), xlwt.easyxf('font: name Arial,'
                                                                      'height 160; align: vert center; '))

        else:
            worksheet.write(first_row, 8, '', xlwt.easyxf('font: name Arial,'
                                                          'height 160; align: vert center; '))

        first_row = 10
        worksheet.write_merge(first_row, 10, 0, 3, "Customer",
                              xlwt.easyxf('font: name Arial, bold on,'
                                          'color White,height 200; align: vert center;'
                                          'pattern: pattern solid, fore_colour Indigo;'))
        first_row += 1

        if self.partner_id:
            cust = self.partner_id
            if cust.name:
                worksheet.write(first_row, 0, str(cust.name), xlwt.easyxf('font: name Arial,bold on,'
                                                                          'height 200; align: vert center; '))
                first_row += 1

            if cust.parent_id:
                worksheet.write(first_row, 0, str(cust.parent_id.name),
                                xlwt.easyxf('font: name Tahoma,bold on, height 180; align: vert center; '))
                first_row += 1

            if cust.street:
                worksheet.write(first_row, 0, str(cust.street), xlwt.easyxf('font: name Arial,'
                                                                            'height 160; align: vert center; '))
                first_row += 1

            if cust.street2:
                worksheet.write(first_row, 0, str(cust.street2), xlwt.easyxf('font: name Arial,'
                                                                             'height 160; align: vert center; '))
                first_row += 1

            cust_addr = ''
            if cust.city:
                cust_addr += str(cust.city) + ", "

            if cust.state_id:
                cust_addr += str(cust.state_id.name) + ", "

            if cust.country_id:
                cust_addr += str(cust.country_id.name) + ', '

            if cust.zip:
                cust_addr += str(cust.zip)

            if cust_addr != '':
                worksheet.write(first_row, 0, cust_addr, xlwt.easyxf('font: name Arial,'
                                                                     'height 160; align: vert center; '))
                first_row += 1

            xlwt.add_palette_colour("back", 0x16)
            workbook.set_colour_RGB(0x16, 220, 220, 220)

            xlwt.add_palette_colour("fcolour", 0x0C)
            workbook.set_colour_RGB(0x0C, 51, 104, 135)
            if cust.phone:
                worksheet.write(first_row, 0, 'Tel: ', xlwt.easyxf('font: name Arial, '
                                                                   'color fcolour,'
                                                                   'height 160; align: vert center; '))
                worksheet.write(first_row, 1, cust.phone, xlwt.easyxf('font: name Arial, '
                                                                      'color fcolour,'
                                                                      'height 160; align: vert center; '))
            if cust.mobile:
                worksheet.write(first_row, 2, 'Mobile: ', xlwt.easyxf('font: name Arial, '
                                                                      'color fcolour,'
                                                                      'height 160; align: vert center; '))
                worksheet.write(first_row, 3, cust.mobile, xlwt.easyxf('font: name Arial, '
                                                                       'color fcolour,'
                                                                       'height 160; align: vert center; '))
            if cust.email:
                first_row += 1
                worksheet.write(first_row, 0, 'Email: ', xlwt.easyxf('font: name Arial, '
                                                                     'color fcolour,'
                                                                     'height 160; align: vert center; '))
                worksheet.write_merge(first_row, first_row,1,2, cust.email, xlwt.easyxf('font: name Arial,color fcolour,'
                                                                           'underline on,height 200; align: vert center; '
                                                                           'pattern: pattern solid, fore_colour back;'))

        worksheet.write(19, 0, "Item",
                        xlwt.easyxf('font: name Arial, bold on,'
                                    'color White,height 180; align: vert center;'
                                    'pattern: pattern solid, fore_colour Indigo;'))

        worksheet.write_merge(19, 19, 1, 3, "Description",
                              xlwt.easyxf('font: name Arial, bold on,'
                                          'color White,height 180; align: vert center;'
                                          'pattern: pattern solid, fore_colour Indigo;'))

        worksheet.write(19, 4, "Part No.", xlwt.easyxf('font: name Arial, bold on,'
                                                   'color White,height 180; align: horiz left, vert center;'
                                                   'pattern: pattern solid, fore_colour Indigo;'))

        worksheet.write(19, 5, "Qty.", xlwt.easyxf('font: name Arial, bold on,'
                                                   'color White,height 180; align: horiz center, vert center;'
                                                   'pattern: pattern solid, fore_colour Indigo;'))

        worksheet.write(19, 6, "Unit", xlwt.easyxf('font: name Arial, bold on,'
                                                   'color White,height 180; align: horiz center,vert center;'
                                                   'pattern: pattern solid, fore_colour Indigo;'))

        # worksheet.write(19, 7, "Discount", xlwt.easyxf('font: name Liberation Sans, bold on,'
        #                                                'color White,height 210; align: horiz right,vert center;'
        #                                                'pattern: pattern solid, fore_colour Indigo;'))

        worksheet.write(19, 7, "Unit Price", xlwt.easyxf('font: name Arial, bold on,'
                                                         'color White,height 180; align: horiz right,vert center;'
                                                         'pattern: pattern solid, fore_colour Indigo;'))

        worksheet.write(19, 8, "Line Total", xlwt.easyxf('font: name Arial, bold on,'
                                                         'color White,height 180; align: horiz right,vert center;'
                                                         'pattern: pattern solid, fore_colour Indigo;'))
        count = 1
        line_count = 1
        index = 0
        first_row = 20
        first_col = 1
        current_subtotal = 0.0
        original_total = 0.0
        diff = 0.0
        # amount = 0.0
        prod_disc_amt = 0.0
        current_note = self.env['sale.order.line']
        section_total = 0.0
        list = []
        if self.order_line:
            for line in self.order_line:
                if self.user_has_groups('product.group_discount_per_so_line'):
                    prod_disc_amt = (line.product_uom_qty * line.price_unit * line.discount) / 100
                original_total = original_total + (line.price_unit * line.product_uom_qty)
                # current_subtotal = current_subtotal + line.price_subtotal
                current_subtotal = current_subtotal + (line.price_unit * line.product_uom_qty)
                section = line.name

                last_line = self.order_line[-1]

                if line.display_type == 'line_section':
                    if line.type != 'product':
                        list = section.split(': ')
                        if len(list) > 1:
                            amount = list[1]
                        list = amount.split(']')
                        if list[0] and line.type == 'boq_child' and (line == last_line or self.order_line[index + 1].type != 'boq_child'):
                            list[0] = str(0.0)
                            # section_total += float(list[0])
                        # line_last = self.order_line[-1]
                        # if not self.order_line[index+1].display_type or not line_last.display_type:
                        #     if line.type == 'eng' and (self.order_line[index+1].type == 'eng' or line_last.type == 'eng'):
                        #         amount = self.order_line[index+1].product_uom_qty * self.order_line[index+1].product_uom_qty
                    if count > 1:
                        worksheet.write(first_row, 0, '', xlwt.easyxf('border: left thin, top thin, bottom thin'))
                        worksheet.write(first_row, 8, '', xlwt.easyxf('font: name Arial,'
                                                                      'height 180; align: vert center;'
                                                                      'border: right thin'))
                        first_row += 1

                    if line.type != 'product':
                        worksheet.write(first_row, 0, str(count), xlwt.easyxf('font: name Arial, bold on,'
                                                                              'height 180; align:vert top;'
                                                                              'border: top thin, left thin, right thin, bottom thin'))
                    else:
                        worksheet.write(first_row, 0, '', xlwt.easyxf('border: top thin, left thin, right thin, bottom thin'))



                    if line.type == 'boq':
                        section = 'Hardware (Refer BOQ)'
                        unit = 'SET'

                    elif line.type == 'doc':
                        section = 'Document'
                        unit = 'JOB'

                    elif line.type == 'eng':
                        section = 'Engineering'
                        unit = 'JOB'

                    elif line.type == 'boq_child':
                        section = 'Hardware (REF BOQ)'
                        unit = 'lot'

                    else:
                        unit = ''

                    worksheet.write_merge(first_row, first_row, 1, 3, section,
                                          xlwt.easyxf('font: name Arial, bold on,'
                                                      'height 180; align: vert top;'
                                                      'border: top thin, left thin, right thin, bottom thin'))

                    worksheet.write(first_row, first_col + 3, '',
                                    xlwt.easyxf('font: name Arial,bold on,'
                                                'height 180; align: horiz right, vert top;'
                                                'border: top thin, left thin, right thin, bottom thin'))

                    if line.type != 'product':
                        worksheet.write(first_row, first_col + 4, '1',
                                        xlwt.easyxf('font: name Arial,bold on,'
                                                    'height 180; align: horiz center,vert top;'
                                                    'border: top thin, left thin, right thin, bottom thin'))
                    else:
                        worksheet.write(first_row, first_col + 4, '',
                                        xlwt.easyxf('border: top thin, left thin, right thin, bottom thin'))

                    worksheet.write(first_row, first_col + 5, str(unit),
                                    xlwt.easyxf('font: name Arial,bold on,'
                                                'height 180; align: horiz center,vert top;'
                                                'border: top thin, left thin, right thin, bottom thin'))

                    # worksheet.write(first_row, first_col + 6, '',
                    #                 xlwt.easyxf('font: name Liberation Sans,bold on,'
                    #                             'height 210; align: horiz right, vert center;'
                    #                             'border: top thin, left thin, right thin, bottom thin'))

                    if line.type != 'product' and list[0]:
                        worksheet.write(first_row, first_col + 6, str("{0:,.2f}".format(float(list[0]))),
                                        xlwt.easyxf('font: name Arial,bold on,'
                                                    'height 180; align: horiz right, vert top;'
                                                    'border: top thin, left thin, right thin, bottom thin'))

                        worksheet.write(first_row, first_col + 7, str("{0:,.2f}".format(float(list[0]))),
                                        xlwt.easyxf('font: name Arial,bold on,'
                                                    'height 180; align: horiz right, vert top;'
                                                    'border: top thin, left thin, right thin, bottom thin'))
                        list = []
                        amount = ''
                        count += 1

                    else:
                        worksheet.write(first_row, first_col + 6, '',
                                        xlwt.easyxf('border: top thin, left thin, right thin, bottom thin'))

                        worksheet.write(first_row, first_col + 7, '',
                                        xlwt.easyxf('border: top thin, left thin, right thin, bottom thin'))

                    first_row += 1

                elif not line.display_type and line.type == 'product':
                    # neededWidth = int((1 + len(str(line.name))) * 256)
                    # if worksheet.col(first_col).width < neededWidth:
                    #     worksheet.row(first_row).height = worksheet.row(first_row).height + 400
                    neededWidth = int((1 + len(str(line.product_id.name)))) * 255
                    if worksheet.col(1).width < neededWidth and (worksheet.col(1).width/int((1 + len(str(line.product_id.name)))))<100:
                        # worksheet.row(first_row).height = (neededWidth /380 )*255
                        worksheet.row(first_row).height = int(((neededWidth - worksheet.col(1).width) / 400) * 10)

                    worksheet.write(first_row, 0, str(count), xlwt.easyxf('font: name Arial,'
                                                                  'height 180; align:vert top;'
                                                                  'border: left thin, bottom thin, top thin, right thin;'
                                                                  'alignment: wrap on'))
                    # worksheet.write(first_row, 0, '', xlwt.easyxf('font: name Arial,'
                    #                                                       'height 180; align: horiz center,vert center;'
                    #                                                       'border: left thin, bottom thin, top thin, right thin;'
                    #                                                                                 'alignment: wrap on'))

                    worksheet.write_merge(first_row, first_row, 1, 3, line.product_id.name,
                                          xlwt.easyxf('font: name Arial,'
                                                      'height 180; align: vert top;'
                                                      'border: top thin, left thin, right thin, bottom thin;'
                                                                                                    'alignment: wrap on'))

                    if line.product_id.default_code:
                        worksheet.write(first_row, first_col + 3, line.product_id.default_code,
                                        xlwt.easyxf('font: name Arial,'
                                                    'height 180; align: horiz left, vert top;'
                                                    'border: top thin, left thin, right thin, bottom thin;'
                                                                                                    'alignment: wrap on'))

                    else:
                        worksheet.write(first_row, first_col + 3, '',
                                        xlwt.easyxf('font: name Arial,'
                                                    'height 180; align: horiz left, vert top;'
                                                    'border: top thin, left thin, right thin, bottom thin;'
                                                                                                    'alignment: wrap on'))

                    worksheet.write(first_row, first_col + 4, line.product_uom_qty,
                                    xlwt.easyxf('font: name Arial,'
                                                'height 180; align: horiz center, vert top;'
                                                'border: top thin, left thin, right thin, bottom thin;'
                                                                                                    'alignment: wrap on'))

                    worksheet.write(first_row, first_col + 5, line.product_uom.name,
                                    xlwt.easyxf('font: name Arial,'
                                                'height 180; align: horiz center, vert top;'
                                                'border: top thin, left thin, right thin, bottom thin;'
                                                                                                    'alignment: wrap on'))

                    # worksheet.write(first_row, first_col + 6, prod_disc_amt,
                    #                 xlwt.easyxf('font: name Liberation Sans,'
                    #                             'height 210; align: horiz right, vert center;'
                    #                             'border: top thin, left thin, right thin, bottom thin'))

                    worksheet.write(first_row, first_col + 6, str("{0:,.2f}".format(line.price_unit)),
                                    xlwt.easyxf('font: name Arial,'
                                                'height 180; align: horiz right, vert top;'
                                                'border: top thin, left thin, right thin, bottom thin;'
                                                                                                    'alignment: wrap on'))

                    worksheet.write(first_row, first_col + 7, str("{0:,.2f}".format(line.product_uom_qty * line.price_unit)),
                                    xlwt.easyxf('font: name Arial,'
                                                'height 180; align: horiz right, vert top;'
                                                'border: top thin, left thin, right thin, bottom thin;'
                                                'alignment: wrap on'))

                    # worksheet.write(first_row, first_col + 7, str("{0:,.2f}".format(line.price_subtotal)),
                    #                 xlwt.easyxf('font: name Arial,'
                    #                             'height 180; align: horiz right, vert center;'
                    #                             'border: top thin, left thin, right thin, bottom thin;'
                    #                                                                                 'alignment: wrap on'))

                    count += 1
                    first_row += 1


                else:
                    if line.type != 'boq' and line.display_type == 'line_note':
                        # neededWidth = int((1 + len(str(line.name))) * 256)
                        # if worksheet.col(first_col).width < neededWidth:
                        #     worksheet.row(first_row).height = worksheet.row(first_row).height + 400

                        worksheet.write(first_row, 0, '', xlwt.easyxf('border: top thin, left thin, right thin, bottom thin'))

                        worksheet.write_merge(first_row, first_row, first_col, 3, line.name,
                                              xlwt.easyxf('font: name Arial,'
                                                          'height 180; align: vert top;'
                                                          'border: top thin, left thin, right thin, bottom thin'))

                        worksheet.write(first_row, first_col + 3, '',
                                        xlwt.easyxf('font: name Arial,'
                                                    'height 180; align: vert top;'
                                                    'border: top thin, left thin, right thin, bottom thin'))

                        worksheet.write(first_row, first_col + 4, '',
                                        xlwt.easyxf('font: name Arial,'
                                                    'height 180; align: horiz center,vert top;'
                                                    'border: top thin, left thin, right thin, bottom thin'))

                        worksheet.write(first_row, first_col + 5, '', xlwt.easyxf('font: name Arial,'
                                                                                  'height 180; align: horiz right,vert top;'
                                                                                  'border: top thin, left thin, right thin, bottom thin'))

                        # worksheet.write(first_row, first_col + 6, '', xlwt.easyxf('font: name Liberation Sans,'
                        #                                                           'height 210; align: horiz right,vert center;'
                        #                                                           'border: top thin, left thin, right thin, bottom thin'))

                        worksheet.write(first_row, first_col + 6, '',
                                        xlwt.easyxf('font: name Arial,'
                                                    'height 180; align: horiz right, vert top;'
                                                    'border: top thin, left thin, right thin, bottom thin'))

                        worksheet.write(first_row, first_col + 7, '',
                                        xlwt.easyxf('font: name Arial,'
                                                    'height 180; align: vert top;'
                                                    'border: top thin, left thin, right thin, bottom thin'))
                        first_row += 1

                    if line.display_type == 'line_note' and line.type == 'boq':
                        current_note = line
                        current_subtotal = 0
                        original_total = 0
                        diff = 0

                    if current_note and line.type == 'boq':
                        # last_line = self.order_line[-1]
                        if line == last_line or self.order_line[index + 1].display_type == 'line_note' or \
                                (line.type == 'boq' and self.order_line[index + 1].type != 'boq'):

                            diff = original_total - current_subtotal

                            worksheet.write(first_row, 0, '', xlwt.easyxf('border: top thin, left thin, right thin, bottom thin'))

                            worksheet.write_merge(first_row, first_row, first_col, 3, current_note.name,
                                                  xlwt.easyxf('font: name Arial,'
                                                              'height 180; align: vert top;'
                                                              'border: top thin, left thin, right thin, bottom thin'))

                            worksheet.write(first_row, first_col + 3, '',
                                            xlwt.easyxf('font: name Arial,'
                                                        'height 180; align: vert top;'
                                                        'border: top thin, left thin, right thin, bottom thin'))

                            worksheet.write(first_row, first_col + 4, '',
                                            xlwt.easyxf('font: name Arial,'
                                                        'height 180; align: vert top;'
                                                        'border: top thin, left thin, right thin, bottom thin'))

                            worksheet.write(first_row, first_col + 5, '',
                                            xlwt.easyxf('font: name Arial,'
                                                        'height 180; align: horiz right,vert top;'
                                                        'border: top thin, left thin, right thin, bottom thin'))

                            # if diff:
                            #     worksheet.write(first_row, first_col + 6, str(float(diff)),
                            #                     xlwt.easyxf('font: name Liberation Sans,'
                            #                                 'height 210; align: horiz right,vert center;'
                            #                                 'border: top thin, left thin, right thin, bottom thin'))
                            #
                            # else:
                            #     worksheet.write(first_row, first_col + 6, '',
                            #                     xlwt.easyxf('font: name Liberation Sans,'
                            #                                 'height 210; align: horiz right,vert center;'
                            #                                 'border: top thin, left thin, right thin, bottom thin'))

                            worksheet.write(first_row, first_col + 6, str("{0:,.2f}".format(current_subtotal)),
                                            xlwt.easyxf('font: name Arial,'
                                                        'height 180; align: horiz right, vert top;'
                                                        'border: top thin, left thin, right thin, bottom thin'))

                            worksheet.write(first_row, first_col + 7, '',
                                            xlwt.easyxf('font: name Arial,'
                                                        'height 180; align: vert top;'
                                                        'border: top thin, left thin, right thin, bottom thin'))
                            current_subtotal = 0
                            original_total = 0
                            diff = 0
                            first_row += 1

                    # if line.type == 'boq_child' and self.add_child_prod:
                    #     if line_count == 1:
                    #         worksheet.write(first_row, 0, str(count), xlwt.easyxf('border: left thin'))
                    #
                    #         worksheet.write_merge(first_row, first_row, first_col, 3, 'Hardware (REF BOQ)',
                    #                               xlwt.easyxf('font: name Liberation Sans,bold on,'
                    #                                           'height 210; align: vert center;'
                    #                                           'border: top thin, left thin, right thin, bottom thin'))
                    #
                    #         worksheet.write(first_row, first_col + 3, '1',
                    #                         xlwt.easyxf('font: name Liberation Sans,bold on,'
                    #                                     'height 210; align: horiz right, vert center;'
                    #                                     'border: top thin, left thin, right thin, bottom thin'))
                    #
                    #         worksheet.write(first_row, first_col + 4, 'lot', xlwt.easyxf('font: name Liberation Sans,bold on,'
                    #                                                                   'height 210; align: horiz right,vert center;'
                    #                                                                   'border: top thin, left thin, right thin, bottom thin'))
                    #
                    #         worksheet.write(first_row, first_col + 5, '', xlwt.easyxf('font: name Liberation Sans,bold on,'
                    #                                                                   'height 210; align: horiz right,vert center;'
                    #                                                                   'border: top thin, left thin, right thin, bottom thin'))
                    #
                    #         worksheet.write(first_row, first_col + 6, str(list[0]),
                    #                         xlwt.easyxf('font: name Liberation Sans,bold on,'
                    #                                     'height 210; align: horiz right, vert center;'
                    #                                     'border: top thin, left thin, right thin, bottom thin'))
                    #
                    #         worksheet.write(first_row, first_col + 7, str(list[0]),
                    #                         xlwt.easyxf('font: name Liberation Sans,bold on,'
                    #                                     'height 210; align: horiz right,vert center;'
                    #                                     'border: top thin, left thin, right thin, bottom thin'))
                    #         first_row += 1
                    #         line_count += 1

                index += 1

            worksheet.write(first_row, 0, '', xlwt.easyxf('border: top thin'))

        #Adding amount without discount
        worksheet.write(first_row, 7, 'Subtotal', xlwt.easyxf('font: name Arial,'
                                                              'height 180; align: horiz right,vert center;'))
        worksheet.write(first_row, 8, str("{0:,.2f}".format(self.total_without_disc)), xlwt.easyxf('font: name Arial,'
                                                                                               'height 180; align: horiz right,vert center;'))
        first_row += 1

        # Adding Discount Amount
        worksheet.write(first_row, 7, 'Discount', xlwt.easyxf('font: name Arial,'
                                                              'height 180; align: horiz right,vert center;'))
        worksheet.write(first_row, 8, str("{0:,.2f}".format(self.discount_amt)), xlwt.easyxf('font: name Arial,'
                                                                     'height 180; align: horiz right,vert center;'))

        worksheet.write(first_row, 0, 'Commercial Condition', xlwt.easyxf('font: name Calibri, bold on,'
                                                                          'height 200; align: horiz left,vert center;'))
        first_row += 1

        # Adding Untaxed Amount
        worksheet.write(first_row, 7, 'Total Net', xlwt.easyxf('font: name Arial,'
                                                              'height 180; align: horiz right,vert center;'))
        worksheet.write(first_row, 8, str("{0:,.2f}".format(self.amount_untaxed)), xlwt.easyxf('font: name Arial,'
                                                                                               'height 180; align: horiz right,vert center;'))
        worksheet.write_merge(first_row, first_row, 0, 1, '1. Currency:', xlwt.easyxf('font: name Calibri,'
                                                                                      'height 200; align: horiz left,vert center;'))
        if self.company_id:
            if self.company_id.currency_id.name == 'THB':
                worksheet.write(first_row, 2, 'Baht', xlwt.easyxf('font: name Calibri,'
                                                                  'height 200; align: horiz left,vert center;'))
            else:
                worksheet.write(first_row, 2, self.company_id.currency_id.name,
                                xlwt.easyxf('font: name Calibri,'
                                            'height 200; align: horiz left,vert center;'))

        first_row += 1

        # Adding Tax
        worksheet.write(first_row, 7, 'Tax/VAT Rate', xlwt.easyxf('font: name Arial,'
                                                                  'height 180; align: horiz right,vert center;'))
        worksheet.write(first_row, 8, str("%.2f" % self.tax_vat_perc)+'%', xlwt.easyxf('font: name Arial,'
                                                                        'height 160; align: horiz right,vert center;'))

        worksheet.write_merge(first_row, first_row, 0, 1, '2. Delivery:', xlwt.easyxf('font: name Calibri,'
                                                                                      'height 200; align: horiz left,vert center;'))

        if self.delivery:
            worksheet.write(first_row, 2, self.delivery,
                            xlwt.easyxf('font: name Calibri,'
                                        'height 200; align: horiz left,vert center;'))
        else:
            worksheet.write(first_row, 2, '',
                            xlwt.easyxf('font: name Calibri,'
                                        'height 200; align: horiz left,vert center;'))
        first_row += 1

        # Adding tax rate
        worksheet.write(first_row, 7, 'Tax/VAT', xlwt.easyxf('font: name Arial,'
                                                             'height 180; align: horiz right,vert center;'))
        worksheet.write(first_row, 8, str("{0:,.2f}".format(self.amount_tax)), xlwt.easyxf('font: name Arial,'
                                                                   'height 160; align: horiz right,vert center;'))

        worksheet.write_merge(first_row, first_row, 0, 1, '3. Term Of Payment:',
                              xlwt.easyxf('font: name Calibri,'
                                          'height 200; align: horiz left,vert center;'))

        if self.payment_term_id:
            worksheet.write(first_row, 2, self.payment_term_id.name,
                            xlwt.easyxf('font: name Calibri,'
                                        'height 200; align: horiz left,vert center;'))

        else:
            worksheet.write(first_row, 2, '',
                            xlwt.easyxf('font: name Calibri,'
                                        'height 200; align: horiz left,vert center;'))

        new_line = 0
        if self.note:
            new_line = str(self.note).count('\n')
            first_row += 1
            # worksheet.row(first_row).height = 1000
            worksheet.write_merge(first_row, first_row + new_line, 2, 3, self.note,
                                  xlwt.easyxf('font: name Arial,'
                                              'height 160; align: horiz left,vert top;'))

            # Adding Total Amount
            worksheet.write(first_row, 7, ' Grand Total', xlwt.easyxf('font: name Arial, bold on,'
                                                               'height 200; align: horiz right,vert center;'))
            worksheet.write(first_row, 8, str("{0:,.2f}".format(self.amount_total)),
                            xlwt.easyxf('font: name Arial, bold on, color White,'
                                        'height 200; align: horiz right,vert center;'
                                        'pattern: pattern solid, fore_colour Indigo;'))

            first_row = first_row + new_line + 1

        else:
            first_row += 1
            # Adding Total Amount
            worksheet.write(first_row, 7, 'Grand Total', xlwt.easyxf('font: name Arial, bold on,'
                                                               'height 200; align: horiz right,vert center;'))
            worksheet.write(first_row, 8, str("{0:,.2f}".format(self.amount_total)),
                            xlwt.easyxf('font: name Arial, bold on, color White,'
                                        'height 200; align: horiz right,vert center;'
                                        'pattern: pattern solid, fore_colour Indigo;'))



        worksheet.write_merge(first_row, first_row, 0, 1, '4. Warranty:',
                              xlwt.easyxf('font: name Calibri,'
                                          'height 200; align: horiz left,vert center;'))

        if self.warranty_period and self.warranty_period_type:
            worksheet.write(first_row, 2, str(self.warranty_period) + ' ' + str(self.warranty_period_type),
                            xlwt.easyxf('font: name Calibri,'
                                        'height 200; align: horiz left,vert center;'))

        first_row += 3
        worksheet.write(first_row, 0, 'Please confirm your acceptance of this quote by signing this document',
                        xlwt.easyxf('font: name Arial,'
                                    'height 160; align: horiz left,vert center;'))

        xlwt.add_palette_colour("gray", 0x17)
        workbook.set_colour_RGB(0x17, 178, 178, 178)
        worksheet.write_merge(first_row, first_row, 6, 7, 'Signature',
                              xlwt.easyxf('font: name Arial,color gray,'
                                          'height 160; align: horiz left,vert center;'
                                          'border: bottom thin, bottom_color gray'))
        first_row += 1

        worksheet.write(first_row, 0, 'Once signed, please Fax, mail or e-mail it to the provided address.',
                        xlwt.easyxf('font: name Arial,'
                                    'height 160; align: horiz left,vert center;'))

        worksheet.write_merge(first_row, first_row, 6, 7, 'Print Name',
                              xlwt.easyxf('font: name Arial,color gray,'
                                          'height 160; align: horiz left,vert center;'
                                          'border: bottom thin, bottom_color gray'))

        first_row += 1
        worksheet.write_merge(first_row, first_row, 6, 7, 'Date',
                              xlwt.easyxf('font: name Arial,color gray,'
                                          'height 160; align: horiz left,vert center;'
                                          'border: bottom thin, bottom_color gray'))

        first_row += 1
        sales_contact = ''
        if self.user_id.phone:
            sales_contact = self.user_id.phone
        elif self.user_id.mobile:
            sales_contact = self.user_id.mobile
        worksheet.write_merge(first_row, first_row, 0, 8, 'If you have any questions concerning this quote, '
                                                          'contact [' + str(self.user_id.name)
                              + ' ,' + sales_contact + ']',
                              xlwt.easyxf('font: name Arial,height 200; align: horiz center,vert center;'))

        first_row += 2
        worksheet.row(first_row).height = 400
        worksheet.write_merge(first_row, first_row, 0, 8, 'Thank you for your business!',
                              xlwt.easyxf('font: name Arial, bold on,'
                                          'height 240; align: horiz center,vert center;')
                              )

        first_row += 1
        worksheet.write_merge(first_row, first_row, 0, 8, 'SMART DEV SOLUTION CO., LTD',
                              xlwt.easyxf('font: name Arial, bold on,'
                                          'height 200; align: horiz center,vert center;'))

        first_row += 1
        worksheet.write_merge(first_row, first_row, 0, 8, 'High Performance Partnership',
                              xlwt.easyxf('font: name Arial,'
                                          'height 200; align: horiz center,vert center;'))

        # Adding Section For Quotation Name
        # if self.project_id:
        first_row = 10
        worksheet.write_merge(first_row, 10, 6, 8, "Quote/Project Description",
                              xlwt.easyxf('font: name Arial, bold on,'
                                          'color White,height 200; align: vert center;'
                                          'pattern: pattern solid, fore_colour Indigo;'))
        first_row += 1
        for row in range(first_row, 17):
            if row == 11:
                if self.quote_name:
                    worksheet.write_merge(row, row, 6, 8, self.quote_name, xlwt.easyxf('font: name Arial,'
                                                                                            'height 200; align: vert center;'
                                                                                            'border: left thin, right thin'))
                else:
                    worksheet.write_merge(row, row, 6, 8, '', xlwt.easyxf('font: name Arial,'
                                                                                       'height 200; align: vert center;'
                                                                                       'border: left thin, right thin'))
            elif row == 16:
                worksheet.write_merge(row, row, 6, 8, '', xlwt.easyxf('font: name Arial,'
                                                                      'height 200; align: vert center;'
                                                                      'border: left thin, right thin, bottom thin'))

            else:
                worksheet.write_merge(row, row, 6, 8, '', xlwt.easyxf('font: name Arial,'
                                                                      'height 200; align: vert center;'
                                                                      'border: left thin, right thin'))

        worksheet.show_grid = False
        fp = io.BytesIO()
        workbook.save(fp)
        self.so_excel_file = base64.encodestring(fp.getvalue())
        self.so_file_name = filename

    def get_boq_report(self):
        section_count = 0
        note_count = 0
        item_no = 1
        filename = 'BOQ - ' + str(self.name) + '.xls'
        workbook = xlwt.Workbook()
        worksheet = workbook.add_sheet('BOQ')

        worksheet.row(0).height = 600
        worksheet.col(0).width = 1300
        worksheet.col(1).width = 12000
        worksheet.row(1).height = 380
        worksheet.col(2).width = 10000
        worksheet.col(3).width = 6000
        worksheet.col(6).width = 5000

        first_row = 0
        xlwt.add_palette_colour("header_colour", 0x0C)
        workbook.set_colour_RGB(0x0C, 0, 66, 105)
        worksheet.write_merge(first_row, 0, 0, 8, "BOQ HARDWARE", xlwt.easyxf('font: name Arial, bold on,'
                                                                              'color White,height 480; align: vert center;'
                                                                              'pattern: pattern solid, fore_colour header_colour;'))
        first_row += 1

        worksheet.write(first_row, 0, self.name, xlwt.easyxf('font: name Arial, bold on,'
                                                             'height 200; align: vert center;'))
        first_row += 2
        worksheet.row(first_row).height = 380
        worksheet.write(first_row, 0, 'NO.', xlwt.easyxf('font: name Segoe UI, bold on,'
                                                         'color White,height 180; align: vert center;'
                                                         'pattern: pattern solid, fore_colour header_colour;'
                                                         'border: top thin, left thin, right thin, bottom thin'))
        worksheet.write(first_row, 1, 'DESCRIPTION', xlwt.easyxf('font: name Segoe UI, bold on,'
                                                                 'color White,height 180; align: vert center;'
                                                                 'pattern: pattern solid, fore_colour header_colour;'
                                                                 'border: top thin, left thin, right thin, bottom thin'))
        worksheet.write(first_row, 2, 'FUNCTION', xlwt.easyxf('font: name Segoe UI, bold on,'
                                                              'color White,height 180; align: vert center;'
                                                              'pattern: pattern solid, fore_colour header_colour;'
                                                              'border: top thin, left thin, right thin, bottom thin'))
        worksheet.write(first_row, 3, 'PART NO.', xlwt.easyxf('font: name Segoe UI, bold on,'
                                                              'color White,height 180; align: vert center;'
                                                              'pattern: pattern solid, fore_colour header_colour;'
                                                              'border: top thin, left thin, right thin, bottom thin'))
        worksheet.write(first_row, 4, 'UNIT', xlwt.easyxf('font: name Segoe UI, bold on,'
                                                          'color White,height 180; align: horiz center,vert center;'
                                                          'pattern: pattern solid, fore_colour header_colour;'
                                                          'border: top thin, left thin, right thin, bottom thin'))
        worksheet.write(first_row, 5, 'QTY.', xlwt.easyxf('font: name Segoe UI, bold on,'
                                                          'color White,height 180; align: horiz center,vert center;'
                                                          'pattern: pattern solid, fore_colour header_colour;'
                                                          'border: top thin, left thin, right thin, bottom thin'))
        worksheet.write(first_row, 6, 'MANUFACTURING', xlwt.easyxf('font: name Segoe UI, bold on,'
                                                                   'color White,height 180; align: horiz center,vert center;'
                                                                   'pattern: pattern solid, fore_colour header_colour;'
                                                                   'border: top thin, left thin, right thin, bottom thin'))
        worksheet.write(first_row, 7, 'PRICE', xlwt.easyxf('font: name Segoe UI, bold on,'
                                                           'color White,height 180; align: horiz right,vert center;'
                                                           'pattern: pattern solid, fore_colour header_colour;'
                                                           'border: top thin, left thin, right thin, bottom thin'))
        worksheet.write(first_row, 8, 'AMOUNT', xlwt.easyxf('font: name Segoe UI, bold on,'
                                                            'color White,height 180; align: horiz right,vert center;'
                                                            'pattern: pattern solid, fore_colour header_colour;'
                                                            'border: top thin, left thin, right thin, bottom thin'))
        first_row += 1

        if self.bom_details_id:
            for line in self.bom_details_id:
                if line.display_type == 'line_section':
                    if section_count > 0:
                        worksheet.write(first_row, 0, '', xlwt.easyxf('border: right thin, left thin'))
                        worksheet.write(first_row, 1, '', xlwt.easyxf('border: right thin, left thin'))
                        worksheet.write(first_row, 2, '', xlwt.easyxf('border: right thin, left thin'))
                        worksheet.write(first_row, 3, '', xlwt.easyxf('border: right thin, left thin'))
                        worksheet.write(first_row, 4, '', xlwt.easyxf('border: right thin, left thin'))
                        worksheet.write(first_row, 5, '', xlwt.easyxf('border: right thin, left thin'))
                        worksheet.write(first_row, 6, '', xlwt.easyxf('border: right thin, left thin'))
                        worksheet.write(first_row, 7, '', xlwt.easyxf('border: right thin, left thin'))
                        worksheet.write(first_row, 8, '', xlwt.easyxf('border: right thin, left thin'))
                        first_row += 1
                        if note_count > 0:
                            note_count = 0

                    worksheet.row(first_row).height = 420
                    # xlwt.add_palette_colour("section_colour", 0x16)
                    # workbook.set_colour_RGB(0x16, 224, 225, 225)
                    style = xlwt.easyxf('font: name Arial, bold on, underline on,'
                                        'height 220; align: vert center;'
                                        # 'pattern: pattern solid, fore_colour section_colour;'
                                        'border: top thin, left thin, right thin')
                    worksheet.write(first_row, 0, str(item_no), xlwt.easyxf('font: name Arial, bold on,'
                                                                            'height 220; align: vert center;'
                                                                            'border: top thin, left thin, right thin'))
                    # worksheet.write(first_row, 0, '', xlwt.easyxf('border: top thin, left thin, right thin'))
                    worksheet.write(first_row, 1, line.name.upper(), style)
                    worksheet.write(first_row, 2, '', style)
                    worksheet.write(first_row, 3, '', style)
                    worksheet.write(first_row, 4, 'SET', xlwt.easyxf('font: name Arial, bold on,'
                                                                     'height 220; align: horiz center, vert center;'
                                                                     # 'pattern: pattern solid, fore_colour section_colour;'
                                                                     'border: top thin, left thin, right thin'))
                    worksheet.write(first_row, 5, '1', xlwt.easyxf('font: name Arial, bold on,'
                                                                   'height 220; align: horiz center, vert center;'
                                                                   # 'pattern: pattern solid, fore_colour section_colour;'
                                                                   'border: left thin, right thin, top thin'))
                    worksheet.write(first_row, 6, '', style)
                    worksheet.write(first_row, 7, str("{0:,.2f}".format(line.product_subtotal)), xlwt.easyxf('font: name Arial, bold on,'
                                                                                     'height 220; align: horiz right, vert center;'
                                                                                     # 'pattern: pattern solid, fore_colour section_colour;'
                                                                                     'border: top thin, right thin, left thin'))
                    worksheet.write(first_row, 8, str("{0:,.2f}".format(line.product_subtotal)), xlwt.easyxf('font: name Arial, bold on,'
                                                                                     'height 220; align: horiz right, vert center;'
                                                                                     'border: top thin, right thin, left thin'))
                    section_count += 1
                    item_no += 1

                elif line.display_type == 'line_note':
                    worksheet.row(first_row).height = 380
                    if note_count > 0:
                        worksheet.write(first_row, 0, '', xlwt.easyxf('border: right thin, left thin'))
                        worksheet.write(first_row, 1, '', xlwt.easyxf('border: right thin, left thin'))
                        worksheet.write(first_row, 2, '', xlwt.easyxf('border: right thin, left thin'))
                        worksheet.write(first_row, 3, '', xlwt.easyxf('border: right thin, left thin'))
                        worksheet.write(first_row, 4, '', xlwt.easyxf('border: right thin, left thin'))
                        worksheet.write(first_row, 5, '', xlwt.easyxf('border: right thin, left thin'))
                        worksheet.write(first_row, 6, '', xlwt.easyxf('border: right thin, left thin'))
                        worksheet.write(first_row, 7, '', xlwt.easyxf('border: right thin, left thin'))
                        worksheet.write(first_row, 8, '', xlwt.easyxf('border: right thin, left thin'))
                        first_row += 1

                    worksheet.row(first_row).height = 380
                    xlwt.add_palette_colour("note_colour", 0x34)
                    workbook.set_colour_RGB(0x34, 242, 242, 242)
                    style = xlwt.easyxf('font: name Arial, bold on, italic on,'
                                        'height 180; align: vert center;'
                                        'pattern: pattern solid, fore_colour note_colour;'
                                        'border: left thin, right thin')
                    worksheet.write(first_row, 0, '', xlwt.easyxf('border: left thin, right thin'))
                    worksheet.write(first_row, 1, line.name.upper(), style)
                    worksheet.write(first_row, 2, '', style)
                    worksheet.write(first_row, 3, '', style)
                    worksheet.write(first_row, 4, '', style)
                    worksheet.write(first_row, 5, '', style)
                    worksheet.write(first_row, 6, '', style)
                    worksheet.write(first_row, 7, str("{0:,.2f}".format(line.product_subtotal)),
                                    xlwt.easyxf('font: name Arial, bold on, italic on,'
                                                'height 180; align: vert center, horiz right;'
                                                'pattern: pattern solid, fore_colour note_colour;'
                                                'border: left thin, right thin'))
                    worksheet.write(first_row, 8, '', xlwt.easyxf('border: left thin, right thin'))
                    note_count += 1

                else:
                    worksheet.row(first_row).height = 380

                    neededWidth = int((1 + len(str(line.product_id.name)))) * 255
                    if worksheet.col(1).width < neededWidth:
                        # worksheet.row(first_row).height = (neededWidth /380 )*255
                        worksheet.row(first_row).height = int(((neededWidth - worksheet.col(1).width) / 380) * 10)

                    style = xlwt.easyxf('font: name Arial,'
                                        'height 180; align: vert top;'
                                        'border: left thin, right thin;'
                                        'alignment: wrap on')

                    worksheet.write(first_row, 0, '', style)
                    worksheet.write(first_row, 1, line.product_id.name, style)
                    if line.function:
                        worksheet.write(first_row, 2, line.function, style)
                    else:
                        worksheet.write(first_row, 2, '', style)

                    if line.product_id.default_code:
                        worksheet.write(first_row, 3, line.product_id.default_code, style)
                    else:
                        worksheet.write(first_row, 3, '', style)

                    worksheet.write(first_row, 4, line.product_uom.name, xlwt.easyxf('font: name Arial, height 180;'
                                                                                     'align: vert top, horiz center;'
                                                                                     'border: left thin, right thin;'
                                                                                     'alignment: wrap on'))
                    worksheet.write(first_row, 5, line.product_qty, xlwt.easyxf('font: name Arial, height 180;'
                                                                                'align: vert top, horiz center;'
                                                                                'border: left thin, right thin;'
                                                                                'alignment: wrap on'))
                    if line.product_id.manufacturing:
                        worksheet.write(first_row, 6, line.product_id.manufacturing,
                                        xlwt.easyxf('font: name Arial, height 180;'
                                                    'align: vert top, horiz center;'
                                                    'border: left thin, right thin;'
                                                    'alignment: wrap on'))
                    else:
                        worksheet.write(first_row, 6, '', xlwt.easyxf('font: name Arial, height 180;'
                                                                      'align: vert top, horiz center;'
                                                                      'border: left thin, right thin;'
                                                                      'alignment: wrap on'))
                    worksheet.write(first_row, 7, '', style)
                    worksheet.write(first_row, 8, '', style)

                first_row += 1
        worksheet.row(first_row).height = 380
        worksheet.write(first_row, 0, '', xlwt.easyxf('border: right thin, left thin, top thin, bottom thin'))
        worksheet.write(first_row, 1, '', xlwt.easyxf('border: right thin, left thin, top thin, bottom thin'))
        worksheet.write(first_row, 2, '', xlwt.easyxf('border: right thin, left thin, top thin, bottom thin'))
        worksheet.write(first_row, 3, '', xlwt.easyxf('border: right thin, left thin, top thin, bottom thin'))
        worksheet.write(first_row, 4, '', xlwt.easyxf('border: right thin, left thin, top thin, bottom thin'))
        worksheet.write(first_row, 5, '', xlwt.easyxf('border: right thin, left thin, top thin, bottom thin'))
        worksheet.write(first_row, 6, '', xlwt.easyxf('border: right thin, left thin, top thin, bottom thin'))
        worksheet.write(first_row, 7, 'Total', xlwt.easyxf('font: name Arial, bold on,'
                                                           'height 220; align: horiz right,vert center;'
                                                           'border: right thin, left thin, top thin, bottom thin'))
        worksheet.write(first_row, 8, str("{0:,.2f}".format(self.boq_details_amount_total)), xlwt.easyxf('font: name Arial, bold on,'
                                                                                 'height 200; align: horiz right,vert center;'
                                                                                 'border: right thin, left thin, top thin, bottom thin'))

        first_row += 1
        worksheet.row(first_row).height = 380
        worksheet.write_merge(first_row, first_row, 0, 8, self.company_id.name.upper(),
                              xlwt.easyxf('font: name Arial, bold on, height 200; align: horiz center,vert center;'))
        first_row += 1
        worksheet.row(first_row).height = 340
        worksheet.write_merge(first_row, first_row, 0, 8, 'High Performance Partnership',
                              xlwt.easyxf('font: name Arial, height 200; align: horiz center,vert center;'))

        worksheet.show_grid = False

        fp = io.BytesIO()
        workbook.save(fp)
        self.boq_excel_file = base64.encodestring(fp.getvalue())
        self.boq_file_name = filename

    def get_boq_child_report(self):
        section_count = 0
        note_count = 0
        item_no = 1
        filename = 'BOQ - ' + str(self.name) + '.xls'
        workbook = xlwt.Workbook()
        worksheet = workbook.add_sheet('BOQ')

        worksheet.row(0).height = 600
        worksheet.col(0).width = 1300
        worksheet.col(1).width = 12000
        worksheet.row(1).height = 380
        worksheet.col(2).width = 6000
        worksheet.col(5).width = 5000

        first_row = 0
        xlwt.add_palette_colour("header_colour", 0x0C)
        workbook.set_colour_RGB(0x0C, 0, 66, 105)
        worksheet.write_merge(first_row, 0, 0, 7, "BOQ HARDWARE", xlwt.easyxf('font: name Arial, bold on,'
                                                                              'color White,height 480; align: vert center;'
                                                                              'pattern: pattern solid, fore_colour header_colour;'))
        first_row += 1

        worksheet.write(first_row, 0, self.name, xlwt.easyxf('font: name Arial, bold on,'
                                                             'height 200; align: vert center;'))
        first_row += 2
        worksheet.row(first_row).height = 320
        worksheet.write(first_row, 0, 'NO.', xlwt.easyxf('font: name Segoe UI, bold on,'
                                                         'color White,height 180; align: vert center;'
                                                         'pattern: pattern solid, fore_colour header_colour;'
                                                         'border: top thin, left thin, right thin, bottom thin'))
        worksheet.write(first_row, 1, 'DESCRIPTION', xlwt.easyxf('font: name Segoe UI, bold on,'
                                                                 'color White,height 180; align: vert center;'
                                                                 'pattern: pattern solid, fore_colour header_colour;'
                                                                 'border: top thin, left thin, right thin, bottom thin'))
        # worksheet.write(first_row, 2, 'FUNCTION', xlwt.easyxf('font: name Segoe UI, bold on,'
        #                                                       'color White,height 180; align: vert center;'
        #                                                       'pattern: pattern solid, fore_colour header_colour;'
        #                                                       'border: top thin, left thin, right thin, bottom thin'))
        worksheet.write(first_row, 2, 'PART NO.', xlwt.easyxf('font: name Segoe UI, bold on,'
                                                              'color White,height 180; align: vert center;'
                                                              'pattern: pattern solid, fore_colour header_colour;'
                                                              'border: top thin, left thin, right thin, bottom thin'))
        worksheet.write(first_row, 3, 'UNIT', xlwt.easyxf('font: name Segoe UI, bold on,'
                                                          'color White,height 180; align: horiz center,vert center;'
                                                          'pattern: pattern solid, fore_colour header_colour;'
                                                          'border: top thin, left thin, right thin, bottom thin'))
        worksheet.write(first_row, 4, 'QTY.', xlwt.easyxf('font: name Segoe UI, bold on,'
                                                          'color White,height 180; align: horiz center,vert center;'
                                                          'pattern: pattern solid, fore_colour header_colour;'
                                                          'border: top thin, left thin, right thin, bottom thin'))
        worksheet.write(first_row, 5, 'MANUFACTURING', xlwt.easyxf('font: name Segoe UI, bold on,'
                                                                   'color White,height 180; align: horiz center,vert center;'
                                                                   'pattern: pattern solid, fore_colour header_colour;'
                                                                   'border: top thin, left thin, right thin, bottom thin'))
        worksheet.write(first_row, 6, 'PRICE', xlwt.easyxf('font: name Segoe UI, bold on,'
                                                           'color White,height 180; align: horiz right,vert center;'
                                                           'pattern: pattern solid, fore_colour header_colour;'
                                                           'border: top thin, left thin, right thin, bottom thin'))
        worksheet.write(first_row, 7, 'AMOUNT', xlwt.easyxf('font: name Segoe UI, bold on,'
                                                            'color White,height 180; align: horiz right,vert center;'
                                                            'pattern: pattern solid, fore_colour header_colour;'
                                                            'border: top thin, left thin, right thin, bottom thin'))
        first_row += 1

        if self.bom_details_id:
            if self.add_child_prod:
                for line in self.bom_details_id:
                    if line.display_type == 'line_section':
                        if section_count > 0:
                            # worksheet.write(first_row, 0, '', xlwt.easyxf('border: right thin, left thin'))
                            # worksheet.write(first_row, 1, '', xlwt.easyxf('border: right thin, left thin'))
                            # worksheet.write(first_row, 2, '', xlwt.easyxf('border: right thin, left thin'))
                            # worksheet.write(first_row, 3, '', xlwt.easyxf('border: right thin, left thin'))
                            # worksheet.write(first_row, 4, '', xlwt.easyxf('border: right thin, left thin'))
                            # worksheet.write(first_row, 5, '', xlwt.easyxf('border: right thin, left thin'))
                            # worksheet.write(first_row, 6, '', xlwt.easyxf('border: right thin, left thin'))
                            # worksheet.write(first_row, 7, '', xlwt.easyxf('border: right thin, left thin'))
                            # worksheet.write(first_row, 8, '', xlwt.easyxf('border: right thin, left thin'))
                            # first_row += 1
                            if note_count > 0:
                                note_count = 0

                        worksheet.row(first_row).height = 420
                        xlwt.add_palette_colour("section_colour", 0x34)
                        workbook.set_colour_RGB(0x34, 242, 242, 242)
                        style = xlwt.easyxf('font: name Arial, bold on, underline on,'
                                            'height 220; align: vert center;'
                                            'pattern: pattern solid, fore_colour section_colour;'
                                            'border: top thin, left thin, right thin')
                        worksheet.write(first_row, 0, '', xlwt.easyxf('border: top thin, left thin, right thin;'
                                                                      'pattern: pattern solid, fore_colour section_colour;'))
                        worksheet.write(first_row, 1, line.name.upper(), style)
                        # worksheet.write(first_row, 2, '', style)
                        worksheet.write(first_row, 2, '', style)
                        worksheet.write(first_row, 3, 'SET', xlwt.easyxf('font: name Arial, bold on,'
                                                                         'height 220; align: horiz center, vert center;'
                                                                         'pattern: pattern solid, fore_colour section_colour;'
                                                                         'border: top thin, left thin, right thin'))
                        worksheet.write(first_row, 4, '1', xlwt.easyxf('font: name Arial, bold on,'
                                                                       'height 220; align: horiz center, vert center;'
                                                                       'pattern: pattern solid, fore_colour section_colour;'
                                                                       'border: left thin, right thin, top thin'))
                        worksheet.write(first_row, 5, '', style)
                        worksheet.write(first_row, 6, '', xlwt.easyxf('font: name Arial, bold on,'
                                                                     'height 220; align: horiz right, vert center;'
                                                                     'pattern: pattern solid, fore_colour section_colour;'
                                                                     'border: top thin, right thin, left thin'))
                        worksheet.write(first_row, 7, str("{0:,.2f}".format(line.product_subtotal)), xlwt.easyxf('font: name Arial, bold on,'
                                                                                         'height 220; align: horiz right, vert center;'
                                                                                         'border: top thin, right thin, left thin;'
                                                                                         'pattern: pattern solid, fore_colour section_colour;'))
                        section_count += 1

                    elif line.display_type == 'line_note':
                        if note_count > 0:
                            worksheet.write(first_row, 0, '', xlwt.easyxf('border: right thin, left thin'))
                            worksheet.write(first_row, 1, '', xlwt.easyxf('border: right thin, left thin'))
                            worksheet.write(first_row, 2, '', xlwt.easyxf('border: right thin, left thin'))
                            worksheet.write(first_row, 3, '', xlwt.easyxf('border: right thin, left thin'))
                            worksheet.write(first_row, 4, '', xlwt.easyxf('border: right thin, left thin'))
                            worksheet.write(first_row, 5, '', xlwt.easyxf('border: right thin, left thin'))
                            worksheet.write(first_row, 6, '', xlwt.easyxf('border: right thin, left thin'))
                            worksheet.write(first_row, 7, '', xlwt.easyxf('border: right thin, left thin'))
                            # worksheet.write(first_row, 8, '', xlwt.easyxf('border: right thin, left thin'))
                            first_row += 1

                        worksheet.row(first_row).height = 380
                        # xlwt.add_palette_colour("note_colour", 0x34)
                        # workbook.set_colour_RGB(0x34, 242, 242, 242)
                        style = xlwt.easyxf('font: name Arial, bold on, italic on,'
                                            'height 180; align: vert top;'
                                            # 'pattern: pattern solid, fore_colour note_colour;'
                                            'border: left thin, right thin')
                        worksheet.write(first_row, 0, '', xlwt.easyxf('border: left thin, right thin'))
                        worksheet.write(first_row, 1, line.name.upper(), style)
                        # worksheet.write(first_row, 2, '', style)
                        worksheet.write(first_row, 2, '', style)
                        worksheet.write(first_row, 3, '', style)
                        worksheet.write(first_row, 4, '', style)
                        worksheet.write(first_row, 5, '', style)
                        worksheet.write(first_row, 6, str("{0:,.2f}".format(line.product_subtotal)),
                                        xlwt.easyxf('font: name Arial, bold on, italic on,'
                                                    'height 180; align: vert top, horiz right;'
                                                    # 'pattern: pattern solid, fore_colour note_colour;'
                                                    'border: left thin, right thin'))
                        worksheet.write(first_row, 7, '', xlwt.easyxf('border: left thin, right thin'))
                        note_count += 1

                    else:
                        worksheet.row(first_row).height = 380
                        neededWidth = int((1 + len(str(line.product_id.name))))*255
                        if worksheet.col(1).width < neededWidth:
                            # worksheet.row(first_row).height = (neededWidth /380 )*255
                            worksheet.row(first_row).height = int(((neededWidth - worksheet.col(1).width) / 380 )*10)

                        style = xlwt.easyxf('font: name Arial,'
                                            'height 180; align: vert top;'
                                            'border: left thin, right thin, top thin;'
                                            'alignment: wrap on')

                        worksheet.write(first_row, 0, str(item_no), style)
                        worksheet.write(first_row, 1, line.product_id.name, style)

                        # cell_value = worksheet.cell(first_row, 1).value

                        # if line.function:
                        #     worksheet.write(first_row, 2, line.function, style)
                        # else:
                        #     worksheet.write(first_row, 2, '', style)

                        if line.product_id.default_code:
                            worksheet.write(first_row, 2, line.product_id.default_code, style)
                        else:
                            worksheet.write(first_row, 2, '', style)

                        worksheet.write(first_row, 3, line.product_uom.name, xlwt.easyxf('font: name Arial, height 180;'
                                                                                         'align: vert top, horiz center;'
                                                                                         'border: left thin, right thin, top thin;'
                                                                                         'alignment: wrap on'))
                        worksheet.write(first_row, 4, line.product_qty, xlwt.easyxf('font: name Arial, height 180;'
                                                                                    'align: vert top, horiz center;'
                                                                                    'border: left thin, right thin, top thin;'
                                                                                    'alignment: wrap on'))
                        if line.product_id.manufacturing:
                            worksheet.write(first_row, 5, line.product_id.manufacturing,
                                            xlwt.easyxf('font: name Arial, height 180;'
                                                        'align: vert top, horiz center;'
                                                        'border: left thin, right thin, top thin;'
                                                        'alignment: wrap on'))
                        else:
                            worksheet.write(first_row, 5, '', xlwt.easyxf('font: name Arial, height 180;'
                                                                          'align: vert top, horiz center;'
                                                                          'border: left thin, right thin, top thin;'
                                                                          'alignment: wrap on'))
                        worksheet.write(first_row, 6, str("{0:,.2f}".format(line.product_cost_price)), xlwt.easyxf('font: name Arial, height 180;'
                                                                                                        'align: vert top, horiz right;'
                                                                                                        'border: left thin, right thin, top thin;'
                                                                                                        'alignment: wrap on'))
                        worksheet.write(first_row, 7, str("{0:,.2f}".format(line.product_subtotal)), xlwt.easyxf('font: name Arial, height 180;'
                                                                                                        'align: vert top, horiz right;'
                                                                                                        'border: left thin, right thin, top thin;'
                                                                                                        'alignment: wrap on'))
                        item_no += 1

                    first_row += 1
        worksheet.row(first_row).height = 380
        worksheet.write(first_row, 0, '', xlwt.easyxf('border: right thin, left thin, top thin, bottom thin'))
        worksheet.write(first_row, 1, '', xlwt.easyxf('border: right thin, left thin, top thin, bottom thin'))
        # worksheet.write(first_row, 2, '', xlwt.easyxf('border: right thin, left thin, top thin, bottom thin'))
        worksheet.write(first_row, 2, '', xlwt.easyxf('border: right thin, left thin, top thin, bottom thin'))
        worksheet.write(first_row, 3, '', xlwt.easyxf('border: right thin, left thin, top thin, bottom thin'))
        worksheet.write(first_row, 4, '', xlwt.easyxf('border: right thin, left thin, top thin, bottom thin'))
        worksheet.write(first_row, 5, '', xlwt.easyxf('border: right thin, left thin, top thin, bottom thin'))
        worksheet.write(first_row, 6, 'Total', xlwt.easyxf('font: name Arial, bold on,'
                                                           'height 220; align: horiz right,vert center;'
                                                           'border: right thin, left thin, top thin, bottom thin'))
        worksheet.write(first_row, 7, str("{0:,.2f}".format(self.boq_details_amount_total)), xlwt.easyxf('font: name Arial, bold on,'
                                                                                 'height 200; align: horiz right,vert center;'
                                                                                 'border: right thin, left thin, top thin, bottom thin'))

        first_row += 1
        worksheet.row(first_row).height = 380
        worksheet.write_merge(first_row, first_row, 0, 7, self.company_id.name.upper(),
                              xlwt.easyxf('font: name Arial, bold on, height 200; align: horiz center,vert center;'))
        first_row += 1
        worksheet.row(first_row).height = 340
        worksheet.write_merge(first_row, first_row, 0, 7, 'High Performance Partnership',
                              xlwt.easyxf('font: name Arial, height 200; align: horiz center,vert center;'))

        worksheet.show_grid = False


        fp = io.BytesIO()
        workbook.save(fp)
        self.boq_child_excel_file = base64.encodestring(fp.getvalue())
        self.boq_child_file_name = filename


class SaleOrderLineInherit(models.Model):

    _inherit = 'sale.order.line'

    type = fields.Selection([('product', 'Product'), ('boq', 'BOQ'), ('boq_child', 'BOQ Child'), ('doc', 'Document'), ('eng', 'Engineering')],
                            default='product', string='Type')
    parent_product_id = fields.Many2one('product.product', string='Parent Product')
    mrp_bom_id = fields.Integer()
    after_disc_prod_price = fields.Float("After Disc Cost Price")
    po_location = fields.Many2one('stock.location', 'PO Location', related='order_id.wh_location')
    check_available=fields.Boolean("Available")

    @api.onchange('product_uom', 'product_uom_qty')
    def product_uom_change(self):
        if not self.product_uom or not self.product_id:
            self.price_unit = 0.0
            return
        if self.order_id.pricelist_id and self.order_id.partner_id:
            product = self.product_id.with_context(
                lang=self.order_id.partner_id.lang,
                partner=self.order_id.partner_id,
                quantity=self.product_uom_qty,
                date=self.order_id.date_order,
                pricelist=self.order_id.pricelist_id.id,
                uom=self.product_uom.id,
                fiscal_position=self.env.context.get('fiscal_position')
            )
            if not self.price_unit:
                self.price_unit = self.env['account.tax']._fix_tax_included_price_company(
                    self._get_display_price(product),
                    product.taxes_id, self.tax_id,
                    self.company_id)