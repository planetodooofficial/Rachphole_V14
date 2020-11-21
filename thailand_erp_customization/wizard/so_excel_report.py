from odoo import fields,models

class SOReort(models.TransientModel):
    _name = 'so.excel.report'

    so_excel_file = fields.Binary('Sale Quotation Excel Report')
    so_file_name = fields.Char('Excel File')

    boq_excel_file = fields.Binary('BOQ Excel Report')
    boq_file_name = fields.Char('Excel File')

    boq_child_excel_file = fields.Binary('BOQ Child Excel Report')
    boq_child_file_name = fields.Char('Excel File')