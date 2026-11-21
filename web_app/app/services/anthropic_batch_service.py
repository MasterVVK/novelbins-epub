"""
Пакетный режим Anthropic (Message Batches API) для перевода глав — вход и выход на 50% дешевле.

Схема: submit → Anthropic обрабатывает асинхронно (обычно < 1 ч, максимум 24 ч) → collect.
Промпты собираются так же, как в TranslatorService.translate_chapter: системный промпт шаблона
новеллы + «НАЗВАНИЕ ГЛАВЫ» + резюме 5 предыдущих глав + глоссарий по главе + текст части.
Резюме берутся у 5 глав перед переводимой (как при последовательном переводе), поэтому режим
рассчитан на новеллы с готовыми резюме и глоссарием — например, на перевод заново.

Режимы (mode):
- dry_run — бесплатно: пакет НЕ отправляется; запросы пишутся в data/anthropic_batches/dryrun-<время>/,
  печатается оценка токенов и $ (калибровка по собранным пакетам);
- files   — платно: пакет отправляется, результаты только в файлы data/anthropic_batches/<batch_id>/,
  БД не трогается; потом их можно применить к БД один раз: apply_batch(batch_id, 'initial'|'edited');
- initial — новый перевод translation_type='initial', статус 'translated'. Главы, уже прошедшие
  редактуру (edited/aligned), в пакет не попадают и не оплачиваются;
- edited  — финальный текст translation_type='edited', статус 'edited' (4 этапа редактуры не нужны).
Резюме переносится из прежнего перевода главы, новые термины не извлекаются.
Глава, которую успели отредактировать после отправки пакета, при сборе не перезаписывается.

Метаданные пакета: data/anthropic_batches/<batch_id>.json. До отправки пишется
data/anthropic_batches/pending-<время>.pending — если отправка оборвалась, пакет ищется по нему.
Повторный collect не создаёт дублей: собранный пакет возвращает сохранённый отчёт.
"""
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Dict, Iterator, List, Optional

import httpx

from app import db
from app.models import AIModel, Chapter, Novel, Translation
from app.services.log_service import LogService
from app.services.translator_service import (TranslationContext, TranslatorService,
                                             format_prompt_with_novel_context)

logger = logging.getLogger(__name__)

API_BASE = 'https://api.anthropic.com/v1'
BATCH_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                         'data', 'anthropic_batches')
MODES = ('dry_run', 'files', 'initial', 'edited')
APPLY_MODES = ('initial', 'edited')
# Статусы глав, уже прошедших редактуру: initial-перевод их не трогает
EDITED_STATUSES = ('edited', 'aligned')

# $ за 1M токенов (вход, выход) — обычная цена, пакет = половина.
# platform.claude.com/docs/en/about-claude/pricing на 25.10.2026; для оценки, не для бухгалтерии.
PRICES = {
    'claude-opus-5-5': (4, 20),
    'claude-sonnet-5-5': (2, 10),
    'claude-haiku-5-5': (0.10, 0.50),
    'claude-fable-5-1': (10, 50),
}
# Кэш промпта: запись 5-минутного кэша ×1.25 цены входа, чтение ×0.1
CACHE_WRITE_MULT, CACHE_READ_MULT = 1.25, 0.1
# Оценка dry_run, калибровка по пакетам N23 (Opus 5.5, effort=low, 11.2026):
# вход ≈0.81 токена на символ промпта, выход ≈1.8 токена на иероглиф оригинала
EST_INPUT_TOKENS_PER_CHAR = 0.81
EST_OUTPUT_TOKENS_PER_HAN = 1.8
HAN_RE = re.compile(r'[一-鿿]')


class AnthropicBatchClient:
    """Минимальный клиент Message Batches API."""

    def __init__(self, api_key: str, base: str = API_BASE):
        self.api_key = api_key
        self.base = base.rstrip('/')

    def _headers(self) -> Dict:
        return {'x-api-key': self.api_key, 'anthropic-version': '2023-06-01',
                'content-type': 'application/json'}

    def _check(self, response: httpx.Response) -> Dict:
        data = response.json()
        if response.status_code != 200 or 'error' in data:
            err = data.get('error', {})
            msg = err.get('message') if isinstance(err, dict) else str(err)
            raise RuntimeError(f"Anthropic Batches API HTTP {response.status_code}: {msg}")
        return data

    def create(self, requests: List[Dict]) -> Dict:
        with httpx.Client(timeout=httpx.Timeout(300.0, connect=30.0)) as c:
            return self._check(c.post(f"{self.base}/messages/batches", headers=self._headers(),
                                      json={'requests': requests}))

    def retrieve(self, batch_id: str) -> Dict:
        with httpx.Client(timeout=60.0) as c:
            return self._check(c.get(f"{self.base}/messages/batches/{batch_id}", headers=self._headers()))

    def list_recent(self, limit: int = 20) -> List[Dict]:
        with httpx.Client(timeout=60.0) as c:
            return self._check(c.get(f"{self.base}/messages/batches", headers=self._headers(),
                                     params={'limit': limit})).get('data', [])

    def cancel(self, batch_id: str) -> Dict:
        with httpx.Client(timeout=60.0) as c:
            return self._check(c.post(f"{self.base}/messages/batches/{batch_id}/cancel", headers=self._headers()))

    def iter_results(self, batch_id: str) -> Iterator[Dict]:
        """Результаты потоком (JSONL, порядок произвольный — сопоставлять по custom_id)."""
        with httpx.Client(timeout=httpx.Timeout(600.0, connect=30.0)) as c:
            with c.stream('GET', f"{self.base}/messages/batches/{batch_id}/results",
                          headers=self._headers()) as r:
                if r.status_code != 200:
                    raise RuntimeError(f"Anthropic Batches results HTTP {r.status_code}: "
                                       f"{r.read().decode('utf-8', 'replace')[:300]}")
                for line in r.iter_lines():
                    if line.strip():
                        yield json.loads(line)


def effort_for(ai_model: AIModel) -> Optional[str]:
    """Тот же маппинг переключателя Thinking, что в AIAdapterService._call_anthropic."""
    if not getattr(ai_model, 'enable_thinking', False):
        return 'low'
    if getattr(ai_model, 'thinking_mode', None) == 'high':
        return 'max'
    return None


def _meta_path(batch_id: str) -> str:
    return os.path.join(BATCH_DIR, f'{batch_id}.json')


def _write_json(path: str, data: Dict) -> None:
    os.makedirs(BATCH_DIR, exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def _save_meta(meta: Dict) -> None:
    _write_json(_meta_path(meta['batch_id']), meta)


def load_meta(batch_id: str) -> Dict:
    with open(_meta_path(batch_id), encoding='utf-8') as f:
        return json.load(f)


def list_batches() -> List[Dict]:
    if not os.path.isdir(BATCH_DIR):
        return []
    out = []
    for fn in sorted(os.listdir(BATCH_DIR)):
        if fn.endswith('.json'):
            with open(os.path.join(BATCH_DIR, fn), encoding='utf-8') as f:
                out.append(json.load(f))
    return out


def list_pending() -> List[str]:
    """Незавершённые отправки (пакет мог создаться, но метаданные не записаны)."""
    if not os.path.isdir(BATCH_DIR):
        return []
    return sorted(os.path.join(BATCH_DIR, fn) for fn in os.listdir(BATCH_DIR) if fn.endswith('.pending'))


def build_chapter_requests(chapter: Chapter, ai_model: AIModel) -> List[Dict]:
    """Запросы пакета для одной главы (по одному на часть) — промпты как в translate_chapter."""
    novel = chapter.novel
    template = novel.get_prompt_template()
    system_prompt = format_prompt_with_novel_context(template.translation_prompt, novel)

    context = TranslationContext(novel.id, chapter.original_text)
    # В проде резюме — у последних 5 переведённых глав; при последовательном переводе это
    # 5 предыдущих. В пакете главы идут не по порядку, поэтому берём именно предыдущие.
    prev = (Chapter.query.filter(Chapter.novel_id == novel.id,
                                 Chapter.chapter_number < chapter.chapter_number)
            .order_by(Chapter.chapter_number.desc()).limit(5).all())
    context.previous_summaries = []
    for p in reversed(prev):
        t = p.current_translation
        if t and t.summary and p.original_text and len(p.original_text) >= 500:
            context.previous_summaries.append({'title': p.original_title, 'summary': t.summary})
    context_prompt = context.build_context_prompt()
    if chapter.original_title:
        context_prompt = (f"НАЗВАНИЕ ГЛАВЫ: {chapter.original_title}\n\n{context_prompt}"
                          if context_prompt else f"НАЗВАНИЕ ГЛАВЫ: {chapter.original_title}")

    text = TranslatorService.preprocess_text(None, chapter.original_text)
    parts = TranslatorService.split_long_text(None, text)
    effort = effort_for(ai_model)

    requests = []
    for i, part in enumerate(parts):
        params = {
            'model': ai_model.model_id,
            'max_tokens': ai_model.max_output_tokens or 64000,
            # Системный промпт одинаков для всех глав новеллы — кэшируем. Кэш в пакете best-effort;
            # промпт короче минимума модели API молча не кэширует.
            'system': [{'type': 'text', 'text': system_prompt, 'cache_control': {'type': 'ephemeral'}}],
            # как UniversalLLMTranslator.translate_text
            'messages': [{'role': 'user', 'content': f"{context_prompt}\n\nТЕКСТ ДЛЯ ПЕРЕВОДА:\n{part}"}],
        }
        # temperature не передаём: Claude 5.x его отклоняют, а в пакете ошибка = потерянный запрос
        if effort:
            params['output_config'] = {'effort': effort}
        requests.append({'custom_id': f'c{chapter.id}-p{i}', 'params': params})
    return requests


def _request_chars(request: Dict) -> int:
    params = request['params']
    system = ''.join(b['text'] for b in params['system'])
    return len(system) + sum(len(m['content']) for m in params['messages'])


def _estimate_cost(model: str, input_chars: int, han: int) -> Dict:
    price_in, price_out = PRICES.get(model, (0, 0))
    inp = int(input_chars * EST_INPUT_TOKENS_PER_CHAR)
    out = int(han * EST_OUTPUT_TOKENS_PER_HAN)
    return {'input_tokens': inp, 'output_tokens': out,
            'cost_usd_estimate': round((inp * price_in + out * price_out) / 1e6 / 2, 2)}


def submit_translation_batch(chapter_ids: List[int], ai_model_id: int, mode: str = 'dry_run') -> Dict:
    """Собрать запросы по главам и отправить пакет (dry_run — только собрать и оценить).

    Возвращает метаданные пакета."""
    if mode not in MODES:
        raise ValueError(f'mode должен быть одним из {MODES}')
    ai_model = AIModel.query.get(ai_model_id)
    if not ai_model or ai_model.provider != 'anthropic':
        raise ValueError(f'Модель {ai_model_id} не найдена или не Anthropic')
    if mode != 'dry_run' and not ai_model.api_key:
        raise ValueError(f'У модели {ai_model.name} не задан API-ключ')

    chapters = Chapter.query.filter(Chapter.id.in_(chapter_ids)).order_by(Chapter.chapter_number).all()
    if not chapters:
        raise ValueError('Главы не найдены')
    novel_ids = {c.novel_id for c in chapters}
    if len(novel_ids) != 1:
        raise ValueError('Все главы пакета должны быть из одной новеллы')
    novel_id = novel_ids.pop()

    requests, chapters_meta, skipped = [], {}, []
    input_chars = han = 0
    for ch in chapters:
        if not ch.original_text:
            skipped.append({'chapter': ch.chapter_number, 'reason': 'нет оригинала'})
            LogService.log_warning(f"Пакет: у главы {ch.chapter_number} нет оригинала — пропущена",
                                   novel_id=ch.novel_id, chapter_id=ch.id)
            continue
        if mode == 'initial' and ch.status in EDITED_STATUSES:
            # Новый initial для отредактированной главы откатил бы её статус — и стоил бы денег
            skipped.append({'chapter': ch.chapter_number, 'reason': f'глава уже {ch.status}'})
            continue
        reqs = build_chapter_requests(ch, ai_model)
        requests.extend(reqs)
        input_chars += sum(_request_chars(r) for r in reqs)
        han += len(HAN_RE.findall(ch.original_text))
        chapters_meta[str(ch.id)] = {'number': ch.chapter_number, 'parts': len(reqs),
                                     'status_before': ch.status}
    if not requests:
        raise ValueError(f'Нечего отправлять: все главы пропущены ({skipped[:5]})')

    common = {'kind': 'translation', 'mode': mode, 'novel_id': novel_id, 'ai_model_id': ai_model.id,
              'model': ai_model.model_id, 'effort': effort_for(ai_model), 'requests': len(requests),
              'chapters': chapters_meta, 'skipped': skipped,
              'estimate': _estimate_cost(ai_model.model_id, input_chars, han)}

    if mode == 'dry_run':
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        out_dir = os.path.join(BATCH_DIR, f'dryrun-{stamp}')
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, 'requests.jsonl'), 'w', encoding='utf-8') as f:
            for r in requests:
                f.write(json.dumps(r, ensure_ascii=False) + '\n')
        meta = {**common, 'batch_id': None, 'dir': out_dir}
        _write_json(os.path.join(out_dir, 'meta.json'), meta)
        return meta

    # Метаданные — ДО отправки: если create оборвётся после того, как Anthropic принял пакет,
    # по pending-файлу его можно найти (оплаченный пакет не потеряется)
    started_at = datetime.now(timezone.utc).isoformat()
    pending_path = os.path.join(BATCH_DIR, f"pending-{datetime.now().strftime('%Y%m%d-%H%M%S')}.pending")
    _write_json(pending_path, {**common, 'started_at': started_at})
    client = AnthropicBatchClient(ai_model.api_key)
    try:
        batch = client.create(requests)
    except Exception as e:
        batch = _find_created_batch(client, started_at, len(requests))
        if not batch:
            LogService.log_error(f"Пакет Anthropic: отправка оборвалась ({e}); если пакет всё же создан, "
                                 f"сверить по {pending_path}", novel_id=novel_id)
            raise
        LogService.log_warning(f"Пакет Anthropic: ответ на отправку потерян ({e}), но пакет "
                               f"{batch['id']} создан — подхватываем", novel_id=novel_id)

    meta = {**common, 'batch_id': batch['id'], 'created_at': batch.get('created_at'),
            'expires_at': batch.get('expires_at'), 'processing_status': batch.get('processing_status'),
            'request_counts': batch.get('request_counts'), 'collected': False}
    _save_meta(meta)
    os.remove(pending_path)
    LogService.log_info(f"Пакет Anthropic {batch['id']} отправлен: {len(chapters_meta)} глав, "
                        f"{len(requests)} запросов, модель {ai_model.model_id}, режим {mode}, "
                        f"оценка ≈${common['estimate']['cost_usd_estimate']}", novel_id=novel_id)
    return meta


def _find_created_batch(client: AnthropicBatchClient, started_at: str, n_requests: int) -> Optional[Dict]:
    """Пакет, созданный после started_at с тем же числом запросов (create вернул ошибку, но успел)."""
    try:
        recent = client.list_recent()
    except Exception as e:
        logger.warning(f'Не удалось получить список пакетов: {e}')
        return None
    for b in recent:
        counts = b.get('request_counts') or {}
        if (b.get('created_at', '') >= started_at[:19]
                and sum(v for v in counts.values() if isinstance(v, int)) == n_requests):
            return b
    return None


def refresh_status(batch_id: str) -> Dict:
    meta = load_meta(batch_id)
    ai_model = AIModel.query.get(meta['ai_model_id'])
    batch = AnthropicBatchClient(ai_model.api_key).retrieve(batch_id)
    meta.update({'processing_status': batch.get('processing_status'),
                 'request_counts': batch.get('request_counts'), 'ended_at': batch.get('ended_at')})
    _save_meta(meta)
    return meta


USAGE_KEYS = ('input_tokens', 'output_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens')


def _batch_cost(model: str, usage: Dict) -> float:
    price_in, price_out = PRICES.get(model, (0, 0))
    inp = ((usage.get('input_tokens') or 0)
           + (usage.get('cache_creation_input_tokens') or 0) * CACHE_WRITE_MULT
           + (usage.get('cache_read_input_tokens') or 0) * CACHE_READ_MULT)
    return (inp * price_in + (usage.get('output_tokens') or 0) * price_out) / 1e6 / 2


def collect_translation_batch(batch_id: str) -> Dict:
    """Забрать результаты завершённого пакета и применить их согласно mode.

    Повторный вызов для собранного пакета ничего не пишет и возвращает сохранённый отчёт."""
    meta = load_meta(batch_id)
    if meta.get('collected'):
        return {'ready': True, 'meta': meta, 'already_collected': True}
    meta = refresh_status(batch_id)
    if meta['processing_status'] != 'ended':
        return {'ready': False, 'meta': meta}
    # Пакеты dry_run до 21.11.2026 отправлялись платно — собираем их как files (только файлы)
    return _process_results(meta, 'files' if meta['mode'] == 'dry_run' else meta['mode'])


def apply_batch(batch_id: str, mode: str) -> Dict:
    """Применить к БД собранный пакет режима files (один раз). Результаты перечитываются у Anthropic."""
    if mode not in APPLY_MODES:
        raise ValueError(f'mode должен быть одним из {APPLY_MODES}')
    meta = load_meta(batch_id)
    # dry_run — старые платные пакеты (до 21.11.2026), их результаты тоже можно применить
    if meta.get('mode') not in ('files', 'dry_run'):
        raise ValueError(f"Пакет {batch_id} в режиме {meta.get('mode')} — применяются только пакеты files")
    if not meta.get('collected'):
        raise ValueError(f'Пакет {batch_id} ещё не собран — сначала collect')
    if meta.get('applied_as'):
        raise ValueError(f"Пакет {batch_id} уже применён как {meta['applied_as']}")
    return _process_results(meta, mode, applying=True)


def _process_results(meta: Dict, mode: str, applying: bool = False) -> Dict:
    batch_id = meta['batch_id']
    ai_model = AIModel.query.get(meta['ai_model_id'])
    parts: Dict[str, Dict[int, str]] = {}
    failures: Dict[str, str] = {}
    usage_total = dict.fromkeys(USAGE_KEYS, 0)
    for item in AnthropicBatchClient(ai_model.api_key).iter_results(batch_id):
        cid, result = item.get('custom_id', ''), item.get('result') or {}
        chapter_key, part_idx = cid[1:].split('-p')
        rtype = result.get('type')
        if rtype != 'succeeded':
            err = (result.get('error') or {}).get('error', {}).get('message') or rtype
            failures[chapter_key] = f'{cid}: {err}'
            continue
        msg = result['message']
        for k in USAGE_KEYS:
            usage_total[k] += (msg.get('usage') or {}).get(k) or 0
        if msg.get('stop_reason') in ('max_tokens', 'refusal'):
            failures[chapter_key] = f"{cid}: stop_reason={msg.get('stop_reason')}"
            continue
        text = ''.join(b.get('text', '') for b in msg.get('content', []) if b.get('type') == 'text')
        parts.setdefault(chapter_key, {})[int(part_idx)] = text

    out_dir = os.path.join(BATCH_DIR, batch_id)
    os.makedirs(out_dir, exist_ok=True)
    report = {'saved': [], 'failed': [], 'skipped': []}
    for chapter_key, info in meta['chapters'].items():
        number = info['number']
        if chapter_key in failures:
            report['failed'].append({'chapter': number, 'reason': failures[chapter_key]})
            continue
        got = parts.get(chapter_key, {})
        if len(got) != info['parts']:
            report['failed'].append({'chapter': number, 'reason': f"частей {len(got)}/{info['parts']}"})
            continue
        chapter = Chapter.query.get(int(chapter_key))
        full = '\n\n'.join(got[i] for i in range(info['parts']))
        title, content = TranslatorService.extract_title_and_content(None, full)
        validation = TranslatorService.validate_translation(None, chapter.original_text, content, number)
        quality = TranslatorService.calculate_quality_score(None, validation)

        with open(os.path.join(out_dir, f'ch{number:04d}.txt'), 'w', encoding='utf-8') as f:
            f.write(f"{title}\n\n{content}\n")
        if validation['critical']:
            report['failed'].append({'chapter': number, 'reason': f"валидация: {validation['critical_issues']}"})
            continue
        if mode == 'files':
            report['saved'].append({'chapter': number, 'quality': quality, 'file': f'ch{number:04d}.txt'})
            continue
        if mode == 'initial' and chapter.status in EDITED_STATUSES:
            report['skipped'].append({'chapter': number, 'reason': f'глава уже {chapter.status}'})
            continue
        if chapter.status in EDITED_STATUSES and info.get('status_before') not in EDITED_STATUSES:
            # Пока пакет считался, главу отредактировали другим путём — не затираем
            report['skipped'].append({'chapter': number,
                                      'reason': f"отредактирована после отправки ({info.get('status_before')} → {chapter.status})"})
            continue

        prev = chapter.current_translation
        translation = Translation(
            chapter_id=chapter.id,
            translated_title=title or chapter.translated_title,
            translated_text=content,
            summary=prev.summary if prev else None,
            translation_type='initial' if mode == 'initial' else 'edited',
            api_used='anthropic-batch',
            model_used=ai_model.model_id,
            quality_score=quality,
            context_used={
                'batch_id': batch_id, 'effort': meta.get('effort'), 'mode': mode,
                'validation': validation, 'parts_count': info['parts'],
                'saved_at': datetime.now().isoformat(),
            },
        )
        db.session.add(translation)
        chapter.status = 'translated' if mode == 'initial' else 'edited'
        report['saved'].append({'chapter': number, 'quality': quality})

    if mode != 'files' and report['saved']:
        novel = Novel.query.get(meta['novel_id'])
        novel.translated_chapters = Chapter.query.filter_by(novel_id=novel.id, status='translated').count()
        novel.edited_chapters = Chapter.query.filter(Chapter.novel_id == novel.id,
                                                     Chapter.status.in_(['edited', 'aligned'])).count()
        db.session.commit()

    now = datetime.now().isoformat()
    if applying:
        meta.update({'applied_as': mode, 'applied_at': now, 'apply_report': report})
    else:
        meta.update({'collected': True, 'collected_at': now, 'usage': usage_total,
                     'cost_usd_estimate': round(_batch_cost(meta['model'], usage_total), 4), 'report': report})
    _save_meta(meta)
    action = f'применён как {mode}' if applying else 'собран'
    LogService.log_info(f"Пакет Anthropic {batch_id} {action}: сохранено {len(report['saved'])}, "
                        f"ошибок {len(report['failed'])}, пропущено {len(report['skipped'])}, "
                        f"≈${meta.get('cost_usd_estimate')} (кэш: чтение {usage_total['cache_read_input_tokens']}, "
                        f"запись {usage_total['cache_creation_input_tokens']})", novel_id=meta['novel_id'])
    return {'ready': True, 'meta': meta}


def wait_and_collect(batch_id: str, poll_seconds: int = 60, timeout_seconds: int = 26 * 3600) -> Dict:
    """Опрос до завершения пакета и сбор результатов (для фоновой задачи/CLI)."""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        res = collect_translation_batch(batch_id)
        if res['ready']:
            return res
        time.sleep(poll_seconds)
    raise TimeoutError(f'Пакет {batch_id} не завершился за {timeout_seconds} с')
