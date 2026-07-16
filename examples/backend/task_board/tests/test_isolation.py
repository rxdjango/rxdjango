"""Two-connection isolation and cross-connection delivery for the routed
tier (routed-list-delivery task 5.3, task 3.1's "two connections on
different dimension values stay isolated" scenario), and the deferred task
2.4 autodiscovery integration test: a management-command writer that never
imports `task_board.channels` still reaches a connection's dimension group,
because `rxdjango`'s `AppConfig.ready()` imported the registration for it.
"""

from __future__ import annotations

import json

from django.core.management import call_command

from testing.integration import RxIntegrationTestCase

from task_board.models import Project, Task


class TaskBoardIsolationIntegrationTests(RxIntegrationTestCase):
    app_label = 'task_board'
    channel = 'TaskBoardChannel'
    url = '/ws/task_board/'

    def setUp(self):
        super().setUp()
        Task.objects.all().delete()
        Project.objects.all().delete()
        self.p1 = Project.objects.create(id=201, name='P1')
        self.p2 = Project.objects.create(id=202, name='P2')

    def _two_connection_runner(self, body: str) -> str:
        return (
            'import { TaskBoardChannel } from '
            '"./task_board/task_board.channels.ts";\n'
            + r"""
const wsUrl = process.argv[2];

function connect(): Promise<any> {
  const channel: any = new (TaskBoardChannel as any)(wsUrl);
  return new Promise<any>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("connect timeout")), 5000);
    const unsub = channel.rx.subscribe(() => {
      clearTimeout(timer);
      unsub();
      resolve(channel);
    });
  });
}

function waitFor(cond: () => boolean, label: string, timeout = 5000): Promise<void> {
  return new Promise((resolve, reject) => {
    const start = Date.now();
    const check = () => {
      if (cond()) return resolve();
      if (Date.now() - start > timeout) return reject(new Error(`wait_for timeout: ${label}`));
      setTimeout(check, 10);
    };
    check();
  });
}

async function main() {
""" + body + r"""
}

main().catch((err) => {
  console.error(err?.stack || String(err));
  process.exit(1);
});
"""
        )

    def test_creation_reaches_only_the_matching_connection(self):
        code = self._two_connection_runner(r"""
  const a = await connect();
  const b = await connect();
  await a.select_project(201);
  await b.select_project(202);
  await waitFor(() => a.tasks !== null, "a bound");
  await waitFor(() => b.tasks !== null, "b bound");

  await a.add_task("Only for A", 1);
  await waitFor(() => a.tasks.length === 1, "a sees its own creation");

  // b never sees a creation announced to a different project_id value.
  await new Promise((resolve) => setTimeout(resolve, 300));

  process.stdout.write(JSON.stringify({
    a: a.tasks.map((t: any) => t.name),
    b: b.tasks.map((t: any) => t.name),
  }));
  process.exit(0);
""")
        self.write_runner(code)
        result = self.run_node('runner.ts', self.ws_url(self.url))
        self.assertEqual(
            result.returncode, 0,
            f'node runner failed:\nstdout={result.stdout}\nstderr={result.stderr}',
        )
        parsed = json.loads(result.stdout)
        self.assertEqual(parsed['a'], ['Only for A'])
        self.assertEqual(parsed['b'], [])

    def test_dimension_move_leaves_one_connection_and_enters_the_other(self):
        task = Task.objects.create(name='Movable', status='open', priority=1, project_id=201)

        code = self._two_connection_runner(r"""
  const a = await connect();
  const b = await connect();
  await a.select_project(201);
  await b.select_project(202);
  await waitFor(() => a.tasks !== null, "a bound");
  await waitFor(() => b.tasks !== null, "b bound");
  await waitFor(() => a.tasks.length === 1, "a holds the row before the move");

  await a.move_task(""" + str(task.id) + r""", 202);
  await waitFor(() => a.tasks.length === 0, "a loses the row live");
  await waitFor(() => b.tasks.length === 1, "b gains the row live");

  process.stdout.write(JSON.stringify({
    a: a.tasks.map((t: any) => t.name),
    b: b.tasks.map((t: any) => t.name),
  }));
  process.exit(0);
""")
        self.write_runner(code)
        result = self.run_node('runner.ts', self.ws_url(self.url))
        self.assertEqual(
            result.returncode, 0,
            f'node runner failed:\nstdout={result.stdout}\nstderr={result.stderr}',
        )
        parsed = json.loads(result.stdout)
        self.assertEqual(parsed['a'], [])
        self.assertEqual(parsed['b'], ['Movable'])

    def test_management_command_writer_broadcasts_via_autodiscovered_routing(self):
        """`create_task` (task 2.4) never imports `task_board.channels`
        itself -- only `task_board.models` -- and still reaches a live
        connection's dimension group when driven through `call_command`,
        exactly the "writer process with no channel import of its own"
        shape ADR-0018 D6 exists for.

        This test's *own* process also has `task_board.channels` imported
        already (this suite's `RxIntegrationTestCase.setUp` runs codegen
        over it), so it does not by itself isolate autodiscovery from "some
        other import happened to run first" -- that stronger claim (nothing
        in the whole process ever imports the module, only
        `AppConfig.ready()` does) is `packages/core/tests/test_apps.py`'s
        marker-module test. What this test pins is the write path's actual
        behavior: a command that only ever touches `models.py` still
        broadcasts correctly.
        """
        code = self._two_connection_runner(r"""
  const a = await connect();
  await a.select_project(201);
  await waitFor(() => a.tasks !== null, "a bound");

  process.stdout.write(JSON.stringify({ ok: true }));
  process.exit(0);
""")
        self.write_runner(code)
        result = self.run_node('runner.ts', self.ws_url(self.url))
        self.assertEqual(result.returncode, 0, result.stderr)

        call_command('create_task', 'Via command', '201', '--priority=1')

        # Poll the already-bound connection for the row the command created.
        second_code = self._two_connection_runner(r"""
  const a = await connect();
  await a.select_project(201);
  await waitFor(() => a.tasks !== null, "a bound");
  await waitFor(
    () => a.tasks.some((t: any) => t.name === "Via command"),
    "management-command creation relayed",
  );
  process.stdout.write(JSON.stringify({ ok: true }));
  process.exit(0);
""")
        self.write_runner(second_code)
        result = self.run_node('runner.ts', self.ws_url(self.url))
        self.assertEqual(
            result.returncode, 0,
            f'node runner failed:\nstdout={result.stdout}\nstderr={result.stderr}',
        )
