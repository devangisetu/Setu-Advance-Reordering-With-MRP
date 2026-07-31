# -*- coding: utf-8 -*-
from odoo import fields, models, api, _


class ProductConsumptionHistory(models.Model):
    _name = "product.consumption.history"
    _description = "Product Consumption History"
    _order = "start_date desc, id desc"

    orderpoint_id = fields.Many2one("stock.warehouse.orderpoint", string="Order Point", ondelete='cascade', index=True)
    product_id = fields.Many2one("product.product", string="Product", required=True)
    warehouse_id = fields.Many2one("stock.warehouse", string="Warehouse", required=True)
    start_date = fields.Date(string="Start Date")
    end_date = fields.Date(string="End Date")
    duration = fields.Integer(string="Duration In Days")
    consumed_qty = fields.Float(string="Consumed Qty")
    average_daily_consumption = fields.Float(string="Average Daily Consumption")
    total_production_orders = fields.Integer(string="Total Production Orders")
    maximum_daily_consumption = fields.Float(string="Maximum Daily Consumption")
    minimum_daily_consumption = fields.Float(string="Minimum Daily Consumption")




