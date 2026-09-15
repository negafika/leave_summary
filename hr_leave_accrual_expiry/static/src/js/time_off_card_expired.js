/** @odoo-module **/

import { TimeOffCard } from "@hr_holidays/dashboard/time_off_card";
import { formatNumber } from "@hr_holidays/views/hooks";
import { patch } from "@web/core/utils/patch";

patch(TimeOffCard.prototype, {

    onClickInfo(ev) {

        const { data } = this.props;
        this.popover.open(ev.target, {

            allocated: formatNumber(this.lang, data.max_leaves + data.total_expired),

            accrual_bonus: formatNumber(this.lang, data.accrual_bonus),

            approved: formatNumber(this.lang, data.leaves_approved),

            planned: formatNumber(this.lang, data.leaves_requested),

            left: formatNumber(this.lang, data.virtual_remaining_leaves),

            expired: formatNumber(this.lang, data.total_expired || 0),

            warning: this.warning,
            closest: data.closest_allocation_duration,
            request_unit: data.request_unit,
            exceeding_duration: data.exceeding_duration,
            allows_negative: data.allows_negative,
            max_allowed_negative: data.max_allowed_negative,
            onClickNewAllocationRequest: this.newAllocationRequestFrom.bind(this),
            errorLeaves: this.errorLeaves,
            accrualExcess: this.getAccrualExcess(data),
        });
    },

});