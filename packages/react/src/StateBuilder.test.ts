import { describe, expect, it } from "vitest";

import { StateBuilder, type Model } from "./StateBuilder";

const model: Model = {
  "app.UserSerializer": { company: "app.CompanySerializer" },
  "app.CompanySerializer": {},
};

describe("StateBuilder", () => {
  it("returns null before any update", () => {
    const builder = new StateBuilder(model, "app.UserSerializer");
    expect(builder.state).toBeNull();
  });

  it("rebuilds a nested instance from flat layers", () => {
    const builder = new StateBuilder(model, "app.UserSerializer");
    builder.update([
      { _type: "app.UserSerializer", id: 1, name: "Alice", company: 10 },
      { _type: "app.CompanySerializer", id: 10, name: "ACME" },
    ]);
    expect(builder.state).toEqual({
      id: 1,
      name: "Alice",
      company: { id: 10, name: "ACME" },
    });
  });

  it("strips underscore-prefixed keys from the output", () => {
    const builder = new StateBuilder(model, "app.UserSerializer");
    builder.update([
      { _type: "app.UserSerializer", id: 1, name: "Alice", company: null },
    ]);
    expect(Object.keys(builder.state as object)).not.toContain("_type");
  });

  it("keeps null relations null", () => {
    const builder = new StateBuilder(model, "app.UserSerializer");
    builder.update([
      { _type: "app.UserSerializer", id: 1, name: "Alice", company: null },
    ]);
    expect(builder.state).toEqual({ id: 1, name: "Alice", company: null });
  });

  it("resolves missing children to null", () => {
    const builder = new StateBuilder(model, "app.UserSerializer");
    builder.update([
      { _type: "app.UserSerializer", id: 1, name: "Alice", company: 99 },
    ]);
    expect(builder.state).toEqual({ id: 1, name: "Alice", company: null });
  });

  it("rebuilds array relations in order", () => {
    const listModel: Model = {
      "app.TeamSerializer": { members: "app.UserSerializer" },
      "app.UserSerializer": {},
    };
    const builder = new StateBuilder(listModel, "app.TeamSerializer");
    builder.update([
      { _type: "app.TeamSerializer", id: 1, members: [2, 1] },
      { _type: "app.UserSerializer", id: 1, name: "Alice" },
      { _type: "app.UserSerializer", id: 2, name: "Bob" },
    ]);
    expect(builder.state).toEqual({
      id: 1,
      members: [
        { id: 2, name: "Bob" },
        { id: 1, name: "Alice" },
      ],
    });
  });

  it("applies later updates to existing instances", () => {
    const builder = new StateBuilder(model, "app.UserSerializer");
    builder.update([
      { _type: "app.UserSerializer", id: 1, name: "Alice", company: 10 },
      { _type: "app.CompanySerializer", id: 10, name: "ACME" },
    ]);
    builder.update([
      { _type: "app.CompanySerializer", id: 10, name: "ACME Corp" },
    ]);
    expect(builder.state).toEqual({
      id: 1,
      name: "Alice",
      company: { id: 10, name: "ACME Corp" },
    });
  });
});
