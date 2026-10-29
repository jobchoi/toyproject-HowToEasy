from dataclasses import dataclass, asdict, field


@dataclass(frozen=True)
class Source:
    name: str
    sha256: str
    text: str


@dataclass(frozen=True)
class Article:
    title: str
    markdown: str
    sources: tuple[Source, ...]
    warnings: tuple[str, ...]
    template_version: str = 'information-v1'
    article_id: str = ''
    parent_id: str = ''
    saved_at: str = ''
    style: str = 'plain'
    appearance: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)
