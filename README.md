# «Визарий» — Telegram-сервис помощи мигрантам в РФ

Проводит человека по пути легализации: миграционный учёт → патент → РВП → ВНЖ → гражданство.
Определяет этап по структурированным фактам (детерминированный rule engine, не LLM),
отвечает только из выверенной базы знаний (RAG) и напоминает о персональных дедлайнах
за 7/3/1 день (killer-фича, по подписке Telegram Stars).

## Архитектура в двух словах

**Детерминированное ядро, LLM на краях.**

- `app/domain/` — этапы, классификатор, дедлайны: чистые функции, покрыты табличными тестами. LLM здесь нет.
- `app/ai/` — LangGraph: guardrail → извлечение фактов (NLU) → проверка полноты → классификация (domain!) → RAG → оформление ответа (NLG). Нет approved-блоков в базе знаний — честный шаблонный отказ без LLM.
- `app/bot/` — aiogram 3: кнопочный intake (мимо LLM), free-text вопросы, i18n через ключи.
- `app/scheduler/` — APScheduler: ежедневная рассылка напоминаний.
- Дисклеймер к юридическим ответам добавляется кодом, не моделью.
- PII: не собираем ФИО/документы, PII-фильтр в structlog и Sentry, `/delete_my_data` стирает всё.

## LLM-провайдер

По умолчанию — любой OpenAI-совместимый агрегатор (`LLM_PROVIDER=openai_compatible`), например
[Polza.AI](https://polza.ai): оплата в рублях, `LLM_BASE_URL=https://api.polza.ai/api/v1`,
модель — `LLM_MODEL` (например, `openai/gpt-5.4-mini`; каталог и цены: polza.ai/models).
Прямой Anthropic API: `LLM_PROVIDER=anthropic` + `ANTHROPIC_API_KEY`.

## Запуск

Требуется: Docker + docker-compose, токен бота от @BotFather, ключ LLM-провайдера.

```bash
cp .env.example .env       # заполнить TELEGRAM_BOT_TOKEN, LLM_API_KEY, WEBHOOK_URL, WEBHOOK_SECRET

# 1. Поднять контейнеры (app + pgvector/pgvector:pg16 + redis)
docker compose up -d --build

# 2. Применить миграции (создаст расширение vector и все таблицы)
docker compose exec app alembic upgrade head

# 3. Проиндексировать базу знаний (только approved-блоки; для dev: --include-drafts)
docker compose exec app python -m scripts.index_kb

# 4. Вебхук ставится автоматически при старте приложения (WEBHOOK_URL + secret_token).
#    Проверить: curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo
```

### Обкатка без домена и HTTPS (long polling)

Вебхук нужен только в проде. Для теста достаточно Postgres + Redis + токена бота:

```bash
uv run python -m app.polling
```

Локальная разработка без Docker:

```bash
uv sync                                  # Python 3.12+, зависимости
uv sync --extra embeddings-local         # + локальная модель эмбеддингов
uv run alembic upgrade head              # нужен запущенный Postgres (pgvector) и Redis
uv run python -m scripts.index_kb --include-drafts
uv run uvicorn app.main:app --reload
```

## Тесты

```bash
uv run pytest
```

Покрыто: матрица «факты → этап», дедлайны (границы месяцев, ЕАЭС), RAG (approved-only,
фильтры, пустая выдача), guardrails (инъекции), сквозные сценарии LangGraph на фейках,
freemium-гейтинг.

## База знаний

`knowledge_base/*.md` с фронтматтером (`stage`, `applies_to`, `status`, `reviewed_by`, `reviewed_at`).
В прод-индекс попадают только `status: approved`. Текущий контент — демо-заглушки
с пометками `# TODO: выверить с юристом`; реальный контент пишет и утверждает юрист-партнёр
(меняет `status` на `approved` и заполняет `reviewed_by`/`reviewed_at` в Git).

## Freemium

- Бесплатно: этап + краткий следующий шаг + 3 вопроса в день + один тизер-напоминание.
- Подписка (Telegram Stars, `/subscribe`): полная роадмапа, чек-листы документов,
  персональные напоминания 7/3/1, вопросы без лимита.

## Точки расширения (вне MVP)

Mini App, новостной пайплайн, Celery вместо APScheduler, реальная мультиязычность
(словари `app/bot/i18n/tj.py`, `uz.py` уже подключены), админ-панель.
