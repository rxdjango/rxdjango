/**
 * Wire-contract fixtures shared with the Python suite.
 *
 * Each JSON file in packages/contract/wire/ is produced and asserted by
 * packages/model/tests/test_wire_contract.py; this side proves that
 * StateBuilder rebuilds the flat `payload` into the `expected` nested
 * object. Neither suite can drift from the protocol without failing.
 */
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { StateBuilder, type Model } from "./StateBuilder";

interface WireContract {
  anchor: string;
  model: Model;
  payload: Array<{ _type: string; id?: number }>;
  expected: unknown;
}

const wireDir = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../contract/wire",
);

const fixtures = readdirSync(wireDir).filter((name) => name.endsWith(".json"));

describe("wire contract", () => {
  it("has at least one fixture", () => {
    expect(fixtures.length).toBeGreaterThan(0);
  });

  it.each(fixtures)("%s rebuilds to the expected nested object", (name) => {
    const contract: WireContract = JSON.parse(
      readFileSync(path.join(wireDir, name), "utf-8"),
    );
    const builder = new StateBuilder(contract.model, contract.anchor);
    builder.update(contract.payload);
    expect(builder.state).toEqual(contract.expected);
  });
});
