# Leave Summary

Clear visibility, history, and reporting for accrual leave expiry in Odoo 18.

## Purpose

Odoo 18 provides built-in accrual validity and expiry through accrual plan levels. This module complements that native functionality by recording expiry events and providing dedicated reporting and visibility into expired and remaining leave.

The module does **not** replace Odoo's native accrual or expiry calculations. Odoo remains responsible for calculating and updating leave balances; this module provides the history and reporting layer around those events.

## Features

* **Expiry History / Analysis** — Review and analyze accrual leave that has expired, including the employee, leave type, allocation, expiry date, and expired amount.
* **Leave Summary** — View allocated, taken, remaining, and expired leave balances as of a selected date.
* **Automatic expiry history** — Records expiry events when Odoo processes accrual validity and expiry.
* **Allocation expiry history** — View related expiry records directly from leave allocations.
* **Time Off visibility** — Shows expired amounts alongside Odoo's standard leave balances.
* **Pivot and list analysis** — Analyze expiry history using Odoo's standard reporting tools.

## Configuration

Expiry is configured using Odoo 18's standard accrual plan level settings.

1. Go to **Time Off → Configuration → Accrual Plans**.
2. Open the relevant accrual plan.
3. On the appropriate level, configure **Carry over**:

   * *All accrued time carried over*, or
   * *Carry over with a maximum*.
4. Enable **Accrual Validity** and configure the validity period.

Odoo's native accrual mechanism continues to calculate carryover, validity, and expiry. This module records the resulting expiry events for historical tracking and reporting.

## Reporting

The module provides two complementary reporting views:

### Expiry History / Analysis

A detailed history of accrual expiry events. Use list and pivot views to analyze:

* Employee
* Department
* Time Off Type
* Allocation
* Expiry Date
* Expired Days
* Company

### Leave Summary

A consolidated view of leave balances for employees and time-off types, including:

* Allocated Days
* Taken Days
* Remaining Days
* Expired Days
* Closest Expiry
* Next Expiry Date

The report can be generated **as of a selected date**, allowing historical leave balances and expiry information to be reviewed.

## What This Module Does Not Do

This module intentionally relies on Odoo 18's native accrual functionality.

* It does **not** replace Odoo's accrual calculation.
* It does **not** override `_get_consumed_leaves`.
* It does **not** implement a separate expiry engine.
* It does **not** modify Odoo's native allocation balance calculation.
* It does **not** add separate expiry configuration outside Odoo's standard accrual plan level settings.

Odoo remains the source of truth for accrual balances and expiry processing. This module adds the **history, analysis, reporting, and visibility** needed to understand those results.

## Compatibility

* **Odoo:** 18.0
* **Application:** Time Off
* **License:** OPL-1
