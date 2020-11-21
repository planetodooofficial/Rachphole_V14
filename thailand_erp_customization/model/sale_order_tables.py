from odoo import fields,api,models,_
import logging
_logger = logging.getLogger(__name__)

class BillOfQuantities(models.Model):
    _name = 'bill.of.quantities'

    name = fields.Text(string='Description', required=True)
    product_id = fields.Many2one('product.product','Product/Material')
    bom_product_id = fields.Many2one('mrp.bom', 'Product/Material')
    bom_product_reference = fields.Char('Reference')
    product_uom = fields.Many2one('uom.uom','UoM')
    product_qty = fields.Float('Quantity', required=True, default=1.0)
    product_cost_price = fields.Float('Unit price', required=True, default=0.0)
    product_sale_price = fields.Float('Sale price',compute='get_sale_price')
    product_subtotal = fields.Float('Subtotal',compute='get_sub_total')
    sale_order_id = fields.Many2one('sale.order')
    display_type = fields.Selection([
        ('line_section', "Section"),
        ('line_note', "Note")], default=False, help="Technical field for UX purpose.")
    prod_disc=fields.Float ("DISC%")
    after_disc_prod_price=fields.Float("After Disc Cost Price")
    total_price_after_disc=fields.Float("After Disc Total Cost Price ",compute='_get_after_disc_total_price')
    po_location=fields.Many2one('stock.location', 'PO Location', related='sale_order_id.wh_location')


    @api.onchange('prod_disc','product_cost_price')
    def _get_disc_amount(self):
        for line in self:
            if line.prod_disc:
                disc_amount=(line.product_cost_price*line.prod_disc)/100
                line.after_disc_prod_price=line.product_cost_price-disc_amount


    @api.onchange('product_id')
    def get_child_cost_price(self):
        for line in self:
            if line.product_id and line.sale_order_id.add_child_prod:
                try:
                    # if line.product_id:
                    #     vendor_price=0.0
                    #     for price in line.product_id.seller_ids:
                    #         if vendor_price==0.0:
                    #              vendor_price=price.price
                    #         else:
                    #             if vendor_price > price.price:
                    #                 vendor_price=price.price
                    line.product_cost_price = line.product_id.standard_price
                    line.product_uom = line.product_id.product_tmpl_id.uom_id
                    line.after_disc_prod_price=line.product_id.standard_price
                    # line.bom_product_reference = line.product_id.code
                    if line.product_id.default_code:
                        line.name = "["+line.product_id.default_code+"] "+line.product_id.name
                    else:
                        line.name = line.product_id.name

                except Exception as e:
                    _logger.info('------------------The error in sale price for BoM------------%s', e)

    @api.onchange('bom_product_id')
    def get_cost_price(self):
        for line in self:
            if line.bom_product_id and not line.sale_order_id.add_child_prod:
                try:
                    line.product_cost_price = line.bom_product_id.total_price
                    # if not line.bom_product_id.total_price:
                    #     if line.bom_product_id.product_tmpl_id:
                    #         vendor_price = 0.0
                    #         for price in line.bom_product_id.product_tmpl_id.seller_ids:
                    #             if vendor_price == 0.0:
                    #                 vendor_price = price.price
                    #             else:
                    #                 if vendor_price > price.price:
                    #                     vendor_price = price.price
                    #         line.product_cost_price=vendor_price
                    line.product_uom = line.bom_product_id.product_tmpl_id.uom_id
                    line.after_disc_prod_price = line.bom_product_id.total_price
                    line.bom_product_reference = line.bom_product_id.code
                    if line.bom_product_id.product_tmpl_id.default_code:
                        line.name = "["+line.bom_product_id.product_tmpl_id.default_code+"] "+line.bom_product_id.product_tmpl_id.name
                    else:
                        line.name = line.bom_product_id.product_tmpl_id.name

                except Exception as e:
                    _logger.info('------------------The error in sale price for BoM------------%s', e)

    @api.depends('product_cost_price','sale_order_id.bom_multiplier')
    def get_sale_price(self):
        """
        This function will calculate the sale price of a product depending upon the multiplier set in sale order and cost price entered by the user
        :return:
        """
        for line in self:
            try:
                line.product_sale_price = line.product_cost_price * (line.sale_order_id.bom_multiplier/100)

            except Exception as e:
                _logger.info('------------------The error in sale price for BoM------------%s',e)

    @api.depends('product_qty','product_sale_price')
    def get_sub_total(self):
        """
        This function will calculate the subtotal depending on the quantity and sale price
        :return:
        """
        for line in self:
            try:
                line.product_subtotal = line.product_sale_price * line.product_qty

            except Exception as e:
                _logger.info('-------------------The error in subtotal for BoM-------------%s',e)



    @api.depends('product_qty', 'after_disc_prod_price')
    def _get_after_disc_total_price(self):
        """
        This function will calculate the subtotal depending on the quantity and after disc prod price
        :return:
        """
        for line in self:
            try:
                line.total_price_after_disc = line.after_disc_prod_price * line.product_qty

            except Exception as e:
                _logger.info('-------------------The error in _get_after_disc_total_price for BoM-------------%s', e)


class DocumentsInSaleOrder(models.Model):
    _name = 'document.sale.order'

    @api.depends('product_qty', 'product_cost_price')
    def _line_total_cost_price(self):
        """
        This function will calculate the subtotal depending on the quantity and after disc prod price
        :return:
        """
        for line in self:
            try:
                line.line_cost_total = line.product_cost_price * line.product_qty

            except Exception as e:
                _logger.info('-------------------The error in _get_after_disc_total_price for BoM-------------%s', e)


    product_id = fields.Many2one('product.product', 'Product/Service')
    product_uom = fields.Many2one('uom.uom', 'UoM', related='product_id.uom_id')
    product_qty = fields.Float('Quantity', default=1.0)
    product_cost_price = fields.Float('Cost Price')
    product_sale_price = fields.Float('Sale price', compute='get_sale_price', store='True')
    # days = fields.Float('Day')
    # man = fields.Float('Man')
    # # man_hours = fields.Float('MH',compute='get_man_hours')
    # man_hours = fields.Float('MH')
    # hotel = fields.Float('Hotel')
    # allowance = fields.Float('Allowance')
    # mobilize = fields.Float('Mobilize')
    # car = fields.Float('Car rent')
    line_total = fields.Float(' Total Sale price',compute='get_line_total')
    line_cost_total = fields.Float(' Total Cost price',compute='_line_total_cost_price')
    sale_order_id = fields.Many2one('sale.order')



    @api.onchange('product_id')
    def get_cost_price(self):
        for line in self:
            if line.product_id:
                try:
                    line.product_cost_price = line.product_id.standard_price

                except Exception as e:
                    _logger.info('------------------The error in sale price for BoM------------%s', e)

    @api.depends('product_sale_price', 'product_qty')
    def get_line_total(self):
        """
        Will get the line total
        :return:
        """
        for line in self:
            try:
                line.line_total = line.product_sale_price * line.product_qty

            except Exception as e:
                _logger.info('----------Error in Document line total is------------%s', e)

    @api.depends('product_cost_price', 'sale_order_id.document_multiplier')
    def get_sale_price(self):
        """

        :return:
        """
        for line in self:
            try:
                line.product_sale_price = line.product_cost_price * (line.sale_order_id.document_multiplier / 100)

            except Exception as e:
                _logger.info('-----------Error in Sale Price for Document-------------')

    # # Comments*******************
    # @api.depends('days','man')
    # def get_man_hours(self):
    #     """
    #     This function will calculate the cost of man hours depending upon man and days, 500 * 10 is the default wage
    #     :return:
    #     """
    #     for line in self:
    #         try:
    #             line.man_hours = 10 * 500 * line.man * line.days
    #
    #         except Exception as e:
    #             _logger.info('----------Error in Document man hours is------------%s',e)


    # # Comments**********************
    # @api.depends('man_hours','hotel','allowance','mobilize','car')
    # def get_line_total(self):
    #     """
    #     Will get the line total
    #     :return:
    #     """
    #     for line in self:
    #         try:
    #             line.line_total = line.allowance + line.hotel + line.man_hours + line.car + line.mobilize
    #
    #         except Exception as e:
    #             _logger.info('----------Error in Document line total is------------%s', e)@api.depends('man_hours','hotel','allowance','mobilize','car')



class EngineeringLinesInSaleOrder(models.Model):
    _name = 'engineering.line'


    @api.depends('product_qty', 'product_cost_price')
    def _line_total_cost_price(self):
        """
        This function will calculate the subtotal depending on the quantity and after disc prod price
        :return:
        """
        for line in self:
            try:
                line.line_cost_total = line.product_cost_price * line.product_qty

            except Exception as e:
                _logger.info('-------------------The error in _get_after_disc_total_price for BoM-------------%s', e)


    product_id = fields.Many2one('product.product', 'Product/Service')
    product_uom = fields.Many2one('uom.uom', 'UoM', related='product_id.uom_id')
    product_qty = fields.Float('Quantity', default=1.0)
    product_cost_price = fields.Float('Cost Price')
    product_sale_price = fields.Float('Sale price', compute='get_sale_price', store=True)
    # product_sale_price = fields.Float('Sale price')
    #
    # days = fields.Float('Day')
    # man = fields.Float('Man')
    # # man_hours = fields.Float('MH', compute='get_man_hours')
    # man_hours = fields.Float('MH')
    # hotel = fields.Float('Hotel')
    # allowance = fields.Float('Allowance')
    # mobilize = fields.Float('Mobilize')
    # car = fields.Float('Car rent')
    line_total = fields.Float('Total Sale Price', compute='get_line_total')
    # line_total = fields.Float('Line Total')
    line_cost_total = fields.Float(' Total Cost price', compute='_line_total_cost_price')

    sale_order_id = fields.Many2one('sale.order')
    tax_id = fields.Many2many('account.tax', string='Taxes')

    @api.onchange('product_id')
    def get_data(self):
        for line in self:
            if line.product_id:
                try:
                    line.product_cost_price = line.product_id.standard_price
                    line.tax_id = line.product_id.taxes_id

                except Exception as e:
                    _logger.info('------------------The error in sale price for BoM------------%s', e)

    @api.depends('product_cost_price', 'sale_order_id.engineering_multiplier')
    def get_sale_price(self):
        """
        This function will calculate the sale price of a product depending upon the multiplier set in sale order and cost price entered by the user
        :return:
        """
        for line in self:
            try:
                line.product_sale_price = line.product_cost_price * (line.sale_order_id.engineering_multiplier / 100)

            except Exception as e:
                _logger.info('------------------The error in sale price for BoM------------%s', e)

    # # Comment****************************
    # @api.depends('days', 'man')
    # def get_man_hours(self):
    #     """
    #     This function will calculate the cost of man hours depending upon man and days, 500 * 10 is the default wage
    #     :return:
    #     """
    #     for line in self:
    #         try:
    #             line.man_hours = 10 * 500 * line.man * line.days
    #
    #         except Exception as e:
    #             _logger.info('----------Error in Document man hours is------------%s', e)


    # Comment***********************
    # @api.depends('man_hours', 'hotel', 'allowance', 'mobilize', 'car','sale_order_id.engineering_multiplier')
    # def get_line_total(self):
    #     """
    #     Will get the line total
    #     :return:
    #     """
    #     for line in self:
    #         try:
    #             line.line_total = (line.allowance + line.hotel + line.man_hours + line.car + line.mobilize) * (line.sale_order_id.engineering_multiplier/100)
    #
    #         except Exception as e:
    #             _logger.info('----------Error in Document line total is------------%s', e)
    #
    @api.depends('product_sale_price', 'product_qty')
    def get_line_total(self):
        """
        Will get the line total
        :return:
        """
        for line in self:
            try:
                line.line_total = line.product_sale_price * line.product_qty

            except Exception as e:
                _logger.info('----------Error in Document line total is------------%s', e)


class BOM(models.Model):
    _name = 'bom.details'

    name = fields.Text(string='Description', required=True)
    product_id = fields.Many2one('product.product','Product/Material')
    reference = fields.Char('Reference')
    function = fields.Char('Function')
    product_uom = fields.Many2one('uom.uom','UoM')
    product_qty = fields.Float('Quantity', required=True, default=1.0)
    product_cost_price = fields.Float('Unit price', required=True, default=0.0)
    # product_sale_price = fields.Float('Sale price',compute='get_sale_price')
    product_subtotal = fields.Float('Subtotal')
    sale_order_id = fields.Many2one('sale.order')
    display_type = fields.Selection([
        ('line_section', "Section"),
        ('line_note', "Note")], default=False, help="Technical field for UX purpose.")
    boq_id = fields.Many2one('bill.of.quantities')
    prod_disc = fields.Float("DISC%")
    after_disc_prod_price = fields.Float("After Disc Cost Price")
    total_price_after_disc = fields.Float("After Disc Total Cost Price ")
    po_location = fields.Many2one('stock.location', 'PO Location')