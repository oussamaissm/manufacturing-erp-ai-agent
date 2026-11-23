# Production Planning and Scheduling

## Weekly plan
The production planner publishes the plan every Thursday for the next week. It is built from open sales orders, safety stock of finished goods and machine capacity. Work orders are created in the ERP from the plan.

## Sequencing rules
1. Tier 1 accounts first (Hexa Aero, Toulouse Aerostructures) on shared machines, especially CNC-02.
2. Then the earliest delivery date.
3. Same date: the order with the smaller remaining quantity goes first so that it ships complete.
4. Changeovers are grouped: run the same material or the same fixture in a row when the dates allow.

## Capacity
Two shifts of 8 hours, 5 days a week, so 80 machine hours per machine per week, minus planned maintenance. CNC-03 and WELD-01 can add unattended night hours. LATHE-02 runs two jobs in parallel (twin spindle) and the assembly line ASSY-01 three benches.

## Material check before release
A work order is released only when all components in its bill of materials are in stock. If a component is short, the planner checks the open purchase order and the supplier lead time, and moves the work order.

## Bottlenecks
CNC-02 is the usual bottleneck because it is the only 5-axis machine and turbine hubs need 90 minutes each. GRIND-01 follows CNC-02 for turbine hubs. Do not plan more than 30 turbine hubs a week.

## Changes to the plan
Urgent changes are agreed by the planner and the sales manager. A machine breakdown longer than 4 hours triggers a re-plan the same day.
