# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    # App Information
    'name': 'Inter Company Transfer',
    'version': '1.4',
    'license': 'OPL-1',
    'sequence': 19,
    'category': 'stock',

    # Author
    'author': 'Setu Consulting Services Pvt. Ltd.',
    'website': 'https://www.setuconsulting.com',
    'support': 'support@setuconsulting.com',

    # Banner
    'images': ['static/description/banner.gif'],

    # Dependencies
    'depends': ['sale_management', 'purchase_stock', 'sale_stock'],

    # Views
    'data': [
        'data/data.xml',
        'views/setu_ict_auto_workflow_views.xml',
        'views/setu_intercompany_channel_views.xml',
        'views/setu_interwarehouse_channel_views.xml',
        'views/setu_intercompany_transfer_views.xml',
        'views/setu_interwarehouse_transfer_views.xml',
        'views/setu_reverse_transfer_views.xml',
        'views/res_company_views.xml',
        'views/sale_order_views.xml',
        'views/purchase_order_views.xml',
        'views/stock_picking_views.xml',
        'views/account_move_views.xml',
        'wizard_views/wizard_import_ict_products_views.xml',
        'security/ir.model.access.csv',
    ],

    # Technical
    'installable': True,
    'auto_install': False,
    'application': True,
    'active': False,

    # Price
    'price': 149,
    'currency': 'EUR',

    # Live Preview
    'live_test_url': 'https://www.youtube.com/watch?v=SUDr7uA83uk&list=PLH6xCEY0yCID5xMUPKh_818Dq6Fpq6rg8',

    # Summary & Description
    'summary': """
        Inter Company Transfer / Inter Warehouse Transfer
        This app is used to keep track of all the transactions between two warehouses, source warehouse
        and destination warehouse can be of same company and can be of different company.

        -Intercompany transaction (transaction between warehouses of two different companies)
        -Interwarehouse transaction (transaction between warehouses of same company)
        -Reverse transactions / Reverse transfer (Inter company transaction or Inter warehouse transaction)

        -Define inter company rules which will create inter company transactions record automatically
        -Create intercompany transaction automatically when any sales order validated in the company
        -Create interwarehouse transaction automatically when any sales order validated in the company
	-stock manage, inventory management techniques, internal transfer, coverage,
	ict, twt""",
    'description': """
       Intercompany Transfer
       ==========================================================
       This app is used to keep track of all the transactions between two warehouses, source warehouse
       and destination warehouse can be of same company and can be of different company.

       This app will perform following operations.
       -> Inter company transaction (transaction between warehouses of two different companies)
       -> Inter warehouse transaction (transaction between warehouses of same company)
       -> Reverse transactions (Inter company or Inter warehouse)

       Advance features
       -> Define inter company rules which will create inter company transactions record automatically
       -> Create intercompany transaction automatically when any sales order validated in the company
       -> Create interwarehouse transaction automatically when any sales order validated in the company""",

}
