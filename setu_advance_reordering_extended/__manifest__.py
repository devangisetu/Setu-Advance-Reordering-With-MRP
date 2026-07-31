# -*- coding: utf-8 -*-
{
    'name': 'Advance Reordering Extended | MRP Integration',
    'version': '18.0.1.0.1',
    'category': 'Manufacturing/Inventory',
    'summary': 'MRP integration for Advance Reordering with real demand and component planning',
    'description': """
        Extends Advance Reordering with:
        - Finished Good / Semi-Finished Good classification
        - Per-product BOM selection and demand planning type
        - Production-driven demand calculation
        - Component demand explosion on validate
    """,
    'author': 'Setu Consulting Services Pvt. Ltd.',
    'website': 'https://www.setuconsulting.com',
    'depends': [
        'setu_advance_reordering',
        'mrp',
    ],
    'license': 'OPL-1',
    'data': [
        'security/ir.model.access.csv',
        'db_function/get_products_production_warehouse_group_wise.sql',
        'db_function/get_subcontracting_move_warehouse_group_wise.sql',
        'db_function/get_products_scrap_warehouse_group_wise.sql',
        'db_function/get_kit_product_component_warehouse_group_wise.sql',
        'views/advance_reordering_settings_views.xml',
        'views/advance_reorder_demand_source_views.xml',
        'views/advance_reorder_order_process_views.xml',
    ],
    'application': False,
    'installable': True,
    'auto_install': False,
}
