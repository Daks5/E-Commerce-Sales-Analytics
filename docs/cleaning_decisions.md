# Cleaning decisions and audit trail

1. Preserve the downloaded ZIP and every source CSV. Record SHA-256 fingerprints in `reports/source_manifest.json` and inventory all seven files.
2. Read identifiers as text. Parse Amazon dates with explicit `%m-%d-%y`; preserve original source index as a stable `line_id = index + 1`. Repeated Order ID + SKU is not a sufficient duplicate rule.
3. Flag six exact business-field duplicates excluding the export index and the ambiguous `Unnamed: 22` column. All 128,975 cleaned/fact rows remain stored; `v_order_lines` excludes the six later copies. This is an export-duplicate assumption, not proof that identical transactions cannot occur. Including them changes recorded amount by ₹2,635 and eligible shipped value by ₹2,635 (about 0.0038%). See the six flagged records in the audit CSV.
4. Strip whitespace, normalize shipping city/state case, and apply the reviewed state aliases in `docs/state_aliases.csv`. 69 raw state labels become 38 labels, including Unknown and Unmapped (APO). Leave ambiguous territory labels unexpanded. No city-to-state inference.
5. Convert postal codes such as `400081.0` to six-character strings, preserving zeros. Do not use them as numeric measures.
6. Keep missing currency and amount null. Every observed currency is INR, but missing currency is not silently assigned INR. Convert known amount to integer paise; reconcile both per-line money and totals. SQL stores `amount` as DECIMAL and `amount_minor` as BIGINT.
7. Retain zero-quantity and zero-value records. Classify statuses explicitly and expose eligibility/quality flags. Courier disagreements do not override the source order status; 93 conflict flags remain inspectable.
8. Normalize `kurta` to `Kurta`. Product grain is SKU; Style, Category and Size are consistent within SKU. Five SKUs map to multiple ASINs, so ASIN stays on the fact table rather than becoming a falsely unique product attribute.
9. Build one-to-many Date, Product, Geography and Status dimensions; assert uniqueness and merge cardinality. Validate all foreign keys in MySQL. Power BI uses single-direction dimension-to-fact relationships.
10. Load all seven sources into separate staging tables. Only the Amazon report feeds the main star model. International sales, stock, expense, and historical price files lack demonstrated compatible date/currency/entity grains; avoid fabricated joins or profit calculations.

Raw missing amount: 7,795; retained missing amount: 7,792. Raw/cleaned rows: 128,975; analytical rows: 128,969. Raw recorded amount: ₹78,592,678.30; retained recorded amount: ₹78,590,043.30. See `reports/cleaning_summary.json`, `reports/sql_load_inventory.json`, and `reports/validation.json` for machine-readable evidence.
