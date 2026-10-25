"""
Пакетный режим Anthropic (Message Batches API) для перевода глав — вход и выход на 50% дешевле.

Схема: submit → Anthropic обрабатывает асинхронно (обычно < 1 ч, максимум 24 ч) → collect.
Промпты собираются так же, как в TranslatorService.translate_chapter: системный промпт шаблона
новеллы + «НАЗВАНИЕ ГЛАВЫ» + резюме 5 предыдущих глав + глоссарий по главе + текст части.
Резюме берутся у 5 глав перед переводимой (как при последовательном переводе), поэтому режим
рассчитан на новеллы с готовыми резюме и глоссарием — например, на перевод заново.

Режимы сохранения (mode):
- dry_run — только файлы в data/anthropic_batches/<batch_id>/, БД не трогается;
- initial — новый перевод translation_type='initial', статус 'translated' (главы 'edited' пропускаются);
- edited  — финальный текст translation_type='edited', статус 'edited' (4 этапа редактуры не нужны).
Резюме переносится из прежнего перевода главы, новые термины не извлекаются.

Метаданные пакета: data/anthropic_batches/<batch_id>.json.
"""
import json
import logging
import os
import time
from datetime import datetime
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
MODES = ('dry_run', 'initial', 'edited')

# $ за 1M токенов (вход, выход) — обычная цена, пакет = половина.
# platform.claude.com/docs/en/about-claude/pricing на 25.10.2026; для оценки, не для бухгалтерии.
PRICES = {
    'claude-opus-5-5': (4, 20),
    'claude-sonnet-5-5': (2, 10),
    'claude-haiku-5-5': (0.10, 0.50),
    'claude-fable-5-1': (10, 50),
}


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


def _save_meta(meta: Dict) -> None:
    os.makedirs(BATCH_DIR, exist_ok=True)
    tmp = _meta_path(meta['batch_id']) + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    os.replace(tmp, _meta_path(meta['batch_id']))


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
            'system': system_prompt,
            # как UniversalLLMTranslator.translate_text
            'messages': [{'role': 'user', 'content': f"{context_prompt}\n\nТЕКСТ ДЛЯ ПЕРЕВОДА:\n{part}"}],
        }
        # temperature не передаём: Claude 5.x его отклоняют, а в пакете ошибка = потерянный запрос
        if effort:
            params['output_config'] = {'effort': effort}
        requests.append({'custom_id': f'c{chapter.id}-p{i}', 'params': params})
    return requests


def submit_translation_batch(chapter_ids: List[int], ai_model_id: int, mode: str = 'dry_run') -> Dict:
    """Собрать запросы по главам и отправить пакет. Возвращает метаданные пакета."""
    if mode not in MODES:
        raise ValueError(f'mode должен быть одним из {MODES}')
    ai_model = AIModel.query.get(ai_model_id)
    if not ai_model or ai_model.provider != 'anthropic':
        raise ValueError(f'Модель {ai_model_id} не найдена или не Anthropic')
    if not ai_model.api_key:
        raise ValueError(f'У модели {ai_model.name} не задан API-ключ')

    chapters = Chapter.query.filter(Chapter.id.in_(chapter_ids)).order_by(Chapter.chapter_number).all()
    if not chapters:
        raise ValueError('Главы не найдены')
    novel_ids = {c.novel_id for c in chapters}
    if len(novel_ids) != 1:
        raise ValueError('Все главы пакета должны быть из одной новеллы')

    requests, chapters_meta = [], {}
    for ch in chapters:
        if not ch.original_text:
            LogService.log_warning(f"Пакет: у главы {ch.chapter_number} нет оригинала — пропущена",
                                   novel_id=ch.novel_id, chapter_id=ch.id)
            continue
        reqs = build_chapter_requests(ch, ai_model)
        requests.extend(reqs)
        chapters_meta[str(ch.id)] = {'number': ch.chapter_number, 'parts': len(reqs),
                                     'status_before': ch.status}

    batch = AnthropicBatchClient(ai_model.api_key).create(requests)
    meta = {
        'batch_id': batch['id'], 'kind': 'translation', 'mode': mode,
        'novel_id': novel_ids.pop(), 'ai_model_id': ai_model.id, 'model': ai_model.model_id,
        'effort': effort_for(ai_model), 'created_at': batch.get('created_at'),
        'expires_at': batch.get('expires_at'), 'processing_status': batch.get('processing_status'),
        'request_counts': batch.get('request_counts'), 'requests': len(requests),
        'chapters': chapters_meta, 'collected': False,
    }
    _save_meta(meta)
    LogService.log_info(f"Пакет Anthropic {batch['id']} отправлен: {len(chapters_meta)} глав, "
                        f"{len(requests)} запросов, модель {ai_model.model_id}, режим {mode}",
                        novel_id=meta['novel_id'])
    return meta


def refresh_status(batch_id: str) -> Dict:
    meta = load_meta(batch_id)
    ai_model = AIModel.query.get(meta['ai_model_id'])
    batch = AnthropicBatchClient(ai_model.api_key).retrieve(batch_id)
    meta.update({'processing_status': batch.get('processing_status'),
                 'request_counts': batch.get('request_counts'), 'ended_at': batch.get('ended_at')})
    _save_meta(meta)
    return meta


def _batch_cost(model: str, usage: Dict) -> float:
    price_in, price_out = PRICES.get(model, (0, 0))
    inp = ((usage.get('input_tokens') or 0) + (usage.get('cache_creation_input_tokens') or 0)
           + (usage.get('cache_read_input_tokens') or 0))
    return (inp * price_in + (usage.get('output_tokens') or 0) * price_out) / 1e6 / 2


def collect_translation_batch(batch_id: str) -> Dict:
    """Забрать результаты завершённого пакета и применить их согласно mode."""
    meta = refresh_status(batch_id)
    if meta['processing_status'] != 'ended':
        return {'ready': False, 'meta': meta}

    ai_model = AIModel.query.get(meta['ai_model_id'])
    parts: Dict[str, Dict[int, str]] = {}
    failures: Dict[str, str] = {}
    usage_total = {'input_tokens': 0, 'output_tokens': 0}
    for item in AnthropicBatchClient(ai_model.api_key).iter_results(batch_id):
        cid, result = item.get('custom_id', ''), item.get('result') or {}
        chapter_key, part_idx = cid[1:].split('-p')
        rtype = result.get('type')
        if rtype != 'succeeded':
            err = (result.get('error') or {}).get('error', {}).get('message') or rtype
            failures[chapter_key] = f'{cid}: {err}'
            continue
        msg = result['message']
        for k in usage_total:
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
        if meta['mode'] == 'dry_run':
            report['saved'].append({'chapter': number, 'quality': quality, 'file': f'ch{number:04d}.txt'})
            continue
        if meta['mode'] == 'initial' and chapter.status == 'edited':
            report['skipped'].append({'chapter': number, 'reason': 'глава уже edited'})
            continue

        prev = chapter.current_translation
        translation = Translation(
            chapter_id=chapter.id,
            translated_title=title or chapter.translated_title,
            translated_text=content,
            summary=prev.summary if prev else None,
            translation_type='initial' if meta['mode'] == 'initial' else 'edited',
            api_used='anthropic-batch',
            model_used=ai_model.model_id,
            quality_score=quality,
            context_used={
                'batch_id': batch_id, 'effort': meta.get('effort'), 'mode': meta['mode'],
                'validation': validation, 'parts_count': info['parts'],
                'saved_at': datetime.now().isoformat(),
            },
        )
        db.session.add(translation)
        chapter.status = 'translated' if meta['mode'] == 'initial' else 'edited'
        report['saved'].append({'chapter': number, 'quality': quality})

    if meta['mode'] != 'dry_run' and report['saved']:
        novel = Novel.query.get(meta['novel_id'])
        novel.translated_chapters = Chapter.query.filter_by(novel_id=novel.id, status='translated').count()
        novel.edited_chapters = Chapter.query.filter(Chapter.novel_id == novel.id,
                                                     Chapter.status.in_(['edited', 'aligned'])).count()
        db.session.commit()

    meta.update({'collected': True, 'collected_at': datetime.now().isoformat(),
                 'usage': usage_total, 'cost_usd_estimate': round(_batch_cost(meta['model'], usage_total), 4),
                 'report': report})
    _save_meta(meta)
    LogService.log_info(f"Пакет Anthropic {batch_id} собран: сохранено {len(report['saved'])}, "
                        f"ошибок {len(report['failed'])}, пропущено {len(report['skipped'])}, "
                        f"≈${meta['cost_usd_estimate']}", novel_id=meta['novel_id'])
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
