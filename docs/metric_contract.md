# Metric contract

The unit of observation is an exported **order line**, not a customer or an entire order. The Amazon report spans 31 March–29 June 2022. Amounts are INR. All raw records remain in staging; the analytical view excludes six flagged exact business-field copies.

| Metric | Inclusion and denominator |
|---|---|
| Observed lines | 128,969 retained Amazon order lines |
| Observed orders | Distinct Order ID in the retained lines: 120,378 |
| Shipped sales value | Amount on positive-quantity, known-INR lines with status Shipped, Delivered to Buyer, Picked Up, or Out for Delivery. Missing amounts remain null; known zero amounts are included. ₹69,660,658. This is a shipped-value proxy, not recognized or collected revenue. |
| Valued shipped units/orders | Quantity sum / distinct Order ID on the same eligible lines: 107,746 units / 100,227 orders |
| Complete-order AOV | Eligible value divided by distinct eligible orders, excluding any order containing a positive-quantity unvalued shipped line. ₹695.03. The 115 unvalued shipped orders have no eligible valued lines in this snapshot, so this equals the valued-order average. |
| Cancelled-line rate | Strict Cancelled status lines / all retained lines: 18,329 / 128,969 = 14.21% |
| Cancelled-order rate | Orders containing a cancelled line / all observed orders: 17,185 / 120,378. All such orders are fully cancelled in this export. Do not interchange this with the line rate. |
| Returned-line rate | Returned to Seller or Returning to Seller status lines / all retained lines. These are snapshot statuses, not independently verified refund events. |
| Recorded amount | Sum of all known retained amounts across every status: ₹78,590,043.30. Includes cancelled and pending records; not sales revenue or cancellation loss. |
| Missing amount | 7,792 retained lines. Raw report has 7,795, including three excluded duplicate copies. No zero imputation. |
| Unvalued shipped lines | 115 positive-quantity shipped-status lines failing value eligibility. Excluded from monetary and valued-unit metrics; exposed separately. |
| Comparable May–June change | May 1–29 versus June 1–29. Both have 29 observed calendar days. ₹21,906,300 → ₹20,433,336, or −6.72%. |

April and May are complete **calendar coverage** months, which does not prove complete commercial capture. March has one day and June has 29 days. Raw full-month totals should not be used as a like-for-like growth measure. The fixed-period DAX comparison removes Date filters and keeps product, geography, fulfillment and B2B context; standard sales measures respect slicers.

Product value shares are additive line-value shares. Category-level distinct order counts can overlap and should not be summed. Cancellation rates at SKU level are descriptive; SQL rankings require at least 30 observed lines. Promotion and fulfillment comparisons show associations only.

No transaction cost, reliable refund ledger, customer identifier, inventory history, promised delivery date, or payment reconciliation exists in the main report. Profit, retention, delivery SLA, stockout effects, and causal promotion ROI are outside this project's evidence.
