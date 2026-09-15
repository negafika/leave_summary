from odoo.tools.date_utils import get_timedelta
from odoo import models, fields, api, _
from dateutil.relativedelta import relativedelta

class HrLeaveAllocation(models.Model):
    _inherit = 'hr.leave.allocation'

    expiry_record_ids = fields.One2many(
        'hr.leave.accrual.expiry',
        'allocation_id',
        string='Expiry Records',
    )

    expiry_record_count = fields.Integer(
        string='Expiry Records',
        compute='_compute_expiry_record_count',
    )

    @api.depends('expiry_record_ids')
    def _compute_expiry_record_count(self):
        for allocation in self:
            allocation.expiry_record_count = len(allocation.expiry_record_ids)

    def action_open_expiry_records(self):
        self.ensure_one()

        action = self.env.ref(
            'hr_leave_accrual_expiry.action_hr_leave_accrual_expiry'
        ).read()[0]

        action['domain'] = [
            ('allocation_id', '=', self.id),
        ]
        action['context'] = {
            'default_allocation_id': self.id,
        }

        return action

    def _get_expired_amount(self, target_date=False):
        # Computes the total expired amount for this allocation up to a target date.
        # Filters related expiry records then sums expired amount.

        self.ensure_one()

        if not target_date:
            target_date = fields.Date.today()
        expired_records = self.expiry_record_ids.filtered(
            lambda l: (
                    l.expiry_date
                    and l.expiry_date <= target_date
            )
        )

        return sum(expired_records.mapped('expired_days'))


    def _create_expiry_log(self, carryover_date, expiry_date, expired_days):
        self.ensure_one()

        if expired_days <= 0:
            return

        Expiry = self.env['hr.leave.accrual.expiry']

        # Prevent duplicate logs if the same expiry is processed again.
        existing = Expiry.search([
            ('allocation_id', '=', self.id),
            ('carryover_date', '=', carryover_date),
            ('expiry_date', '=', expiry_date),
        ], limit=1)

        if existing:
            return existing

        expired_hours = 0.0
        hours_per_day = self.employee_id.resource_calendar_id.hours_per_day or 8
        expired_hours = expired_days * hours_per_day

        return Expiry.create({
            'employee_id': self.employee_id.id,
            'allocation_id': self.id,
            'carryover_date': carryover_date,
            'expiry_date': expiry_date,
            'expired_days': expired_days,
            'expired_hours': expired_hours,
        })

    def _process_accrual_plans(self, date_to=False, force_period=False, log=True):
        """
        This method is part of the cron's process.
        The goal of this method is to retroactively apply accrual plan levels and progress from nextcall to date_to or today.
        If force_period is set, the accrual will run until date_to in a prorated way (used for end of year accrual actions).
        """
        def _get_leaves_taken(allocation):
            precomputed_allocations = allocation
            if context_precomputed := self.env.context.get('precomputed_allocations'):
                precomputed_allocations |= context_precomputed
            # By setting `precomputed_allocations`, avoid infinite loop (otherwise _get_consumed_leaves -> _get_future_leaves_on -> _process_accrual_plans -> ...)
            employee_days_per_allocation = allocation.employee_id.with_context(precomputed_allocations=precomputed_allocations)._get_consumed_leaves(
                allocation.holiday_status_id, allocation.nextcall, ignore_future=True)[0]
            origin = allocation._origin
            leaves_taken = employee_days_per_allocation[origin.employee_id][origin.holiday_status_id][origin]['leaves_taken']
            return leaves_taken
        date_to = date_to or fields.Date.today()
        already_accrued = {allocation.id: allocation.already_accrued or (allocation.number_of_days != 0 and allocation.accrual_plan_id.accrued_gain_time == 'start') for allocation in self}
        first_allocation = _("""This allocation have already ran once, any modification won't be effective to the days allocated to the employee. If you need to change the configuration of the allocation, delete and create a new one.""")
        for allocation in self:
            expiration_date = False
            if allocation.allocation_type != 'accrual':
                continue
            level_ids = allocation.accrual_plan_id.level_ids.sorted('sequence')
            if not level_ids:
                continue
            # "cache" leaves taken, as it gets recomputed every time allocation.number_of_days is assigned to. Without this,
            # every loop will take 1+ second. It can be removed if computes don't chain in a way to always reassign accrual plan
            # even if the value doesn't change. This is the best performance atm.
            first_level = level_ids[0]
            first_level_start_date = allocation.date_from + get_timedelta(first_level.start_count, first_level.start_type)
            allocation.already_accrued = already_accrued[allocation.id]
            # first time the plan is run, initialize nextcall and take carryover / level transition into account
            if not allocation.nextcall:
                # Accrual plan is not configured properly or has not started
                if date_to < first_level_start_date:
                    continue
                allocation.lastcall = max(allocation.lastcall, first_level_start_date)
                allocation.actual_lastcall = allocation.lastcall
                allocation.nextcall = first_level._get_next_date(allocation.lastcall)
                # adjust nextcall for carryover
                carryover_date = allocation._get_carryover_date(allocation.nextcall)
                allocation.nextcall = min(carryover_date, allocation.nextcall)
                # adjust nextcall for level_transition
                if len(level_ids) > 1:
                    second_level_start_date = allocation.date_from + get_timedelta(level_ids[1].start_count, level_ids[1].start_type)
                    allocation.nextcall = min(second_level_start_date, allocation.nextcall)
                if log:
                    allocation._message_log(body=first_allocation)
            (current_level, current_level_idx) = (False, 0)
            current_level_maximum_leave = 0.0
            # all subsequent runs, at every loop:
            # get current level and normal period boundaries, then set nextcall, adjusted for level transition and carryover
            # add days, trimmed if there is a maximum_leave
            while allocation.nextcall <= date_to:
                if allocation.holiday_status_id.request_unit in ["day", "half_day"]:
                    leaves_taken = _get_leaves_taken(allocation)
                else:
                    leaves_taken = _get_leaves_taken(allocation) / allocation.employee_id._get_hours_per_day(allocation.nextcall or allocation.date_from)
                (current_level, current_level_idx) = allocation._get_current_accrual_plan_level_id(allocation.nextcall)
                if not current_level:
                    break
                if current_level.cap_accrued_time:
                    if current_level.added_value_type == "day":
                        current_level_maximum_leave = current_level.maximum_leave
                    else:
                        current_level_maximum_leave = current_level.maximum_leave / allocation.employee_id._get_hours_per_day(allocation.nextcall or allocation.date_from)
                nextcall = current_level._get_next_date(allocation.nextcall)
                # Since _get_previous_date returns the given date if it corresponds to a call date
                # this will always return lastcall except possibly on the first call
                # this is used to prorate the first number of days given to the employee
                period_start = current_level._get_previous_date(allocation.lastcall)
                period_end = current_level._get_next_date(allocation.lastcall)
                # There are 3 cases where nextcall could be closer than the normal period:
                # 1. Passing from one level to another, if mode is set to 'immediately'
                current_level_last_date = False
                if current_level_idx < (len(level_ids) - 1) and allocation.accrual_plan_id.transition_mode == 'immediately':
                    next_level = level_ids[current_level_idx + 1]
                    current_level_last_date = allocation.date_from + get_timedelta(next_level.start_count, next_level.start_type)
                    if allocation.nextcall != current_level_last_date:
                        nextcall = min(nextcall, current_level_last_date)
                # 2. On carry-over date
                carryover_date = allocation._get_carryover_date(allocation.nextcall)
                if allocation.nextcall < carryover_date < nextcall:
                    nextcall = min(nextcall, carryover_date)

                if current_level.accrual_validity:
                    # 3. On carried over days expiration date
                    expiration_date = allocation.carried_over_days_expiration_date
                    # - not expiration_date -> expiration_date needs to be initialized.
                    # - allocation.nextcall > expiration_date -> the expiration date has passed and the new one should be computed.
                    # - allocation.expiring_carryover_days == 0 -> If the carryover date of the accrual plan was changed or if a level
                    #   transition occurred, then the expiration date needs to be updated. However, if allocation.expiring_carryover_days != 0,
                    #   then this means that some days will expire on expiration_date and that expiration date should be respected and
                    #   Expiration date will be updated correctly when allocation.nextcall is greater than expiration_date.
                    if not expiration_date or allocation.nextcall > expiration_date or allocation.expiring_carryover_days == 0:
                        expiration_date = carryover_date + relativedelta(**{current_level.accrual_validity_type + 's': current_level.accrual_validity_count})
                        allocation.carried_over_days_expiration_date = expiration_date
                    if allocation.nextcall < expiration_date < nextcall:
                        nextcall = expiration_date
                    if allocation.nextcall == expiration_date:
                        expiring_days = max(
                            0,
                            allocation.expiring_carryover_days - leaves_taken
                        )
                        if expiring_days > 0:
                            allocation._create_expiry_log(
                                carryover_date=allocation.last_executed_carryover_date,
                                expiry_date=expiration_date,
                                expired_days=expiring_days,
                            )

                        allocation.number_of_days = max(
                            0,
                            allocation.number_of_days - expiring_days
                        )
                        allocation.expiring_carryover_days = 0

                is_accrual_date = allocation.nextcall == period_end or allocation.nextcall == current_level_last_date
                if not allocation.already_accrued and is_accrual_date and allocation.accrual_plan_id.accrued_gain_time == 'start':
                    allocation._add_days_to_allocation(current_level, current_level_maximum_leave, leaves_taken, period_start, period_end)

                # if it's the carry-over date, adjust days using current level's carry-over policy
                if allocation.nextcall == carryover_date:
                    allocation.last_executed_carryover_date = carryover_date
                    if current_level.action_with_unused_accruals in ['lost', 'maximum']:
                        allocated_days_left = allocation.number_of_days - leaves_taken
                        allocation_max_days = 0 # default if unused_accrual are lost
                        if current_level.action_with_unused_accruals == 'maximum':
                            if current_level.added_value_type == 'day':
                                postpone_max_days = current_level.postpone_max_days
                            else:
                                postpone_max_days = current_level.postpone_max_days / allocation.employee_id._get_hours_per_day(allocation.date_from)
                            allocation_max_days = min(postpone_max_days, allocated_days_left)
                        allocation.number_of_days = min(allocation.number_of_days, allocation_max_days) + leaves_taken
                    allocation.expiring_carryover_days = allocation.number_of_days

                if not allocation.already_accrued and is_accrual_date and allocation.accrual_plan_id.accrued_gain_time == 'end':
                    allocation._add_days_to_allocation(current_level, current_level_maximum_leave, leaves_taken, period_start, period_end)

                if allocation.nextcall == carryover_date:
                    allocation.yearly_accrued_amount = 0

                # 1. When accrued_gain_time == 'start', all the days are accrued on the start of the accrual period. For example, if the accrual period
                #    is from 01/01/2023 to 01/01/2024, then the days will be accrued on 01/01/2023. Given that the carryover date will be >= the start of the accrual period
                #    (01/01/2023 in the example) the carryover policy should apply to any day accrued during the period from 01/01/2023 to 01/01/2024.
                # 2.However, if a level transistion occurred, the carryover policy should apply to the days that were accrued during the carryover level only.
                #   Any days accrued after the carryover level should be excluded.
                #   So, if carryover date was 01/06/2023, it should be applied to any day accrued between 01/01/2023 and 01/01/2024. If a level transition
                #   occurred on 01/09/2023 for example, then the carryover should be applied to any day accrued between 01/01/2023 and 01/09/2023.
                # 3. The following if block will handle the carryover for days accrued after carryover_date until carryover_period_end. Carryover period end is
                #    adjusted if a level transition occurred. The carryover for days accrued before carryover_date is handled above.
                if allocation.accrual_plan_id.accrued_gain_time == 'start' and allocation.last_executed_carryover_date:
                    last_carryover_date = allocation.last_executed_carryover_date
                    carryover_level, carryover_level_idx = allocation._get_current_accrual_plan_level_id(last_carryover_date)
                    carryover_period_start = carryover_level._get_previous_date(last_carryover_date)
                    carryover_period_end = carryover_level._get_next_date(last_carryover_date)
                    # Adjust carryover_period_end based on level_transition.
                    if carryover_level_idx < (len(level_ids) - 1) and allocation.accrual_plan_id.transition_mode == 'immediately':
                        next_level = level_ids[carryover_level_idx + 1]
                        carryover_level_last_date = allocation.date_from + get_timedelta(next_level.start_count, next_level.start_type)
                        carryover_period_end = min(carryover_period_end, carryover_level_last_date)
                    # Handle the special case for hourly/daily accruals. Carryover_period_end should be equal to last_carryover_date
                    # because the carryover period is just 1 day.
                    if carryover_level.frequency == 'hourly' or carryover_level.frequency == 'daily':
                        carryover_period_end = last_carryover_date
                    # Carryover policy should be only applied to the days accrued on period_end.
                    # Days accrued on level transition date aren't subject to the carryover policy.
                    # That is why (allocation.nextcall == period_end) is used instead of (is_accrual_date)
                    accrued = not allocation.already_accrued and allocation.nextcall == period_end
                    # If the days were accrued on the carryover period, then apply the carryover policy
                    # If allocation.actual_lastcall == carryover_period_start, it means this loop has already been run once (skip to avoid applying the carryover twice)
                    if accrued and last_carryover_date <= allocation.nextcall <= carryover_period_end and allocation.actual_lastcall != carryover_period_start:
                        if carryover_level.action_with_unused_accruals in ['lost', 'maximum']:
                            allocation.last_executed_carryover_date = carryover_date
                            allocated_days_left = allocation.number_of_days - leaves_taken
                            postpone_max_days = current_level.postpone_max_days if current_level.added_value_type == 'day' \
                                else current_level.postpone_max_days / allocation.employee_id._get_hours_per_day(allocation.date_from)
                            allocated_days_left = allocation.number_of_days - leaves_taken
                            allocation_max_days = 0 # default if unused_accrual are lost
                            if current_level.action_with_unused_accruals == 'maximum':
                                postpone_max_days = current_level.postpone_max_days
                                allocation_max_days = min(postpone_max_days, allocated_days_left)
                            allocation.number_of_days = min(allocation.number_of_days, allocation_max_days) + leaves_taken

                if is_accrual_date:
                    allocation.lastcall = allocation.nextcall
                allocation.actual_lastcall = allocation.nextcall
                allocation.nextcall = nextcall
                allocation.already_accrued = False
                if force_period and allocation.nextcall > date_to:
                    allocation.nextcall = date_to
                    force_period = False

            # if plan.accrued_gain_time == 'start', process next period and set flag 'already_accrued', this will skip adding days
            # once, preventing double allocation.
            if allocation.accrual_plan_id.accrued_gain_time == 'start':
                # check that we are at the start of a period, not on a carry-over or level transition date
                level_start = {level._get_level_transition_date(allocation.date_from): level for level in allocation.accrual_plan_id.level_ids}
                current_level = level_start.get(allocation.actual_lastcall) or current_level or allocation.accrual_plan_id.level_ids[0]
                period_start = current_level._get_previous_date(allocation.actual_lastcall)
                if current_level.cap_accrued_time:
                    if current_level.added_value_type == "day":
                        current_level_maximum_leave = current_level.maximum_leave
                    else:
                        current_level_maximum_leave = current_level.maximum_leave / allocation.employee_id._get_hours_per_day(allocation.date_from)
                if allocation.actual_lastcall in {period_start, allocation.date_from} | set(level_start.keys())\
                        or (allocation.actual_lastcall - get_timedelta(current_level.accrual_validity_count, current_level.accrual_validity_type)
                        in {period_start, allocation.date_from} | set(level_start.keys())):
                    leaves_taken = _get_leaves_taken(allocation)
                    allocation._add_days_to_allocation(current_level, current_level_maximum_leave, leaves_taken, period_start, allocation.nextcall)
                    allocation.already_accrued = True
