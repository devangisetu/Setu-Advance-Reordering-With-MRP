# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductScrapHistory(models.Model):
    _name = "product.scrap.history"
    _description = "Product Scrap History"
    _order = "start_date desc, id desc"

    orderpoint_id = fields.Many2one("stock.warehouse.orderpoint", string="Order Point", ondelete='cascade', index=True)
    product_id = fields.Many2one("product.product", string="Product", required=True)
    warehouse_id = fields.Many2one("stock.warehouse", string="Warehouse", required=True)
    start_date = fields.Date(string="Start Date")
    end_date = fields.Date(string="End Date")
    duration = fields.Integer(string="Duration In Days")
    scrap_qty = fields.Float(string="Scrap Qty")
    average_daily_scrap = fields.Float(string="Average Daily Scrap")
    maximum_daily_scrap = fields.Float(string="Maximum Daily Scrap")
    minimum_daily_scrap = fields.Float(string="Minimum Daily Scrap")
