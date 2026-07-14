# RxDjango

**Reactive Django models with typed TypeScript clients. No manual WebSocket plumbing.**

RxDjango lets you declare reactive state on the server using familiar DRF
serializers and have it automatically streamed to a strongly-typed client.
When the underlying models change — through a save, an action, or any
external event — every connected frontend sees the update without polling,
without writing a consumer, and without managing channel groups by hand.

This document assumes you know Django, Django REST Framework, Django
Channels, and React. If you've ever built a real-time feature on Django and
ended up writing the same group-management, signal-handler, message-routing
boilerplate for the third time, RxDjango is for you.

---

## Table of contents

1. [The five-minute version](#the-five-minute-version)
2. [Declaring a channel](#declaring-a-channel)
3. [Generating the TypeScript client](#generating-the-typescript-client)
4. [Wiring URLs](#wiring-urls)
5. [Using the channel from React](#using-the-channel-from-react)
6. [Actions: calling the server from the client](#actions-calling-the-server-from-the-client)
7. [Authorization with grants](#authorization-with-grants)
8. [External events with @consumer](#external-events-with-consumer)
9. [Derived values](#derived-values)
10. [Architecture](#architecture)
11. [Caching and reconnection](#caching-and-reconnection)
12. [The rx primitive: design notes](#the-rx-primitive-design-notes)

---

## The five-minute version

Here is a complete real-time project view. The server:

```python
# myapp/channels.py
from rxdjango import ContextChannel, rx, action
from myapp.serializers import ProjectSerializer, UserSerializer
from myapp.models import Project

class ProjectChannel(ContextChannel):
    user = rx.model(UserSerializer())
    project = rx.model(ProjectSerializer())

    async def on_connect(self, project_id: int):
        self.project = await Project.objects.aget(id=project_id)

    @action
    async def authenticate(self, token: str):
        user = await validate_token(token)
        self.user = user
        if user.can_edit(self.project):
            self.grant('project.name')
            self.grant('project.task_set')
```

The client, after running `manage.py makefrontend`:

```tsx
// app/ProjectView.tsx
import { useProjectChannel } from '@/rxdjango/myapp';

export function ProjectView({ projectId, token }: Props) {
  const { state, authenticate } = useProjectChannel({ project_id: projectId });

  useEffect(() => { authenticate(token); }, [token]);

  if (!state.project) return <Spinner />;

  return (
    <div>
      <h1>{state.project.name}</h1>
      <ul>
        {state.project.task_set.map(task => (
          <li key={task.id}>{task.title}</li>
        ))}
      </ul>
      <button onClick={() => state.project.task_set.create({ title: 'New task' })}>
        Add task
      </button>
    </div>
  );
}
```

That's the whole loop. Any save to the project or any task — from this
client, another client, the Django admin, a Celery job, or a `psql` session
— shows up here in milliseconds. The `create` button works because the
server granted `project.task_set` for this user. Without that grant, the
method would still appear on the typed state (so TypeScript stays clean)
but the call would be rejected at runtime.

The rest of this document fills in how each piece works.

---

## Declaring a channel

A `ContextChannel` is a class whose attributes declare reactive state.
RxDjango uses the `rx` primitive to mark a field as reactive. There are
three kinds of reactive fields, expressed in two call shapes.

**Scalar fields** carry a Python value:

```python
class MyChannel(ContextChannel):
    counter = rx[int](0)
    label = rx[str | None](None)
    multiplier = rx[float](1.0)
```

The bracketed type declares the value type and the call argument provides
the initial value. The bracketed type must accommodate the initial value,
which the type checker enforces and which RxDjango verifies at
class-construction time.

**Model fields** hold a model instance (or list of instances), shaped by
the given serializer:

```python
from myapp.serializers import ProjectSerializer, TaskSerializer

class MyChannel(ContextChannel):
    project = rx.model(ProjectSerializer())
    favorite_tasks = rx.model(TaskSerializer(many=True))
```

Pass any DRF serializer. Use `many=True` for collections. The serializer
instance carries the type information and any DRF configuration RxDjango
needs.

**Derived fields** are computed from other reactive fields. The first
argument is the compute callable; `deps` lists the reactive paths it
reads:

```python
class MyChannel(ContextChannel):
    multiplier = rx[int](2)
    project = rx.model(ProjectSerializer())
    weighted_task_count = rx[int](
        lambda self: (self.project.task_set.count() if self.project else 0)
                     * self.multiplier,
        deps=['project', 'project.task_set', 'multiplier'],
    )
```

Derived fields share the `rx[T](...)` shape with scalars; the presence
of a callable plus `deps=` is what marks them derived. They are covered
in detail in [Derived values](#derived-values).

The set of declared `rx` fields is static — fields cannot be added or
removed at runtime. This is what allows the TypeScript generator to emit a
complete typed interface for the channel at build time.

### Lifecycle hooks

Two optional async hooks are available. `on_connect` runs when a client
connects, before any state is sent. Keyword arguments come from the URL
pattern (see [Wiring URLs](#wiring-urls) below).

```python
class ProjectChannel(ContextChannel):
    user = rx.model(UserSerializer())
    project = rx.model(ProjectSerializer())

    async def on_connect(self, project_id: int):
        self.user = AnonymousUser()
        self.project = await Project.objects.aget(id=project_id)

    async def on_disconnect(self):
        # Release any resources held by this channel instance.
        pass
```

Inside a hook or action, assign to a serializer field by passing a model
instance. RxDjango handles serialization, subscription registration, and
streaming the initial state to the client. Reassign the same field later
and RxDjango computes the diff between the old and new subscription sets,
preserving continuity for any instances common to both. Assign `None` to
clear the field on the client.

For collection fields declared with `many=True`, the modification path is
through `create` and `delete` methods on the field's nodes (see
[Authorization with grants](#authorization-with-grants)). Reassigning the
whole list is also valid when the developer wants to swap the entire
contents at once.

---

## Generating the TypeScript client

RxDjango ships with a management command that introspects every routed
channel and emits a typed TypeScript SDK:

```bash
python manage.py makefrontend
```

This produces, for each Django app with channels, a directory of TypeScript
files containing:

- A typed interface for each model serializer used in any channel field,
  matching the serializer's output shape exactly.
- A typed channel class for each `ContextChannel`, with typed `state`,
  typed `@action` methods, and typed write methods (`save`, `create`,
  `delete`) on every node where they apply.
- A React hook (`useProjectChannel`) wrapping the channel class for
  ergonomic use in components.

Re-run the command whenever serializers or channels change. In development
this typically runs as part of the watcher.

The output directory is configurable. By default it lands at
`frontend/src/rxdjango/<app_label>/` so the generated SDK sits alongside
the rest of your client code.

---

## Wiring URLs

Channels are routed through Django Channels' URL system. RxDjango provides
a `path` helper that mirrors the standard Django one:

```python
# myapp/routing.py
from rxdjango.routing import path
from myapp.channels import ProjectChannel, DashboardChannel

websocket_urlpatterns = [
    path('ws/projects/<int:project_id>/', ProjectChannel.as_asgi()),
    path('ws/dashboard/', DashboardChannel.as_asgi()),
]
```

Then mount it in your ASGI configuration the same way you would any
Channels routing module:

```python
# myproject/asgi.py
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from myapp.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    'http': get_asgi_application(),
    'websocket': URLRouter(websocket_urlpatterns),
})
```

URL kwargs are passed to `on_connect` as keyword arguments. The
`<int:project_id>` capture in the example above becomes the `project_id`
parameter on `on_connect(self, project_id: int)`.

---

## Using the channel from React

The generated React hook handles connection lifecycle, reconnection, and
state synchronization. Call it with the URL parameters and you get back a
reactive state object plus any `@action` methods.

```tsx
import { useProjectChannel } from '@/rxdjango/myapp';

function ProjectView({ projectId }: { projectId: number }) {
  const { state, connected, authenticate } = useProjectChannel({
    project_id: projectId,
  });

  if (!connected) return <ConnectionLost />;
  if (!state.project) return <Spinner />;

  return <ProjectDetails project={state.project} />;
}
```

`state` is a fully-typed object whose shape matches the channel's `rx`
fields. Reading `state.project.task_set` returns a typed list of tasks.
Reading `state.project.task_set[0].assignee.email` resolves through the
nested serializers as declared on the server. The shape on the client is
exactly the shape your serializers produce on the server.

State updates trigger re-renders through the standard React mechanism. The
hook uses fine-grained subscriptions internally: a component reading
`state.project.name` re-renders when the project name changes, not when an
unrelated task changes.

The hook also exposes `connected` (boolean), `error` (any connection
error), and methods for any `@action` declared on the channel.

---

## Actions: calling the server from the client

`@action` declares a method that the client can call as an async function.
Arguments and return values are typed end-to-end.

```python
from rxdjango import ContextChannel, rx, action

class ProjectChannel(ContextChannel):
    project = rx.model(ProjectSerializer())
    last_search_results = rx.model(TaskSerializer(many=True))

    @action
    async def search_tasks(self, query: str, limit: int = 20) -> int:
        results = [t async for t in Task.objects.filter(
            project=self.project,
            title__icontains=query,
        )[:limit]]
        self.last_search_results = results
        return len(results)
```

On the client, `search_tasks` is a typed method on the hook's return
value:

```tsx
const { state, search_tasks } = useProjectChannel({ project_id });

const handleSearch = async (query: string) => {
  const count = await search_tasks(query, 50);
  console.log(`Found ${count} tasks`);
  // state.last_search_results is now populated with the results.
};
```

Action calls are RPC-shaped: the client awaits a return value. They are
also reactive: any `rx` field assignments inside the action body
propagate to the client as part of the same round trip, so by the time the
promise resolves, the state already reflects the action's effects.

Within a single action, state is consistent: external saves and consumer
events that arrive while the action body is running are queued and
applied between actions, never interleaved with the body. Concurrent
updates from other clients can land before or after, but not during.

Actions are how clients trigger server-side work that doesn't fit a model
save — searches, complex queries, mode switches, authentication, anything
that needs server logic.

### Action errors

Raise any exception from an action body and the client receives a typed
rejection. RxDjango ships with a small set of standard exception classes
(`AuthenticationFailed`, `Forbidden`, `ValidationError`, `NotFound`) that
map to corresponding error types on the client.

```python
@action
async def authenticate(self, token: str):
    user = await validate_token(token)
    if user is None:
        raise AuthenticationFailed("Invalid token")
    self.user = user
```

```tsx
try {
  await authenticate(token);
} catch (err) {
  if (err instanceof AuthenticationFailed) {
    redirectToLogin();
  }
}
```

---

## Authorization with grants

Write permissions are issued at runtime by the server, inside `@action`
handlers or lifecycle hooks. There is no class-level writability
declaration — authorization is a function of who the user turned out to be
and what they're allowed to do, which is information that only exists at
runtime.

```python
class ProjectChannel(ContextChannel):
    user = rx.model(UserSerializer())
    project = rx.model(ProjectSerializer())

    async def on_connect(self, project_id: int):
        self.project = await Project.objects.aget(id=project_id)

    @action
    async def authenticate(self, token: str):
        user = await validate_token(token)
        if not user.can_view(self.project):
            raise Forbidden()
        self.user = user

        if user.can_edit(self.project):
            self.grant('project.name')
            self.grant('project.description')
            self.grant('project.task_set')
            self.grant('project.task_set.**')
```

### Path syntax

A grant path is a dot-separated sequence starting with an `rx` field name
on the channel, followed by serializer field names. Three forms are
supported:

- **Specific field**: `'project.name'` grants writes to that one field.
- **Wildcard**: `'project.task_set.*'` grants writes to every direct field
  of every task in the set.
- **Recursive wildcard**: `'project.task_set.**'` grants writes through
  every nested serializer reachable from each task.

### Operations

The optional second argument is a list of operations from
`rxdjango.operations`: `SAVE`, `CREATE`, `DELETE`. Defaults are inferred
from what the path points at:

- A scalar field defaults to `[SAVE]`.
- A relation field (foreign key, many-to-many, reverse manager) defaults
  to `[SAVE, CREATE, DELETE]`.

Pass an explicit list to override:

```python
self.grant('project.task_set', [CREATE])  # can create tasks but not delete
```

The recursive form is a distinct syntax (`**`), not a flag on the
single-wildcard form. Grants and revokes match by path string, so
`'a.b.*'` and `'a.b.**'` are independent entries.

### Path-bound vs pinned grants

By default, a grant follows the channel's *path*, not a specific instance.
If `self.project` is later reassigned to a different project, a grant on
`'project.name'` continues to apply to whatever project is now at
`self.project`. This matches the common case: "the user has editor
permissions on the current project, whatever that happens to be."

For grants that should follow a specific instance instead, pass
`to='instance'`:

```python
self.grant('project.name', to='instance')
```

A pinned grant binds to the instance present at the path *at grant time*.
If the channel later swaps in a different instance, the pinned grant
becomes inert. If the original instance is reassigned to the same path
later, the grant resumes.

### Revocation

`self.revoke(path, ...)` cancels a grant. Arguments must match the
original `grant` call exactly — same path, same `to`. This makes grant
bookkeeping a simple table lookup with no overlap rules to remember.

```python
self.grant('project.task_set.**')
# ...later...
self.revoke('project.task_set.**')
```

### Frontend surface

Grants translate to method handles on the corresponding nodes of the
client state tree:

```tsx
// Edit a scalar field on the project.
await state.project.save({ name: 'New name' });

// Create a new task in the project's task set.
await state.project.task_set.create({ title: 'Review PR' });

// Update an existing task.
await state.project.task_set[0].save({ done: true });

// Delete a task.
await state.project.task_set[1].delete();
```

The TypeScript SDK exposes these methods on every applicable typed node.
Whether a particular call succeeds depends on the runtime grants the
server has issued for the active connection. A call to an ungranted path
receives a `Forbidden` rejection.

---

## External events with @consumer

`@action` covers events triggered by the client. Model saves are picked up
automatically through Django's signals. The remaining category is events
that arrive from neither — a Celery task completing, a webhook from an
external service, a custom Channels group message broadcast from elsewhere
in your code.

`@consumer` is the escape hatch for those.

```python
from rxdjango import ContextChannel, rx, consumer
from rxdjango.operations import group_send

class DashboardChannel(ContextChannel):
    user = rx.model(UserSerializer())
    job_status = rx[str]('idle')

    @consumer('jobs')
    async def on_job_event(self, event: dict):
        if event['user_id'] != self.user.id:
            return
        self.job_status = event['status']
```

`@consumer('jobs')` subscribes the channel to the Channels group named
`jobs`. Whenever any code in the project does:

```python
await group_send('jobs', {'user_id': 42, 'status': 'completed'})
```

…every channel instance subscribed to `jobs` receives the event in its
handler. The handler is an ordinary method on the channel — it can read
and assign `rx` fields exactly like an `@action` body, and any state
changes propagate to the client.

Use `@consumer` for cross-cutting events like background-job progress,
external webhook fan-out, or system-wide announcements. Use `@action` for
client-initiated calls. Use model signals (handled automatically) for
ORM-driven updates.

---

## Derived values

A reactive field whose value is computed from other reactive fields is
declared by passing a callable and a list of dependency paths:

```python
class ProjectChannel(ContextChannel):
    project = rx.model(ProjectSerializer())
    multiplier = rx[int](1)

    weighted_task_count = rx[int](
        lambda self: (self.project.task_set.count() if self.project else 0)
                     * self.multiplier,
        deps=['project', 'project.task_set', 'multiplier'],
    )
```

The first argument is the compute callable, invoked with `self`. The
`deps` keyword argument is a list of dependency paths using the same
syntax as grants. A path may reference another `rx` field on the same
channel (`'multiplier'`) or a field reachable through a model-typed `rx`
(`'project.task_set'`).

Dependency tracking is **manual**: every `rx` field the callable reads
must appear in `deps`. The example above lists `'project'` because the
callable reads `self.project`, and `'project.task_set'` because it reads
`self.project.task_set`. Omitting a path means the field will not
recompute when that dependency changes. RxDjango does not introspect the
callable to infer dependencies — that would require either AST parsing
(fragile) or a reactive-tracking layer (heavy), neither of which buys
enough over an explicit list.

The compute callable may be sync or async. It runs once during channel
initialization so the value is present in the initial state dump, then
again whenever any dependency changes. The new value is diffed against the
old one before it is broadcast — recomputes that produce the same value
do not generate client traffic.

Direct assignment to a derived field raises. Derived fields are read-only
on the frontend and the TypeScript generator marks them `readonly`.

Cycles among derived fields are detected at class-construction time and
raise immediately, not at runtime.

Wildcards are supported for derived dependencies, with the same syntax
as grants: `'project.manager.*'` triggers a recompute when any direct
field of the manager changes; `'project.manager.**'` triggers on any
nested field reachable through it.

---

## Architecture

This section explains what RxDjango is doing under the hood. None of it is
required reading to use the framework, but it helps when debugging or
tuning a deployment.

### One subscription per (serializer, instance)

Every `(serializer_class, instance_id)` pair is a Channels group. When you
assign `self.project = some_project_instance`, RxDjango:

1. Serializes the project through `ProjectSerializer` (the serializer
   declared on the `rx` field).
2. Walks the serialized output for nested instances. For each one, it
   identifies the `(nested_serializer, nested_id)` pair and joins that
   group too.
3. Sends a flat-instance dump to the client — one entry per visited
   instance, identified by `(serializer_dotted_path, id)`.
4. The client's `StateBuilder` receives the flat entries and reconstructs
   the nested object graph using the foreign-key references present in
   each entry.

Every channel that has touched a given `(serializer, instance)` pair is
subscribed to the same group. When any save happens to the underlying
model, RxDjango's signal handler:

1. Identifies which serializers in the project include this model.
2. For each one, re-serializes the instance and broadcasts the new flat
   dump to the corresponding `(serializer, id)` group.
3. Every subscribed channel forwards the dump to its client.
4. Each client's `StateBuilder` updates the affected entries in its local
   state tree, which triggers re-renders of components reading those
   entries.

The crucial property is that **subscription is keyed by serializer, not by
model**. Two channels that view the same Project instance through
different serializers (one for editors, one for read-only viewers, with
different fields exposed) receive different broadcasts and are
independently invalidated. The cache key, the group key, and the wire
format all use the same `(serializer, id)` identity.

### Refcounted subscriptions

A single channel often references the same `(serializer, instance)` pair
from multiple places — the project at `self.project` includes a manager
in `project.manager`, and the same user might also be at `self.user`. The
channel maintains a refcount per pair: subscriptions are added when the
count goes from zero to one and dropped when it returns to zero. Group
operations are batched per assignment, so a reassignment that swaps in a
new project produces a single Redis round trip for the entire diff.

### Flat wire format, nested client reconstruction

The wire format is a list of flat instance dumps, each carrying its
`(serializer, id)` identity and its serialized fields. Foreign-key
references inside a dump are *ids*, not embedded objects. The client's
`StateBuilder` is what reassembles the graph: it stores instances by
`(serializer, id)` and resolves references on read.

This is why progressive streaming works. RxDjango doesn't wait for the
entire serializer tree to resolve before sending — instances are pushed
to the client as they're produced, breadth-first: an `rx.model` field
assignment executes a compiled, pk-first query plan and flushes each
completed layer as its own `rx` frame the moment it's ready, so an
instance's frame always precedes the frame of every parent referencing
it. The client renders a typed `{ id, _loaded: false }` stub for any
reference whose target hasn't arrived yet; the stub is replaced by the
real instance, unconditionally, the moment its frame lands. The UI shows
loading state per-row, not per-tree.

Frames for the same field are **merge frames**, not replacements: the
client merges each incoming layer into that field's accumulated flat
state per instance, keyed by `(serializer, id)` and reconciled by a
`_v` version watermark rather than by arrival order. This matters
because the server subscribes a connection to live broadcasts *before*
fetching the initial snapshot, so a live update for a row can arrive
ahead of that row's own snapshot layer; the watermark ensures the newer
data always wins regardless of which one the client saw first. Stubs
carry no watermark, so any real instance replaces one unconditionally.
Reassigning an `rx.model` field (including to `None`) before its layers
have finished arriving supersedes the in-flight walk outright — no
further frames from the superseded assignment are sent.

#### Cross-instance consistency during load

Because each layer is its own query, executed at its own instant, a
write landing in the middle of a walk can be reflected in some
already-fetched layers but not others — a project fetched before a
task's assignee changes, for instance, can briefly show the task under
its old assignee. This is an accepted framework semantic, not a bug:
holding a snapshot-isolated transaction across the whole walk was judged
not worth the cost, and the tear is self-correcting. Cross-instance
invariants converge once every layer has arrived, and any individual
instance is repaired sooner than that by the same watermarked live
events described above — a write to a row broadcasts to every connection
already subscribed to it, independent of where that row's fetch was in
the walk. What's guaranteed is *eventual, per-instance* consistency
during load, not a consistent cross-instance snapshot at every instant.

### Action and consumer dispatch

`@action` methods are called from the client with a request id. The
server runs the method, captures any `rx` field changes that occurred
during execution, and sends back a single message containing both the
state diff and the action return value tagged with the request id. The
client awaits the request id and resolves the corresponding promise.

`@consumer` methods are dispatched by Channels group events, exactly as
in vanilla Django Channels. RxDjango wraps them to capture `rx` field
changes the same way `@action` does, so a handler that updates `rx`
fields produces the appropriate client broadcasts.

### Where the framework lives

RxDjango is a Django app and a Channels consumer. It runs inside your
existing ASGI process. There is no separate worker, no out-of-band
service, no daemon to deploy. The only infrastructure dependencies are
the ones Channels itself needs (a channel layer, typically Redis) and an
optional cache backend.

---

## Caching and reconnection

### Caching

Caching is optional and configured globally:

```python
# settings.py
RX_CACHE_BACKEND = 'mongodb'   # or 'memcached', or None to disable
RX_CACHE_LOCATION = 'mongodb://localhost:27017/rxdjango'
```

Cache entries are keyed by `(serializer_dotted_path, instance_id)` and
hold the flat serialized form. They are populated on first serialize and
invalidated by `post_save`/`post_delete` for the relevant
`(model, id)` across every serializer that includes that model. The set
of relevant serializers is computed once at startup by introspecting
declared channels.

Caching is a pure optimization. With caching disabled, a channel
initialization re-runs the serializers against the live ORM. The
framework remains correct.

The global default is overridable per channel:

```python
class MyChannel(ContextChannel):
    class Meta:
        cache = False
```

Or per field:

```python
class MyChannel(ContextChannel):
    project = rx.model(ProjectSerializer(), cache=False)
```

### Reconnection

Channel state survives client disconnections. Each connection is given a
session id, persisted in Redis with a TTL. The session record contains
the set of `(field_name, value)` pairs that describe the channel's state
— primarily the instance ids assigned to each `rx` field, plus any
scalar values.

When the client reconnects, it presents its session id. If the session
exists, the consumer reconstructs the channel and re-runs `on_connect`,
allowing the developer's hook to perform any setup that should happen on
every connection (including reconnections). The previously assigned
instances are then re-fetched and re-subscribed.

Grants are not persisted across reconnections. A grant is the live
expression of an authorization decision, and the framework's position is
that authorization should be re-evaluated rather than remembered. The
typical pattern is for the client to call `authenticate` again on
reconnect, which re-issues whatever grants the server's authentication
logic determines are appropriate. This puts grant lifetime under the
developer's control rather than tying it to a session TTL.

### Last-update reconnection

For channels subscribed to large collections, sending the full state on
every reconnect is wasteful. RxDjango supports a `last_update`
optimization: the client tracks the timestamp of the most recent update
it has received per `(serializer, id)`, and on reconnect sends those
timestamps to the server. The server returns only the entries that have
changed since.

This requires a cache backend that supports indexed queries, which is
why the cache layer is pluggable. With MongoDB as the backend, RxDjango
indexes the cache on `(serializer, last_update)` and the reconnect
diff query is a single indexed lookup. With memcached or no cache, a
reconnect falls back to a full state dump.

For applications where reconnect bandwidth matters — large dashboards,
collaborative editors, anything with a long-lived state tree — MongoDB
caching is the recommended configuration.

### Session loss

If the session id is not found on reconnect (Redis eviction, server
restart without persistence, expired TTL), the client treats the
connection as fresh and re-runs whatever flow originally populated the
state. This is acceptable because session loss is a UX hiccup, not a
data-integrity issue: the source of truth is always Postgres.

---

## The rx primitive: design notes

This section is for developers who want to understand why `rx` is shaped
the way it is. Skip it if you just want to ship.

### Two call shapes for two semantics

Scalar and model fields use different call shapes deliberately, because
they have different semantics and unifying them would obscure that.
Derived fields share the scalar shape — they produce a typed value —
distinguished by a callable plus `deps`.

A scalar field is a value that exists from channel construction. It
needs an initial value at declaration time. The bracketed type carries
the type, the call argument carries the value:

```python
counter = rx[int](0)
```

A model field is a slot that gets filled later by assignment. It has no
construction-time value — it's implicitly null until the developer
assigns a model instance, typically inside `on_connect` or an action.
The serializer instance carries everything RxDjango needs (the model
class, `many`, DRF context), which is why it goes in the call argument
rather than the bracket:

```python
project = rx.model(ProjectSerializer())
```

Trying to force these into one shape produces awkward results. A unified
`rx[ProjectSerializer](None)` looks like it should work but elides the
fact that `ProjectSerializer` is a configured DRF instance, not a type;
it also implies the field has an initial value when in fact the slot is
always implicitly nullable until first assignment. The split between
`rx[T](...)` (a typed value, scalar or derived) and `rx.model(...)` (a
slot bound to a model instance) is the honest representation of two
genuinely different things.

### Static field set

The set of declared `rx` fields is fixed at class-construction time.
Fields cannot be added or removed at runtime. This is what allows the
TypeScript generator to emit a complete typed channel interface, which
is what allows the entire client experience to be typed end-to-end. The
constraint is what enables the payoff.

### One path language for everything

Grant paths, revoke paths, derived-value dependencies, and the
underlying wire-format identities all use the same `rx_field.serializer_field.…`
syntax, with the same wildcard rules. Learning the path language once
unlocks read, write, and computed surfaces. This unification is why the
framework's surface is small relative to what it does.

---

## Comparisons

**vs. raw Django Channels.** Channels is a transport layer. RxDjango is a
framework that uses Channels for transport and provides everything above
it: serialization, subscription management, cache invalidation, typed
client generation, authorization. If you want fine control over
individual messages, Channels alone is right. If you want reactive
state, RxDjango.

**vs. Supabase Realtime / Firebase.** Those are excellent if you can fit
your app into a Postgres-with-row-policies or document-store model.
RxDjango fits into a Django + DRF model — your serializers are the
contract, including any computed fields, custom representations, and
authorization logic that DRF gives you. If your data shape is more than
"select rows from this table," DRF + RxDjango is going to fit better
than a database-driven realtime layer.

**vs. polling DRF endpoints.** Polling works until it doesn't. The
crossover point is usually around the second feature where the user
expects another tab's changes to show up immediately. Once you're there,
the polling architecture costs more in client requests and server load
than RxDjango costs in WebSocket plumbing.

---

## Status

RxDjango is open source and available on PyPI:

```bash
pip install rxdjango
```

The TypeScript SDK is published to npm:

```bash
npm install @rxdjango/client
```

Full documentation, tutorials, and example projects are at the project
website. Issues, discussions, and contributions are welcome on GitHub.
