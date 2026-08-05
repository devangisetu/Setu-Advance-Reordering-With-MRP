# -*- coding: utf-8 -*-
from odoo import api, models, _
from odoo.exceptions import UserError


class AdvanceReorderPoVendorWizard(models.TransientModel):
    _inherit = 'advance.reorder.po.vendor.wizard'

    @api.model_create_multi
    def create(self, vals_list):
        """Preloads all purchase demand lines for purchase order generation."""
        records = super().create(vals_list)
        for rec in records:
            if not rec.reorder_process_id:
                continue
            purchase_summaries = rec.reorder_process_id.summary_ids.filtered(
                lambda summary: summary.order_action == 'purchase')
            if not purchase_summaries:
                raise UserError(_('No summary lines are set to Generate Purchase Orders.'))
            rec.line_ids.filtered(
                lambda line: line.summary_line_id not in purchase_summaries
            ).unlink()
            if not rec.line_ids and purchase_summaries:
                rec.line_ids = [(0, 0, {'summary_line_id': summary.id}) for summary in purchase_summaries]
        return records