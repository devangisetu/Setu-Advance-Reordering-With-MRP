from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ManufacturingOrderWizard(models.TransientModel):
    _name = "advance.reorder.mrp.wizard"
    _description = "Advance Reorder Manufacturing Wizard"
    _rec_name = 'reorder_process_id'

    reorder_process_id = fields.Many2one(
        'advance.reorder.orderprocess',
        string='Reorder',
    )

    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Warehouse',
    )

    line_ids = fields.One2many(
        'advance.reorder.mrp.wizard.line',
        'wizard_id',
        string='Products',
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super(ManufacturingOrderWizard, self).create(vals_list)

        for rec in records:
            if not rec.reorder_process_id:
                continue

            production_summaries = rec.reorder_process_id.summary_ids.filtered(
                lambda summary: summary.order_action == 'production')
            if not production_summaries:
                raise UserError(_("No summary lines are set to Generate Manufacturing Orders."))

            if not rec.line_ids:
                rec.line_ids = [(0, 0, {'summary_line_id': summary.id}) for summary in production_summaries]

        return records

    def action_confirm(self):
        if not self.warehouse_id:
            raise UserError(_("Please select a warehouse to create manufacturing orders."))
        self.reorder_process_id.create_manufacturing_orders(self.warehouse_id)
