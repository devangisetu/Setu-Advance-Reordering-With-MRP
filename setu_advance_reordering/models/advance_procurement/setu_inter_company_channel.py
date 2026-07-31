from datetime import datetime
from odoo import fields, models, api, _


class SetuIntercomapnyChannel(models.Model):
    _inherit = 'setu.intercompany.channel'

    procurement_lead_days = fields.Integer('Lead days',
                                           help="Lead Days will be in Replenishment from Warehouses Configuration")

    def prepare_intercompany_vals_from_adv(self, requestor_warehouse, inter_company_channel_id, data={}):
        """
              added by: Aastha Vora | On: Oct - 15 - 2024 | Task: 998
              use: use to prepare Intercompany Vals from advance reordering.
        """
        ict_vals = {
            'ict_date': datetime.today(),
            'requestor_warehouse_id': requestor_warehouse.id,
            'fulfiller_warehouse_id': inter_company_channel_id.fulfiller_warehouse_id and
                                      inter_company_channel_id.fulfiller_warehouse_id.id or False,
            'manage_lot_serial': inter_company_channel_id.manage_lot_serial,
            'auto_workflow_id': inter_company_channel_id.auto_workflow_id and
                                inter_company_channel_id.auto_workflow_id.id or False,
            'intercompany_channel_id': inter_company_channel_id.id,
            'pricelist_id': inter_company_channel_id.pricelist_id and
                            inter_company_channel_id.pricelist_id.id or False,
            'sales_team_id': inter_company_channel_id.sales_team_id and
                             inter_company_channel_id.sales_team_id.id or False,
            'ict_user_id': inter_company_channel_id.ict_user_id and
                           inter_company_channel_id.ict_user_id.id or False,
            'transfer_type': 'inter_company',
            'state': 'draft',
        }
        data and ict_vals.update(data)
        return ict_vals
