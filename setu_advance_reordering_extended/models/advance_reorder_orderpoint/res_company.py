# -*- coding: utf-8 -*-
from odoo import api, fields, models

class ResCompany(models.Model):
    _inherit = 'res.company'

    @api.model_create_multi
    def create(self, vals_list):
        companies = super(ResCompany, self).create(vals_list)
        products = self.env['product.product'].sudo().search([])
        planning_vals = []
        for company in companies:
            for product in products:
                planning_vals.append({
                    'product_id': product.id,
                    'company_id': company.id,
                    'demand_planning_type': 'sales_driven',
                })
        if planning_vals:
            self.env['product.planning'].sudo().create(planning_vals)
        return companies
