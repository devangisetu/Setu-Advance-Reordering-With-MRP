# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProductProduct(models.Model):
    _inherit = 'product.product'

    reorder_product_classification = fields.Selection(
        selection=[
            ('finished_good', 'Finished Good'),
            ('semi_finished_good', 'Semi-Finished Good'),
            ('raw_material', 'Raw Material'),
            ('other', 'Other'),
        ],
        string='Reorder Classification',
        compute='_compute_reorder_product_classification',
    )

    reorder_bom_id = fields.Many2one(
        'mrp.bom',
        string='Reorder BOM',
        domain="['|', ('product_id', '=', id), '&', ('product_tmpl_id', '=', product_tmpl_id), ('product_id', '=', False), ('active', '=', True)]",
        help='BOM used for MRP component demand calculation.',
        company_dependent=True,
    )

    reorder_bom_type = fields.Selection([
        ('normal', 'Normal'),
        ('kit', 'Kit'),
        ('subcontract', 'Subcontract'),
    ], string="BOM Type",
        compute="_compute_reorder_bom_type",
        store=True)

    demand_planning_type = fields.Selection(
        selection=[
            ('sales_driven', 'Sales Driven'),
            ('production_driven', 'Production Driven'),
            ('combined', 'Combined'),
        ],
        string='Demand Planning Type',
        compute='_compute_demand_planning_type',
        store=True,
        readonly=False,
        help='Defines how demand is calculated in Advance Reordering.',
    )

    is_kit_product = fields.Boolean(
        string="Kit Product",
        compute="_compute_is_kit_product",
        store=True,
    )

    is_kit_component = fields.Boolean(
        string="Kit Component",
        compute="_compute_is_kit_component",
    )


    @api.depends('reorder_bom_id', 'reorder_bom_type')
    def _compute_is_kit_product(self):
        """Computes whether the product is configured as a kit product."""
        for product in self:
            product.is_kit_product = (product.reorder_bom_id and product.reorder_bom_type == 'kit')

    def _compute_is_kit_component(self):
        """Computes whether the product is used as a component in any active kit BOM."""
        BomLine = self.env['mrp.bom.line']

        for product in self:
            product.is_kit_component = bool(BomLine.search_count([
                ('product_id', '=', product.id),
                ('bom_id.type', '=', 'phantom'),
                ('bom_id.active', '=', True),
            ]))

    def get_default_bom(self, company_id=None):
        """Returns the default active BOM for the product by sequence."""
        self.ensure_one()

        domain = [
            ('active', '=', True),
            '|',
            ('product_id', '=', self.id),
            '&',
            ('product_tmpl_id', '=', self.product_tmpl_id.id),
            ('product_id', '=', False),
        ]

        if company_id:
            domain += [
                '|',
                ('company_id', '=', company_id),
                ('company_id', '=', False),
            ]

        return self.env['mrp.bom'].search(
            domain,
            order='sequence, id',
            limit=1,
        )


    @api.depends('reorder_product_classification')
    def _compute_demand_planning_type(self):
        """Computes the demand planning type based on the product classification."""
        for product in self:
            demand_type = (
                'production_driven'
                if product.reorder_product_classification in ('semi_finished_good', 'raw_material')
                else 'sales_driven'
            )
            product.demand_planning_type = demand_type

    def _compute_reorder_product_classification(self):
        """Classifies the product as Finished Good, Semi-Finished Good, Raw Material, or Other based on its BOM usage."""
        for product in self:
            has_bom = product.bom_ids
            is_component = product.bom_line_ids
            if has_bom and not is_component:
                classification = 'finished_good'
            elif has_bom and is_component:
                classification = 'semi_finished_good'
            elif not has_bom and is_component:
                classification = 'raw_material'
            else:
                classification = 'other'
            product.reorder_product_classification = classification

    @api.depends('reorder_bom_id', 'reorder_bom_id.type')
    def _compute_reorder_bom_type(self):
        """Computes the custom BOM type from the selected reorder BOM."""
        for product in self:
            product.reorder_bom_type = self.get_bom_type(product.reorder_bom_id)

    def get_bom_type(self, bom):
        """Returns the custom BOM type (Normal, Kit, or Subcontract) for the given BOM."""
        if not bom:
            return False
        if bom.type == 'subcontract':
            return 'subcontract'
        elif bom.type == 'phantom':
            return 'kit'
        return 'normal'