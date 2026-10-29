from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from ..models import Article


class Capability(str, Enum):
    EXPORT = 'export'
    CREATE_DRAFT = 'create_draft'


class UnsupportedOperation(ValueError):
    pass


@dataclass(frozen=True)
class DraftResult:
    provider: str
    remote_id: str
    simulated: bool


class Publisher(ABC):
    """Subclass per platform. Unsupported features fail before any external call."""
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def capabilities(self) -> frozenset[Capability]: ...

    def create_draft(self, article: Article, *, reviewed: bool = False) -> DraftResult:
        if Capability.CREATE_DRAFT not in self.capabilities:
            raise UnsupportedOperation(f'{self.name}: 초안 업로드는 지원하지 않습니다. 내보내기를 사용하세요.')
        if not reviewed:
            raise ValueError('현재 원고를 검토한 뒤 초안 작업을 요청하세요.')
        return self._create_draft(article)

    def _create_draft(self, article: Article) -> DraftResult:
        raise UnsupportedOperation(f'{self.name}: 초안 업로드 구현이 없습니다.')


class ManualExportPublisher(Publisher):
    name = 'manual-export'
    capabilities = frozenset({Capability.EXPORT})


class MockPublisher(Publisher):
    name = 'mock'
    capabilities = frozenset({Capability.EXPORT, Capability.CREATE_DRAFT})

    def _create_draft(self, article: Article) -> DraftResult:
        from hashlib import sha256
        return DraftResult(self.name, 'mock-' + sha256(article.markdown.encode()).hexdigest()[:16], True)


class PublisherRegistry:
    def __init__(self):
        self._providers: dict[str, Publisher] = {}

    def register(self, provider: Publisher):
        if provider.name in self._providers:
            raise ValueError('이미 등록된 게시 모듈입니다.')
        self._providers[provider.name] = provider

    def get(self, name: str) -> Publisher:
        try:
            return self._providers[name]
        except KeyError:
            raise ValueError(f'지원하지 않는 게시 모듈: {name}') from None


def builtin_registry() -> PublisherRegistry:
    registry = PublisherRegistry()
    registry.register(ManualExportPublisher())
    registry.register(MockPublisher())
    return registry
