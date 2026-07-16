import React, { useEffect, useRef, useState } from 'react';
import { useChannel } from '@rxdjango/react';
import { TaskBoardChannel } from '../../rx/task_board/task_board.channels';
import type { Task } from '../../rx/task_board/task_board.models';
import {
  Sections,
  Note,
  Row,
  Button,
  TextInput,
} from '../../components/demo';

function Board({ projectId, otherProjectId }: { projectId: number; otherProjectId: number }) {
  const channel = useChannel(TaskBoardChannel);
  const selected = useRef<number | null>(null);
  const [name, setName] = useState('');
  const [priority, setPriority] = useState('0');

  useEffect(() => {
    if (selected.current !== projectId) {
      selected.current = projectId;
      channel.select_project(projectId);
    }
  });

  return (
    <div
      data-testid={`board-${projectId}`}
      className="flex-1 space-y-3 rounded-md border border-ink/20 p-4"
    >
      <h3 className="font-semibold text-ink">
        Project {projectId}
      </h3>
      {channel.tasks === null ? (
        <p>
          Connecting...
        </p>
      ) : channel.tasks.length === 0 ? (
        <p data-testid={`empty-state-${projectId}`}>
          No open tasks.
        </p>
      ) : (
        <ul className="space-y-3">
          {channel.tasks.map((task: Task) => (
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
                  onClick={() => channel.move_task(task.id, otherProjectId)}
                >
                  Move to Project {otherProjectId}
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
      <Row>
        <TextInput
          id={`task-board-new-task-name-${projectId}`}
          label="New task name"
          value={name}
          onChange={setName}
        />
        <TextInput
          id={`task-board-new-task-priority-${projectId}`}
          label="Priority"
          value={priority}
          onChange={setPriority}
        />
        <Button
          variant="primary"
          onClick={() => {
            channel.add_task(name, parseInt(priority, 10) || 0);
            setName('');
          }}
        >
          Add task
        </Button>
      </Row>
    </div>
  );
}

export function TaskBoardDemo() {
  return (
    <Sections>
      <div>
        <Note>
          Each board below is its own WebSocket connection, calling
          `select_project` to pick which `project_id` it watches --
          `tasks` declares `routing=&apos;project_id&apos;`, so a task added
          on one board appears live on that board alone, with no rebind.
          Moving a task to the other project makes it disappear from this
          board and appear on the other, live, the moment the write
          commits.
        </Note>
      </div>
      <div className="flex flex-col gap-4 sm:flex-row">
        <Board projectId={1} otherProjectId={2} />
        <Board projectId={2} otherProjectId={1} />
      </div>
    </Sections>
  );
}

export default TaskBoardDemo;
