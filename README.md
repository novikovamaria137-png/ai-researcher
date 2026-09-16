# ai-researcher

**Ежедневный дайджест новостей конкурентов в Telegram. Без платных API-ключей.**

[![CI](https://github.com/novikovamaria137-png/ai-researcher/actions/workflows/ci.yml/badge.svg)](https://github.com/novikovamaria137-png/ai-researcher/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

Скрипт раз в сутки обходит блоги и changelog'и конкурентов, находит то, что появилось
с прошлого запуска, сжимает в короткие буллеты и присылает дайджест в Telegram.
Запускается по расписанию в GitHub Actions — сервер не нужен.

Ключевое отличие от туториальной версии: **суммаризация не привязана к платному API**.
Движки подключаются как плагины, и дефолтный работает вообще без ключей и без интернета.

---

## Быстрый старт (30 секунд, без регистраций)

```bash
git clone https://github.com/novikovamaria137-png/ai-researcher.git
cd ai-researcher
pip install -r requirements.txt

make demo                 # офлайн-демо на встроенных данных
make run                  # реальные фиды -> дайджест в консоль
```

`make run` ничего не отправляет и не меняет состояние — это `--dry-run`.

```
🔍 *AI-конкуренты — что нового* — 15.09.2026
_12 новых публикаций у 4 конкурентов · движок: extractive_

*OpenAI* (3)
• Competitor A launches an AI assistant for enterprise support. Pricing starts at $49 per seat.
  https://example.com/a1
• Ключевые темы: assistant, enterprise, support, pricing, beta
```

---

## Почему это бесплатно

| Что | Чем решено | Стоимость |
|---|---|---|
| Суммаризация | extractive-движок на чистом Python (TextRank + TF-IDF) | 0 ₽, ключ не нужен |
| Суммаризация «умнее» | Ollama локально / Groq / Gemini / OpenRouter free tier | 0 ₽, ключ бесплатный |
| Доставка | Telegram Bot API | 0 ₽ |
| Расписание | GitHub Actions cron | 0 ₽ на публичном репо |
| Хранение состояния | `seen.json`, коммитится обратно в репозиторий | 0 ₽, БД не нужна |

---

## Архитектура

```
cron (GitHub Actions)
   │
   ├─ sources.py    RSS/Atom + HTML-fallback ──┐
   │                                           │
   ├─ state.py      diff vs seen.json ─────────┤  только новое
   │                                           │
   ├─ summarizers/  backend = auto ────────────┤
   │     ollama → groq → gemini → openrouter → extractive
   │     (FallbackSummarizer: упал провайдер — секция не теряется)
   │                                           │
   ├─ digest.py     сборка + split по 4096 ────┤
   │                                           │
   └─ delivery.py   Telegram / Markdown / stdout
```

Три решения, из-за которых это не одноразовый скрипт:

1. **Движок выбирается сам.** `backend: auto` опрашивает бэкенды по очереди и берёт
   первый доступный. Платный `anthropic` в эту очередь не входит никогда — его можно
   выбрать только явным флагом.
2. **Провайдер не может уронить прогон.** `FallbackSummarizer` ловит исчерпанную квоту,
   таймаут и пустой ответ и деградирует до extractive — дайджест приходит в любом случае.
3. **Первый запуск не заваливает чат.** Пустой `seen.json` означает «истории нет»,
   поэтому первый дайджест ограничен тремя записями на источник (снимается `--full-first-run`).

---

## Движки суммаризации

| Движок | Ключ | Сеть | Комментарий |
|---|---|---|---|
| `extractive` | нет | нет | дефолт. TextRank + TF-IDF, RU/EN стоп-слова, буст на бизнес-сигналы (launch, партнёрство, раунд) |
| `ollama` | нет | localhost | локальная модель, `ollama pull llama3.2` |
| `groq` | бесплатный | да | быстрый, щедрый free tier |
| `gemini` | бесплатный | да | Google AI Studio |
| `openrouter` | бесплатный | да | модели со слагом `:free` |
| `anthropic` | платный | да | для сравнения качества, автоматически не выбирается |

```bash
python -m ai_researcher --backend extractive --dry-run   # без сети
python -m ai_researcher --backend ollama --dry-run       # локальная LLM
SUMMARIZER_BACKEND=groq python -m ai_researcher          # free tier
```

Добавить свой провайдер — это один класс с двумя методами (`available`, `summarize`)
и строка в `REGISTRY`.

---

## Источники

Два готовых пресета в `config/`, переключаются флагом:

```bash
python -m ai_researcher --preset ai        # OpenAI, DeepMind, Google AI, Hugging Face
python -m ai_researcher --preset fashion   # WWD, Hypebeast, Glossy, Vogue Business
python -m ai_researcher --config my.yaml   # свой список
```

```yaml
preset: my
title: "Мои конкуренты"
backend: auto
sources:
  - name: Competitor A
    rss: https://compA.com/feed.xml
  - name: Competitor B
    changelog: https://compB.com/changelog   # без RSS — парсится HTML
```

---

## Telegram и расписание

1. `@BotFather` → `/newbot` → токен.
2. `@userinfobot` → твой `chat_id`.
3. Локально — `.env` (см. `.env.example`); в GitHub — Settings → Secrets →
   `TG_BOT_TOKEN`, `TG_CHAT_ID`.
4. `.github/workflows/digest.yml` уже настроен на 09:00 МСК и коммитит `seen.json`
   обратно, чтобы состояние жило между запусками.

Если секреты не заданы, прогон не падает: дайджест уходит в лог.

---

## CLI

```
--preset {ai,fashion}   набор источников
--config PATH           свой YAML
--backend NAME          движок или auto
--dry-run               печать в консоль, без Telegram и без записи состояния
--save-markdown         архив дайджеста в digests/YYYY-MM-DD.md
--state PATH            путь к seen.json
--limit N               сколько записей брать из фида
--full-first-run        не ограничивать первый дайджест
-v, --verbose           логи
```

---

## Тесты

```bash
pip install -r requirements-dev.txt
make test    # 47 тестов
make lint
```

Тесты не ходят в сеть: фиды замоканы фикстурой, ключи не нужны — CI зелёный
у любого, кто форкнул репозиторий. Покрыты диффинг состояния (включая битый
JSON и дедупликацию внутри батча), парсинг фидов, деградация провайдера,
разбиение сообщения по лимиту Telegram в 4096 символов и русское согласование
числительных.

---

## Что дальше

- [ ] Playwright для сайтов без RSS и без разметки
- [ ] Отдельный поток по вакансиям конкурентов — сильный стратегический сигнал
- [ ] Недельный отчёт с трендами поверх накопленного архива
- [ ] Классификация «опасно / нейтрально / возможность» отдельной моделью

---

## Стек

Python 3.10+ · feedparser · httpx · PyYAML · BeautifulSoup · pytest · ruff · GitHub Actions

MIT © 2026 Maria Novikova
