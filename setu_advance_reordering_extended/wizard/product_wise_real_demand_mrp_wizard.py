# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ProductWiseRealDemandMrpWizard(models.TransientModel):
    _name = 'advance.reorder.product.real.demand.mrp.wizard'
    _description = 'Product-Wise Real Demand Manufacturing Wizard'
    _rec_name = 'real_demand_id'

    real_demand_id = fields.Many2one(
        'advance.reorder.product.real.demand',
        string='Product-Wise Real Demand',
        required=True,
    )
    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Warehouse',
    )
    line_ids = fields.One2many(
        'advance.reorder.product.real.demand.mrp.wizard.line',
        'wizard_id',
        string='Products',
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if not rec.real_demand_id:
                continue
            production_summaries = rec.real_demand_id.summary_ids.filtered(
                lambda summary: summary.order_action == 'production'
            )
            if not production_summaries:
                raise UserError(_('No summary lines are set to Generate Manufacturing Orders.'))
            if not rec.line_ids:
                rec.line_ids = [
                    (0, 0, {'summary_line_id': summary.id}) for summary in production_summaries
                ]
        return records

    def action_confirm(self):
        self.ensure_one()
        if not self.warehouse_id:
            raise UserError(_('Please select a warehouse to create manufacturing orders.'))
        self.real_demand_id.create_manufacturing_orders(self.warehouse_id)
        return {'type': 'ir.actions.act_window_close'}


class ProductWiseRealDemandMrpWizardLine(models.TransientModel):
    _name = 'advance.reorder.product.real.demand.mrp.wizard.line'
    _description = 'Product-Wise Real Demand Manufacturing Wizard Line'

    wizard_id = fields.Many2one(
        'advance.reorder.product.real.demand.mrp.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade',
    )
    summary_line_id = fields.Many2one(
        'advance.reorder.product.real.demand.summary',
        string='Summary line',
        required=True,
        ondelete='cascade',
    )
    product_id = fields.Many2one(
        related='summary_line_id.product_id',
        string='Product',
        store=True,
    )
    order_qty = fields.Integer(
        related='summary_line_id.order_qty',
        string='Order Quantity',
        store=True,
    )
