---
invokable: true
---

Review this code for potential issues, including:

## Critical Issues to Check

### Translation Quality & Consistency
- **Glossary Usage**: Ensure new terms are properly extracted and saved using `GlossaryItem.get_glossary_dict()` and `extract_new_terms()`
- **Context Preservation**: Check that `TranslationContext.build_context_prompt()` is properly used to maintain narrative continuity
- **Validation Logic**: Verify `validate_translation()` is called to check paragraph structure, length ratios, and content quality
- **Sound Effects Handling**: Ensure `preprocess_chapter_text()` properly handles repetitive sound effects (Wooo..., Ahhh... etc.)

### AI Model Integration
- **Universal Adapter Usage**: Confirm `UniversalLLMTranslator` is used instead of deprecated `LLMTranslator` for new code
- **Model Configuration**: Check that AIModel configurations are properly loaded from database, not hardcoded
- **API Key Rotation**: Ensure intelligent key rotation is working - keys should cycle through available keys and mark failed ones
- **Temperature Settings**: Verify translation temperature (0.1-0.3) and editing temperature (0.7+) are appropriate for task

### Error Handling & Resilience
- **Content Blocking**: Check for proper handling of Gemini safety filters - should retry with fiction disclaimer or split content
- **Rate Limiting**: Ensure 429 errors trigger key rotation and don't cause infinite loops
- **Network Timeouts**: Verify proper timeout handling (600s for large translations) and retry logic
- **Database Rollbacks**: Check that `db.session.rollback()` is called in exception handlers

### Text Processing Edge Cases
- **Long Text Splitting**: Ensure `split_long_text()` properly handles Chinese text vs English text with different delimiters
- **Chapter Title Detection**: Verify `extract_title_and_content()` logic for detecting actual titles vs regular text
- **Paragraph Structure**: Check preservation of double newlines (\n\n) for proper EPUB formatting
- **Character Encoding**: Ensure proper handling of Chinese characters (\u4e00-\u9fff range)

### Security & Performance
- **SQL Injection**: Verify all database queries use SQLAlchemy ORM, no raw SQL concatenation
- **Path Traversal**: Check file operations use safe paths, especially in upload handling
- **Memory Management**: Ensure large texts are processed in chunks, not loaded entirely into memory
- **Task Cancellation**: Verify Celery tasks properly handle SIGTERM and update Novel.status

### Code Quality Standards
- **Logging Context**: Check that LogService.log_* calls include `novel_id` and `chapter_id` parameters
- **Type Hints**: Ensure complex functions have proper type annotations (especially in services)
- **Exception Handling**: Verify specific exceptions are caught, not bare `except:` clauses
- **Resource Cleanup**: Check that Selenium drivers and HTTP clients are properly closed in finally blocks

### Database Transaction Safety
- **Atomic Operations**: Ensure translation saves use proper transaction boundaries
- **Concurrent Updates**: Check for race conditions in chapter status updates
- **Foreign Key Constraints**: Verify proper handling of novel_id/chapter_id relationships
- **Glossary Conflicts**: Ensure term updates don't overwrite existing manual entries

### User Experience
- **Progress Reporting**: Check Celery tasks update progress metadata regularly
- **Error Messages**: Ensure user-friendly error messages for common failures
- **Task Status**: Verify Novel.status reflects actual task state (parsing, translated, error, etc.)
- **Validation Feedback**: Check validation results are clearly communicated to users

## Translation-Specific Checks

### Literary Translation Quality
- **Character Names**: Ensure consistent translation using established glossary entries
- **Culturally Specific Terms**: Check handling of xianxia terms (修真, 元神, 法宝 etc.)
- **Dialogue Markers**: Verify proper formatting of dialogue (「」quotes, speech patterns)
- **Sound Effects**: Ensure Chinese onomatopoeia are properly translated to Russian equivalents

### Technical Implementation
- **Context Length**: Check that context prompts don't exceed model token limits
- **Batch Processing**: Verify efficient processing of multi-part chapters
- **Quality Scoring**: Ensure the 1-10 quality score calculation is meaningful
- **Prompt History**: Check that translation prompts are properly saved for debugging

Provide specific, actionable feedback for improvements.