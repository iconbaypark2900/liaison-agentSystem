import { describe, expect, it } from "vitest";

import {
  agentFromQuery,
  buildHubHref,
  mergeQueryParams,
  patternFromQuery,
  projectFromQuery,
  taskFromQuery,
} from "@/lib/url-query-helpers";

describe("url-query-helpers", () => {
  it("parses project task pattern agent from query", () => {
    expect(projectFromQuery("project=foo&task=t1&pattern=p1&agent=hermes")).toBe("foo");
    expect(taskFromQuery("project=foo&task=t1&pattern=p1&agent=hermes")).toBe("t1");
    expect(patternFromQuery("project=foo&task=t1&pattern=p1&agent=hermes")).toBe("p1");
    expect(agentFromQuery("project=foo&task=t1&pattern=p1&agent=hermes")).toBe("hermes");
  });

  it("mergeQueryParams updates and clears keys", () => {
    expect(mergeQueryParams("project=a&task=b", { task: null })).toBe("project=a");
    expect(mergeQueryParams("", { project: "x", task: "y" })).toBe("project=x&task=y");
    expect(mergeQueryParams("project=a", { agent: "hermes" })).toBe("project=a&agent=hermes");
    expect(mergeQueryParams("agent=hermes", { agent: null })).toBe("");
  });

  it("buildHubHref preserves session query keys", () => {
    expect(
      buildHubHref(
        { project: "sigma", task: "t1", pattern: "hermes-led-slice", agent: "hermes" },
        "refresh=1"
      )
    ).toBe("/hub?refresh=1&project=sigma&task=t1&pattern=hermes-led-slice&agent=hermes");
  });
});
