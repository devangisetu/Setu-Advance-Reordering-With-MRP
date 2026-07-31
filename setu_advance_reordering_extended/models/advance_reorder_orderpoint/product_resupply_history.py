# -*- coding: utf-8 -*-
from odoo import fields, models, api, _

class ProductResupplyHistory(models.Model):
    _name = "product.resupply.history"
    _description = "Product Resupply History"
    _order = "start_date desc, id desc"

    orderpoint_id = fields.Many2one("stock.warehouse.orderpoint", string="Order Point", ondelete='cascade', index=True)
    product_id = fields.Many2one("product.product", string="Product", required=True)
    warehouse_id = fields.Many2one("stock.warehouse", string="Warehouse", required=True)
    start_date = fields.Date(string="Start Date")
    end_date = fields.Date(string="End Date")
    duration = fields.Integer(string="Duration In Days")
    resupply_qty = fields.Float(string="Resupply Qty")
    resupply_return_qty = fields.Float(string="Resupply Return Qty")
    total_resupply_qty = fields.Float(string="Total Resupply Qty")
    average_daily_resupply = fields.Float(string="Average Daily Resupply")
    total_resupply_orders = fields.Integer(string="Total Resupply Pickings")
    maximum_daily_resupply = fields.Float(string="Maximum Daily Resupply")
    minimum_daily_resupply = fields.Float(string="Minimum Daily Resupply")
