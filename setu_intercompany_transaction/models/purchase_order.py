# -*- coding: utf-8 -*-
from datetime import datetime

from odoo import models, fields, api, _


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    intercompany_transfer_id = fields.Many2one("setu.intercompany.transfer", string="Intercompany Transfer", copy=False,
                                               index=True)

    def _prepare_invoice(self):
        vals = super(PurchaseOrder, self)._prepare_invoice()
        if self.intercompany_transfer_id:
            date = self.date_order.date() or datetime.now().date()
            if date:
                vals.update({'invoice_date': date})
        return vals
