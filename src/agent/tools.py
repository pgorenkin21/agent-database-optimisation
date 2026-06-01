"""Tool definitions shared across LLM providers."""

from __future__ import annotations

TOOL_DEFINITIONS_OPENAI = [
    {
        "type": "function",
        "function": {
            "name": "execute_sql",
            "description": (
                "Execute a read-only SQL query (SELECT or WITH) on the task database. "
                "Use for exploration; results are returned as text."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "SQLite SELECT query to execute.",
                    }
                },
                "required": ["sql"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_sql",
            "description": (
                "Submit the final SQL query that answers the user's question. "
                "Call this when you are confident in the answer."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "Final SQLite SELECT query.",
                    }
                },
                "required": ["sql"],
            },
        },
    },
]
