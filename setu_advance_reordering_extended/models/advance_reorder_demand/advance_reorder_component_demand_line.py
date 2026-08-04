# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class AdvanceReorderComponentDemandLine(models.Model):
    _name = 'advance.reorder.component.demand.line'
    _description = 'Component Demand Calculation Line'
    _order = 'product_id, id'

    reorder_process_id = fields.Many2one(
        'advance.reorder.orderprocess',
        string='Reorder Process',
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
        help='Available stock across configured warehouse groups.',
    )
    required_qty = fields.Float(
        string='Required Qty',
        help='Merged required quantity from BOM ratios and finished good demand.',
    )
    incoming_qty = fields.Float(
        string='Incoming',
        help='Incoming from PO, ICT, and IWT.',
    )
    net_demand = fields.Float(
        string='Net Demand',
        store=True,
    )
    scrap_qty = fields.Float(string='Scrap Qty',)

    source_line_ids = fields.One2many(
        'advance.reorder.demand.source',
        'component_demand_line_id',
        string='Source Products',
    )

    warehouse_group_id = fields.Many2one('stock.warehouse.group', string="Warehouse group")

    def action_incoming_stock_moves(self):
        self.ensure_one()
        warehouse_groups = self.reorder_process_id.config_ids.mapped('warehouse_group_id')
        stock_location_ids = warehouse_groups.mapped('warehouse_ids.lot_stock_id').ids
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
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Source Products'),
            'res_model': 'advance.reorder.demand.source',
            'view_mode': 'list',
            'target': 'new',
            'domain': [
                ('component_demand_line_id', '=', self.id)
            ],
        }

