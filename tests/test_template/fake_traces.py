"""
Fake browser-use traces for testing the template extraction pipeline.

These mimic the AgentHistoryList / AgentHistory / BrowserState interfaces
from browser-use without importing the actual library.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ──────────────────────────────────────────────────────────────
# Mock browser-use types
# ──────────────────────────────────────────────────────────────


@dataclass
class MockElement:
    highlight_index: int
    tag_name: str
    attributes: dict[str, str]
    text_content: str | None = None


@dataclass
class MockElementTree:
    elements: list[MockElement] = field(default_factory=list)

    def get_clickable_elements(self) -> list[MockElement]:
        return self.elements


@dataclass
class MockBrowserState:
    url: str
    title: str = ""
    element_tree: MockElementTree | None = None


@dataclass
class MockActionValue:
    """Simulates a pydantic model field value with model_dump()."""

    _data: dict[str, Any]

    def model_dump(self) -> dict[str, Any]:
        return self._data


class MockAction:
    """Simulates a browser-use ActionModel pydantic model."""

    model_fields: dict[str, Any]

    def __init__(self, **kwargs: Any):
        self.model_fields = {}
        for k, v in kwargs.items():
            self.model_fields[k] = True
            setattr(self, k, v)


@dataclass
class MockActionResult:
    error: str | None = None
    extracted_content: str | None = None


@dataclass
class MockModelOutput:
    actions: list[MockAction] = field(default_factory=list)


@dataclass
class MockHistoryEntry:
    model_output: MockModelOutput | None = None
    result: MockActionResult | None = None
    state: MockBrowserState | None = None


class MockAgentHistoryList:
    """Simulates browser-use AgentHistoryList."""

    def __init__(
        self,
        entries: list[MockHistoryEntry],
        urls: list[str] | None = None,
        done: bool = True,
        duration: float = 30.0,
    ):
        self.history = entries
        self._urls = urls or []
        self._done = done
        self._duration = duration

    def urls(self) -> list[str]:
        return self._urls

    def is_done(self) -> bool:
        return self._done

    def total_duration_seconds(self) -> float:
        return self._duration

    def action_names(self) -> list[str]:
        names = []
        for entry in self.history:
            if entry.model_output:
                for action in entry.model_output.actions:
                    for field_name in action.model_fields:
                        if getattr(action, field_name, None) is not None:
                            names.append(field_name)
        return names

    def errors(self) -> list[str]:
        errs = []
        for entry in self.history:
            if entry.result and entry.result.error:
                errs.append(entry.result.error)
        return errs

    def final_result(self) -> str | None:
        for entry in reversed(self.history):
            if entry.result and entry.result.extracted_content:
                return entry.result.extracted_content
        return None


# ──────────────────────────────────────────────────────────────
# Trace 1: Amazon Search (5 steps — navigate, click, input, send_keys, wait)
# ──────────────────────────────────────────────────────────────


def make_amazon_search_trace() -> MockAgentHistoryList:
    """Simulate: 'Search for wireless mouse under $50 on Amazon'."""

    search_box = MockElement(
        highlight_index=3,
        tag_name="input",
        attributes={
            "id": "twotabsearchtextbox",
            "name": "field-keywords",
            "type": "text",
            "aria-label": "Search Amazon",
            "placeholder": "Search Amazon",
        },
        text_content=None,
    )
    element_tree = MockElementTree(elements=[search_box])

    entries = [
        # Step 0: Navigate to amazon.com
        MockHistoryEntry(
            model_output=MockModelOutput(
                actions=[MockAction(navigate=MockActionValue({"url": "https://www.amazon.com"}))]
            ),
            result=MockActionResult(),
            state=MockBrowserState(
                url="https://www.amazon.com",
                title="Amazon.com",
                element_tree=element_tree,
            ),
        ),
        # Step 1: Click search box
        MockHistoryEntry(
            model_output=MockModelOutput(
                actions=[MockAction(click=MockActionValue({"index": 3}))]
            ),
            result=MockActionResult(),
            state=MockBrowserState(
                url="https://www.amazon.com",
                title="Amazon.com",
                element_tree=element_tree,
            ),
        ),
        # Step 2: Type search query
        MockHistoryEntry(
            model_output=MockModelOutput(
                actions=[
                    MockAction(
                        input=MockActionValue(
                            {"index": 3, "text": "wireless mouse under $50"}
                        )
                    )
                ]
            ),
            result=MockActionResult(),
            state=MockBrowserState(
                url="https://www.amazon.com",
                title="Amazon.com",
                element_tree=element_tree,
            ),
        ),
        # Step 3: Press Enter
        MockHistoryEntry(
            model_output=MockModelOutput(
                actions=[MockAction(send_keys=MockActionValue({"keys": "Enter"}))]
            ),
            result=MockActionResult(),
            state=MockBrowserState(
                url="https://www.amazon.com/s?k=wireless+mouse+under+%2450",
                title="Amazon.com: wireless mouse under $50",
            ),
        ),
        # Step 4: Click on a specific product (DYNAMIC — depends on results)
        MockHistoryEntry(
            model_output=MockModelOutput(
                actions=[MockAction(click=MockActionValue({"index": 15}))]
            ),
            result=MockActionResult(
                extracted_content="Logitech M510 Wireless Mouse - $24.99"
            ),
            state=MockBrowserState(
                url="https://www.amazon.com/s?k=wireless+mouse+under+%2450",
                title="Amazon.com: wireless mouse under $50",
                element_tree=MockElementTree(
                    elements=[
                        MockElement(
                            highlight_index=15,
                            tag_name="a",
                            attributes={
                                "class": "a-link-normal s-no-outline",
                                "href": "/dp/B003NR57BY",
                            },
                            text_content="Logitech M510 Wireless Mouse",
                        )
                    ]
                ),
            ),
        ),
    ]

    return MockAgentHistoryList(
        entries=entries,
        urls=[
            "about:blank",
            "https://www.amazon.com",
            "https://www.amazon.com",
            "https://www.amazon.com",
            "https://www.amazon.com/s?k=wireless+mouse+under+%2450",
            "https://www.amazon.com/dp/B003NR57BY",
        ],
        done=True,
        duration=35.2,
    )


# ──────────────────────────────────────────────────────────────
# Trace 2: Google Search (3 steps — navigate, input, send_keys)
# ──────────────────────────────────────────────────────────────


def make_google_search_trace() -> MockAgentHistoryList:
    """Simulate: 'Search for python tutorial on Google'."""

    search_box = MockElement(
        highlight_index=1,
        tag_name="textarea",
        attributes={
            "name": "q",
            "aria-label": "Search",
            "role": "combobox",
        },
        text_content=None,
    )
    element_tree = MockElementTree(elements=[search_box])

    entries = [
        # Step 0: Navigate to google.com
        MockHistoryEntry(
            model_output=MockModelOutput(
                actions=[MockAction(navigate=MockActionValue({"url": "https://www.google.com"}))]
            ),
            result=MockActionResult(),
            state=MockBrowserState(
                url="https://www.google.com",
                title="Google",
                element_tree=element_tree,
            ),
        ),
        # Step 1: Type search query
        MockHistoryEntry(
            model_output=MockModelOutput(
                actions=[
                    MockAction(
                        input=MockActionValue({"index": 1, "text": "python tutorial"})
                    )
                ]
            ),
            result=MockActionResult(),
            state=MockBrowserState(
                url="https://www.google.com",
                title="Google",
                element_tree=element_tree,
            ),
        ),
        # Step 2: Press Enter
        MockHistoryEntry(
            model_output=MockModelOutput(
                actions=[MockAction(send_keys=MockActionValue({"keys": "Enter"}))]
            ),
            result=MockActionResult(
                extracted_content="Search results for python tutorial"
            ),
            state=MockBrowserState(
                url="https://www.google.com/search?q=python+tutorial",
                title="python tutorial - Google Search",
            ),
        ),
    ]

    return MockAgentHistoryList(
        entries=entries,
        urls=[
            "about:blank",
            "https://www.google.com",
            "https://www.google.com",
            "https://www.google.com/search?q=python+tutorial",
        ],
        done=True,
        duration=12.5,
    )


# ──────────────────────────────────────────────────────────────
# Trace 3: Form Fill (4 steps)
# ──────────────────────────────────────────────────────────────


def make_form_fill_trace() -> MockAgentHistoryList:
    """Simulate: 'Fill out contact form on example.com'."""

    name_input = MockElement(
        highlight_index=2,
        tag_name="input",
        attributes={"id": "name", "type": "text", "name": "name", "placeholder": "Your Name"},
    )
    email_input = MockElement(
        highlight_index=3,
        tag_name="input",
        attributes={
            "id": "email",
            "type": "email",
            "name": "email",
            "placeholder": "Email Address",
        },
    )
    message_input = MockElement(
        highlight_index=4,
        tag_name="textarea",
        attributes={"id": "message", "name": "message", "placeholder": "Your Message"},
    )
    submit_btn = MockElement(
        highlight_index=5,
        tag_name="button",
        attributes={"type": "submit", "class": "btn-primary"},
        text_content="Submit",
    )
    element_tree = MockElementTree(
        elements=[name_input, email_input, message_input, submit_btn]
    )

    entries = [
        # Step 0: Navigate
        MockHistoryEntry(
            model_output=MockModelOutput(
                actions=[
                    MockAction(
                        navigate=MockActionValue({"url": "https://example.com/contact"})
                    )
                ]
            ),
            result=MockActionResult(),
            state=MockBrowserState(
                url="https://example.com/contact",
                title="Contact Us",
                element_tree=element_tree,
            ),
        ),
        # Step 1: Fill name
        MockHistoryEntry(
            model_output=MockModelOutput(
                actions=[
                    MockAction(input=MockActionValue({"index": 2, "text": "John Doe"}))
                ]
            ),
            result=MockActionResult(),
            state=MockBrowserState(
                url="https://example.com/contact",
                title="Contact Us",
                element_tree=element_tree,
            ),
        ),
        # Step 2: Fill email
        MockHistoryEntry(
            model_output=MockModelOutput(
                actions=[
                    MockAction(
                        input=MockActionValue({"index": 3, "text": "john@example.com"})
                    )
                ]
            ),
            result=MockActionResult(),
            state=MockBrowserState(
                url="https://example.com/contact",
                title="Contact Us",
                element_tree=element_tree,
            ),
        ),
        # Step 3: Fill message and submit
        MockHistoryEntry(
            model_output=MockModelOutput(
                actions=[
                    MockAction(
                        input=MockActionValue({"index": 4, "text": "Hello, this is a test."})
                    ),
                    MockAction(click=MockActionValue({"index": 5})),
                ]
            ),
            result=MockActionResult(extracted_content="Form submitted successfully"),
            state=MockBrowserState(
                url="https://example.com/contact",
                title="Contact Us",
                element_tree=element_tree,
            ),
        ),
    ]

    return MockAgentHistoryList(
        entries=entries,
        urls=[
            "about:blank",
            "https://example.com/contact",
            "https://example.com/contact",
            "https://example.com/contact",
            "https://example.com/contact/thanks",
        ],
        done=True,
        duration=18.0,
    )


# ──────────────────────────────────────────────────────────────
# Edge case traces
# ──────────────────────────────────────────────────────────────


def make_empty_trace() -> MockAgentHistoryList:
    """Empty trace — no steps at all."""
    return MockAgentHistoryList(entries=[], urls=[], done=False, duration=0.0)


def make_all_failed_trace() -> MockAgentHistoryList:
    """Trace where every step failed."""
    entries = [
        MockHistoryEntry(
            model_output=MockModelOutput(
                actions=[MockAction(click=MockActionValue({"index": 99}))]
            ),
            result=MockActionResult(error="Element not found"),
            state=MockBrowserState(url="https://example.com"),
        ),
        MockHistoryEntry(
            model_output=MockModelOutput(
                actions=[MockAction(click=MockActionValue({"index": 98}))]
            ),
            result=MockActionResult(error="Element not found"),
            state=MockBrowserState(url="https://example.com"),
        ),
    ]
    return MockAgentHistoryList(
        entries=entries, urls=["https://example.com"], done=False, duration=5.0
    )


def make_retry_noise_trace() -> MockAgentHistoryList:
    """Trace with retry noise: step fails, then succeeds on retry."""
    entries = [
        # Step 0: Navigate (success)
        MockHistoryEntry(
            model_output=MockModelOutput(
                actions=[MockAction(navigate=MockActionValue({"url": "https://example.com"}))]
            ),
            result=MockActionResult(),
            state=MockBrowserState(url="https://example.com"),
        ),
        # Step 1: Click fails
        MockHistoryEntry(
            model_output=MockModelOutput(
                actions=[MockAction(click=MockActionValue({"index": 5}))]
            ),
            result=MockActionResult(error="Element not visible"),
            state=MockBrowserState(url="https://example.com"),
        ),
        # Step 2: Click succeeds (retry)
        MockHistoryEntry(
            model_output=MockModelOutput(
                actions=[MockAction(click=MockActionValue({"index": 5}))]
            ),
            result=MockActionResult(),
            state=MockBrowserState(url="https://example.com"),
        ),
    ]
    return MockAgentHistoryList(
        entries=entries,
        urls=["about:blank", "https://example.com", "https://example.com", "https://example.com"],
        done=True,
        duration=10.0,
    )


def make_single_step_trace() -> MockAgentHistoryList:
    """Minimal trace: one navigate step."""
    entries = [
        MockHistoryEntry(
            model_output=MockModelOutput(
                actions=[MockAction(navigate=MockActionValue({"url": "https://example.com"}))]
            ),
            result=MockActionResult(extracted_content="Example Domain"),
            state=MockBrowserState(url="https://example.com", title="Example Domain"),
        ),
    ]
    return MockAgentHistoryList(
        entries=entries,
        urls=["about:blank", "https://example.com"],
        done=True,
        duration=2.0,
    )
