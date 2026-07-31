# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductProductionHistory(models.Model):
    _name = "product.production.history"
    _description = "Product Production History"
    _order = "mo_date desc, id desc"

    orderpoint_id = fields.Many2one("stock.warehouse.orderpoint", string="Order Point", ondelete='cascade', index=True)
    product_id = fields.Many2one("product.product", string="Product", required=True)
    warehouse_id = fields.Many2one("stock.warehouse", string="Warehouse", required=True)
    production_id = fields.Many2one("mrp.production", string="Production Order", required=True)
    mo_date = fields.Date(string="MO Date")
    produced_qty = fields.Float(string="Produced Qty")
    lead_time = fields.Float(string="Lead Time")
