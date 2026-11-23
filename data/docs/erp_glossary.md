# ERP Glossary

Terms used in ERPNext and in this plant.

## Documents and statuses
- Draft: a document saved but not submitted (docstatus 0). It has no effect on stock or orders.
- Submitted: a confirmed document (docstatus 1). Stock entries move stock; sales orders become open demand.
- Cancelled: a submitted document that was cancelled (docstatus 2).
- Sales order statuses: "To Deliver and Bill" (nothing or part delivered), "To Bill" (delivered, not invoiced), "Completed", "Closed" (stopped manually), "On Hold".

## Stock
- Item code: the unique code of an item, for example STEEL-BAR-20.
- Warehouse: a stock location, for example "Stores".
- Bin: the ERP record that holds the current quantity of one item in one warehouse (actual quantity, reserved quantity, ordered quantity, projected quantity).
- Actual quantity: what is physically in the warehouse.
- Reserved quantity: quantity promised to open sales orders.
- Ordered quantity: quantity on open purchase orders, not yet received.
- Projected quantity: actual + ordered + planned - reserved.
- Safety stock: the minimum level; below it, a purchase request is raised.
- Stock Entry: a stock movement (Material Receipt, Material Issue, Material Transfer, Manufacture).
- Stock Ledger: the history of every stock movement.

## Selling and buying
- Sales Order: a customer's confirmed order. Delivery Note: the shipment of goods against it. Sales Invoice: the bill.
- Purchase Order: our order to a supplier. Purchase Receipt: goods received against it. Purchase Invoice: the supplier's bill.
- Price List: Standard Selling (our prices) and Standard Buying (supplier prices).

## Production
- BOM (bill of materials): the components and operations needed to make one unit.
- Work Order: an order to produce a quantity of an item using its BOM.
- Workstation: a machine or work centre, for example CNC-01. Its hour rate is the cost of one hour.
- Operation: a step done on a workstation, for example Milling.
