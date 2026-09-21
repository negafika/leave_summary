from odoo import models, fields, api


class HrLeaveExpiry(models.Model):
    _name = 'hr.leave.accrual.expiry'
    _description = 'Accrual Expiry Log'
    _order = 'expiry_date desc, id desc'

    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        readonly=True,
        index=True,
    )

    allocation_id = fields.Many2one(
        'hr.leave.allocation',
        string='Source Allocation',
        required=True,
        readonly=True,
        index=True,
        ondelete='restrict',
    )

    holiday_status_id = fields.Many2one(
        'hr.leave.type',
        string='Time Off Type',
        related='allocation_id.holiday_status_id',
        store=True,
        readonly=True,
    )

    carryover_date = fields.Date(
        string='Carryover Date',
        readonly=True,
    )

    expiry_date = fields.Date(
        string='Expire Date',
        required=True,
        readonly=True,
        index=True,
    )

    expired_days = fields.Float(
        string='Expired Days',
        required=True,
        readonly=True,
    )

    expired_hours = fields.Float(
        string='Expired Hours',
        store=True,
        readonly=True,
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        readonly=True,
        default=lambda self: self.env.company,
        index=True,
    )