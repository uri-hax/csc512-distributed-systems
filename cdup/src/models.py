"""Core dataclasses for the CDUP intermediate representation.

Defines the three IR building-blocks used throughout the pipeline:
:class:`Slot` (a memory location), :class:`Statement` (a classified source
statement), and :class:`Segment` (a scoped code block such as a function,
loop, or branch body).
"""

from dataclasses import dataclass, field
from typing import List, Optional, Any, Dict


@dataclass
class Slot:
    """A single named memory location in the IR.

    Represents a variable, parameter, loop iterator, literal constant, or
    struct field slot within a scoped segment.

    Attributes:
        name: The bare (unscoped) name, e.g. ``"x"`` or ``"p1.x"``.
        scoped_name: The fully-qualified name, e.g. ``"root.fn.x"``.
        type: C type string, e.g. ``"int"``, ``"float*"``, ``"field"``.
        constant: ``True`` if this slot holds a literal constant value.
        param: ``True`` if this slot is a function parameter.
        loop_iterator: ``True`` if declared as a ``for``-loop iterator.
        value: The literal value for constant slots; ``None`` otherwise.
        udt_parent: For struct-field slots, the parent variable name.
        udt_type: For struct-field slots, the struct type name.
    """

    name: str
    scoped_name: str
    type: str
    constant: bool = False
    param: bool = False
    loop_iterator: bool = False
    value: Any = None
    udt_parent: Optional[str] = None
    udt_type: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialise the slot to a plain dict for JSON output.

        Returns:
            A dict with all non-default fields populated, suitable for
            ``json.dumps``.
        """
        res: Dict[str, Any] = {
            "name": self.name,
            "scoped_name": self.scoped_name,
            "type": self.type,
            "constant": self.constant,
        }
        if self.param:
            res["param"] = True
        if self.loop_iterator:
            res["loop_iterator"] = True
        if self.value is not None:
            res["value"] = self.value
        if self.udt_parent:
            res["udt_parent"] = self.udt_parent
        if self.udt_type:
            res["udt_type"] = self.udt_type
        return res


@dataclass
class Statement:
    """A classified source statement extracted from a segment.

    Attributes:
        raw: The original source text of the statement.
        kind: Classification label — one of ``"decl"``, ``"assign"``,
            ``"branch"``, ``"loop_head"``, ``"control"``, ``"call"``,
            ``"func_decl"``, or ``"expr"``.
        l_name: Left-hand-side name for assignments and declarations.
        r_names: Names read on the right-hand side.
        expr: Resolved expression-tree dict, or ``None``.
        type: C type string for declaration statements.
        iterator_type: C type of the iterator variable for ``for`` loops.
    """

    raw: str
    kind: str
    l_name: Optional[str] = None
    r_names: List[str] = field(default_factory=list)
    expr: Optional[Dict[str, Any]] = None
    type: Optional[str] = None
    iterator_type: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialise the statement to a plain dict for JSON output.

        Returns:
            A dict with all non-default fields populated, suitable for
            ``json.dumps``.
        """
        res: Dict[str, Any] = {
            "raw": self.raw,
            "kind": self.kind,
            "l_name": self.l_name,
            "r_names": self.r_names,
        }
        if self.expr:
            res["expr"] = self.expr
        if self.type:
            res["type"] = self.type
        if self.iterator_type:
            res["iterator_type"] = self.iterator_type
        return res


@dataclass
class Segment:
    """A scoped code block: a function, loop, branch, struct, or file root.

    Attributes:
        id: Unique integer identifier assigned in parse order.
        parent: The ``id`` of the enclosing segment (equal to ``id`` for root).
        type: One of ``"root"``, ``"function"``, ``"loop"``, ``"branch"``,
            ``"struct"``, or ``"class"``.
        name: Human-readable name, e.g. ``"main"``, ``"loop_1"``.
        scope_path: Dot-separated fully-qualified path,
            e.g. ``"root.main.loop_1"``.
        head: The header statement from the parent that introduced this block,
            e.g. ``"for (int i = 0; i < n; i++) {}"``. ``None`` for the root.
        memory: Variable and parameter slots declared in this scope.
        constants: Literal constant slots used within this scope.
        stmts: Classified statements in program order.
    """

    id: int
    parent: int
    type: str
    name: str
    scope_path: str
    head: Optional[str]
    memory: List[Slot] = field(default_factory=list)
    constants: List[Slot] = field(default_factory=list)
    stmts: List[Statement] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise the segment to a plain dict for JSON output.

        Returns:
            A dict with all fields populated and nested slots/statements
            also serialised, suitable for ``json.dumps``.
        """
        return {
            "id": self.id,
            "parent": self.parent,
            "type": self.type,
            "name": self.name,
            "scope_path": self.scope_path,
            "head": self.head,
            "memory": [s.to_dict() for s in self.memory],
            "constants": [s.to_dict() for s in self.constants],
            "stmts": [s.to_dict() for s in self.stmts],
        }