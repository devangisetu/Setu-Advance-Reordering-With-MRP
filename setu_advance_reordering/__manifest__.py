# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Advance Reordering | Advance Purchase Reordering',
    'version': '1.4',
    'price': 600,
    'currency': 'EUR',
    'category': 'stock',
    'summary': """
        Advance Reordering / Purchase Reorder
        It helps to manage customer demand with the right level of inventory by placing Purchase Order or replenishing 
        inventories using inter company or inter warehouse, inventory management technique, inventory coverage ratio,
        Advance reorder, order points, reordering rule, advance purchase ordering, sales forecast, inter company 
        transfer, inter warehouse transfer, stock replenishment, demand, advanced reordering, advanced purchase reordering,
        advance reordering dashboard, inventory forecast, cashflow, stock management, advance dashboard, procurement,
        advance reorder dashboard, advanced reorder dashboard, reorder dashboard, 
        inventory, advance inventory,out of stock, over stock, order point, supply chain management, accurate inventory ,
        advance orderpoint, real demand, cash forecast, demand generation, stock replenishment, sales forecast,
        Efficiently utilize warehouse, Avoid out of stock, future sales, future revenue, minimum order quantities, multiple warehouses,
        demand planner, 
    """,
    'author': 'Setu Consulting Services Pvt. Ltd.',
    'description': """
        Advance Reordering - Setu Consulting
        ==========================================================
        Purchasing is the main point in supply chain management. Manage accurate inventories is the key point for 
        businesses and nightmares as well. 
        Inaccurate inventories puts organizations either in Over stock or Out of stock. 
        Overstock blocks cash flow whereas Out of stock breaks revenue channels. 
        It is always necessary to bring the right inventories at the right time in the warehouses. 
        Effective inventory management is one of the biggest challenges that entrepreneurs face. 
        It’s not easy to balance customer demand with the right level of inventory.
        
        Advance Reordering is the solution for those nightmares. 
        It helps to manage accurate inventories by placing accurate purchase orders or replenish inventories from the 
        other warehouses of the same companies or other companies. 
        It helps to prevent Out of stock and Overstock situations with it’s smart features.
    """,
    'website': 'https://www.setuconsulting.com',
    'support': 'support@setuconsulting.com',
    'images': ['static/description/banner.gif'],
    'depends': ['setu_intercompany_transaction'],
    'license': 'OPL-1',
    'sequence': 26,
    'data': [
        'data/system_parameter.xml',
        'security/ir.model.access.csv',
        'security/advance_reordering_group.xml',
        'security/advance_reorder_security.xml',
        'views/res_config_settings_views.xml',
        'views/stock_warehouse.xml',
        'views/stock_warehouse_orderpoint.xml',
        'views/stock_move.xml',
        'views/advance_reorder_order_process.xml',
        'views/setu_inter_company_warehouse_channel.xml',
        'views/advance_procurement_process.xml',
        'views/reorder_fiscalyear.xml',
        'views/stock_warehouse_group.xml',
        'views/forecast_product_sale.xml',
        'views/advance_reorder_planner.xml',
        'views/advance_reorder_process_auto_workflow.xml',
        'wizard/create_reordering.xml',
        'wizard/advance_reorder_po_vendor_wizard.xml',
        'wizard/sale_forecast_auto_import_wizard.xml',
        'views/advance_reorder_menu.xml',
        'views/advance_inventory_reports_menu.xml',
        'views/res_partner.xml',
        'views/product_product.xml',
        'views/stock_warehouse_orderpoint.xml',
        'views/product_sales_history.xml',
        'views/product_purchase_history.xml',
        'views/product_iwt_history.xml',
        'data/ir_sequence.xml',
        'data/mail_template_data.xml',
        'db_function/get_stock_data.sql',
        'db_function/get_products_sales_warehouse_group_wise.sql',
        'db_function/get_reorder_forecast_data.sql',
        'db_function/get_reorder_non_product_forecast.sql',
        'db_function/get_product_purchase_history_from_stock_move.sql',
        'db_function/update_product_purchase_history.sql',
        'db_function/get_product_sales_history_data.sql',
        'db_function/update_product_sales_history.sql',
        'db_function/create_reordering_rule.sql',
        'db_function/update_actual_sales.sql',
        'db_function/update_iwt_history.sql',
        'data/ir_cron.xml'
    ],
    'application': True,
    'live_test_url': 'https://www.youtube.com/channel/UCUxH_derG7MpEhFbXwJ99jA/playlists',
}
