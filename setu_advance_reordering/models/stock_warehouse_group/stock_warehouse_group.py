from odoo import fields, models, api, _


class StockWarehouseGroup(models.Model):
    _name = 'stock.warehouse.group'
    _description = "Warehouse Group"

    name = fields.Char("Name", help="Name to identify group")
    warehouse_ids = fields.Many2many("stock.warehouse", string="Warehouses",
                                     domain="[('company_id', '=', company_id)]",
                                     help="Can set one or more Warehouse for configuring in Advance " \
                                          "Reorder Process Application")
    company_id = fields.Many2one(comodel_name='res.company', string='Company', default=lambda self: self.env.company,)

    _sql_constraints = [
        ('warehouse_group_name', 'UNIQUE(name)', 'You can not have two warehouse group with the same name !')
    ]
