import React, { useState } from 'react';
import { useChannel } from '@rxdjango/react';
import { StaticQuerysetChannel } from '../../rx/static_queryset/static_queryset.channels';
import {
  Sections,
  Button,
  TextInput,
  Row,
  Note,
} from '../../components/demo';

export function StaticQuerysetDemo() {
  const channel = useChannel(StaticQuerysetChannel);
  const [name, setName] = useState('');
  const [priority, setPriority] = useState('0');

  return (
    <Sections>
      <div>
        <Note>
          `tasks` is a bare queryset bound once in `on_connect` -- open
          tasks, ordered by descending priority. Toggling a task&apos;s
          status flips it out of (or back into) the list; bumping priority
          re-sorts it; deleting a task removes it. A newly added task only
          appears when you press Rebind -- updates reach rows already in
          the list, never new rows.
        </Note>
      </div>
      <div>
        {channel.tasks === null ? (
          <p>
            Connecting...
          </p>
        ) : channel.tasks.length === 0 ? (
          <p data-testid="empty-state">
            No open tasks.
          </p>
        ) : (
          <ul className="space-y-3">
            {channel.tasks.map((task) => (
              <li
                key={task.id}
                data-testid={`task-${task.id}`}
                className="flex flex-col gap-2 rounded-md border border-ink/20 p-3 sm:flex-row sm:items-center sm:justify-between"
              >
                <div>
                  <span className="font-medium text-ink">
                    {task.name}
                  </span>
                  <span className="ml-2 text-sm text-primary-700">
                    priority {task.priority}
                  </span>
                </div>
                <Row>
                  <Button
                    variant="secondary"
                    onClick={() => channel.bump_priority(task.id, 1)}
                  >
                    +1 priority
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => channel.toggle_status(task.id)}
                  >
                    Close
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => channel.delete_task(task.id)}
                  >
                    Delete
                  </Button>
                </Row>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div>
        <Row>
          <TextInput
            id="static-queryset-new-task-name"
            label="New task name"
            value={name}
            onChange={setName}
          />
          <TextInput
            id="static-queryset-new-task-priority"
            label="Priority"
            value={priority}
            onChange={setPriority}
          />
          <Button
            variant="secondary"
            onClick={() => channel.add_task(name, parseInt(priority, 10) || 0)}
          >
            Add task
          </Button>
          <Button
            variant="primary"
            onClick={() => channel.rebind()}
          >
            Rebind
          </Button>
        </Row>
      </div>
    </Sections>
  );
}

export default StaticQuerysetDemo;
