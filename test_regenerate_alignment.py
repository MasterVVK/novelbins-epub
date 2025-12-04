#!/usr/bin/env python3
"""
Пересоздание сопоставления с новой температурой 0.0
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / 'web_app'))

from app import create_app
from app.models import Chapter
from app.services.bilingual_alignment_service import BilingualAlignmentService

app = create_app()

def regenerate_alignment():
    """Пересоздать сопоставление для главы 1"""
    with app.app_context():
        chapter = Chapter.query.filter_by(novel_id=21, chapter_number=1).first()

        if not chapter:
            print("❌ Глава не найдена")
            return

        print("=" * 80)
        print("🔄 ПЕРЕСОЗДАНИЕ СОПОСТАВЛЕНИЯ С ТЕМПЕРАТУРОЙ 0.0")
        print("=" * 80)
        print(f"\n📖 Новелла: {chapter.novel_id}, Глава: {chapter.chapter_number}")

        service = BilingualAlignmentService(
            template_id=1,  # Шаблон с температурой 0.0
            model_id=12     # kimi-k2:1t-cloud
        )

        print(f"\n🔄 Удаляем старое сопоставление...")
        alignments = service.regenerate_alignment(chapter)

        print(f"\n✅ Новое сопоставление создано: {len(alignments)} пар")

        # Проверяем качество
        from app.models import BilingualAlignment
        alignment = BilingualAlignment.query.filter_by(chapter_id=chapter.id).first()

        if alignment:
            print(f"\n📊 МЕТРИКИ КАЧЕСТВА:")
            print(f"  Quality Score:    {alignment.quality_score:.4f} ({alignment.quality_score*100:.2f}%)")
            print(f"  Coverage RU:      {alignment.coverage_ru:.4f} ({alignment.coverage_ru*100:.2f}%)")
            print(f"  Coverage ZH:      {alignment.coverage_zh:.4f} ({alignment.coverage_zh*100:.2f}%)")
            print(f"  Avg Confidence:   {alignment.avg_confidence:.4f} ({alignment.avg_confidence*100:.2f}%)")
            print(f"  Total Pairs:      {alignment.total_pairs}")
            print(f"  Misalignments:    {alignment.misalignment_count}")
            print(f"  High Quality:     {'✅ Да' if alignment.is_high_quality else '❌ Нет'}")
            print(f"  Needs Review:     {'⚠️ Да' if alignment.needs_review else '✅ Нет'}")

        print("\n" + "=" * 80)

if __name__ == '__main__':
    regenerate_alignment()
