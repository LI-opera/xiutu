"""Separate-process technical checkpoint probe, never a diagnosis graph."""

import json
import os
import sys
from typing import TypedDict

import psycopg
from app.infrastructure.db_target import validate_target
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from psycopg.rows import dict_row


class State(TypedDict):
    count: int
    approval: str


def increment(state):
    return {"count": state["count"] + 1}


def pause(state):
    return {"approval": interrupt("approve environment probe")}


mode, workflow, schema = sys.argv[1:]
target = validate_target(os.environ["TEST_DATABASE_URL"], "test")
with psycopg.connect(
    **target.connect_kwargs(schema=schema),
    autocommit=True,
    prepare_threshold=0,
    row_factory=dict_row,
) as conn:
    saver = PostgresSaver(conn)
    saver.setup()
    builder = StateGraph(State)
    builder.add_node("increment", increment)
    builder.add_node("pause", pause)
    builder.add_edge(START, "increment")
    builder.add_edge("increment", "pause")
    builder.add_edge("pause", END)
    graph = builder.compile(checkpointer=saver)
    config = {"configurable": {"thread_id": workflow}}
    if mode == "start":
        graph.invoke({"count": 0, "approval": ""}, config)
    elif mode == "resume":
        if not graph.get_state(config).values:
            print(json.dumps({"error": "unknown_workflow", "pid": os.getpid()}))
            sys.exit(4)
        graph.invoke(Command(resume="approved"), config)
    snapshot = graph.get_state(config)
    print(
        json.dumps(
            {
                "pid": os.getpid(),
                "workflow_id": workflow,
                "values": snapshot.values,
                "next": snapshot.next,
            }
        )
    )
