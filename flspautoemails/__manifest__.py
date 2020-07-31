{
    'name': "FLSP - Automatic Emails",

    'summary': """
        This module intend to send reports by email according to the scheduled action.
        First Light Safety Products""",

    'description': """
        Customizations performed:

        Daily Sales Order Report:
            * Material Planners report - used to place the purchase order based on the demand.
    """,

    'author': "Alexandre Sousa",
    'website': "http://www.smartrendmfg.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/13.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Technical Settings',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base'],
    'depends': ['sale_management'],

    # always loaded
    'data': [
        'views/dailysalesorder_tmpl.xml',
        'data/dailysalesorder_cron.xml',
        'views/weeklysalesorder_tmpl.xml',
        'data/weeklysalesorder_cron.xml',
    ],
}
