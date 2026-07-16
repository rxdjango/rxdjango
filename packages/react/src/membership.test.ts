import { describe, expect, it } from "vitest";

import { compareByOrdering, evaluateConditions } from "./membership";

// Per-lookup parity suite (static-queryset-lists task 3.2): client verdicts
// must match Django's for each supported lookup, on already-serialized
// values (including DRF's ISO-8601 datetime strings, design D3).

describe("evaluateConditions: exact", () => {
  it("matches equal values", () => {
    expect(evaluateConditions({ status: "open" }, [["status", "exact", "open"]])).toBe(true);
  });

  it("rejects unequal values", () => {
    expect(evaluateConditions({ status: "closed" }, [["status", "exact", "open"]])).toBe(false);
  });

  it("does not coerce types (string vs number)", () => {
    expect(evaluateConditions({ priority: 1 }, [["priority", "exact", "1"]])).toBe(false);
  });
});

describe("evaluateConditions: in", () => {
  it("matches a member of the set", () => {
    expect(evaluateConditions({ status: "open" }, [["status", "in", ["open", "closed"]]])).toBe(true);
  });

  it("rejects a non-member", () => {
    expect(evaluateConditions({ status: "archived" }, [["status", "in", ["open", "closed"]]])).toBe(false);
  });
});

describe("evaluateConditions: gt/gte/lt/lte on numbers", () => {
  it("gt", () => {
    expect(evaluateConditions({ priority: 5 }, [["priority", "gt", 3]])).toBe(true);
    expect(evaluateConditions({ priority: 3 }, [["priority", "gt", 3]])).toBe(false);
  });

  it("gte", () => {
    expect(evaluateConditions({ priority: 3 }, [["priority", "gte", 3]])).toBe(true);
    expect(evaluateConditions({ priority: 2 }, [["priority", "gte", 3]])).toBe(false);
  });

  it("lt", () => {
    expect(evaluateConditions({ priority: 1 }, [["priority", "lt", 3]])).toBe(true);
    expect(evaluateConditions({ priority: 3 }, [["priority", "lt", 3]])).toBe(false);
  });

  it("lte", () => {
    expect(evaluateConditions({ priority: 3 }, [["priority", "lte", 3]])).toBe(true);
    expect(evaluateConditions({ priority: 4 }, [["priority", "lte", 3]])).toBe(false);
  });
});

describe("evaluateConditions: gte on ISO-8601 datetime strings (design D3)", () => {
  it("agrees with the server on an exact boundary match", () => {
    const boundary = "2026-07-16T10:00:00.000000Z";
    expect(evaluateConditions(
      { created_at: boundary },
      [["created_at", "gte", boundary]],
    )).toBe(true);
  });

  it("orders later timestamps as greater", () => {
    expect(evaluateConditions(
      { created_at: "2026-07-16T11:00:00.000000Z" },
      [["created_at", "gte", "2026-07-16T10:00:00.000000Z"]],
    )).toBe(true);
    expect(evaluateConditions(
      { created_at: "2026-07-16T09:00:00.000000Z" },
      [["created_at", "gte", "2026-07-16T10:00:00.000000Z"]],
    )).toBe(false);
  });
});

// Datetime lookup parity under mixed UTC offsets (DST transitions, or a
// bind-time value serialized with a different offset than a live row's):
// two representations of the same instant must compare equal, and ordering
// must follow the instant, not the string.
describe("evaluateConditions: exact/gte on mixed-offset ISO-8601 datetime strings", () => {
  it("exact treats two offset spellings of the same instant as equal", () => {
    expect(evaluateConditions(
      { created_at: "2026-07-16T12:00:00+02:00" },
      [["created_at", "exact", "2026-07-16T10:00:00Z"]],
    )).toBe(true);
  });

  it("exact still rejects two offset spellings of different instants", () => {
    expect(evaluateConditions(
      { created_at: "2026-07-16T12:00:01+02:00" },
      [["created_at", "exact", "2026-07-16T10:00:00Z"]],
    )).toBe(false);
  });

  it("gte agrees on a boundary match across differing offsets", () => {
    expect(evaluateConditions(
      { created_at: "2026-07-16T12:00:00+02:00" },
      [["created_at", "gte", "2026-07-16T10:00:00Z"]],
    )).toBe(true);
  });

  it("gt/lt order by instant, not by the offset-shifted string", () => {
    // Lexicographically "+02:00" < "Z" would flip this verdict if compared
    // as strings; as instants, 12:00+02:00 (10:00Z) is NOT after 10:30Z.
    expect(evaluateConditions(
      { created_at: "2026-07-16T12:00:00+02:00" },
      [["created_at", "gt", "2026-07-16T10:30:00Z"]],
    )).toBe(false);
    expect(evaluateConditions(
      { created_at: "2026-07-16T13:00:00+02:00" },
      [["created_at", "gt", "2026-07-16T10:30:00Z"]],
    )).toBe(true);
  });

  it("a naive (offset-less) datetime string still compares lexicographically", () => {
    expect(evaluateConditions(
      { created_at: "2026-07-16T10:00:00" },
      [["created_at", "exact", "2026-07-16T10:00:00"]],
    )).toBe(true);
  });
});

describe("evaluateConditions: isnull", () => {
  it("isnull=true matches null and undefined", () => {
    expect(evaluateConditions({ team: null }, [["team", "isnull", true]])).toBe(true);
    expect(evaluateConditions({}, [["team", "isnull", true]])).toBe(true);
  });

  it("isnull=false matches a present value", () => {
    expect(evaluateConditions({ team: 1 }, [["team", "isnull", false]])).toBe(true);
    expect(evaluateConditions({ team: null }, [["team", "isnull", false]])).toBe(false);
  });
});

describe("evaluateConditions: residual/null-safety on ordering lookups", () => {
  it("gt/gte/lt/lte never match a null or missing field", () => {
    for (const lookup of ["gt", "gte", "lt", "lte"]) {
      expect(evaluateConditions({ priority: null }, [["priority", lookup, 0]])).toBe(false);
      expect(evaluateConditions({}, [["priority", lookup, 0]])).toBe(false);
    }
  });
});

describe("evaluateConditions: conjunction", () => {
  it("requires every condition to pass", () => {
    const conditions: Array<[string, string, unknown]> = [
      ["status", "exact", "open"],
      ["priority", "gte", 3],
    ];
    expect(evaluateConditions({ status: "open", priority: 5 }, conditions)).toBe(true);
    expect(evaluateConditions({ status: "open", priority: 1 }, conditions)).toBe(false);
    expect(evaluateConditions({ status: "closed", priority: 5 }, conditions)).toBe(false);
  });

  it("an empty condition list always matches", () => {
    expect(evaluateConditions({ anything: 1 }, [])).toBe(true);
  });
});

describe("evaluateConditions: unsupported lookup", () => {
  it("never matches (forward-compatibility posture)", () => {
    expect(evaluateConditions({ name: "foo bar" }, [["name", "contains", "foo"]])).toBe(false);
  });
});

// -- Ordering comparator (task 3.3) -----------------------------------------

describe("compareByOrdering", () => {
  it("ascending, single column", () => {
    expect(compareByOrdering({ priority: 1 }, { priority: 2 }, ["priority"])).toBeLessThan(0);
    expect(compareByOrdering({ priority: 2 }, { priority: 1 }, ["priority"])).toBeGreaterThan(0);
    expect(compareByOrdering({ priority: 1 }, { priority: 1 }, ["priority"])).toBe(0);
  });

  it("descending via the `-` prefix", () => {
    expect(compareByOrdering({ priority: 1 }, { priority: 2 }, ["-priority"])).toBeGreaterThan(0);
    expect(compareByOrdering({ priority: 2 }, { priority: 1 }, ["-priority"])).toBeLessThan(0);
  });

  it("multi-column: second column breaks ties in the first", () => {
    const ordering = ["-priority", "id"];
    expect(compareByOrdering(
      { priority: 5, id: 2 }, { priority: 5, id: 1 }, ordering,
    )).toBeGreaterThan(0);
    expect(compareByOrdering(
      { priority: 5, id: 1 }, { priority: 9, id: 1 }, ordering,
    )).toBeGreaterThan(0);
  });

  it("orders ISO-8601 datetime strings correctly", () => {
    expect(compareByOrdering(
      { created_at: "2026-07-16T09:00:00Z" },
      { created_at: "2026-07-16T10:00:00Z" },
      ["created_at"],
    )).toBeLessThan(0);
  });

  it("orders ISO-8601 datetime strings by instant across differing offsets", () => {
    // Lexicographically "+02:00" < "Z", which would (wrongly) order the
    // 13:00+02:00 row (11:00Z) before 10:00Z if compared as strings.
    expect(compareByOrdering(
      { created_at: "2026-07-16T13:00:00+02:00" },
      { created_at: "2026-07-16T10:00:00Z" },
      ["created_at"],
    )).toBeGreaterThan(0);
    expect(compareByOrdering(
      { created_at: "2026-07-16T12:00:00+02:00" },
      { created_at: "2026-07-16T10:00:00Z" },
      ["created_at"],
    )).toBe(0);
  });

  it("nulls sort first ascending, last descending", () => {
    expect(compareByOrdering({ v: null }, { v: 1 }, ["v"])).toBeLessThan(0);
    expect(compareByOrdering({ v: null }, { v: 1 }, ["-v"])).toBeGreaterThan(0);
  });
});
