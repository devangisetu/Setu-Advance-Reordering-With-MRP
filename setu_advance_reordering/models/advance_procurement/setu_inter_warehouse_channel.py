from datetime import datetime
from odoo import fields, models, api, _


class SetuInterwarehouseChannel(models.Model):
    _inherit = 'setu.interwarehouse.channel'

    procurement_lead_days = fields.Integer('Lead Days',
                                           help="Lead Days will be in Replenishment from Warehouses Configuration")

    def prepare_interwarehouse_values(self, requestor_warehouse, inter_warehouse_channel_id, data={}):
        """
             added by: Aastha Vora | On: Oct - 15 - 2024 | Task: 998
             use: use to prepare Inter Warehouse Vals from advance reordering.
        """
        iwt_vals = {
            'ict_date': datetime.today(),
            'requestor_warehouse_id': requestor_warehouse.id,
            'fulfiller_warehouse_id': inter_warehouse_channel_id.fulfiller_warehouse_id
                                      and inter_warehouse_channel_id.fulfiller_warehouse_id.id or False,
            'interwarehouse_channel_id': inter_warehouse_channel_id.id,
            'ict_user_id': inter_warehouse_channel_id.ict_user_id
                           and inter_warehouse_channel_id.ict_user_id.id or False,
            'transfer_type': 'inter_warehouse',
            'state': 'draft',
            'transfer_with_single_picking': inter_warehouse_channel_id.transfer_with_single_picking,
            'location_id': self.location_id and self.location_id.id or False,
        }
        data and iwt_vals.update(data)
        return iwt_vals