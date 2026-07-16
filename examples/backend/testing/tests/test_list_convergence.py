"""Convergence and semantics tests for rx[list[S]] fields (ADR-0017).

Drives `ListConvergenceChannel` from the real generated TS client over a live
websocket (the same infrastructure `RxIntegrationTestCase` gives every other
integration test), asserting the client's list converges to the server's
list after every mutator in design D2's table, after an interleaved burst,
and around None-union semantics and per-connection isolation.
"""

from __future__ import annotations

import json

from testing.integration import RxIntegrationTestCase


def _reference_result(action_name, args):
    """Apply the same mutation to a plain Python list seeded like the
    channel's default (`[1, 2, 3]`), so each scenario's expected value is
    computed the same way Python computes it — not hand-transcribed."""
    items = [1, 2, 3]
    if action_name == 'do_append':
        items.append(*args)
    elif action_name == 'do_insert':
        items.insert(*args)
    elif action_name == 'do_setitem':
        items[args[0]] = args[1]
    elif action_name == 'do_delitem':
        del items[args[0]]
    elif action_name == 'do_remove':
        items.remove(*args)
    elif action_name == 'do_pop':
        items.pop()
    elif action_name == 'do_extend':
        items.extend(args[0])
    elif action_name == 'do_iadd':
        items += args[0]
    elif action_name == 'do_clear':
        items.clear()
    elif action_name == 'do_sort':
        items.sort()
    elif action_name == 'do_reverse':
        items.reverse()
    elif action_name == 'do_imul':
        items *= args[0]
    elif action_name == 'do_slice_assign':
        items[0:2] = [100, 101, 102]
    elif action_name == 'do_slice_delete':
        del items[0:2]
    elif action_name == 'do_reset':
        items = list(args[0])
    else:
        raise ValueError(f'unknown action {action_name!r}')
    return items


# (action, args, number of rx frames it emits). Single-element positional
# mutators emit one op frame; extend/+= emit one insert per element (design
# D2); bulk mutators (clear/sort/reverse/*=/slice ops/reassignment) emit one
# whole-value replace frame.
MUTATIONS = [
    ('do_append', [4], 1),
    ('do_insert', [0, 9], 1),
    ('do_setitem', [1, 9], 1),
    ('do_delitem', [1], 1),
    ('do_remove', [2], 1),
    ('do_pop', [], 1),
    ('do_extend', [[4, 5]], 2),
    ('do_iadd', [[4, 5]], 2),
    ('do_clear', [], 1),
    ('do_sort', [], 1),
    ('do_reverse', [], 1),
    ('do_imul', [2], 1),
    ('do_slice_assign', [], 1),
    ('do_slice_delete', [], 1),
    ('do_reset', [[9, 8]], 1),
]


class ListMutatorConvergenceIntegrationTests(RxIntegrationTestCase):
    app_label = 'testing'
    channel = 'ListConvergenceChannel'
    url = '/ws/testing/list/'

    def test_every_mutator_converges_to_the_servers_list(self):
        for action_name, args, frame_count in MUTATIONS:
            with self.subTest(action=action_name):
                params_js = json.dumps(args)
                self.eval('const __versionBefore = channel.rx.getVersion()')
                self.eval(f'await channel.{action_name}(...{params_js})')
                self.wait_for(
                    f'channel.rx.getVersion() - __versionBefore >= {frame_count}'
                )
                result = self.get_result('channel.items')
                self.assertEqual(
                    result, _reference_result(action_name, args),
                    f'{action_name}{tuple(args)} diverged from the server list',
                )


class ListBurstOrderingIntegrationTests(RxIntegrationTestCase):
    app_label = 'testing'
    channel = 'ListConvergenceChannel'
    url = '/ws/testing/list/'

    def test_interleaved_burst_converges_in_mutation_order(self):
        self.eval('const versionBefore = channel.rx.getVersion()')
        self.eval('await channel.do_burst()')
        self.wait_for('channel.rx.getVersion() - versionBefore >= 4')
        result = self.get_result('channel.items')

        # append(10) -> [1,2,3,10]; insert(0,-1) -> [-1,1,2,3,10];
        # [1] = 999 -> [-1,999,2,3,10]; del [-1] -> [-1,999,2,3]
        self.assertEqual(result, [-1, 999, 2, 3])


class ListNoneUnionSemanticsIntegrationTests(RxIntegrationTestCase):
    app_label = 'testing'
    channel = 'ListConvergenceChannel'
    url = '/ws/testing/list/'

    def test_null_travels_on_replace(self):
        self.eval('await channel.do_set_optional([1, 2])')
        self.wait_for('channel.optional_items !== null')
        result = self.get_result('channel.optional_items')
        self.assertEqual(result, [1, 2])

    def test_reassigning_to_null_clears_it(self):
        self.eval('await channel.do_set_optional([1, 2])')
        self.wait_for('channel.optional_items !== null')
        self.eval('await channel.do_set_optional(null)')
        self.wait_for('channel.optional_items === null')
        result = self.get_result('channel.optional_items')
        self.assertIsNone(result)

    def test_mutating_while_none_rejects_with_an_error(self):
        code = (
            'import { ListConvergenceChannel } from '
            '"./testing/testing.channels.ts";\n'
            + r"""
const wsUrl = process.argv[2];

async function main() {
  const channel: any = new (ListConvergenceChannel as any)(wsUrl);

  await new Promise<void>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("connect timeout")), 5000);
    const unsub = channel.rx.subscribe(() => {
      clearTimeout(timer);
      unsub();
      resolve();
    });
  });

  let code: number | null = null;
  let message = "";
  try {
    await channel.do_append_optional(1);
  } catch (e: any) {
    code = e.code ?? null;
    message = String(e.message ?? "");
  }

  process.stdout.write(JSON.stringify({ code, message }));
  process.exit(0);
}

main().catch((err) => {
  console.error(err?.stack || String(err));
  process.exit(1);
});
"""
        )
        self.write_runner(code)
        result = self.run_node('runner.ts', self.ws_url(self.url))
        self.assertEqual(
            result.returncode, 0,
            f'node runner failed:\nstdout={result.stdout}\nstderr={result.stderr}',
        )
        parsed = json.loads(result.stdout)
        self.assertEqual(parsed['code'], 500)
        self.assertIn('has no attribute', parsed['message'])


class ListConnectionIsolationIntegrationTests(RxIntegrationTestCase):
    app_label = 'testing'
    channel = 'ListConvergenceChannel'
    url = '/ws/testing/list/'

    def test_one_connections_mutation_leaves_another_untouched(self):
        code = (
            'import { ListConvergenceChannel } from '
            '"./testing/testing.channels.ts";\n'
            + r"""
const wsUrl = process.argv[2];

function connect(): Promise<any> {
  const channel: any = new (ListConvergenceChannel as any)(wsUrl);
  return new Promise<any>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("connect timeout")), 5000);
    const unsub = channel.rx.subscribe(() => {
      clearTimeout(timer);
      unsub();
      resolve(channel);
    });
  });
}

async function main() {
  const a = await connect();
  const b = await connect();

  const versionBefore = a.rx.getVersion();
  await a.do_append(99);
  await new Promise<void>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("append timeout")), 5000);
    const check = () => {
      if (a.rx.getVersion() - versionBefore >= 1) {
        clearTimeout(timer);
        resolve();
      } else {
        setTimeout(check, 10);
      }
    };
    check();
  });

  process.stdout.write(JSON.stringify({ a: a.items, b: b.items }));
  process.exit(0);
}

main().catch((err) => {
  console.error(err?.stack || String(err));
  process.exit(1);
});
"""
        )
        self.write_runner(code)
        result = self.run_node('runner.ts', self.ws_url(self.url))
        self.assertEqual(
            result.returncode, 0,
            f'node runner failed:\nstdout={result.stdout}\nstderr={result.stderr}',
        )
        parsed = json.loads(result.stdout)
        self.assertEqual(parsed['a'], [1, 2, 3, 99])
        self.assertEqual(parsed['b'], [1, 2, 3])
