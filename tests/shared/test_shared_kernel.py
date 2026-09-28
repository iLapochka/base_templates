from dataclasses import dataclass
from pathlib import Path

import pytest

import src.main  # noqa: F401 — every context's entities, so the subclass sweep below sees them
from scripts.check_ddd_layering import check
from src.shared.domain.entities import BaseEntity
from src.shared.domain.unit_of_work import UnitOfWork


class RecordingUnitOfWork(UnitOfWork):
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def commit(self) -> None:
        self.calls.append('commit')

    async def rollback(self) -> None:
        self.calls.append('rollback')


async def test_a_failed_block_rolls_back_instead_of_leaving_its_changes_staged() -> None:
    unit_of_work = RecordingUnitOfWork()

    with pytest.raises(RuntimeError):
        async with unit_of_work:
            raise RuntimeError

    async with unit_of_work:
        pass

    assert unit_of_work.calls == ['rollback', 'commit']


class FailingCommitUnitOfWork(RecordingUnitOfWork):
    async def commit(self) -> None:
        self.calls.append('commit')
        raise ConnectionError


async def test_a_failed_commit_rolls_back_so_the_next_write_can_record_the_failure() -> None:
    unit_of_work = FailingCommitUnitOfWork()

    with pytest.raises(ConnectionError):
        async with unit_of_work:
            pass

    assert unit_of_work.calls == ['commit', 'rollback']


@dataclass(kw_only=True, eq=False)
class SampleEntity(BaseEntity):
    title: str


def test_entities_are_equal_by_id_and_hashable() -> None:
    entity = SampleEntity(title='before')
    renamed = SampleEntity(id=entity.id, title='after')

    assert entity == renamed
    assert entity != SampleEntity(title='before')
    assert {entity, renamed} == {entity}


def all_subclasses(cls: type) -> list[type]:
    return [subclass for direct in cls.__subclasses__() for subclass in (direct, *all_subclasses(direct))]


@pytest.mark.parametrize('entity_class', all_subclasses(BaseEntity), ids=lambda cls: cls.__name__)
def test_every_entity_keeps_identity_equality(entity_class: type[BaseEntity]) -> None:
    """A subclass declared with a plain `@dataclass` regenerates `__eq__` — it needs `eq=False`."""
    assert entity_class.__eq__ is BaseEntity.__eq__
    assert entity_class.__hash__ is BaseEntity.__hash__


@pytest.mark.parametrize(
    'source',
    [
        'from ..infrastructure.models import SampleModel\n',
        'from src.jobs import infrastructure\n',
        'from . import subprocess_runner\nimport subprocess\n',
        'import asyncio\nasyncio.create_subprocess_exec("ffmpeg")\n',
        'from asyncio import create_subprocess_exec\n',
        'from asyncio.subprocess import PIPE\n',
        'import os\n',
    ],
)
def test_layering_check_sees_relative_and_name_imports(tmp_path: Path, source: str) -> None:
    domain_file = tmp_path / 'src' / 'jobs' / 'domain' / 'entities.py'
    domain_file.parent.mkdir(parents=True)
    domain_file.write_text(source, encoding='utf-8')

    assert check(domain_file)


def test_layering_check_allows_a_sibling_import_in_the_same_layer(tmp_path: Path) -> None:
    domain_file = tmp_path / 'src' / 'jobs' / 'domain' / 'entities.py'
    domain_file.parent.mkdir(parents=True)
    domain_file.write_text('from .value_objects import JobStatus\n', encoding='utf-8')

    assert check(domain_file) == []
