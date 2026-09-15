from collections import defaultdict
from odoo import models, fields, api, _
from datetime import datetime

class HrLeaveType(models.Model):
    _inherit = 'hr.leave.type'

    def get_allocation_data(self, employees, target_date=None):
        """
        Overriding the main data fetcher.
        'res' is a dict: { employee_id: [(leave_type_obj, stats_dict), ...] }
        """
        allocation_data = super(HrLeaveType, self).get_allocation_data(employees, target_date)
        if isinstance(target_date, str):
            target_date = datetime.fromisoformat(target_date).date()
        elif isinstance(target_date, datetime):
            target_date = target_date.date()
        reference_date = target_date or fields.Date.today()

        # Fetch all relevant allocations for this employee at once
        allocations = self.env['hr.leave.allocation'].search([
            ('employee_id', 'in', employees.ids),
            ('state', '=', 'validate'),
            ('allocation_type', '=', 'accrual')
        ])
        allocations_by_employee = defaultdict(lambda: defaultdict(lambda: self.env['hr.leave.allocation']))
        for allocation in allocations:
            allocations_by_employee[allocation.employee_id][allocation.holiday_status_id] |= allocation

        for employee in allocation_data:
            for leave_tuple in allocation_data[employee]:
                leave_data = leave_tuple[1]
                leave_type_id = leave_tuple[3]
                leave_type = self.browse(leave_type_id)

                leave_data['total_expired'] = 0
                for allocation in allocations_by_employee[employee][leave_type]:
                    expired = allocation._get_expired_amount(reference_date)
                    if expired:
                        leave_data['total_expired'] += expired

        return allocation_data