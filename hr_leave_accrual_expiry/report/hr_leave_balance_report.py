from odoo import fields, models, _
from odoo.tools import parse_date

class HrLeaveBalanceReport(models.TransientModel):
    _name = 'hr.leave.balance.report'
    _description = 'Leave Balance Report'
    _order = 'employee_id, leave_type_id, id'

    # Generated report fields
    employee_id = fields.Many2one(
        'hr.employee',
        readonly=True,
        string="Employee",
    )
    department_id = fields.Many2one(
        'hr.department',
        readonly=True,
        string="Department",
    )
    leave_type_id = fields.Many2one(
        'hr.leave.type',
        readonly=True,
        string="Time Off Type",
    )
    total_allocated_days = fields.Float(
        readonly=True,
        string="Total Entitlement",
    )
    leaves_taken = fields.Float(
        readonly=True,
        string="Taken",
    )
    remaining_balance = fields.Float(
        readonly=True,
        string="Remaining",
    )
    total_expired = fields.Float(
        readonly=True,
        string="Expired",
    )
    closest_remaining = fields.Float(
        readonly=True,
        string="Expiring Soon",
    )
    next_expire_date = fields.Date(
        readonly=True,
        string="Next Expiry Date",
    )

    # Wizard fields
    department_ids = fields.Many2many(
        'hr.department',
        string="Departments",
    )
    employee_ids = fields.Many2many(
        'hr.employee',
        domain="department_ids and [('department_id', 'in', department_ids)] or []",
        string="Employees",
    )
    as_of_date = fields.Date(
        string="As of Date",
        default=fields.Date.context_today,
        required=True,
    )


    def action_generate_and_view(self):
        self.ensure_one()

        # Remove previous generated rows/wizards belonging to this user.
        self.search([
            ('create_uid', '=', self.env.user.id),
            ('id', '!=', self.id),
        ]).unlink()

        target_date = self.as_of_date or fields.Date.context_today(self)

        employees = self.env['hr.employee'].search([])
        if self.employee_ids:
            employees = self.employee_ids
        elif self.department_ids:
            employees = self.env['hr.employee'].search([
                ('department_id', 'in', self.department_ids.ids),
            ])

        if not employees:
            return self._open_report_action()

        leave_types = self.env['hr.leave.type'].search([
            ('requires_allocation', '=', 'yes'),
        ])

        # Odoo's native allocation engine accepts a target date and calculates
        # the balance as it stood on that date.
        all_data = leave_types.get_allocation_data(employees, target_date)
        vals_list = []

        for employee, leave_infos in all_data.items():
            for leave_info in leave_infos:
                stats = leave_info[1]
                leave_type = self.env['hr.leave.type'].browse(leave_info[3])

                total_expired = stats.get('total_expired', 0.0)
                total_allocated_days = stats.get('max_leaves', 0.0) + total_expired
                leaves_taken = stats.get('leaves_taken', 0.0)
                remaining_balance = stats.get('remaining_leaves', 0.0)

                # Don't show completely empty rows
                if (
                        total_allocated_days == 0
                        and leaves_taken == 0
                        and remaining_balance == 0
                        and total_expired == 0
                ):
                    continue

                next_expire_date = parse_date(
                    self.env,
                    stats.get('closest_allocation_expire')
                )
                expiring_soon = stats.get('closest_allocation_remaining', 0)

                values = {
                    'employee_id': employee.id,
                    'department_id': employee.department_id.id,
                    'leave_type_id': leave_type.id,
                    'total_allocated_days': total_allocated_days,
                    'leaves_taken': leaves_taken,
                    'total_expired': total_expired,
                    'closest_remaining': expiring_soon,
                    'next_expire_date': next_expire_date,
                    'remaining_balance': remaining_balance,
                }

                vals_list.append(values)

        if vals_list:
            self.create(vals_list)

        return self._open_report_action()

    def _open_report_action(self):
        list_view = self.env.ref(
            'hr_leave_accrual_expiry.view_hr_leave_balance_report_list',
            raise_if_not_found=False,
        )
        search_view = self.env.ref(
            'hr_leave_accrual_expiry.view_hr_leave_balance_report_search',
            raise_if_not_found=False,
        )

        return {
            'name': _('Leave Summary'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.leave.balance.report',
            'view_mode': 'list',
            'view_id': list_view.id if list_view else False,
            'search_view_id': search_view.id if search_view else False,
            'target': 'current',
            'domain': [
                ('create_uid', '=', self.env.user.id),
                ('id', '!=', self.id),
            ],
            'context': {
                'create': False,
                'edit': False,
                'delete': False,
            },
        }
