# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class AdvanceReorderProductwiseProducedDemandLine(models.Model):
    _name = 'advance.reorder.productwise.produced.demand.line'
    _description = 'Product-Wise To Be Produced Demand Line'
    _order = 'product_id, id'

    product_wise_reorder_id = fields.Many2one(
        'advance.reorder.product.wise.process',
        string='Product-Wise Real Demand',
        required=True,
        ondelete='cascade',
        index=True,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
    )
    available_qty = fields.Float(
        string='Free Qty',
        help='Available stock across company warehouses.',
    )
    required_qty = fields.Float(
        string='Required Qty',
        help='Merged quantity to produce from BOM ratios and finished good demand.',
    )
    incoming_qty = fields.Float(
        string='Incoming',
        help='Incoming from PO, ICT, and IWT.',
    )
    net_demand = fields.Float(
        string='Net Demand',
        store=True,
    )
    demand_adjustment_qty = fields.Integer(string='To be Produced')
    bom_id = fields.Many2one(
        'mrp.bom',
        string='Reorder BOM',
        help='BOM used for MRP component demand calculation.',
    )
    bom_type = fields.Selection([
        ('normal', 'Normal'),
        ('kit', 'Kit'),
        ('subcontract', 'Subcontract'),
    ], string='BOM Type',
        compute='_compute_bom_type',
        store=True)
    scrap_qty = fields.Float(string='Scrap Qty')
    source_line_ids = fields.One2many(
        'advance.reorder.demand.source',
        'productwise_to_be_produced_demand_line_id',
        string='Source Products',
    )

    @api.depends('bom_id', 'bom_id.type')
    def _compute_bom_type(self):
        """Compute BOM type from the selected BOM."""
        for record in self:
            record.bom_type = self.env['product.product'].get_bom_type(record.bom_id)

    def action_incoming_stock_moves(self):
        """Open pending incoming stock moves for the product across company warehouses."""
        self.ensure_one()
        warehouses = self.product_wise_reorder_id._get_company_warehouses()
        stock_location_ids = warehouses.mapped('lot_stock_id').ids
        move_ids = self.env['stock.move'].search([
            ('product_id', '=', self.product_id.id),
            ('state', 'not in', ['draft', 'cancel', 'done']),
            ('location_dest_id', 'in', stock_location_ids),
        ]).ids
        action = self.env['ir.actions.actions']._for_xml_id(
            'setu_advance_reordering.actions_advance_reorder_stock_move'
        )
        action['domain'] = [('id', 'in', move_ids)]
        return action

    def action_view_source_products(self):
        """Open source products contributing to this to-be-produced demand line."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Source Products'),
            'res_model': 'advance.reorder.demand.source',
            'view_mode': 'list',
            'target': 'new',
            'domain': [
                ('productwise_to_be_produced_demand_line_id', '=', self.id),
            ],
        }
