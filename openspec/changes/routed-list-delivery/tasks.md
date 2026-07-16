# Tasks: routed-list-delivery

## 1. Router surface and registry

- [x] 1.1 `Router` base (publish/subscribe, optional `columns`, dimension key), `ColumnRouter`, `BroadcastRouter`; `routing=` accepted on `rx.model(many=True)` with column-string sugar; `routing=None` and routing on non-list fields rejected at declaration; unit tests
- [x] 1.2 Routing registry keyed by (model label, router key) with dedup of identical dimensions across fields/channels; group naming `rx.route.<model>.<key>.<hash(value)>` handling opaque tuple values; `None` filtered from publish/subscribe returns; unit tests
- [x] 1.3 Framework-owned autodiscovery of app `channels` modules in `AppConfig.ready()` (extend the existing discovery hook if one exists); unit test that import-time registration lands without app wiring

## 2. Writer-side lifecycle broadcasts

- [ ] 2.1 `ReactiveModel.save()` broadcasts creations to `publish(new)` and updates to `publish(old) ∪ publish(new)` dimension groups on commit, with the create/update discriminator carried in the group message; unit/integration tests
- [ ] 2.2 Gated pre-image read: old input columns read inside the atomic block only when the save is an update and `update_fields` is None or intersects the router's input columns; full-row pre-image when a custom Router omits `columns`; tests for gating (no read on `update_fields=['title']`)
- [ ] 2.3 `ReactiveModel.delete()` sends the tombstone to `publish(row)` dimension groups; test that a non-holder dimension subscriber receives the `_del`
- [ ] 2.4 Integration test: a management-command-style writer (no channel imports of its own) broadcasts to dimension groups via autodiscovered registration

## 3. Consumer bind and relay

- [ ] 3.1 Bind of a routed field runs `subscribe(channel)`, filters `None`, joins dimension groups; stale dimension groups left on rebind/clear (extending cycle 1's per-field group bookkeeping); integration tests including two-connection isolation on different dimension values
- [ ] 3.2 Dimension-group events relay to the client as merge frames tagged with the field; duplicate delivery through per-instance + dimension groups converges by `_v` (integration test)
- [ ] 3.3 Creation-drop optimization: consumer drops relayed creations failing the field's residual `w`, keyed on the create/update discriminator; failing updates always relay (both directions tested)
- [ ] 3.4 `rebind(field)` lever: re-runs subscribe, refreshes joins, re-runs the snapshot walk emitting a fresh `q`; integration test for relation-change-then-rebind

## 4. Wire and client

- [ ] 4.1 Descriptor gains `l: true` for routed fields (absent for static); `PROTOCOL_VERSION` → `0.4.0`; protocol tests
- [ ] 4.2 StateBuilder basis growth for live fields: qualifying full anchor layers join the basis at the ordered position; static fields keep never-grow; vitest for enter, enter-then-leave, and stale-frame rejection on a grown row
- [ ] 4.3 Live-field end-to-end over the reconnect path: rebind after reconnect resets the basis and live growth resumes; vitest/integration

## 5. Example app and e2e

- [ ] 5.1 Routed example app (`routing='project_id'` task board) with seed migration, docs page wired into the toctree, generated page + hand-written demo; `make check` passes
- [ ] 5.2 Playwright e2e: created row appears live at its ordered position; dimension move removes the row; residual flip still toggles membership
- [ ] 5.3 Integration test for two-connection isolation (dimension value A never sees value B's creations)

## 6. Wrap-up

- [ ] 6.1 All three test tiers green: `uv run pytest`, `cd examples/backend && uv run ./manage.py test`, `cd packages/react && npm test`
- [ ] 6.2 Static-tier example and tests unaffected (no routing declared anywhere in cycle 1 surfaces); docs mention the security doctrine (delivery is authorization; residuals are presentation; `BroadcastRouter` greppable)
