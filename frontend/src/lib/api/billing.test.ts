import { describe } from "vitest";
import { itSendsEach, recordFetches, token } from "@/test/fetch-recorder";
import { getBillingSubscription } from "./billing";

const recorder = recordFetches();

describe("billing accessors", () => {
  itSendsEach(recorder, [
    {
      name: "getBillingSubscription",
      call: () => getBillingSubscription(token),
      method: "GET",
      path: "/api/v1/billing/subscription",
    },
  ]);
});
