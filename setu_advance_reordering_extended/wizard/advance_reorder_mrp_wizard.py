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
    product_wise_reorder_id = fields.Many2one(
        'advance.reorder.product.wise.process',
        string='Reorder',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
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
        """
        Preloads all production demand lines for manufacturing order generation.
        """
        records = super(ManufacturingOrderWizard, self).create(vals_list)

        for rec in records:
            production_summaries = self.env['advance.reorder.orderprocess.summary']
            if rec.reorder_process_id:
                production_summaries = rec.reorder_process_id.summary_ids.filtered(
                    lambda summary: summary.order_action == 'production')
                rec.company_id = rec.reorder_process_id.company_id
            elif rec.product_wise_reorder_id:
                production_summaries = rec.product_wise_reorder_id.summary_ids.filtered(
                    lambda summary: summary.order_action == 'production')
                rec.company_id = rec.product_wise_reorder_id.company_id
            else:
                continue
            if not production_summaries:
                raise UserError(_("No summary lines are set to Generate Manufacturing Orders."))

            if not rec.line_ids:
                line_vals = []
                for summary in production_summaries:
                    line_vals.append((0, 0, {
                        'summary_line_id': summary.id if summary._name == 'advance.reorder.orderprocess.summary' else False,
                        'product_wise_summary_line_id': summary.id if summary._name == 'advance.reorder.product.wise.order.summary' else False,
                    }))
                rec.line_ids = line_vals

        return records

    def action_confirm(self):
        """Validates the warehouse selection and creates manufacturing orders for the reorder."""
        if not self.warehouse_id:
            raise UserError(_("Please select a warehouse to create manufacturing orders."))
        if self.reorder_process_id:
            self.reorder_process_id.create_manufacturing_orders(self.warehouse_id)
        elif self.product_wise_reorder_id:
            self.product_wise_reorder_id.create_manufacturing_orders(self.warehouse_id)
        else:
            raise UserError(_("No reorder found to create manufacturing orders."))
        return {'type': 'ir.actions.act_window_close'}
