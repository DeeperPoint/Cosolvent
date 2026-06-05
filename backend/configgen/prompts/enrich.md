You are refining the profile-field definitions of a B2B marketplace configuration.

You are given a flat list of fields (each with participant type, name, current label,
current type, current visibility, and number of options). Improve the human-facing and
privacy aspects ONLY. You may change three things per field:

1. `visibility` — one of: public, protected, private.
   - public: anyone (including anonymous visitors) may read it.
   - protected: only logged-in participants may read it ("members only").
   - private: only the owner and admins may read it.
   Guidance: identity/marketing fields (company name, country, categories, regions,
   certifications, equipment offered) are usually public. Commercially sensitive numbers
   (prices, budgets, insurance coverage, volumes) should usually be protected. Internal
   notes, uploaded documents, and contact details should usually be private.

2. `type` — you may ONLY swap between `select` (single choice) and `multi_select`
   (many choices). Use `select` when a field is naturally one value (e.g. a single
   condition, a single primary country), `multi_select` when several apply (e.g.
   categories carried, regions served). Do not change any other field's type.

3. `label` — a clearer, properly capitalized human label
   (e.g. "Average Unit Price Usd" -> "Average Unit Price (USD)").

Rules:
- Do NOT invent new fields, rename `name`, change options, or alter anything not listed.
- Only emit a field if you are changing at least one of the three attributes above.
- Omit any attribute you are leaving unchanged.

Respond with ONLY a JSON array of adjustment objects. No prose, no markdown fences.
