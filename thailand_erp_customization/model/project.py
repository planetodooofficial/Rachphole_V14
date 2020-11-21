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

class ProjectInherit(models.Model):
    _inherit = 'project.project'

    location_id=fields.Many2one('stock.location','WH Location')
    warehouse_id=fields.Many2one('stock.warehouse','Warehouse')

    @api.onchange('warehouse_id')
    def _get_wh_location(self):
        if self.warehouse_id:
            self.location_id=self.warehouse_id.lot_stock_id.id
