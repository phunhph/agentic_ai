# DANN Agentic Architecture Documentation

## Overview
DANN (Dynamic Agentic Neural Network) transitioned to a multi-agent orchestration architecture using **LangGraph** and **MCP patterns**. The system is decomposed into autonomous, single-responsibility agents.

## Directory Structure
- `v2/agents/`: Independent agent implementations.
  - `ingest/`: Parses raw user input.
  - `reasoning/`: Determines intent & persona alignment.
  - `planning/`: Decomposes high-level goals into executable tasks.
  - `execution/`: Invokes tools (MCP pattern) to perform operations.
  - `learning/`: Neural Matrix updates & feedback loops.
- `v2/graph/`: Orchestration logic defining the workflow (State machine).

## Architectural Principles
1. **Single Responsibility:** Each agent package only does one thing.
2. **State Machine:** Workflow is defined as a `LangGraph` State Machine to allow cyclic loops (re-planning/re-reasoning).
3. **MCP Compatibility:** All interactions between agents happen through controlled state updates and defined interfaces.
4. **Self-Evolution:** The `LearningAgent` continuously feeds data back into the `NeuralMatrix`.

## Adding New Agents
To add a new agent, create a directory in `v2/agents/`, implement the agent logic, and register it in `v2/graph/orchestrator.py`.
