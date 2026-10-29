import argparse
from pathlib import Path
import sys
from .providers import builtin_registry
from .service import prepare_article
from .exporting import export_article


def main():
    parser = argparse.ArgumentParser(description='자료 가져오기 → 규칙 기반 템플릿 → 오프라인 내보내기 (업로드 없음)')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('providers', help='게시 모듈과 지원 기능 확인')
    prepare = sub.add_parser('prepare', help='Markdown/TXT 묶음을 미리보기/내보내기로 변환')
    prepare.add_argument('bundle', help='--root 안의 상대 폴더 이름')
    prepare.add_argument('--root', type=Path, default=Path('resources/inbox'))
    prepare.add_argument('--output', type=Path, required=True)
    prepare.add_argument('--title')
    prepare.add_argument('--provider', default='manual-export')
    args = parser.parse_args()
    registry = builtin_registry()
    if args.command == 'providers':
        for name in ('manual-export', 'mock'):
            provider = registry.get(name)
            print(name, ', '.join(sorted(c.value for c in provider.capabilities)))
        print('mock은 모의 기능이며 네이버/Blogger 실연결 모듈은 아직 없습니다.')
        return 0
    try:
        provider = registry.get(args.provider)
        article = prepare_article(args.root, args.bundle, args.title)
        output = export_article(article, args.output, provider)
    except (OSError, ValueError) as exc:
        print('처리 실패:', str(exc), file=sys.stderr)
        return 1
    print('내보내기 완료 (외부 업로드 없음):', output)
    print('미리보기:', output / 'preview.html')
    for warning in article.warnings:
        print('확인 필요:', warning)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
