# -*- coding: utf-8 -*-
from odoo import api, fields, models

class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.model_create_multi
    def create(self, vals_list):
        products = super(ProductProduct, self).create(vals_list)
        companies = self.env['res.company'].sudo().search([])
        planning_vals = []
        for product in products:
            for company in companies:
                planning_vals.append({
                    'product_id': product.id,
                    'company_id': company.id,
                    'demand_planning_type': 'sales_driven',
                })
        if planning_vals:
            self.env['product.planning'].sudo().create(planning_vals)
        return products
