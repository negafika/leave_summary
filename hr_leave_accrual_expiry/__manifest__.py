{
    'name': 'Leave Summary',
    'version': '18.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Track accrual expiry with clear history, leave summaries, and improved visibility',
    'author': 'Negaye Fikadu',
    'website': 'https://negaye-portfolio.vercel.app',
    'images': ['hr_leave_accrual_expiry/static/description/images/hero_screenshot.gif',],
    'description': '''
        Extend Odoo 18 Time Off accruals with clear visibility into leave expiry.

        This module works with Odoo 18's native accrual validity and expiry logic,
        recording expired accrual balances as an auditable history while providing
        dedicated expiry analysis and leave summary reporting.

        It also enhances the Time Off interface with expiry-related information,
        making it easier for HR users and employees to understand accrued,
        remaining, and expired leave balances.

        The module does not replace or modify Odoo's native accrual expiry
        calculation; it complements it with history, reporting, and visibility.
    ''',
    'depends': ['hr_holidays', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'views/hr_leave_allocation_view.xml',
        'report/hr_leave_balance_report_views.xml',
        'views/hr_leave_expiry_view.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'hr_leave_accrual_expiry/static/src/js/time_off_card_expired.js',
            'hr_leave_accrual_expiry/static/src/xml/time_off_card_popover.xml',
            'hr_leave_accrual_expiry/static/src/css/style.css',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'OPL-1',
}