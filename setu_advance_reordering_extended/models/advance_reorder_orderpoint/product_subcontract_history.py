# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductSubcontractHistory(models.Model):
    _name = "product.subcontract.history"
    _description = "Product Subcontract History"
    _order = "po_date desc, id desc"

    orderpoint_id = fields.Many2one("stock.warehouse.orderpoint", string="Order Point", ondelete='cascade', index=True)
    product_id = fields.Many2one("product.product", string="Product", required=True)
    warehouse_id = fields.Many2one("stock.warehouse", string="Warehouse", required=True)
    purchase_id = fields.Many2one("purchase.order", string="Subcontract Order", required=True)
    partner_id = fields.Many2one("res.partner", string="Subcontractor", required=True)
    po_qty = fields.Float(string="Subcontract Qty")
    purchase_price = fields.Float(string="Subcontract Price")
    currency_id = fields.Many2one("res.currency", string="Currency")
    po_date = fields.Date(string="Subcontract Date")
    lead_time = fields.Float(string="Lead Time")
