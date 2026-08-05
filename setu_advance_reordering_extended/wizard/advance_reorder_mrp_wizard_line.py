from odoo import fields, models


class ManufacturingOrderWizardLine(models.TransientModel):
    _name = "advance.reorder.mrp.wizard.line"
    _description = "Advance Reorder Manufacturing Wizard Line"

    wizard_id = fields.Many2one('advance.reorder.mrp.wizard',string='Wizard')

    summary_line_id = fields.Many2one(
        'advance.reorder.orderprocess.summary', string='Summary line', required=True, ondelete='cascade')

    product_id = fields.Many2one(
        related='summary_line_id.product_id', string='Product', store=True)

    order_qty = fields.Integer(related='summary_line_id.order_qty', string='Order Quantity', store=True)