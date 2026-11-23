# IT and ERP Access Policy

## Accounts
Every person has their own ERP account; shared accounts are not allowed. Accounts are created by IT support on the request of the manager, with the role of the job: operator, warehouse, quality, purchasing, sales, planner or manager.

## Roles and rights
- Operators: read machine status, work orders and documents.
- Warehouse: stock entries, delivery notes, purchase receipts.
- Purchasing: purchase orders and suppliers.
- Sales: quotations, sales orders and customers.
- Only the warehouse manager posts stock reconciliations. Only the plant manager approves purchase orders above 5000 EUR.

## Passwords
At least 12 characters, never shared, changed immediately if exposed. API keys used by integrations are stored only in configuration files on the server, never in documents, e-mails or source code.

## The AI assistant
The assistant uses a read-only integration with the ERP. It cannot create or change records. Questions and answers may be logged for quality review.

## Leavers
Accounts are disabled on the last working day.
