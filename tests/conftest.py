import os
from contextlib import ExitStack

import pytest
from lektor.builder import Builder
from lektor.context import Context
from lektor.project import Project


@pytest.fixture
def lektor_env():
    site_path = os.path.join(os.path.dirname(__file__), "test-site")
    return Project.from_path(site_path).make_env(load_plugins=False)


@pytest.fixture
def lektor_pad(lektor_env):
    return lektor_env.new_pad()


@pytest.fixture
def lektor_builder(lektor_pad, tmp_path):
    return Builder(lektor_pad, str(tmp_path))


@pytest.fixture
def lektor_build_state(lektor_builder):
    build_state = lektor_builder.new_build_state()
    with ExitStack() as stack:
        if hasattr(build_state, "__enter__"):
            build_state = stack.enter_context(build_state)  # lektor < 3.4
        yield build_state


@pytest.fixture
def lektor_source(lektor_pad):
    return lektor_pad.root


@pytest.fixture
def lektor_artifact(lektor_build_state, lektor_source):
    return lektor_build_state.new_artifact("test.html", source_obj=lektor_source)


@pytest.fixture
def lektor_context(lektor_artifact):
    with Context(lektor_artifact) as ctx:
        yield ctx
