# MCP Tool Policy

## Purpose

Control tool access for MCP-connected agents.

## Rules

- MCP servers must be explicitly allowlisted.
- Tools are read-only by default.
- Destructive tools require human approval.
- Tool calls must be logged.
- Secrets must not be exposed through tool responses.
- Agents may not call tools outside the current task scope.

## Required files

- mcp_config.json
- tool_registry.json
- agent_permissions.yaml
