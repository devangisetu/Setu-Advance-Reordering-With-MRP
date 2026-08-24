from odoo import api, fields, models


class ManufacturingOrderWizardLine(models.TransientModel):
    _name = "advance.reorder.mrp.wizard.line"
    _description = "Advance Reorder Manufacturing Wizard Line"

    wizard_id = fields.Many2one('advance.reorder.mrp.wizard',string='Wizard')

    summary_line_id = fields.Many2one(
        'advance.reorder.orderprocess.summary', string='Summary line', ondelete='cascade')
    product_wise_summary_line_id = fields.Many2one(
        'advance.reorder.product.wise.order.summary',
        string='Product-Wise Summary line',
        required=False,
        ondelete='cascade',
    )

    product_id = fields.Many2one(
        'product.product',
        string='Product',
        compute='_compute_summary_fields',
        store=True,
    )
    warehouse_group_id = fields.Many2one(
        'stock.warehouse.group',
        string='Warehouse group',
        compute='_compute_summary_fields',
        store=True,
    )
    order_qty = fields.Integer(
        string='Order Quantity',
        compute='_compute_summary_fields',
        store=True,
    )

    @api.depends(
        'summary_line_id',
        'summary_line_id.product_id',
        'summary_line_id.order_qty',
        'summary_line_id.warehouse_group_id',
        'product_wise_summary_line_id',
        'product_wise_summary_line_id.product_id',
        'product_wise_summary_line_id.order_qty',
    )
    def _compute_summary_fields(self):
        for line in self:
            summary = line.summary_line_id or line.product_wise_summary_line_id
            line.product_id = summary.product_id if summary else False
            line.order_qty = summary.order_qty if summary else 0
            line.warehouse_group_id = (
                line.summary_line_id.warehouse_group_id
                if line.summary_line_id
                else False
            )