"""Extract normalised SQL sub-expressions for overlap analysis and P2 discovery."""

from __future__ import annotations

import sqlglot
from sqlglot import exp


def extract_sql_fragments(sql: str) -> set[str]:
    """
    Normalised sub-expressions for overlap / discovery propagation.

    Collects table references, column references, and predicate-sized nodes.
    """
    try:
        tree = sqlglot.parse_one(sql.strip(), read="sqlite")
    except Exception:
        return set()

    fragments: set[str] = set()
    for node in tree.walk():
        if isinstance(node, exp.Table):
            name = node.name
            if name:
                fragments.add(f"table:{name.lower()}")
        elif isinstance(node, exp.Column):
            col = node.name
            table = node.table
            if col:
                if table:
                    fragments.add(f"col:{str(table).lower()}.{col.lower()}")
                else:
                    fragments.add(f"col:{col.lower()}")
        elif isinstance(node, (exp.EQ, exp.NEQ, exp.GT, exp.GTE, exp.LT, exp.LTE, exp.Like, exp.In)):
            try:
                frag = node.sql(dialect="sqlite", normalize=True).lower()
                if len(frag) > 3:
                    fragments.add(f"pred:{frag}")
            except Exception:
                pass
        elif isinstance(node, exp.Join):
            try:
                on = node.args.get("on")
                if on is not None:
                    frag = on.sql(dialect="sqlite", normalize=True).lower()
                    if frag:
                        fragments.add(f"join_on:{frag}")
            except Exception:
                pass
    return fragments
