Recurring Costs Plan
====================


Questions (& Answers)
---------------------

1. What is in invoice?
  * An invoice tells someone how much they owe, what it was for, and how to pay. It is /informational/.
  * Secondarily, an invoice can provide information to aid in reconciling (i.e. how the income should
    be split between accounts)
2. Do we:
  * Create the invoice, which then immediately creates the necessary transactions?
  * Create the transactions, then create the invoice based on them?
  * The latter, because: Creating invoices based on transactions will also scoop up any other activity in that account
    which was not part of the regular billing cycle
3. How do we auto generate transactions & invoices?
  * Requirements:
    * Changes to the billing cycle should not affect existing data
    * Should handle a failure to generate earlier transactions gracefully (i.e. bring the system up-to-date)
    * Generation should be reenterant (running it twice should not mess anything up)
  * Solution:
    * Create a BillingCycle model, with one instance for each billing cycle.
    * Has: daterange (db constraint. must not overlap), transactions_created (bool). Link to the created transactions?
    * Generate 1 or 2 years of BillingCycle models ahead of time
    * At a change in billing cycle we delete & recreate all BillingCycle models which start in the future
    * Cannot create transactions for BillingCycles which start in the future (db constraint)
    * Transaction & invoice generation runs for all billing cycles
      which a) have not been invoiced, AND b) start in the past.
  * Create line items based on the transactions...
    * ...in the current billing cycle for items billed normally
    * ...in the current billing cycle for items billed in arrears
  * How do we know which transactions to auto-create?
    * Some line items will be the total of all transactions for an account in the previous cycle
    * Some line items will be estimated based on expected values
4. How do we store the details of line-items to auto-create?
  * See Recurring Costs wireframe. We need a RecurringCosts model
  * Amount can be calculated based on: fixed amount, sum of transactions in previous cycle, balance at end of previous cycle
  * To put it another way, the options are:
    * We will have already spent this in the previous cycle, so bill the account's balance
    * We will have already spent this in the previous cycle, so bill the total amount spent in the previous cycle
    * We will not have spent this yet, but we expect to spend [___] per billing cycle

1. There is a concept of a billing cycle (i.e. weekly, monthly)
2. Housemates have a bill generated for that billing cycle
3. Up-to-date reconciliation can be required in order for bills to be generated
4. We want to auto-generate invoices.
  * The line-items should come from outbound transactions in the current billing cycle
  * We should indicate their account balance before and after, and highlight the latter as the owed amount


