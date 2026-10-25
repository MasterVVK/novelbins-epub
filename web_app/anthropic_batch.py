"""Пакетный перевод глав через Anthropic Message Batches API (−50% к цене).

Примеры:
  python anthropic_batch.py submit --novel 25 --chapters 80-81 --model 50            # dry_run: только файлы
  python anthropic_batch.py submit --novel 25 --chapters 80-376 --model 50 --mode edited
  python anthropic_batch.py status <batch_id>
  python anthropic_batch.py collect <batch_id>      # если пакет готов — применить результаты
  python anthropic_batch.py wait <batch_id>         # ждать завершения и собрать
  python anthropic_batch.py list
  python anthropic_batch.py cancel <batch_id>

Режимы (--mode): dry_run (по умолчанию, БД не трогается), initial, edited — см. app/services/anthropic_batch_service.py.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app  # noqa: E402


def parse_numbers(spec: str):
    nums = set()
    for chunk in spec.split(','):
        chunk = chunk.strip()
        if '-' in chunk:
            a, b = chunk.split('-')
            nums.update(range(int(a), int(b) + 1))
        elif chunk:
            nums.add(int(chunk))
    return sorted(nums)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('submit')
    s.add_argument('--novel', type=int, required=True)
    s.add_argument('--chapters', required=True, help='номера глав: 80-90,95')
    s.add_argument('--model', type=int, required=True, help='id AIModel (provider=anthropic)')
    s.add_argument('--mode', default='dry_run', choices=['dry_run', 'initial', 'edited'])
    for name in ('status', 'collect', 'wait', 'cancel'):
        sub.add_parser(name).add_argument('batch_id')
    sub.add_parser('list')
    args = ap.parse_args()

    app = create_app()
    with app.app_context():
        from app.models import Chapter, AIModel
        from app.services import anthropic_batch_service as svc

        if args.cmd == 'submit':
            numbers = parse_numbers(args.chapters)
            chapters = Chapter.query.filter(Chapter.novel_id == args.novel,
                                            Chapter.chapter_number.in_(numbers)).all()
            missing = set(numbers) - {c.chapter_number for c in chapters}
            if missing:
                print(f'Не найдены главы: {sorted(missing)[:20]}')
            meta = svc.submit_translation_batch([c.id for c in chapters], args.model, args.mode)
            print(f"Пакет {meta['batch_id']}: {len(meta['chapters'])} глав, {meta['requests']} запросов, "
                  f"модель {meta['model']}, effort={meta['effort']}, режим {meta['mode']}")
        elif args.cmd == 'status':
            m = svc.refresh_status(args.batch_id)
            print(json.dumps({k: m.get(k) for k in ('processing_status', 'request_counts', 'created_at',
                                                    'ended_at', 'expires_at', 'mode', 'collected')},
                             ensure_ascii=False, indent=1))
        elif args.cmd in ('collect', 'wait'):
            res = (svc.wait_and_collect(args.batch_id) if args.cmd == 'wait'
                   else svc.collect_translation_batch(args.batch_id))
            m = res['meta']
            if not res['ready']:
                print(f"Пакет ещё обрабатывается: {m['processing_status']} {m['request_counts']}")
                return
            print(json.dumps({'report': m['report'], 'usage': m['usage'],
                              'cost_usd_estimate': m['cost_usd_estimate']}, ensure_ascii=False, indent=1))
        elif args.cmd == 'cancel':
            m = svc.load_meta(args.batch_id)
            ai_model = AIModel.query.get(m['ai_model_id'])
            print(svc.AnthropicBatchClient(ai_model.api_key).cancel(args.batch_id).get('processing_status'))
        elif args.cmd == 'list':
            for m in svc.list_batches():
                print(f"{m['batch_id']}  novel={m['novel_id']} глав={len(m['chapters'])} {m['mode']} "
                      f"{m.get('processing_status')} собран={m.get('collected')} ≈${m.get('cost_usd_estimate', '-')}")


if __name__ == '__main__':
    main()
