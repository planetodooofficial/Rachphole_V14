from PIL import Image
from odoo import fields, models, api,_
import base64
import io
from datetime import datetime
from dateutil import relativedelta
import xlwt
import os

class JobCost(models.Model):

    _name = 'job.cost'

    @api.depends('sale_order_ids.total_sale_price')
    def _get_total_sale_price(self):
        for line in self:
            amount=0.0
            for order in line.sale_order_ids:
                amount+=order.total_sale_price
            line.total_sale_price=amount

    @api.depends('purchase_order_ids.total_purchase_price')
    def _get_total_purchase_price(self):
        for line in self:
            p_amount = 0.0
            for p_order in line.purchase_order_ids:
                p_amount += p_order.total_purchase_price
            line.total_purchase_price = p_amount

    @api.depends('sale_overhead_ids.total_overhead_price')
    def _get_total_overhead_price(self):
        for line in self:
            p_amount = 0.0
            for p_order in line.sale_overhead_ids:
                p_amount += p_order.total_overhead_price
            line.total_overhead_price = p_amount

    @api.depends('total_sale_price', 'total_purchase_price')
    def _get_job_cost_margin_amount(self):
        for line in self:
            margin = line.total_sale_price - line.total_purchase_price
            line.job_cost_margin = margin
            if line.job_cost_margin and line.total_sale_price:
                line.margin_percent = (margin / line.total_sale_price)*100

    name = fields.Char('Name')
    partner_id = fields.Many2one('res.partner', 'Customer')
    indent_number = fields.Char('Indent number')
    indent_name = fields.Char('Indent Name')
    date = fields.Date('Date')
    project_id = fields.Many2one('project.project', "Project")
    analytic_account_id = fields.Many2one('account.analytic.account', "Analytic Account")
    delivery_date = fields.Date("Delivery Date")
    warrant_term = fields.Many2one('warrant.term', 'Warrant Term')
    term_of_delivery = fields.Text("Term Of Delivery")
    expense_id = fields.One2many('hr.expense', 'job_cost_id', 'Expense ID')
    timesheet_ids = fields.One2many('account.analytic.line', 'job_cost_id', string="Analytic Lines")
    sale_order_id = fields.Many2one('sale.order','Sale Order')
    payment_id = fields.One2many('payment.details', 'job_cost_id', 'Payment')
    budget_id = fields.One2many('budget.details', 'job_cost_id', 'Budget')
    delivery_date_months = fields.Char()
    sale_order_ids=fields.One2many('job.cost.sale.order','job_id','All Sale Order')
    purchase_order_ids=fields.One2many('job.cost.purchase.order','job_id','All Purchase Order')
    sale_overhead_ids=fields.One2many('job.cost.overhead','job_id','All Overhead')

    excel_file = fields.Binary('Job Cost Excel Report')
    file_name = fields.Char('Excel File')
    total_sale_price=fields.Monetary('Total Subtotal Cost', store=True, compute='_get_total_sale_price')
    total_purchase_price=fields.Monetary('Total Purchase Cost', store=True, compute='_get_total_purchase_price')
    total_overhead_price=fields.Monetary('Total Overhead Cost', store=True, compute='_get_total_overhead_price')
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True,
                                  default=lambda self: self.env.company.currency_id)
    job_cost_margin=fields.Monetary('Margin', store=True, compute='_get_job_cost_margin_amount')
    margin_percent = fields.Float("Margin %", store=True, compute="_get_job_cost_margin_amount")

    @api.model
    def create(self, vals):
        super_call = super(JobCost, self).create(vals)
        super_call.name = self.env['ir.sequence'].next_by_code('job.cost') or _('New')
        return super_call


    def update_job_cost_sheet(self):
        for line in self:
            if line.project_id:
                for rec_s in line.sale_order_ids:
                    rec_s.unlink()
                for rec_p in line.purchase_order_ids:
                    rec_p.unlink()
                order_ids=self.env['sale.order'].search([('project_id','=',line.project_id.id)])
                if order_ids:
                    sale_vals=[]
                    for rec in order_ids:
                        sale_vals1=(0, 0, {'project_id':rec.project_id.id,
                                     'sale_order_id':rec.id,
                                     'date':rec.date_order,
                                     'total_sale_price':float(rec.amount_total),

                                     })
                        sale_vals.append(sale_vals1)
                    if sale_vals:
                        line.write({'sale_order_ids':sale_vals})
                purchase_ids = self.env['purchase.order'].search([('project_id', '=', line.project_id.id)])
                if purchase_ids:
                    vals = []
                    for rec in purchase_ids:
                        vals1 = (0, 0, {'project_id': rec.project_id.id,
                                         'purchase_order_id': rec.id,
                                         'date': rec.date_approve,
                                         'total_purchase_price': float(rec.amount_total),

                                             })
                        vals.append(vals1)
                    if vals:
                        line.write({'purchase_order_ids': vals})
    #
    # def create_job_cost_report(self):
    #     """
    #         To create job cost excel report
    #     :return:
    #     """
    #     filename = 'Job_Cost.xlsx'
    #     workbook = xlwt.Workbook()
    #     worksheet = workbook.add_sheet('JobCost')
    #
    #     # To add company logo in job cost sheet excel report
    #     if self.sale_order_id.company_id.logo:
    #         fh = open("/tmp/imageToSave.png", "wb")
    #         fh.write(base64.b64decode(self.sale_order_id.company_id.logo))
    #         fh.close()
    #         os.chmod("/tmp/imageToSave.png", 0o777)
    #         # open the image with PIL
    #
    #         im = Image.open('/tmp/imageToSave.png').convert("RGB")
    #
    #         file_out = "/tmp/imageTosave.bmp"
    #         im.save(file_out)
    #         im_resize = Image.open('/tmp/imageTosave.bmp')
    #         resize_width, resize_height = im_resize.size
    #         new_im_reszie = im_resize.resize((95, 85), Image.ANTIALIAS)
    #         new_im_reszie.save('/tmp/imageTosave.bmp')
    #
    #         worksheet.insert_bitmap('/tmp/imageTosave.bmp', 0, 0,)
    #
    #     # To add company address in job cost sheet
    #     first_row = 0
    #     if self.sale_order_id.company_id.name:
    #         worksheet.write(first_row, 7, self.sale_order_id.company_id.name,
    #                         style=xlwt.easyxf('font: name Liberation Sans, bold on, color Green; '))
    #         first_row += 1
    #
    #     if self.sale_order_id.company_id.street:
    #         worksheet.write(first_row, 7, self.sale_order_id.company_id.street)
    #         first_row += 1
    #
    #     if self.sale_order_id.company_id.street2:
    #         worksheet.write(first_row, 7, self.sale_order_id.company_id.street2)
    #         first_row += 1
    #
    #     addr = ''
    #     if self.sale_order_id.company_id.city:
    #         addr += str(self.sale_order_id.company_id.city) + ", "
    #
    #     if self.sale_order_id.company_id.state_id:
    #         addr += str(self.sale_order_id.company_id.state_id.name) + ", "
    #
    #     if self.sale_order_id.company_id.zip:
    #         addr += str(self.sale_order_id.company_id.zip) + ", "
    #
    #     if self.sale_order_id.company_id.country_id:
    #         addr += str(self.sale_order_id.company_id.country_id.name)
    #
    #     worksheet.write(first_row, 7, addr)
    #     first_row += 1
    #
    #     if self.sale_order_id.company_id.phone:
    #         worksheet.write(first_row, 7, "Tel. "+ self.sale_order_id.company_id.phone)
    #
    #     style_header = xlwt.easyxf(
    #         "font:height 200; font: name Liberation Sans, bold on,color black; align: horiz center, vert center")
    #     style_table_header = xlwt.easyxf(
    #         "font: name Liberation Sans, color black; align: horiz left")
    #     header_fill_yellow_style = xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
    #                                            'align: horiz center; '
    #                                            'pattern: pattern solid, fore_colour yellow;')
    #     table_heading = xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
    #                                 'align: horiz center,vert center; '
    #                                 'border: left thin, top thin, right thin, bottom thin')
    #
    #     add_border = xlwt.easyxf('border: left thin, top thin, right thin, bottom thin')
    #
    #     worksheet.row(7).height_mismatch = True
    #     worksheet.row(7).height = 300
    #     worksheet.col(0).width = 15 * 300
    #     worksheet.col(7).width = 15 * 300
    #     worksheet.col(15).width = 15 * 70
    #     worksheet.col(1).width = 15 * 350
    #     worksheet.col(8).width = 15 * 350
    #
    #     worksheet.write_merge(7, 7, 0, 9, "PROJECT / JOB COST", style=style_header)
    #     worksheet.write(9, 0, "SDS Job No.:")
    #     worksheet.write(10, 0, "Client Name:")
    #     worksheet.write(11, 0, "Project Name:")
    #     worksheet.write(12, 0, "PO&Qut. No.:")
    #
    #     worksheet.write(9, 7, "Date of Date:")
    #     worksheet.write(10, 7, "Delivery Date:")
    #     worksheet.write(11, 7, "Term of Delivery:")
    #     worksheet.write(12, 7, "Warranty Term:")
    #
    #     worksheet.write(9, 1, str(self.indent_number), style=xlwt.easyxf('font: name Liberation Sans, bold on; '
    #                                                                      'border: bottom medium'))
    #     worksheet.write(10, 1, str(self.partner_id.name), style=xlwt.easyxf('font: name Liberation Sans; '
    #                                                                         'border: bottom medium'))
    #     worksheet.write(11, 1, str(self.project_id.name), style=xlwt.easyxf('font: name Liberation Sans; '
    #                                                                         'border: bottom medium'))
    #     if self.date and self.delivery_date: # to calculate months
    #         first_date = self.date.strftime('%Y-%m-%d %H:%M:%S')
    #         last_date = self.delivery_date.strftime('%Y-%m-%d %H:%M:%S')
    #
    #         date1 = datetime.strptime(str(first_date), '%Y-%m-%d %H:%M:%S').date()
    #         date2 = datetime.strptime(str(last_date), '%Y-%m-%d %H:%M:%S').date()
    #         r = relativedelta.relativedelta(date2, date1)
    #         self.delivery_date_months = str(r.months) + " Month"
    #
    #     worksheet.write(9, 8, str(self.date.strftime('%d/%m/%Y')),
    #                     style=xlwt.easyxf('font:name Liberation Sans, bold on,color Blue;border: bottom medium'))
    #     worksheet.write(10, 8, self.delivery_date_months, style=xlwt.easyxf('font:name Liberation Sans, '
    #                                                                         'bold on,color Blue;border: bottom medium'))
    #
    #     if not self.term_of_delivery:
    #         self.term_of_delivery = ""
    #     worksheet.write(11, 8, str(self.term_of_delivery), style=xlwt.easyxf('font:name Liberation Sans, '
    #                                                                          'bold on,color Blue;border: bottom medium'))
    #     worksheet.write(12, 8, str(self.warrant_term.name), style=xlwt.easyxf('font:name Liberation Sans, '
    #                                                                           'bold on,color Blue;border: bottom medium'))
    #
    #
    #     #  ==================================Table For Sale & Project Management=====================================
    #     worksheet.write_merge(14, 14, 0, 14, "For Sale & Project Management", style=header_fill_yellow_style)
    #     worksheet.write_merge(15, 16, 0, 5, "Sell Price (THB)",
    #                           style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
    #                                             'align: horiz center,vert center; '
    #                                             'border: left medium, top medium, right medium, bottom medium'))
    #     worksheet.write_merge(15, 16, 6, 6, "Billing Date",
    #                           style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
    #                                             'align: horiz center,vert center; '
    #                                             'border: top medium, right medium, bottom medium'))
    #     worksheet.write_merge(15, 15, 7, 8, "Sell Price",
    #                           style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
    #                                             'align: horiz center,vert center; '
    #                                             'border: left medium, top medium, right medium, bottom thin'))
    #     worksheet.write(16, 7, "Bath",
    #                     style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
    #                                       'align: horiz center,vert center; '
    #                                       'border: left medium, top thin, right thin, bottom medium'))
    #     worksheet.write(16, 8, "%",
    #                     style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
    #                                       'align: horiz center,vert center; '
    #                                       'border: left thin, top thin, right medium, bottom medium'))
    #
    #     worksheet.write_merge(15, 15, 9, 10, "Project",
    #                           style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
    #                                             'align: horiz center,vert center; '
    #                                             'border: left medium, top medium, right medium, bottom thin'))
    #     worksheet.write(16, 9, "Bath",
    #                     style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
    #                                       'align: horiz center,vert center; '
    #                                       'border: left medium, top thin, right thin, bottom medium'))
    #     worksheet.write(16, 10, "%",
    #                     style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
    #                                       'align: horiz center,vert center; '
    #                                       'border: left thin, top thin, right medium, bottom medium'))
    #
    #     worksheet.write_merge(15, 15, 11, 12, "Rev.1",
    #                           style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
    #                                             'align: horiz center,vert center; '
    #                                             'border: left medium, top medium, right medium, bottom thin'))
    #     worksheet.write(16, 11, "Bath",
    #                     style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
    #                                       'align: horiz center,vert center; '
    #                                       'border: left medium, top thin, right thin, bottom medium'))
    #     worksheet.write(16, 12, "%",
    #                     style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
    #                                       'align: horiz center,vert center; '
    #                                       'border: left thin, top thin, right medium, bottom medium'))
    #
    #     worksheet.write_merge(15, 15, 13, 14, "Actual",
    #                           style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
    #                                             'align: horiz center,vert center; '
    #                                             'border: left medium, top medium, right medium, bottom thin'))
    #     worksheet.write(16, 13, "Bath",
    #                     style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
    #                                       'align: horiz center,vert center; '
    #                                       'border: left medium, top thin, right thin, bottom medium'))
    #     worksheet.write(16, 14, "%",
    #                     style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
    #                                       'align: horiz center,vert center; '
    #                                       'border: left thin, top thin, right medium, bottom medium'))
    #
    #     first_row = 17
    #     for row in range(first_row, 31):
    #         worksheet.write(row, 5, style=xlwt.easyxf('border: right medium'))
    #
    #     worksheet.write(31, 5, style=xlwt.easyxf('border: right medium,bottom thin, top thin'))
    #
    #     worksheet.write(32, 5, style=xlwt.easyxf('border: right medium, bottom medium'))
    #     worksheet.write(32, 4, "Total Receive(THB)",
    #                     style=xlwt.easyxf('border: bottom medium; font: name Liberation Sans, bold on,color black;'))
    #     worksheet.write(32, 3, style=xlwt.easyxf('border: bottom medium'))
    #     worksheet.write(32, 2, style=xlwt.easyxf('border: bottom medium'))
    #     worksheet.write(32, 1, style=xlwt.easyxf('border: bottom medium'))
    #     worksheet.write(32, 0, style=xlwt.easyxf('border: bottom medium'))
    #
    #     worksheet.write(31, 4, style=xlwt.easyxf('border: bottom thin, top thin'))
    #     worksheet.write(31, 3, style=xlwt.easyxf('border: bottom thin, top thin'))
    #     worksheet.write(31, 2, style=xlwt.easyxf('border: bottom thin, top thin'))
    #     worksheet.write(31, 1, style=xlwt.easyxf('border: bottom thin, top thin'))
    #     worksheet.write(31, 0, style=xlwt.easyxf('border: bottom thin, top thin'))
    #
    #     for row in range(first_row, 31):
    #         worksheet.write(row, 6, style=xlwt.easyxf('border: right medium'))
    #
    #     worksheet.write(31, 6, style=xlwt.easyxf('border: right medium, bottom thin, top thin'))
    #     worksheet.write(32, 6, style=xlwt.easyxf('border: right medium, bottom medium'))
    #
    #     for row in range(first_row, 31):
    #         worksheet.write(row, 7, style=xlwt.easyxf('border: right thin'))
    #
    #     worksheet.write(31, 7, style=xlwt.easyxf('border: right thin, bottom thin, top thin'))
    #     worksheet.write(32, 7, style=xlwt.easyxf('border: right thin, bottom medium'))
    #
    #     for row in range(first_row, 31):
    #         worksheet.write(row, 8, style=xlwt.easyxf('border: right medium'))
    #
    #     worksheet.write(31, 8, style=xlwt.easyxf('border: right medium, bottom thin, top thin'))
    #     worksheet.write(32, 8, style=xlwt.easyxf('border: right medium, bottom medium'))
    #
    #     for row in range(first_row, 31):
    #         worksheet.write(row, 9, style=xlwt.easyxf('border: right thin'))
    #
    #     worksheet.write(31, 9, style=xlwt.easyxf('border: right thin, bottom thin, top thin'))
    #     worksheet.write(32, 9, style=xlwt.easyxf('border: right thin, bottom medium'))
    #
    #     for row in range(first_row, 31):
    #         worksheet.write(row, 10, style=xlwt.easyxf('border: right medium'))
    #
    #     worksheet.write(31, 10, style=xlwt.easyxf('border: right medium, bottom thin, top thin'))
    #     worksheet.write(32, 10, style=xlwt.easyxf('border: right medium, bottom medium'))
    #
    #     for row in range(first_row, 31):
    #         worksheet.write(row, 11, style=xlwt.easyxf('border: right thin'))
    #
    #     worksheet.write(31, 11, style=xlwt.easyxf('border: right thin, bottom thin, top thin'))
    #     worksheet.write(32, 11, style=xlwt.easyxf('border: right thin, bottom medium'))
    #
    #     for row in range(first_row, 31):
    #         worksheet.write(row, 12, style=xlwt.easyxf('border: right medium'))
    #
    #     worksheet.write(31, 12, style=xlwt.easyxf('border: right medium, bottom thin, top thin'))
    #     worksheet.write(32, 12, style=xlwt.easyxf('border: right medium, bottom medium'))
    #
    #     for row in range(first_row, 31):
    #         worksheet.write(row, 13, style=xlwt.easyxf('border: right thin'))
    #
    #     worksheet.write(31, 13, style=xlwt.easyxf('border: right thin, bottom thin, top thin'))
    #     worksheet.write(32, 13, style=xlwt.easyxf('border: right thin, bottom medium'))
    #
    #     for row in range(first_row, 31):
    #         worksheet.write(row, 14, style=xlwt.easyxf('border: right medium'))
    #
    #     worksheet.write(31, 14, style=xlwt.easyxf('border: right medium, bottom thin, top thin'))
    #     worksheet.write(32, 14, style=xlwt.easyxf('border: right medium, bottom medium'))
    #
    #
    #
    #
    #     worksheet.write_merge(34, 35, 0, 5, "Cost & Account Payment",
    #                           style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
    #                                             'align: horiz center,vert center; '
    #                                             'border: left medium, top medium, right medium, bottom medium'))
    #     worksheet.write_merge(34, 35, 6, 6, "Billing Date",
    #                           style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
    #                                             'align: horiz center,vert center; '
    #                                             'border: top medium, right medium, bottom medium'))
    #     worksheet.write_merge(34, 34, 7, 8, "Budget",
    #                           style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
    #                                             'align: horiz center,vert center; '
    #                                             'border: left medium, top medium, right medium, bottom thin'))
    #     worksheet.write(35, 7, "Bath",
    #                     style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
    #                                       'align: horiz center,vert center; '
    #                                       'border: left medium, top thin, right thin, bottom medium'))
    #     worksheet.write(35, 8, "%",
    #                     style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
    #                                       'align: horiz center,vert center; '
    #                                       'border: left thin, top thin, right medium, bottom medium'))
    #
    #     worksheet.write_merge(34, 34, 9, 10, "Budget",
    #                           style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
    #                                             'align: horiz center,vert center; '
    #                                             'border: left medium, top medium, right medium, bottom thin'))
    #     worksheet.write(35, 9, "Bath",
    #                     style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
    #                                       'align: horiz center,vert center; '
    #                                       'border: left medium, top thin, right thin, bottom medium'))
    #     worksheet.write(35, 10, "%",
    #                     style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
    #                                       'align: horiz center,vert center; '
    #                                       'border: left thin, top thin, right medium, bottom medium'))
    #
    #     worksheet.write_merge(34, 34, 11, 12, "Budget",
    #                           style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
    #                                             'align: horiz center,vert center; '
    #                                             'border: left medium, top medium, right medium, bottom thin'))
    #     worksheet.write(35, 11, "Bath",
    #                     style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
    #                                       'align: horiz center,vert center; '
    #                                       'border: left medium, top thin, right thin, bottom medium'))
    #     worksheet.write(35, 12, "%",
    #                     style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
    #                                       'align: horiz center,vert center; '
    #                                       'border: left thin, top thin, right medium, bottom medium'))
    #
    #     worksheet.write_merge(34, 34, 13, 14, "Actual",
    #                           style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
    #                                             'align: horiz center,vert center; '
    #                                             'border: left medium, top medium, right medium, bottom thin'))
    #     worksheet.write(35, 13, "Bath",
    #                     style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
    #                                       'align: horiz center,vert center; '
    #                                       'border: left medium, top thin, right thin, bottom medium'))
    #     worksheet.write(35, 14, "%",
    #                     style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
    #                                       'align: horiz center,vert center; '
    #                                       'border: left thin, top thin, right medium, bottom medium'))
    #
    #     first_row = 36
    #     for row in range(first_row, 68):
    #         worksheet.write(row, 5, style=xlwt.easyxf('border: right medium'))
    #
    #     worksheet.write_merge(68, 68, 5, 6, "Total Cost (THB)",
    #                           style=xlwt.easyxf('border: right medium, top medium; '
    #                                             'font: name Liberation Sans, bold on,color black;'))
    #     worksheet.write_merge(69, 69, 5, 6, "Gross Profit (THB)",
    #                           style=xlwt.easyxf('border: right medium,bottom thin, top thin;'
    #                                             'font: name Liberation Sans, bold on,color black;'))
    #     worksheet.write_merge(70, 70, 5, 6, "Gross Profit (%)", style=xlwt.easyxf('border: right medium, bottom medium;'
    #                                                                               'font: name Liberation Sans, bold on,'
    #                                                                               'color black;'))
    #     first_col = 0
    #     for col in range(first_col, 5):
    #         worksheet.write(70, col, style=xlwt.easyxf('border: bottom medium;'))
    #
    #     for col in range(first_col, 5):
    #         worksheet.write(68, col, style=xlwt.easyxf('border: top medium'))
    #
    #     for col in range(first_col, 5):
    #         worksheet.write(69, col, style=xlwt.easyxf('border: bottom thin, top thin'))
    #
    #     for row in range(first_row, 68):
    #         worksheet.write(row, 6, style=xlwt.easyxf('border: right medium'))
    #
    #     for row in range(first_row, 68):
    #         worksheet.write(row, 7, style=xlwt.easyxf('border: right thin'))
    #
    #     worksheet.write(68, 7, style=xlwt.easyxf('border: right thin, top medium'))
    #     worksheet.write(69, 7, style=xlwt.easyxf('border: right thin, bottom thin, top thin'))
    #     worksheet.write(70, 7, style=xlwt.easyxf('border: right thin, bottom medium'))
    #
    #     for row in range(first_row, 68):
    #         worksheet.write(row, 8, style=xlwt.easyxf('border: right medium'))
    #
    #     worksheet.write(68, 8, style=xlwt.easyxf('border: right medium, top medium'))
    #     worksheet.write(69, 8, style=xlwt.easyxf('border: right medium, bottom thin, top thin'))
    #     worksheet.write(70, 8, style=xlwt.easyxf('border: right medium, bottom medium'))
    #
    #     for row in range(first_row, 68):
    #         worksheet.write(row, 9, style=xlwt.easyxf('border: right thin'))
    #
    #     worksheet.write(68, 9, style=xlwt.easyxf('border: right thin, top medium'))
    #     worksheet.write(69, 9, style=xlwt.easyxf('border: right thin, bottom thin, top thin'))
    #     worksheet.write(70, 9, style=xlwt.easyxf('border: right thin, bottom medium'))
    #
    #     for row in range(first_row, 68):
    #         worksheet.write(row, 10, style=xlwt.easyxf('border: right medium'))
    #
    #     worksheet.write(68, 10, style=xlwt.easyxf('border: right medium, top medium'))
    #     worksheet.write(69, 10, style=xlwt.easyxf('border: right medium, bottom thin, top thin'))
    #     worksheet.write(70, 10, style=xlwt.easyxf('border: right medium, bottom medium'))
    #
    #     for row in range(first_row, 68):
    #         worksheet.write(row, 11, style=xlwt.easyxf('border: right thin'))
    #
    #     worksheet.write(68, 11, style=xlwt.easyxf('border: right thin, top medium'))
    #     worksheet.write(69, 11, style=xlwt.easyxf('border: right thin, bottom thin, top thin'))
    #     worksheet.write(70, 11, style=xlwt.easyxf('border: right thin, bottom medium'))
    #
    #     for row in range(first_row, 68):
    #         worksheet.write(row, 12, style=xlwt.easyxf('border: right medium'))
    #
    #     worksheet.write(68, 12, style=xlwt.easyxf('border: right medium, top medium'))
    #     worksheet.write(69, 12, style=xlwt.easyxf('border: right medium, bottom thin, top thin'))
    #     worksheet.write(70, 12, style=xlwt.easyxf('border: right medium, bottom medium'))
    #
    #     for row in range(first_row, 68):
    #         worksheet.write(row, 13, style=xlwt.easyxf('border: right thin'))
    #
    #     worksheet.write(68, 13, style=xlwt.easyxf('border: right thin, top medium'))
    #     worksheet.write(69, 13, style=xlwt.easyxf('border: right thin, bottom thin, top thin'))
    #     worksheet.write(70, 13, style=xlwt.easyxf('border: right thin, bottom medium'))
    #
    #     for row in range(first_row, 68):
    #         worksheet.write(row, 14, style=xlwt.easyxf('border: right medium'))
    #
    #     worksheet.write(68, 14, style=xlwt.easyxf('border: right medium, top medium'))
    #     worksheet.write(69, 14, style=xlwt.easyxf('border: right medium, bottom thin, top thin'))
    #     worksheet.write(70, 14, style=xlwt.easyxf('border: right medium, bottom medium'))
    #
    #
    #     # ===============================Table For Accounting & Finance===============================================
    #     worksheet.write_merge(14, 14, 16, 28, "For Accounting and Finance",
    #                           style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
    #                                             'align: horiz center; '
    #                                             'pattern: pattern solid, fore_colour 0x31;'))
    #     worksheet.write_merge(15, 15, 16, 19, "Customer Receive",
    #                           style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
    #                                             'align: horiz center,vert center; '
    #                                             'border: left medium, top medium, right medium, bottom thin'))
    #     worksheet.write_merge(16, 16, 16, 17, "Inv.No.",
    #                           style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
    #                                             'align: horiz center,vert center; '
    #                                             'border: left medium, top thin, right thin, bottom medium'))
    #     worksheet.write(16, 18, "Date",
    #                           style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
    #                                             'align: horiz center,vert center; '
    #                                             'border: left thin, top thin, right thin, bottom medium'))
    #     worksheet.write(16, 19, "",
    #                           style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
    #                                             'align: horiz center,vert center; '
    #                                             'border: left thin, top thin, right medium, bottom medium'))
    #
    #     worksheet.write_merge(15, 15, 20, 28, "Actual Receive",
    #                           style=xlwt.easyxf('font: name Liberation Sans, bold on,color dark_blue; '
    #                                             'align: horiz center,vert center; '
    #                                             'border: left medium, top medium, right medium, bottom thin'))
    #     worksheet.write(16, 20, "Advance",
    #                           style=xlwt.easyxf('font: name Liberation Sans, bold on,color Red; '
    #                                             'align: horiz center,vert center; '
    #                                             'border: left medium, top thin, right thin, bottom medium'))
    #     worksheet.write(16, 21, "",
    #                           style=xlwt.easyxf('font: name Liberation Sans, bold on,color dark_blue; '
    #                                             'align: horiz center,vert center; '
    #                                             'border: left thin, top thin, right thin, bottom medium'))
    #     worksheet.write(16, 22, "",
    #                           style=xlwt.easyxf('font: name Liberation Sans, bold on,color dark_blue; '
    #                                             'align: horiz center,vert center; '
    #                                             'border: left thin, top thin, right thin, bottom medium'))
    #     worksheet.write(16, 23, "",
    #                           style=xlwt.easyxf('font: name Liberation Sans, bold on,color dark_blue; '
    #                                             'align: horiz center,vert center; '
    #                                             'border: left thin, top thin, right thin, bottom medium'))
    #     worksheet.write(16, 24, "",
    #                           style=xlwt.easyxf('font: name Liberation Sans, bold on,color dark_blue; '
    #                                             'align: horiz center,vert center; '
    #                                             'border: left thin, top thin, right thin, bottom medium'))
    #     worksheet.write(16, 25, "",
    #                           style=xlwt.easyxf('font: name Liberation Sans, bold on,color dark_blue; '
    #                                             'align: horiz center,vert center; '
    #                                             'border: left thin, top thin, right thin, bottom medium'))
    #     worksheet.write(16, 26, "",
    #                           style=xlwt.easyxf('font: name Liberation Sans, bold on,color dark_blue; '
    #                                             'align: horiz center,vert center; '
    #                                             'border: left thin, top thin, right thin, bottom medium'))
    #     worksheet.write(16, 27, "",
    #                           style=xlwt.easyxf('font: name Liberation Sans, bold on,color dark_blue; '
    #                                             'align: horiz center,vert center; '
    #                                             'border: left thin, top thin, right thin, bottom medium'))
    #     worksheet.write(16, 28, "",
    #                           style=xlwt.easyxf('font: name Liberation Sans, bold on,color dark_blue; '
    #                                             'align: horiz center,vert center; '
    #                                             'border: left thin, top thin, right medium, bottom medium'))
    #
    #     first_row = 17
    #     for row in range(first_row, 31):
    #         worksheet.write(row, 17, style=xlwt.easyxf('border: right thin'))
    #
    #     worksheet.write(31, 17, style=xlwt.easyxf('border: right thin, bottom medium, top medium'))
    #
    #     for row in range(first_row, 31):
    #         worksheet.write(row, 16, style=xlwt.easyxf('border: left medium'))
    #
    #     worksheet.write(31, 16, style=xlwt.easyxf('border: left medium, bottom medium, top medium'))
    #
    #     worksheet.write_merge(32, 32, 16, 18, "Total",
    #                           style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
    #                                             'align: horiz center,vert center; '
    #                                             'border: left medium, top medium, right medium, bottom medium'))
    #
    #     for row in range(first_row, 31):
    #         worksheet.write(row, 18, style=xlwt.easyxf('border: right thin'))
    #
    #     worksheet.write(31, 18, style=xlwt.easyxf('border: right thin, bottom medium, top medium'))
    #
    #     for row in range(first_row, 31):
    #         worksheet.write(row, 19, style=xlwt.easyxf('border: right medium'))
    #
    #     worksheet.write(31, 19, style=xlwt.easyxf('border: right medium, bottom medium, top medium'))
    #     worksheet.write(32, 19, style=xlwt.easyxf('border: right medium, bottom medium, top medium'))
    #
    #     first_col = 20
    #     for col in range(first_col, 28):
    #         worksheet.write(32, col, style=xlwt.easyxf('border: right thin, bottom medium, top medium'))
    #
    #     worksheet.write(32, 28, style=xlwt.easyxf('border: right medium, bottom medium, top medium'))
    #
    #     for row in range(first_row, 31):
    #         worksheet.write(row, 20, style=xlwt.easyxf('border: right thin'))
    #
    #     worksheet.write(31, 20, style=xlwt.easyxf('border: right thin, bottom medium, top medium'))
    #
    #     for row in range(first_row, 31):
    #         worksheet.write(row, 21, style=xlwt.easyxf('border: right thin'))
    #
    #     worksheet.write(31, 21, style=xlwt.easyxf('border: right thin, bottom medium, top medium'))
    #
    #     for row in range(first_row, 31):
    #         worksheet.write(row, 22, style=xlwt.easyxf('border: right thin'))
    #
    #     worksheet.write(31, 22, style=xlwt.easyxf('border: right thin, bottom medium, top medium'))
    #
    #     for row in range(first_row, 31):
    #         worksheet.write(row, 23, style=xlwt.easyxf('border: right thin'))
    #
    #     worksheet.write(31, 23, style=xlwt.easyxf('border: right thin, bottom medium, top medium'))
    #
    #     for row in range(first_row, 31):
    #         worksheet.write(row, 24, style=xlwt.easyxf('border: right thin'))
    #
    #     worksheet.write(31, 24, style=xlwt.easyxf('border: right thin, bottom medium, top medium'))
    #
    #     for row in range(first_row, 31):
    #         worksheet.write(row, 25, style=xlwt.easyxf('border: right thin'))
    #
    #     worksheet.write(31, 25, style=xlwt.easyxf('border: right thin, bottom medium, top medium'))
    #
    #     for row in range(first_row, 31):
    #         worksheet.write(row, 26, style=xlwt.easyxf('border: right thin'))
    #
    #     worksheet.write(31, 26, style=xlwt.easyxf('border: right thin, bottom medium, top medium'))
    #
    #     for row in range(first_row, 31):
    #         worksheet.write(row, 27, style=xlwt.easyxf('border: right thin'))
    #
    #     worksheet.write(31, 27, style=xlwt.easyxf('border: right thin, bottom medium, top medium'))
    #
    #     for row in range(first_row, 31):
    #         worksheet.write(row, 28, style=xlwt.easyxf('border: right medium'))
    #
    #     worksheet.write(31, 28, style=xlwt.easyxf('border: right medium, bottom medium, top medium'))
    #
    #
    #
    #     worksheet.write_merge(34, 34, 16, 19, "Payment",
    #                           style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
    #                                             'align: horiz center,vert center; '
    #                                             'border: left medium, top medium, right medium, bottom thin'))
    #     worksheet.write(35, 16, "Inv.No.",
    #                           style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
    #                                             'align: horiz center,vert center; '
    #                                             'border: left medium, top thin, right thin, bottom medium'))
    #     worksheet.write(35, 17, "PO",
    #                           style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
    #                                             'align: horiz center,vert center; '
    #                                             'border: top thin, right thin, bottom medium'))
    #     worksheet.write(35, 18, "Date",
    #                           style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
    #                                             'align: horiz center,vert center; '
    #                                             'border: top thin, right thin, bottom medium'))
    #     worksheet.write(35, 19, "",
    #                           style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
    #                                             'align: horiz center,vert center; '
    #                                             'border: top thin, right thin, bottom medium'))
    #     worksheet.write_merge(34, 34, 20, 28, "Actual Payment",
    #                           style=xlwt.easyxf('font: name Liberation Sans, bold on,color dark_blue; '
    #                                             'align: horiz center,vert center; '
    #                                             'border: left medium, top medium, right medium, bottom thin'))
    #     worksheet.write(35, 20, "Advance",
    #                     style=xlwt.easyxf('font: name Liberation Sans, bold on,color Red; '
    #                                       'align: horiz center,vert center; '
    #                                       'border: left medium, top thin, right thin, bottom medium'))
    #     worksheet.write(35, 21, "",
    #                     style=xlwt.easyxf('font: name Liberation Sans, bold on,color dark_blue; '
    #                                       'align: horiz center,vert center; '
    #                                       'border: left thin, top thin, right thin, bottom medium'))
    #     worksheet.write(35, 22, "",
    #                     style=xlwt.easyxf('font: name Liberation Sans, bold on,color dark_blue; '
    #                                       'align: horiz center,vert center; '
    #                                       'border: left thin, top thin, right thin, bottom medium'))
    #     worksheet.write(35, 23, "",
    #                     style=xlwt.easyxf('font: name Liberation Sans, bold on,color dark_blue; '
    #                                       'align: horiz center,vert center; '
    #                                       'border: left thin, top thin, right thin, bottom medium'))
    #     worksheet.write(35, 24, "",
    #                     style=xlwt.easyxf('font: name Liberation Sans, bold on,color dark_blue; '
    #                                       'align: horiz center,vert center; '
    #                                       'border: left thin, top thin, right thin, bottom medium'))
    #     worksheet.write(35, 25, "",
    #                     style=xlwt.easyxf('font: name Liberation Sans, bold on,color dark_blue; '
    #                                       'align: horiz center,vert center; '
    #                                       'border: left thin, top thin, right thin, bottom medium'))
    #     worksheet.write(35, 26, "",
    #                     style=xlwt.easyxf('font: name Liberation Sans, bold on,color dark_blue; '
    #                                       'align: horiz center,vert center; '
    #                                       'border: left thin, top thin, right thin, bottom medium'))
    #     worksheet.write(35, 27, "",
    #                     style=xlwt.easyxf('font: name Liberation Sans, bold on,color dark_blue; '
    #                                       'align: horiz center,vert center; '
    #                                       'border: left thin, top thin, right thin, bottom medium'))
    #     worksheet.write(35, 28, "",
    #                     style=xlwt.easyxf('font: name Liberation Sans, bold on,color dark_blue; '
    #                                       'align: horiz center,vert center; '
    #                                       'border: left thin, top thin, right medium, bottom medium'))
    #
    #     first_row = 36
    #     for row in range(first_row, 68):
    #         worksheet.write(row, 16, style=xlwt.easyxf('border: right thin, left medium'))
    #
    #     worksheet.write_merge(68, 68, 16, 18, "Total",
    #                           style=xlwt.easyxf('border: right medium, top medium, left medium;'
    #                                             'font: name Liberation Sans, bold on,color black;'))
    #     worksheet.write_merge(69, 70, 16, 18, "Profit & (-Loss)",
    #                           style=xlwt.easyxf('border: right medium,bottom medium, top medium, left medium;'
    #                                             'font: name Liberation Sans, bold on,color black;'))
    #
    #     for row in range(first_row, 68):
    #         worksheet.write(row, 17, style=xlwt.easyxf('border: right thin'))
    #
    #     for row in range(first_row, 68):
    #         worksheet.write(row, 18, style=xlwt.easyxf('border: right thin'))
    #
    #     for row in range(first_row, 68):
    #         worksheet.write(row, 19, style=xlwt.easyxf('border: right medium'))
    #
    #     worksheet.write(68, 19, style=xlwt.easyxf('border: right medium, top medium, bottom medium'))
    #     worksheet.write(69, 19, style=xlwt.easyxf('border: bottom medium, right medium'))
    #     worksheet.write(70, 19, style=xlwt.easyxf('border: bottom medium, right medium'))
    #
    #     for row in range(first_row, 68):
    #         worksheet.write(row, 20, style=xlwt.easyxf('border: right thin'))
    #
    #     worksheet.write(68, 20, style=xlwt.easyxf('border: top medium, bottom medium, right thin'))
    #     worksheet.write(69, 20, style=xlwt.easyxf('border: bottom medium, right thin'))
    #     worksheet.write(70, 20, style=xlwt.easyxf('border: bottom medium, right thin'))
    #
    #     for row in range(first_row, 68):
    #         worksheet.write(row, 21, style=xlwt.easyxf('border: right thin'))
    #
    #     worksheet.write(68, 21, style=xlwt.easyxf('border: top medium, bottom medium, right thin'))
    #     worksheet.write(69, 21, style=xlwt.easyxf('border: bottom medium, right thin'))
    #     worksheet.write(70, 21, style=xlwt.easyxf('border: bottom medium, right thin'))
    #
    #     for row in range(first_row, 68):
    #         worksheet.write(row, 22, style=xlwt.easyxf('border: right thin'))
    #
    #     worksheet.write(68, 22, style=xlwt.easyxf('border: top medium, bottom medium, right thin'))
    #     worksheet.write(69, 22, style=xlwt.easyxf('border: bottom medium, right thin'))
    #     worksheet.write(70, 22, style=xlwt.easyxf('border: bottom medium, right thin'))
    #
    #     for row in range(first_row, 68):
    #         worksheet.write(row, 23, style=xlwt.easyxf('border: right thin'))
    #
    #     worksheet.write(68, 23, style=xlwt.easyxf('border: top medium, bottom medium, right thin'))
    #     worksheet.write(69, 23, style=xlwt.easyxf('border: bottom medium, right thin'))
    #     worksheet.write(70, 23, style=xlwt.easyxf('border: bottom medium, right thin'))
    #
    #     for row in range(first_row, 68):
    #         worksheet.write(row, 24, style=xlwt.easyxf('border: right thin'))
    #
    #     worksheet.write(68, 24, style=xlwt.easyxf('border: top medium, bottom medium, right thin'))
    #     worksheet.write(69, 24, style=xlwt.easyxf('border: bottom medium, right thin'))
    #     worksheet.write(70, 24, style=xlwt.easyxf('border: bottom medium, right thin'))
    #
    #     for row in range(first_row, 68):
    #         worksheet.write(row, 25, style=xlwt.easyxf('border: right thin'))
    #
    #     worksheet.write(68, 25, style=xlwt.easyxf('border: top medium, bottom medium, right thin'))
    #     worksheet.write(69, 25, style=xlwt.easyxf('border: bottom medium, right thin'))
    #     worksheet.write(70, 25, style=xlwt.easyxf('border: bottom medium, right thin'))
    #
    #     for row in range(first_row, 68):
    #         worksheet.write(row, 26, style=xlwt.easyxf('border: right thin'))
    #
    #     worksheet.write(68, 26, style=xlwt.easyxf('border: top medium, bottom medium, right thin'))
    #     worksheet.write(69, 26, style=xlwt.easyxf('border: bottom medium, right thin'))
    #     worksheet.write(70, 26, style=xlwt.easyxf('border: bottom medium, right thin'))
    #
    #     for row in range(first_row, 68):
    #         worksheet.write(row, 27, style=xlwt.easyxf('border: right thin'))
    #
    #     worksheet.write(68, 27, style=xlwt.easyxf('border: top medium, bottom medium, right thin'))
    #     worksheet.write(69, 27, style=xlwt.easyxf('border: bottom medium, right thin'))
    #     worksheet.write(70, 27, style=xlwt.easyxf('border: bottom medium, right thin'))
    #
    #     for row in range(first_row, 68):
    #         worksheet.write(row, 28, style=xlwt.easyxf('border: right medium'))
    #
    #     worksheet.write(68, 28, style=xlwt.easyxf('border: top medium, bottom medium, right medium'))
    #     worksheet.write(69, 28, style=xlwt.easyxf('border: bottom medium, right medium'))
    #     worksheet.write(70, 28, style=xlwt.easyxf('border: bottom medium, right medium'))
    #     #
    #     # # ===============================Table For Expenses===============================================
    #     # worksheet.write_merge(72, 72, 0, 14, "For Expenses",
    #     #                       style=xlwt.easyxf('font: name Liberation Sans, bold on,color Gold; '
    #     #                                         'align: horiz center; '
    #     #                                         'pattern: pattern solid, fore_colour 0x31;'))
    #     #
    #     # worksheet.write_merge(73, 74, 0, 0, "Date", style=xlwt.easyxf('font: name Liberation Sans, bold on,'
    #     #                                                               'color black; align: horiz center, vert center;'
    #     #                                                               'border: top medium, left medium, right medium,'
    #     #                                                               'bottom medium'))
    #     #
    #     # worksheet.write_merge(73, 74, 1, 3, "Description",
    #     #                       style=xlwt.easyxf('font: name Liberation Sans, bold on,color black;'
    #     #                                         'align: horiz center, vert center;'
    #     #                                         'border: top medium, left medium, right medium, bottom medium'))
    #     #
    #     # worksheet.write_merge(73, 74, 4, 6, "Employee",
    #     #                       style=xlwt.easyxf('font: name Liberation Sans, bold on, color black;'
    #     #                                         'align: horiz center, vert center;'
    #     #                                         'border: top medium, left medium, right medium, bottom medium'))
    #     #
    #     # worksheet.write_merge(73, 74, 7, 10, "Product",
    #     #                       style=xlwt.easyxf('font: name Liberation Sans, bold on, color black;'
    #     #                                         'align: horiz center, vert center;'
    #     #                                         'border: top medium, left medium, right medium, bottom medium'))
    #     #
    #     # worksheet.write_merge(73, 74, 11, 11, "Quantity",
    #     #                       style=xlwt.easyxf('font: name Liberation Sans, bold on, color black;'
    #     #                                         'align: horiz center, vert center;'
    #     #                                         'border: top medium, left medium, right medium, bottom medium'))
    #     #
    #     # worksheet.write_merge(73, 74, 12, 12, "Unit Price",
    #     #                       style=xlwt.easyxf('font: name Liberation Sans, bold on, color black;'
    #     #                                         'align: horiz center, vert center;'
    #     #                                         'border: top medium, left medium, right medium, bottom medium'))
    #     #
    #     # worksheet.write_merge(73, 74, 13, 14, "Subtotal",
    #     #                       style=xlwt.easyxf('font: name Liberation Sans, bold on, color black;'
    #     #                                         'align: horiz center, vert center;'
    #     #                                         'border: top medium, left medium, right medium, bottom medium'))
    #     # #
    #     # # row = 75
    #     # # for rec in self.expense_id:
    #     # #     worksheet.write(row, 0, rec.)
    #     # #     worksheet.write_merge(row, row, 0, 2, rec.description)
    #     # #     worksheet.write_merge(row, row, 3, 5, rec.)
    #     # #
    #
    #     fp = io.BytesIO()
    #     workbook.save(fp)
    #
    #     self.excel_file = base64.encodestring(fp.getvalue())
    #     self.file_name = filename

    def create_job_cost_report(self):
        self.get_job_cost_report()

        my_file = self.env['job.cost.excel.report'].create({
            'job_cost_excel_file': self.excel_file,
            'job_cost_excel_file_name': self.file_name,
        })
        view_id = self.env.ref('thailand_erp_customization.get_jobcost_report_wizard_view')
        return {
            'res_id': my_file.id,
            'res_model': 'job.cost.excel.report',
            'target': 'new',
            'type': 'ir.actions.act_window',
            'view_id': view_id.id,
            'view_mode': 'form',
        }

    def get_job_cost_report(self):
        """
            To create job cost excel report
        :return:
        """
        filename = str(self.name) + '.xls'
        workbook = xlwt.Workbook()
        worksheet = workbook.add_sheet('JobCost')

        # To add company logo in job cost sheet excel report
        if self.sale_order_id.company_id.logo:
            fh = open("/tmp/imageToSave.png", "wb")
            fh.write(base64.b64decode(self.sale_order_id.company_id.logo))
            fh.close()
            os.chmod("/tmp/imageToSave.png", 0o777)
            # open the image with PIL

            im = Image.open('/tmp/imageToSave.png').convert("RGB")

            file_out = "/tmp/imageTosave.bmp"
            im.save(file_out)
            im_resize = Image.open('/tmp/imageTosave.bmp')
            resize_width, resize_height = im_resize.size
            new_im_reszie = im_resize.resize((95, 85), Image.ANTIALIAS)
            new_im_reszie.save('/tmp/imageTosave.bmp')

            worksheet.insert_bitmap('/tmp/imageTosave.bmp', 0, 0,)

        xlwt.add_palette_colour("blue", 0x0C)
        workbook.set_colour_RGB(0x0C, 44, 58, 178)

        xlwt.add_palette_colour("red", 0x0A)
        workbook.set_colour_RGB(0x0A, 229, 28, 41)

        # To add company address in job cost sheet
        first_row = 0
        if self.sale_order_id.company_id.name:
            worksheet.write(first_row, 7, self.sale_order_id.company_id.name,
                            style=xlwt.easyxf('font: name Liberation Sans, bold on, color Green; '))
            first_row += 1

        if self.sale_order_id.company_id.street:
            worksheet.write(first_row, 7, self.sale_order_id.company_id.street)
            first_row += 1

        if self.sale_order_id.company_id.street2:
            worksheet.write(first_row, 7, self.sale_order_id.company_id.street2)
            first_row += 1

        addr = ''
        if self.sale_order_id.company_id.city:
            addr += str(self.sale_order_id.company_id.city) + ", "

        if self.sale_order_id.company_id.state_id:
            addr += str(self.sale_order_id.company_id.state_id.name) + ", "

        if self.sale_order_id.company_id.zip:
            addr += str(self.sale_order_id.company_id.zip) + ", "

        if self.sale_order_id.company_id.country_id:
            addr += str(self.sale_order_id.company_id.country_id.name)

        worksheet.write(first_row, 7, addr)
        first_row += 1

        if self.sale_order_id.company_id.phone:
            worksheet.write(first_row, 7, "Tel. " + self.sale_order_id.company_id.phone)

        style_header = xlwt.easyxf(
            "font:height 200; font: name Liberation Sans, bold on,color black; align: horiz center, vert center")
        style_table_header = xlwt.easyxf(
            "font: name Liberation Sans, color black; align: horiz left")
        header_fill_yellow_style = xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
                                               'align: horiz center; '
                                               'pattern: pattern solid, fore_colour yellow;')
        table_heading = xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
                                    'align: horiz center,vert center; '
                                    'border: left thin, top thin, right thin, bottom thin')

        add_border = xlwt.easyxf('border: left thin, top thin, right thin, bottom thin')

        worksheet.row(7).height_mismatch = True
        worksheet.row(7).height = 300
        worksheet.col(0).width = 15 * 300
        worksheet.col(7).width = 15 * 300
        worksheet.col(15).width = 15 * 70
        worksheet.col(1).width = 15 * 350
        worksheet.col(8).width = 15 * 350

        worksheet.write_merge(7, 7, 0, 9, "PROJECT / JOB COST", style=style_header)
        worksheet.write(9, 0, "SDS Job No.:")
        worksheet.write(10, 0, "Client Name:")
        worksheet.write(11, 0, "Project Name:")
        worksheet.write(12, 0, "PO&Qut. No.:")

        worksheet.write(9, 7, "Date of Date:")
        worksheet.write(10, 7, "Delivery Date:")
        worksheet.write(11, 7, "Term of Delivery:")
        worksheet.write(12, 7, "Warranty Term:")

        worksheet.write(9, 1, '', style=xlwt.easyxf('font: name Liberation Sans, bold on; '
                                                    'border: bottom medium'))
        worksheet.write(10, 1, str(self.partner_id.name), style=xlwt.easyxf('font: name Liberation Sans; '
                                                                            'border: bottom medium'))
        worksheet.write(11, 1, str(self.project_id.name), style=xlwt.easyxf('font: name Liberation Sans; '
                                                                            'border: bottom medium'))
        worksheet.write(12, 1, '', style=xlwt.easyxf('font: name Liberation Sans; '
                                                     'border: bottom medium'))

        if self.date and self.delivery_date:  # to calculate months
            first_date = self.date.strftime('%Y-%m-%d %H:%M:%S')
            last_date = self.delivery_date.strftime('%Y-%m-%d %H:%M:%S')

            date1 = datetime.strptime(str(first_date), '%Y-%m-%d %H:%M:%S').date()
            date2 = datetime.strptime(str(last_date), '%Y-%m-%d %H:%M:%S').date()
            r = relativedelta.relativedelta(date2, date1)
            self.delivery_date_months = str(r.months) + " Month"
        if self.date:
            worksheet.write(9, 8, str(self.date.strftime('%d/%m/%Y')),
                            style=xlwt.easyxf('font:name Liberation Sans, bold on,color blue;border: bottom medium'))
        else:
            worksheet.write(9, 8, '',style=xlwt.easyxf('font:name Liberation Sans, bold on,color blue;border: bottom medium'))

        if self.delivery_date:
            worksheet.write(10, 8, self.delivery_date_months, style=xlwt.easyxf('font:name Liberation Sans, '
                                                                                'bold on,color blue;border: bottom medium'))
        else:
            worksheet.write(10, 8, '', style=xlwt.easyxf('font:name Liberation Sans, '
                                                         'bold on,color blue;border: bottom medium'))

        if not self.term_of_delivery:
            self.term_of_delivery = ""
        worksheet.write(11, 8, str(self.term_of_delivery), style=xlwt.easyxf('font:name Liberation Sans, '
                                                                             'bold on,color blue;border: bottom medium'))

        if self.warrant_term:
            worksheet.write(12, 8, str(self.warrant_term.name), style=xlwt.easyxf('font:name Liberation Sans, '
                                                                                  'bold on,color blue;border: bottom medium'))
        else:
            worksheet.write(12, 8, '', style=xlwt.easyxf('font:name Liberation Sans, '
                                                                                  'bold on,color blue;border: bottom medium'))

        #  ==================================Table For Sale & Project Management=====================================
        worksheet.write_merge(14, 14, 0, 14, "For Sale & Project Management", style=header_fill_yellow_style)
        worksheet.write_merge(15, 16, 0, 5, "Sell Price (THB)",
                              style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
                                                'align: horiz center,vert center; '
                                                'border: left medium, top medium, right medium, bottom medium'))
        worksheet.write_merge(15, 16, 6, 6, "Billing Date",
                              style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
                                                'align: horiz center,vert center; '
                                                'border: top medium, right medium, bottom medium'))
        worksheet.write_merge(15, 15, 7, 8, "Sell Price",
                              style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
                                                'align: horiz center,vert center; '
                                                'border: left medium, top medium, right medium, bottom thin'))
        worksheet.write(16, 7, "Bath",
                        style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
                                          'align: horiz center,vert center; '
                                          'border: left medium, top thin, right thin, bottom medium'))
        worksheet.write(16, 8, "%",
                        style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
                                          'align: horiz center,vert center; '
                                          'border: left thin, top thin, right medium, bottom medium'))

        worksheet.write_merge(15, 15, 9, 10, "Project",
                              style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
                                                'align: horiz center,vert center; '
                                                'border: left medium, top medium, right medium, bottom thin'))
        worksheet.write(16, 9, "Bath",
                        style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
                                          'align: horiz center,vert center; '
                                          'border: left medium, top thin, right thin, bottom medium'))
        worksheet.write(16, 10, "%",
                        style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
                                          'align: horiz center,vert center; '
                                          'border: left thin, top thin, right medium, bottom medium'))

        worksheet.write_merge(15, 15, 11, 12, "Rev.1",
                              style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
                                                'align: horiz center,vert center; '
                                                'border: left medium, top medium, right medium, bottom thin'))
        worksheet.write(16, 11, "Bath",
                        style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
                                          'align: horiz center,vert center; '
                                          'border: left medium, top thin, right thin, bottom medium'))
        worksheet.write(16, 12, "%",
                        style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
                                          'align: horiz center,vert center; '
                                          'border: left thin, top thin, right medium, bottom medium'))

        worksheet.write_merge(15, 15, 13, 14, "Actual",
                              style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
                                                'align: horiz center,vert center; '
                                                'border: left medium, top medium, right medium, bottom thin'))
        worksheet.write(16, 13, "Bath",
                        style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
                                          'align: horiz center,vert center; '
                                          'border: left medium, top thin, right thin, bottom medium'))
        worksheet.write(16, 14, "%",
                        style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
                                          'align: horiz center,vert center; '
                                          'border: left thin, top thin, right medium, bottom medium'))
        worksheet.write_merge(17,17, 0, 5, "Sell Price (THB)",
                              style=xlwt.easyxf('font: name Liberation Sans, bold on,color blue; '
                                                'align: horiz left; '
                                                'border: left medium, right medium'))
        worksheet.write_merge(18, 18, 0, 5, "Customer Payment Terms",
                              style=xlwt.easyxf('font: name Liberation Sans, bold on,color blue; '
                                                'align: horiz left; '
                                                'border: left medium, right medium'))
        worksheet.write_merge(19, 19, 1, 5, "Portion A Hardware",
                              style=xlwt.easyxf('font: name Liberation Sans, bold on,color blue; '
                                                'align: horiz left; '
                                                'border: left medium, right medium'))
        worksheet.write_merge(20, 20, 1, 5, "Portion A All Materials",
                              style=xlwt.easyxf('font: name Liberation Sans,color black; '
                                                'align: horiz left; '
                                                'border: left medium, right medium'))
        worksheet.write_merge(21, 21, 1, 5, "Portion B Engineering",
                              style=xlwt.easyxf('font: name Liberation Sans, bold on,color blue; '
                                                'align: horiz left; '
                                                'border: left medium, right medium'))
        worksheet.write_merge(22, 22, 1, 5, "Portion A All Overhead Cost",
                              style=xlwt.easyxf('font: name Liberation Sans,color black; '
                                                'align: horiz left; '
                                                'border: left medium, right medium'))
        worksheet.write(20, 7, str(self.total_sale_price),
                        style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
                                          'align: horiz center,vert center; '
                                          'border: left medium, top thin, right thin, bottom medium'))
        worksheet.write(22, 7, str(self.total_overhead_price),
                        style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
                                          'align: horiz center,vert center; '
                                          'border: left medium, top thin, right thin, bottom medium'))
        first_row = 23
        for row in range(first_row, 31):
            worksheet.write(row, 5, style=xlwt.easyxf('border: right medium'))
            worksheet.write(row, 0, style=xlwt.easyxf('border: left medium'))
            # worksheet.write(row, 5, style=xlwt.easyxf('border: left medium'))
            # worksheet.write(row, 5, style=xlwt.easyxf('border: left medium'))
            # worksheet.write(row, 5, style=xlwt.easyxf('border: left medium'))
            # worksheet.write(row, 5, style=xlwt.easyxf('border: left medium'))
            # worksheet.write(row, 5, style=xlwt.easyxf('border: left medium'))
            # worksheet.write(row, 5, style=xlwt.easyxf('border: left medium'))


        worksheet.write(31, 5, style=xlwt.easyxf('border: right medium,bottom thin, top thin'))

        worksheet.write(32, 5, style=xlwt.easyxf('border: right medium, bottom medium'))
        worksheet.write(32, 4, "Total Receive(THB)",
                        style=xlwt.easyxf(
                            'border: bottom medium; font: name Liberation Sans, bold on,color black;'))

        for col in range(1, 4):
            worksheet.write(32, col, style=xlwt.easyxf('border: bottom medium'))

        worksheet.write(32, 0, style=xlwt.easyxf('border: bottom medium, left medium'))

        for col in range(1, 5):
            worksheet.write(31, col, style=xlwt.easyxf('border: bottom thin, top thin'))

        worksheet.write(31, 0, style=xlwt.easyxf('border: bottom thin, top thin, left medium'))

        for row in range(first_row, 31):
            worksheet.write(row, 6, style=xlwt.easyxf('border: right medium'))

        worksheet.write(31, 6, style=xlwt.easyxf('border: right medium, bottom thin, top thin'))
        worksheet.write(32, 6, style=xlwt.easyxf('border: right medium, bottom medium'))

        # for row in range(first_row, 31):
        #     worksheet.write(row, 7, style=xlwt.easyxf('border: right thin'))

        worksheet.write(31, 7, style=xlwt.easyxf('border: right thin, bottom thin, top thin'))
        worksheet.write(32, 7, style=xlwt.easyxf('border: right thin, bottom medium'))

        for row in range(first_row, 31):
            worksheet.write(row, 8, style=xlwt.easyxf('border: right medium'))

        worksheet.write(31, 8, style=xlwt.easyxf('border: right medium, bottom thin, top thin'))
        worksheet.write(32, 8, style=xlwt.easyxf('border: right medium, bottom medium'))

        for row in range(first_row, 31):
            worksheet.write(row, 9, style=xlwt.easyxf('border: right thin'))

        worksheet.write(31, 9, style=xlwt.easyxf('border: right thin, bottom thin, top thin'))
        worksheet.write(32, 9, style=xlwt.easyxf('border: right thin, bottom medium'))

        for row in range(first_row, 31):
            worksheet.write(row, 10, style=xlwt.easyxf('border: right medium'))

        worksheet.write(31, 10, style=xlwt.easyxf('border: right medium, bottom thin, top thin'))
        worksheet.write(32, 10, style=xlwt.easyxf('border: right medium, bottom medium'))

        for row in range(first_row, 31):
            worksheet.write(row, 11, style=xlwt.easyxf('border: right thin'))

        worksheet.write(31, 11, style=xlwt.easyxf('border: right thin, bottom thin, top thin'))
        worksheet.write(32, 11, style=xlwt.easyxf('border: right thin, bottom medium'))

        for row in range(first_row, 31):
            worksheet.write(row, 12, style=xlwt.easyxf('border: right medium'))

        worksheet.write(31, 12, style=xlwt.easyxf('border: right medium, bottom thin, top thin'))
        worksheet.write(32, 12, style=xlwt.easyxf('border: right medium, bottom medium'))

        for row in range(first_row, 31):
            worksheet.write(row, 13, style=xlwt.easyxf('border: right thin'))

        worksheet.write(31, 13, style=xlwt.easyxf('border: right thin, bottom thin, top thin'))
        worksheet.write(32, 13, style=xlwt.easyxf('border: right thin, bottom medium'))

        for row in range(first_row, 31):
            worksheet.write(row, 14, style=xlwt.easyxf('border: right medium'))

        worksheet.write(31, 14, style=xlwt.easyxf('border: right medium, bottom thin, top thin'))
        worksheet.write(32, 14, style=xlwt.easyxf('border: right medium, bottom medium'))

        worksheet.write_merge(34, 35, 0, 5, "Cost & Account Payment (AP)",
                              style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
                                                'align: horiz center,vert center; '
                                                'border: left medium, top medium, right medium, bottom medium'))
        worksheet.write_merge(34, 35, 6, 6, "Billing Date",
                              style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
                                                'align: horiz center,vert center; '
                                                'border: top medium, right medium, bottom medium'))
        worksheet.write_merge(34, 34, 7, 8, "Budget",
                              style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
                                                'align: horiz center,vert center; '
                                                'border: left medium, top medium, right medium, bottom thin'))
        worksheet.write(35, 7, "Bath",
                        style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
                                          'align: horiz center,vert center; '
                                          'border: left medium, top thin, right thin, bottom medium'))
        worksheet.write(35, 8, "%",
                        style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
                                          'align: horiz center,vert center; '
                                          'border: left thin, top thin, right medium, bottom medium'))

        worksheet.write_merge(34, 34, 9, 10, "Budget",
                              style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
                                                'align: horiz center,vert center; '
                                                'border: left medium, top medium, right medium, bottom thin'))
        worksheet.write(35, 9, "Bath",
                        style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
                                          'align: horiz center,vert center; '
                                          'border: left medium, top thin, right thin, bottom medium'))
        worksheet.write(35, 10, "%",
                        style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
                                          'align: horiz center,vert center; '
                                          'border: left thin, top thin, right medium, bottom medium'))

        worksheet.write_merge(34, 34, 11, 12, "Budget",
                              style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
                                                'align: horiz center,vert center; '
                                                'border: left medium, top medium, right medium, bottom thin'))
        worksheet.write(35, 11, "Bath",
                        style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
                                          'align: horiz center,vert center; '
                                          'border: left medium, top thin, right thin, bottom medium'))
        worksheet.write(35, 12, "%",
                        style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
                                          'align: horiz center,vert center; '
                                          'border: left thin, top thin, right medium, bottom medium'))

        worksheet.write_merge(34, 34, 13, 14, "Actual",
                              style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
                                                'align: horiz center,vert center; '
                                                'border: left medium, top medium, right medium, bottom thin'))
        worksheet.write(35, 13, "Bath",
                        style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
                                          'align: horiz center,vert center; '
                                          'border: left medium, top thin, right thin, bottom medium'))
        worksheet.write(35, 14, "%",
                        style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
                                          'align: horiz center,vert center; '
                                          'border: left thin, top thin, right medium, bottom medium'))
        worksheet.write_merge(36, 36, 0, 5, "Cost of Goods",
                              style=xlwt.easyxf('font: name Liberation Sans, bold on,color blue; '
                                                'align: horiz left; '
                                                'border: left medium, right medium'))
        worksheet.write_merge(37, 37, 0, 5, "Cost of Job Order Goods",
                              style=xlwt.easyxf('font: name Liberation Sans, bold on,color blue; '
                                                'align: horiz left; '
                                                'border: left medium, right medium'))

        first_row = 38
        for row in range(first_row, 68):
            worksheet.write(row, 5, style=xlwt.easyxf('border: right medium'))
            worksheet.write(row, 0, style=xlwt.easyxf('border: left medium'))

        worksheet.write(68, 0, style=xlwt.easyxf('border: left medium,top medium;'))
        worksheet.write(69, 0, style=xlwt.easyxf('border: left medium,bottom thin, top thin;'))
        worksheet.write(70, 0, style=xlwt.easyxf('border: left medium,bottom medium;'))

        worksheet.write_merge(68, 68, 5, 6, "Total Cost (THB)",
                              style=xlwt.easyxf('border: right medium, top medium; '
                                                'font: name Liberation Sans, bold on,color black;'))
        worksheet.write_merge(69, 69, 5, 6, "Gross Profit (THB)",
                              style=xlwt.easyxf('border: right medium,bottom thin, top thin;'
                                                'font: name Liberation Sans, bold on,color black;'))
        worksheet.write_merge(70, 70, 5, 6, "Gross Profit (%)",
                              style=xlwt.easyxf('border: right medium, bottom medium;'
                                                'font: name Liberation Sans, bold on,'
                                                'color black;'))
        first_col = 1
        for col in range(first_col, 5):
            worksheet.write(70, col, style=xlwt.easyxf('border: bottom medium;'))

        for col in range(first_col, 5):
            worksheet.write(68, col, style=xlwt.easyxf('border: top medium'))

        for col in range(first_col, 5):
            worksheet.write(69, col, style=xlwt.easyxf('border: bottom thin, top thin'))

        for row in range(first_row, 68):
            worksheet.write(row, 6, style=xlwt.easyxf('border: right medium'))

        for row in range(first_row, 68):
            worksheet.write(row, 7, style=xlwt.easyxf('border: right thin'))

        worksheet.write(68, 7, style=xlwt.easyxf('border: right thin, top medium'))
        worksheet.write(69, 7, style=xlwt.easyxf('border: right thin, bottom thin, top thin'))
        worksheet.write(70, 7, style=xlwt.easyxf('border: right thin, bottom medium'))

        for row in range(first_row, 68):
            worksheet.write(row, 8, style=xlwt.easyxf('border: right medium'))

        worksheet.write(68, 8, style=xlwt.easyxf('border: right medium, top medium'))
        worksheet.write(69, 8, style=xlwt.easyxf('border: right medium, bottom thin, top thin'))
        worksheet.write(70, 8, style=xlwt.easyxf('border: right medium, bottom medium'))

        for row in range(first_row, 68):
            worksheet.write(row, 9, style=xlwt.easyxf('border: right thin'))

        worksheet.write(68, 9, style=xlwt.easyxf('border: right thin, top medium'))
        worksheet.write(69, 9, style=xlwt.easyxf('border: right thin, bottom thin, top thin'))
        worksheet.write(70, 9, style=xlwt.easyxf('border: right thin, bottom medium'))

        for row in range(first_row, 68):
            worksheet.write(row, 10, style=xlwt.easyxf('border: right medium'))

        worksheet.write(68, 10, style=xlwt.easyxf('border: right medium, top medium'))
        worksheet.write(69, 10, style=xlwt.easyxf('border: right medium, bottom thin, top thin'))
        worksheet.write(70, 10, style=xlwt.easyxf('border: right medium, bottom medium'))

        for row in range(first_row, 68):
            worksheet.write(row, 11, style=xlwt.easyxf('border: right thin'))

        worksheet.write(68, 11, style=xlwt.easyxf('border: right thin, top medium'))
        worksheet.write(69, 11, style=xlwt.easyxf('border: right thin, bottom thin, top thin'))
        worksheet.write(70, 11, style=xlwt.easyxf('border: right thin, bottom medium'))

        for row in range(first_row, 68):
            worksheet.write(row, 12, style=xlwt.easyxf('border: right medium'))

        worksheet.write(68, 12, style=xlwt.easyxf('border: right medium, top medium'))
        worksheet.write(69, 12, style=xlwt.easyxf('border: right medium, bottom thin, top thin'))
        worksheet.write(70, 12, style=xlwt.easyxf('border: right medium, bottom medium'))

        for row in range(first_row, 68):
            worksheet.write(row, 13, style=xlwt.easyxf('border: right thin'))

        worksheet.write(68, 13, style=xlwt.easyxf('border: right thin, top medium'))
        worksheet.write(69, 13, style=xlwt.easyxf('border: right thin, bottom thin, top thin'))
        worksheet.write(70, 13, style=xlwt.easyxf('border: right thin, bottom medium'))

        for row in range(first_row, 68):
            worksheet.write(row, 14, style=xlwt.easyxf('border: right medium'))

        worksheet.write(68, 14, style=xlwt.easyxf('border: right medium, top medium'))
        worksheet.write(69, 14, style=xlwt.easyxf('border: right medium, bottom thin, top thin'))
        worksheet.write(70, 14, style=xlwt.easyxf('border: right medium, bottom medium'))

        # ===============================Table For Accounting & Finance===============================================
        xlwt.add_palette_colour("bcolour", 0x2C)
        workbook.set_colour_RGB(0x2C, 150, 192, 229)
        worksheet.write_merge(14, 14, 16, 28, "For Accounting and Finance",
                              style=xlwt.easyxf('font: name Liberation Sans, bold on,color blue; '
                                                'align: horiz center; '
                                                'pattern: pattern solid, fore_colour bcolour;'))
        worksheet.write_merge(15, 15, 16, 19, "Customer Receive",
                              style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
                                                'align: horiz center,vert center; '
                                                'border: left medium, top medium, right medium, bottom thin'))
        worksheet.write_merge(16, 16, 16, 17, "Inv.No.",
                              style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
                                                'align: horiz center,vert center; '
                                                'border: left medium, top thin, right thin, bottom medium'))
        worksheet.write(16, 18, "Date",
                        style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
                                          'align: horiz center,vert center; '
                                          'border: left thin, top thin, right thin, bottom medium'))
        worksheet.write(16, 19, "",
                        style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
                                          'align: horiz center,vert center; '
                                          'border: left thin, top thin, right medium, bottom medium'))

        worksheet.write_merge(15, 15, 20, 28, "Actual Receive",
                              style=xlwt.easyxf('font: name Liberation Sans, bold on,color blue; '
                                                'align: horiz center,vert center; '
                                                'border: left medium, top medium, right medium, bottom thin'))
        worksheet.write(16, 20, "Advance",
                        style=xlwt.easyxf('font: name Liberation Sans, bold on,color red; '
                                          'align: horiz center,vert center; '
                                          'border: left medium, top thin, right thin, bottom medium'))
        worksheet.write(16, 21, "",
                        style=xlwt.easyxf('font: name Liberation Sans, bold on,color dark_blue; '
                                          'align: horiz center,vert center; '
                                          'border: left thin, top thin, right thin, bottom medium'))
        worksheet.write(16, 22, "",
                        style=xlwt.easyxf('font: name Liberation Sans, bold on,color dark_blue; '
                                          'align: horiz center,vert center; '
                                          'border: left thin, top thin, right thin, bottom medium'))
        worksheet.write(16, 23, "",
                        style=xlwt.easyxf('font: name Liberation Sans, bold on,color dark_blue; '
                                          'align: horiz center,vert center; '
                                          'border: left thin, top thin, right thin, bottom medium'))
        worksheet.write(16, 24, "",
                        style=xlwt.easyxf('font: name Liberation Sans, bold on,color dark_blue; '
                                          'align: horiz center,vert center; '
                                          'border: left thin, top thin, right thin, bottom medium'))
        worksheet.write(16, 25, "",
                        style=xlwt.easyxf('font: name Liberation Sans, bold on,color dark_blue; '
                                          'align: horiz center,vert center; '
                                          'border: left thin, top thin, right thin, bottom medium'))
        worksheet.write(16, 26, "",
                        style=xlwt.easyxf('font: name Liberation Sans, bold on,color dark_blue; '
                                          'align: horiz center,vert center; '
                                          'border: left thin, top thin, right thin, bottom medium'))
        worksheet.write(16, 27, "",
                        style=xlwt.easyxf('font: name Liberation Sans, bold on,color dark_blue; '
                                          'align: horiz center,vert center; '
                                          'border: left thin, top thin, right thin, bottom medium'))
        worksheet.write(16, 28, "",
                        style=xlwt.easyxf('font: name Liberation Sans, bold on,color dark_blue; '
                                          'align: horiz center,vert center; '
                                          'border: left thin, top thin, right medium, bottom medium'))

        first_row = 17
        for row in range(first_row, 31):
            worksheet.write(row, 17, style=xlwt.easyxf('border: right thin'))

        worksheet.write(31, 17, style=xlwt.easyxf('border: right thin, bottom medium, top medium'))

        for row in range(first_row, 31):
            worksheet.write(row, 16, style=xlwt.easyxf('border: left medium'))

        worksheet.write(31, 16, style=xlwt.easyxf('border: left medium, bottom medium, top medium'))

        worksheet.write_merge(32, 32, 16, 18, "Total",
                              style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
                                                'align: horiz center,vert center; '
                                                'border: left medium, top medium, bottom medium'))

        for row in range(first_row, 31):
            worksheet.write(row, 18, style=xlwt.easyxf('border: right thin'))

        worksheet.write(31, 18, style=xlwt.easyxf('border: right thin, bottom medium, top medium'))

        for row in range(first_row, 31):
            worksheet.write(row, 19, style=xlwt.easyxf('border: right medium'))

        worksheet.write(31, 19, style=xlwt.easyxf('border: right medium, bottom medium, top medium'))
        worksheet.write(32, 19, style=xlwt.easyxf('border: right medium, bottom medium, top medium'))

        first_col = 20
        for col in range(first_col, 28):
            worksheet.write(32, col, style=xlwt.easyxf('border: right thin, bottom medium, top medium'))

        worksheet.write(32, 28, style=xlwt.easyxf('border: right medium, bottom medium, top medium'))

        for row in range(first_row, 31):
            worksheet.write(row, 20, style=xlwt.easyxf('border: right thin'))

        worksheet.write(31, 20, style=xlwt.easyxf('border: right thin, bottom medium, top medium'))

        for row in range(first_row, 31):
            worksheet.write(row, 21, style=xlwt.easyxf('border: right thin'))

        worksheet.write(31, 21, style=xlwt.easyxf('border: right thin, bottom medium, top medium'))

        for row in range(first_row, 31):
            worksheet.write(row, 22, style=xlwt.easyxf('border: right thin'))

        worksheet.write(31, 22, style=xlwt.easyxf('border: right thin, bottom medium, top medium'))

        for row in range(first_row, 31):
            worksheet.write(row, 23, style=xlwt.easyxf('border: right thin'))

        worksheet.write(31, 23, style=xlwt.easyxf('border: right thin, bottom medium, top medium'))

        for row in range(first_row, 31):
            worksheet.write(row, 24, style=xlwt.easyxf('border: right thin'))

        worksheet.write(31, 24, style=xlwt.easyxf('border: right thin, bottom medium, top medium'))

        for row in range(first_row, 31):
            worksheet.write(row, 25, style=xlwt.easyxf('border: right thin'))

        worksheet.write(31, 25, style=xlwt.easyxf('border: right thin, bottom medium, top medium'))

        for row in range(first_row, 31):
            worksheet.write(row, 26, style=xlwt.easyxf('border: right thin'))

        worksheet.write(31, 26, style=xlwt.easyxf('border: right thin, bottom medium, top medium'))

        for row in range(first_row, 31):
            worksheet.write(row, 27, style=xlwt.easyxf('border: right thin'))

        worksheet.write(31, 27, style=xlwt.easyxf('border: right thin, bottom medium, top medium'))

        for row in range(first_row, 31):
            worksheet.write(row, 28, style=xlwt.easyxf('border: right medium'))

        worksheet.write(31, 28, style=xlwt.easyxf('border: right medium, bottom medium, top medium'))

        worksheet.write_merge(34, 34, 16, 19, "Payment",
                              style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
                                                'align: horiz center,vert center; '
                                                'border: left medium, top medium, right medium, bottom thin'))
        worksheet.write(35, 16, "Inv.No.",
                        style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
                                          'align: horiz center,vert center; '
                                          'border: left medium, top thin, right thin, bottom medium'))
        worksheet.write(35, 17, "PO",
                        style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
                                          'align: horiz center,vert center; '
                                          'border: top thin, right thin, bottom medium'))
        worksheet.write(35, 18, "Date",
                        style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
                                          'align: horiz center,vert center; '
                                          'border: top thin, right thin, bottom medium'))
        worksheet.write(35, 19, "",
                        style=xlwt.easyxf('font: name Liberation Sans, bold on,color black; '
                                          'align: horiz center,vert center; '
                                          'border: top thin, right thin, bottom medium'))
        worksheet.write_merge(34, 34, 20, 28, "Actual Payment",
                              style=xlwt.easyxf('font: name Liberation Sans, bold on,color blue; '
                                                'align: horiz center,vert center; '
                                                'border: left medium, top medium, right medium, bottom thin'))
        worksheet.write(35, 20, "Advance",
                        style=xlwt.easyxf('font: name Liberation Sans, bold on,color red; '
                                          'align: horiz center,vert center; '
                                          'border: left medium, top thin, right thin, bottom medium'))
        worksheet.write(35, 21, "",
                        style=xlwt.easyxf('font: name Liberation Sans, bold on,color dark_blue; '
                                          'align: horiz center,vert center; '
                                          'border: left thin, top thin, right thin, bottom medium'))
        worksheet.write(35, 22, "",
                        style=xlwt.easyxf('font: name Liberation Sans, bold on,color dark_blue; '
                                          'align: horiz center,vert center; '
                                          'border: left thin, top thin, right thin, bottom medium'))
        worksheet.write(35, 23, "",
                        style=xlwt.easyxf('font: name Liberation Sans, bold on,color dark_blue; '
                                          'align: horiz center,vert center; '
                                          'border: left thin, top thin, right thin, bottom medium'))
        worksheet.write(35, 24, "",
                        style=xlwt.easyxf('font: name Liberation Sans, bold on,color dark_blue; '
                                          'align: horiz center,vert center; '
                                          'border: left thin, top thin, right thin, bottom medium'))
        worksheet.write(35, 25, "",
                        style=xlwt.easyxf('font: name Liberation Sans, bold on,color dark_blue; '
                                          'align: horiz center,vert center; '
                                          'border: left thin, top thin, right thin, bottom medium'))
        worksheet.write(35, 26, "",
                        style=xlwt.easyxf('font: name Liberation Sans, bold on,color dark_blue; '
                                          'align: horiz center,vert center; '
                                          'border: left thin, top thin, right thin, bottom medium'))
        worksheet.write(35, 27, "",
                        style=xlwt.easyxf('font: name Liberation Sans, bold on,color dark_blue; '
                                          'align: horiz center,vert center; '
                                          'border: left thin, top thin, right thin, bottom medium'))
        worksheet.write(35, 28, "",
                        style=xlwt.easyxf('font: name Liberation Sans, bold on,color dark_blue; '
                                          'align: horiz center,vert center; '
                                          'border: left thin, top thin, right medium, bottom medium'))

        first_row = 36
        for row in range(first_row, 68):
            worksheet.write(row, 16, style=xlwt.easyxf('border: right thin, left medium'))

        worksheet.write_merge(68, 68, 16, 18, "Total",
                              style=xlwt.easyxf('border: right thin, top medium, left medium;'
                                                'font: name Liberation Sans, bold on,color black;'))
        worksheet.write_merge(69, 70, 16, 18, "Profit & (-Loss)",
                              style=xlwt.easyxf('border: right thin,bottom medium, top medium, left medium;'
                                                'font: name Liberation Sans, bold on,color black;'))

        for row in range(first_row, 68):
            worksheet.write(row, 17, style=xlwt.easyxf('border: right thin'))

        for row in range(first_row, 68):
            worksheet.write(row, 18, style=xlwt.easyxf('border: right thin'))

        for row in range(first_row, 68):
            worksheet.write(row, 19, style=xlwt.easyxf('border: right medium'))

        worksheet.write(68, 19, style=xlwt.easyxf('border: right medium, top medium, bottom medium'))
        worksheet.write(69, 19, style=xlwt.easyxf('border: bottom medium, right medium'))
        worksheet.write(70, 19, style=xlwt.easyxf('border: bottom medium, right medium'))

        for row in range(first_row, 68):
            worksheet.write(row, 20, style=xlwt.easyxf('border: right thin'))

        worksheet.write(68, 20, style=xlwt.easyxf('border: top medium, bottom medium, right thin'))
        worksheet.write(69, 20, style=xlwt.easyxf('border: bottom medium, right thin'))
        worksheet.write(70, 20, style=xlwt.easyxf('border: bottom medium, right thin'))

        for row in range(first_row, 68):
            worksheet.write(row, 21, style=xlwt.easyxf('border: right thin'))

        worksheet.write(68, 21, style=xlwt.easyxf('border: top medium, bottom medium, right thin'))
        worksheet.write(69, 21, style=xlwt.easyxf('border: bottom medium, right thin'))
        worksheet.write(70, 21, style=xlwt.easyxf('border: bottom medium, right thin'))

        for row in range(first_row, 68):
            worksheet.write(row, 22, style=xlwt.easyxf('border: right thin'))

        worksheet.write(68, 22, style=xlwt.easyxf('border: top medium, bottom medium, right thin'))
        worksheet.write(69, 22, style=xlwt.easyxf('border: bottom medium, right thin'))
        worksheet.write(70, 22, style=xlwt.easyxf('border: bottom medium, right thin'))

        for row in range(first_row, 68):
            worksheet.write(row, 23, style=xlwt.easyxf('border: right thin'))

        worksheet.write(68, 23, style=xlwt.easyxf('border: top medium, bottom medium, right thin'))
        worksheet.write(69, 23, style=xlwt.easyxf('border: bottom medium, right thin'))
        worksheet.write(70, 23, style=xlwt.easyxf('border: bottom medium, right thin'))

        for row in range(first_row, 68):
            worksheet.write(row, 24, style=xlwt.easyxf('border: right thin'))

        worksheet.write(68, 24, style=xlwt.easyxf('border: top medium, bottom medium, right thin'))
        worksheet.write(69, 24, style=xlwt.easyxf('border: bottom medium, right thin'))
        worksheet.write(70, 24, style=xlwt.easyxf('border: bottom medium, right thin'))

        for row in range(first_row, 68):
            worksheet.write(row, 25, style=xlwt.easyxf('border: right thin'))

        worksheet.write(68, 25, style=xlwt.easyxf('border: top medium, bottom medium, right thin'))
        worksheet.write(69, 25, style=xlwt.easyxf('border: bottom medium, right thin'))
        worksheet.write(70, 25, style=xlwt.easyxf('border: bottom medium, right thin'))

        for row in range(first_row, 68):
            worksheet.write(row, 26, style=xlwt.easyxf('border: right thin'))

        worksheet.write(68, 26, style=xlwt.easyxf('border: top medium, bottom medium, right thin'))
        worksheet.write(69, 26, style=xlwt.easyxf('border: bottom medium, right thin'))
        worksheet.write(70, 26, style=xlwt.easyxf('border: bottom medium, right thin'))

        for row in range(first_row, 68):
            worksheet.write(row, 27, style=xlwt.easyxf('border: right thin'))

        worksheet.write(68, 27, style=xlwt.easyxf('border: top medium, bottom medium, right thin'))
        worksheet.write(69, 27, style=xlwt.easyxf('border: bottom medium, right thin'))
        worksheet.write(70, 27, style=xlwt.easyxf('border: bottom medium, right thin'))

        for row in range(first_row, 68):
            worksheet.write(row, 28, style=xlwt.easyxf('border: right medium'))

        worksheet.write(68, 28, style=xlwt.easyxf('border: top medium, bottom medium, right medium'))
        worksheet.write(69, 28, style=xlwt.easyxf('border: bottom medium, right medium'))
        worksheet.write(70, 28, style=xlwt.easyxf('border: bottom medium, right medium'))

        fp = io.BytesIO()
        workbook.save(fp)

        self.excel_file = base64.encodestring(fp.getvalue())
        self.file_name = filename




class HrExpense(models.Model):

    _inherit = 'hr.expense'
    job_cost_id = fields.Many2one('job.cost', 'Job Cost ID')


class AccountAnalyticLines(models.Model):

    _inherit = 'account.analytic.line'
    job_cost_id = fields.Many2one('job.cost', 'Job Cost ID')
    project_id = fields.Many2one('project.project', 'Project ID')
    employee_id = fields.Many2one('hr.employee', 'Employee ID')


class PaymentDetails(models.Model):

    _name = 'payment.details'

    name = fields.Char()
    payment_type = fields.Selection(
        [('outbound', 'Send Money'), ('inbound', 'Receive Money'), ('transfer', 'Internal Transfer')],
        string='Payment Type')
    invoice_id = fields.Many2one('account.move', 'Invoice ID')
    invoice_date = fields.Date('Invoice Date')
    job_cost_id = fields.Many2one('job.cost', 'Job Cost ID')
    note = fields.Char('Note')
    actual_price = fields.Float('Actual Price')
    action = fields.Char('Action')

class BudgetDetails(models.Model):

    _name = 'budget.details'

    job_cost_id = fields.Many2one('job.cost', 'Job Cost ID')
    expense_type = fields.Char('Expenses Type')
    budget = fields.Char('Budget')
    action = fields.Char('Action')

class WarrantTerm(models.Model):

    _name = 'warrant.term'

    name = fields.Char('Name')

class JobCostSaleOrder(models.Model):

    _name = 'job.cost.sale.order'

    job_id=fields.Many2one('job.cost','Job ID')
    sale_order_id=fields.Many2one('sale.order','SO')
    date=fields.Date('Date')
    project_id=fields.Many2one('project.project', 'Project ID')
    total_sale_price=fields.Float('Total Sale Price')

class JobCostOverhead(models.Model):

    _name = 'job.cost.overhead'

    job_id=fields.Many2one('job.cost','Job ID')
    sale_order_id=fields.Many2one('sale.order','SO')
    date=fields.Date('Date')
    project_id=fields.Many2one('project.project', 'Project ID')
    total_overhead_price=fields.Float('Total Overhead Price')



class JobCostPurchaseOrder(models.Model):

    _name = 'job.cost.purchase.order'

    job_id = fields.Many2one('job.cost', 'Job ID')
    purchase_order_id = fields.Many2one('purchase.order', 'PO')
    date = fields.Date('Date')
    project_id = fields.Many2one('project.project', 'Project ID')
    total_purchase_price = fields.Float('Total Purchase Price')
