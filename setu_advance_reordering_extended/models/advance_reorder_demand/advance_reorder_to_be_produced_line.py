# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class AdvanceReorderToBeProducedLine(models.Model):
    _name = 'advance.reorder.to.be.produced.line'
    _description = 'To Be Produced Line'
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
    production_ids = fields.Many2many(
        'mrp.production',
        'advance_reorder_to_be_produced_line_mrp_production_rel',
        'to_be_produced_line_id',
        'production_id',
        string='Manufacturing Orders',
        readonly=True,
        help='Draft MOs producing this product within the reorder date range.',
    )

    bom_id = fields.Many2one(
        'mrp.bom',
        string='Reorder BOM',
        compute='_compute_bom_id',
        store=True,
        domain="['|', ('product_id', '=', id), '&', ('product_tmpl_id', '=', product_tmpl_id), ('product_id', '=', False), ('active', '=', True)]",
        help='BOM used for MRP component demand calculation.',
    )

    bom_type = fields.Selection([
        ('normal', 'Normal'),
        ('kit', 'Kit'),
        ('subcontract', 'Subcontract'),
    ], string="BOM Type",
        compute="_compute_bom_type",
        store=True)

    scrap_qty = fields.Float(string='Scrap Qty',)

    source_line_ids = fields.One2many(
        'advance.reorder.demand.source',
        'to_be_produced_demand_line_id',
        string='Source Products',
    )

    config_id = fields.Many2one(comodel_name='advance.reorder.orderprocess.config',
                                 string='Reorder configuration', help="Reorder configuration")

    @api.depends('product_id')
    def _compute_bom_id(self):
        for record in self:
            record.bom_id = record.product_id.get_default_bom() if record.product_id else False

    @api.depends('bom_id', 'bom_id.type')
    def _compute_bom_type(self):
        for record in self:
            record.bom_type = self.env['product.product'].get_bom_type(record.bom_id)

    @api.depends('bom_id', 'bom_id.type')
    def _compute_reorder_bom_type(self):
        for product in self:
            bom = product.bom_id
            if not bom:
                product.reorder_bom_type = False
            elif bom.type == 'subcontract':
                product.reorder_bom_type = 'subcontract'
            elif bom.type == 'phantom':
                product.reorder_bom_type = 'kit'
            else:
                product.reorder_bom_type = 'normal'


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
                ('to_be_produced_demand_line_id', '=', self.id)
            ],
        }
