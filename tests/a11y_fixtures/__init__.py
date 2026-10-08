"""Accessibility render-fixture registry (SOP-TEST-002 §X).

A template is *covered* when an axe scenario puts its rendered DOM in front of
axe-core. There are two canonical paths:

* a real-route scenario (``tests/test_axe_app_pages.py``), or
* a registered fixture state, defined here.

A fixture state is ``template -> named render state -> presentation fixture ->
Jinja render -> browser -> axe``. The render uses the app's real Jinja
environment, real inheritance/includes, real context processors and real
response headers; only the presentation input (the page view model) is
supplied directly instead of being assembled by a route (INV-ARC-022: templates
are pure consumers of supplied presentation data).

What a fixture proves: the template renders, from valid presentation input, to
a DOM that passes axe in that state.

What it does NOT prove: that the production route assembles that view model, or
anything about authentication, navigation, or state produced by running the
application. Those stay with the real-route sweep.

Fixtures must be deterministic, free of PII, and free of persistence: rendering
runs under a guard that fails on any SQL statement.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from typing import Callable

from flask import render_template, template_rendered
from sqlalchemy import event

FIXTURE_MODULES = (
    "tests.a11y_fixtures.public",
    "tests.a11y_fixtures.admin",
    "tests.a11y_fixtures.student",
)


class FixtureRenderError(AssertionError):
    """A registered fixture could not be rendered to HTML."""


@dataclass(frozen=True)
class RenderState:
    template: str
    state: str
    context: Callable[[], dict]
    path: str = "/"
    note: str = ""
    # Role of the signed-in shell a template expects ("teacher", "student", or
    # None for a signed-out page). Some layouts read ``g.canonical_context``
    # directly; the harness binds a fixed, fictional one so they render as they
    # do for a signed-in user. This is display plumbing, not authority: nothing
    # in a fixture authorizes anything.
    actor: str | None = None
    # Query string the page is opened with, for templates whose active view is
    # chosen client-side from it (e.g. ``tab=attendance``).
    query: str = ""
    # Selectors clicked, in order, before axe runs: reveals content that is
    # hidden until a user acts (an inactive tab pane), which axe cannot see.
    interact: tuple[str, ...] = ()

    @property
    def id(self) -> str:
        return f"{self.template}::{self.state}"


@dataclass
class RenderedFixture:
    state: RenderState
    html: str
    headers: dict[str, str]
    status: int
    templates: set[str] = field(default_factory=set)


_REGISTRY: dict[str, RenderState] = {}


def register(template: str, state: str, context: Callable[[], dict], *, path: str = "/", note: str = "",
             actor: str | None = None, query: str = "", interact: tuple[str, ...] = ()) -> RenderState:
    entry = RenderState(template=template, state=state, context=context, path=path, note=note, actor=actor,
                        query=query, interact=interact)
    if entry.id in _REGISTRY:
        raise ValueError(f"duplicate accessibility fixture {entry.id}")
    _REGISTRY[entry.id] = entry
    return entry


def load_registry(registry: dict[str, RenderState] | None = None) -> list[RenderState]:
    """Import every fixture module and return the registered states, sorted."""
    for module in FIXTURE_MODULES:
        importlib.import_module(module)
    return sorted((registry or _REGISTRY).values(), key=lambda s: s.id)


def fixture_templates(states: list[RenderState] | None = None) -> set[str]:
    return {s.template for s in (states if states is not None else load_registry())}


def render_state(flask_app, state: RenderState, *, status: int = 200) -> RenderedFixture:
    """Render one state through the real Jinja environment and response pipeline.

    Raises ``FixtureRenderError`` when the template cannot render, does not
    actually render the template it claims to cover, or touches the database.
    """
    rendered: set[str] = set()
    statements: list[str] = []

    def on_render(sender, template, context, **extra):
        if template.name:
            rendered.add(template.name)

    def on_sql(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.splitlines()[0][:120])

    from app.extensions import db

    template_rendered.connect(on_render, flask_app)
    with flask_app.app_context():
        engine = db.engine
        event.listen(engine, "before_cursor_execute", on_sql)
        try:
            return _render(flask_app, state, status, rendered, statements)
        finally:
            event.remove(engine, "before_cursor_execute", on_sql)
            template_rendered.disconnect(on_render, flask_app)


def _render(flask_app, state, status, rendered, statements) -> RenderedFixture:
    with flask_app.test_request_context(state.path + (f"?{state.query}" if state.query else "")):
        if state.actor:
            from flask import g

            from app.services.context_resolver import CanonicalContext
            from tests.a11y_fixtures._layout import CLASS_ID

            g.canonical_context = CanonicalContext(
                user_id="a11y-fixture-user", class_id=CLASS_ID, seat_id=1, actor_role=state.actor,
            )
        try:
            html = render_template(state.template, **state.context())
        except Exception as exc:
            raise FixtureRenderError(
                f"template: templates/{state.template}\nstate: {state.state}\n"
                f"reason: fixture cannot render: {type(exc).__name__}: {exc}"
            ) from exc
        response = flask_app.make_response((html, status))
        response = flask_app.process_response(response)

    if statements:
        raise FixtureRenderError(
            f"template: templates/{state.template}\nstate: {state.state}\n"
            f"reason: fixture rendering touched the database: {statements[0]}"
        )
    if state.template not in rendered:
        raise FixtureRenderError(
            f"template: templates/{state.template}\nstate: {state.state}\n"
            f"reason: render did not include the template it claims to cover"
        )
    return RenderedFixture(
        state=state,
        html=response.get_data(as_text=True),
        headers={k: v for k, v in response.headers.items() if k.lower() not in {"content-length", "set-cookie"}},
        status=status,
        templates=rendered,
    )
