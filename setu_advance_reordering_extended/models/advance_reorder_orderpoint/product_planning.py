# -*- coding: utf-8 -*-
from odoo import api, fields, models

class ProductPlanning(models.Model):
    _name = 'product.planning'
    _description = 'Product Planning Parameters'
    _rec_name = 'product_id'

    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
        ondelete='cascade',
    )
    product_tmpl_id = fields.Many2one(
        'product.template',
        related='product_id.product_tmpl_id',
        string='Product Template',
        readonly=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )
    reorder_bom_id = fields.Many2one(
        'mrp.bom',
        string='Reorder BOM',
        domain="['|', ('product_id', '=', product_id), '&', ('product_tmpl_id', '=', product_tmpl_id), ('product_id', '=', False), ('active', '=', True)]",
    )
    demand_planning_type = fields.Selection(
        selection=[
            ('sales_driven', 'Sales Driven'),
            ('production_driven', 'Production Driven'),
            ('combined', 'Combined'),
        ],
        string='Demand Planning Type',
        default='sales_driven',
    )

    _sql_constraints = [
        ('product_company_uniq', 'unique (product_id, company_id)', 'The product planning parameters must be unique per product and company!'),
    ]

    def init(self):
        # Auto-create product.planning records for all existing products and companies
        self.env.cr.execute("""
            INSERT INTO product_planning (product_id, company_id, demand_planning_type, create_uid, write_uid, create_date, write_date)
            SELECT p.id, c.id, 'sales_driven', 1, 1, now(), now()
            FROM product_product p
            JOIN product_template pt ON pt.id = p.product_tmpl_id
            CROSS JOIN res_company c
            LEFT JOIN product_planning pp ON pp.product_id = p.id AND pp.company_id = c.id
            WHERE pp.id IS NULL AND p.active = True;
        """)
