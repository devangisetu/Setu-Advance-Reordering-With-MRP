from odoo import fields, models


class AdvanceReorderNonProductForecast(models.Model):
    _name = 'advance.reorder.non.product.forecast'
    _description = "Advance Reorder for not create Forecast for Product and Warehouse"

    product_id = fields.Many2one('product.product', string="Product")
    warehouse_id = fields.Many2one('stock.warehouse', string="Warehouse")
    period_id = fields.Many2one('reorder.fiscalperiod', "Fiscal Period")
    forecast_qty = fields.Float("Forecast Quantity")
    reorder_process_id = fields.Many2one('advance.reorder.orderprocess', string="Advance Reorder Process")
    procurement_process_id = fields.Many2one('advance.procurement.process', string="Replenishment from Warehouses")