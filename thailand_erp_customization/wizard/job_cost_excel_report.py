from odoo import fields,models

class JobCostReport(models.TransientModel):

    _name = "job.cost.excel.report"

    job_cost_excel_file = fields.Binary('Job Cost Excel Report')
    job_cost_excel_file_name = fields.Char('Excel File')
