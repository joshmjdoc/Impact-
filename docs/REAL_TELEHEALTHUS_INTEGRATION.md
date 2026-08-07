# Real TelehealthUS activation
The UI accurately reports **Mock** until configured. The EHR team must provide an HTTPS API base URL, server-to-server authentication, clinic/category/package list and detail endpoints, status/price/update fields, rate limits, test tenant, webhook signing contract, and route generation contract. They must confirm whether the middle package route segment is a category ID.

Implement the production methods behind the responses currently exposed at `server/index.ts` (`status`, `clinics`, category/package lookup, action verification, clinic sync). Credentials must be referenced from a secret manager, never returned to clients. Validate provider hosts, enforce timeouts and private-network denial, and use least privilege.
