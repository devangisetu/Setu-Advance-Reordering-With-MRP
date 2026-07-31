from odoo import fields, models


class ProductSupplierinfo(models.Model):
    _inherit = 'product.supplierinfo'

    reorder_minimum_quantity = fields.Float('Reorder Minimum Quantity', help='Set Minimum Quantity for Reorder Summary')