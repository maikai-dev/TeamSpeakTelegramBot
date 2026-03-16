# TeamSpeak 3 Telegram Bot (production-like MVP)

MVP Telegram-бота для TeamSpeak 3 с разделением ролей `admin/user`, админ-панелью, мониторингом, статистикой, TTS-задачами и парсингом TS3-чата.

## Что умеет бот

- Отслеживает онлайн TeamSpeak: входы, выходы, переходы между каналами.
- Показывает `кто сейчас онлайн` по каналам со статусами.
- Даёт админу управление сервером из Telegram:
  - `kick`, `ban`, `move`, `poke`, `mute`, управление server groups.
- Собирает подробную статистику по сессиям и чат-сообщениям.
- Умеет создавать TTS-задачи: админ задает канал и текст, worker озвучивает.
- Пересылает админам сообщения TS3-чата (с фильтрами).
- Поддерживает пользовательские подписки на вход конкретных пользователей и активность каналов.

## Быстрый старт (Docker, рекомендуемый)

1. Скопируйте конфиг:
   - Linux/macOS: `cp .env.example .env`
   - Windows PowerShell: `Copy-Item .env.example .env`
2. Заполните в `.env`:
   - `BOT_TOKEN`
   - `BOT_ADMIN_IDS`
   - `TS3_HOST`, `TS3_QUERY_LOGIN`, `TS3_QUERY_PASSWORD`
3. Запустите:
   - `docker compose up --build -d`
4. Проверьте логи:
   - `docker compose logs -f bot`

После запуска отправьте боту `/start`.

## Docker-образ для ручного запуска

Сборка образа:

```bash
docker build -f docker/bot.Dockerfile -t ts3-telegram-bot:latest .
```

Пример запуска контейнера (с вашим `.env`):

```bash
docker run --rm --name ts3-telegram-bot --env-file .env ts3-telegram-bot:latest
```

## 1. Архитектура

### Слои
- `app/bot` — Telegram-слой (handlers, middleware, keyboards, filters)
- `app/services` — бизнес-логика
- `app/services/teamspeak` — адаптер TS3 ServerQuery + DTO
- `app/db` — SQLAlchemy-модели + репозитории
- `app/workers` — фоновые воркеры (мониторинг TS3, TTS, отчеты)
- `alembic` — миграции БД

### Ключевые инженерные решения
- Интеграция с TS3: отдельный адаптер `TeamSpeakServerQueryAdapter` (командный канал + event-канал)
- Детект join/leave/move: polling + state diff в `TS3MonitorWorker`
- Чат-сообщения TS3: через `notifytextmessage` + фильтры ChatWatch
- TTS: `TTSService` + `TTSWorker` + абстракция `VoiceAdapter`
- Voice: реалистичный sidecar-подход (`command` backend) и вариант `ts3audiobot`
- Роли и права: `PermissionService` + таблицы `roles/user_roles`
- Audit админ-действий: таблица `admin_actions`
- Конфигурация: `pydantic-settings` через `.env`

## 2. Структура проекта

```text
app/
  main.py
  bootstrap.py
  bot/
    factory.py
    handlers/
      start.py
      user.py
      admin.py
    keyboards/
      common.py
      admin.py
      stats.py
    middlewares/
      db.py
      auth.py
      rate_limit.py
    filters/
      admin.py
  core/
    config.py
    enums.py
    logging.py
    security.py
    rate_limiter.py
    constants.py
  db/
    base.py
    session.py
    models/
      user.py
      role.py
      ts3.py
      notification.py
      admin.py
      tts.py
    repositories/
      users.py
      ts3.py
      notifications.py
      admin.py
      tts.py
      stats.py
  services/
    container.py
    permission_service.py
    user_service.py
    notification_service.py
    runtime_config_service.py
    stats_service.py
    audit_service.py
    teamspeak/
      query_codec.py
      dto.py
      adapter.py
      service.py
    tts/
      providers.py
      service.py
    voice/
      adapter.py
      command_worker.py
      ts3audiobot.py
      service.py
  workers/
    monitor.py
    tts_worker.py
    reports.py
  utils/
    formatting.py
    charts.py
    csv_export.py
alembic/
  env.py
  versions/20260316_0001_initial.py
docker/
  bot.Dockerfile
  entrypoint.sh
  voice_worker_example.py
scripts/
  bootstrap_admin.py
tests/
  conftest.py
  test_permission_service.py
  test_rate_limiter.py
  test_stats_utils.py
  test_query_codec.py
```

## 3. Реализованные функции

## Роли
- `admin` — админ-команды, модерация, расширенная статистика, TTS, ChatWatch toggle
- `user` — безопасные команды (онлайн, whois, личная статистика, подписки)

## Базовые обязательные
- Уведомления join/leave/move в Telegram админам
- `Кто сейчас онлайн` с каналами, участниками, статусами mute/deaf/groups
- Админ-операции: kick/ban/move/poke/mute/group add/del
- TTS pipeline: `/say` -> очередь `tts_jobs` -> voice worker
- Парсинг TS3-чата: `notifytextmessage` -> `chat_messages` + пересылка админу
- Статистика: онлайн-время, пики, сообщения, сводки

## Дополнительно реализовано (10 стат-функций)
1. Топ по числу заходов (день/неделя/месяц)
2. Средняя длительность сессии по пользователям
3. Топ каналов по суммарному времени
4. Распределение по дням недели
5. Первый/последний онлайн
6. Оценка частых совместных пересечений
7. Среднее число онлайн по часам
8. Рекордные сессии
9. Молчуны/болтуны (voice/message ratio)
10. Heatmap активности (день недели × час)

## Дополнительно реализовано (10 user-функций)
1. `/online`
2. `/whois <name>`
3. `/mystats`
4. `/myonline`
5. `/mymessages`
6. `/subscribe <name>`
7. `/favuser <name>`
8. `/favchannel <id>`
9. `/lastseen <name>`
10. `/top`

Плюс: `/myfavs`, `/ping`, CSV-экспорт `/userstats` (admin).

## 4. Команды

### User
- `/start`
- `/help`
- `/online`
- `/whois <name>`
- `/mystats`
- `/myonline`
- `/mymessages`
- `/top [day|week|month|all]`
- `/lastseen <name>`
- `/subscribe <name>`
- `/favuser <name>`
- `/favchannel <channel_id>`
- `/myfavs`
- `/ping`

### Admin
- `/admin`
- `/alerts`
- `/kick <name> [reason]`
- `/ban <name> [hours] [reason]`
- `/move <name> <channel_id>`
- `/poke <name> <text>`
- `/mute <name>`
- `/groupadd <name> <sgid>`
- `/groupdel <name> <sgid>`
- `/say` (FSM with confirm)
- `/chatwatch`
- `/serverstats [day|week|month|all]`
- `/userstats <name>`
- `/reloadconfig`

## 5. Схема БД

Основные таблицы:
- `users`
- `roles`
- `user_roles`
- `ts3_clients`
- `sessions`
- `channel_events`
- `chat_messages`
- `notification_settings`
- `subscriptions`
- `admin_actions`
- `tts_jobs`
- `server_snapshots`
- `stats_cache`

Миграция: `alembic/versions/20260316_0001_initial.py`

## 6. Запуск

### Локально
1. Скопировать env:
   - `cp .env.example .env`
2. Заполнить `BOT_TOKEN`, TS3 Query креды, админ ID.
3. Поднять инфраструктуру:
   - `docker compose up -d postgres redis`
4. Установить зависимости:
   - `pip install -e .[dev]`
5. Применить миграции:
   - `alembic upgrade head`
6. Bootstrap admin:
   - `python scripts/bootstrap_admin.py --admin-id <telegram_id>`
7. Запуск:
   - `python -m app.main`

### Полностью в Docker
1. `cp .env.example .env`
2. Заполнить `.env`
3. `docker compose up --build`

## 7. Voice/TTS интеграция

Текущий production-like подход:
- TTS синтезируется через `gTTS` (`TTS_PROVIDER=gtts`)
- Воспроизведение делегируется внешнему voice worker (`VOICE_BACKEND=command`)
- Команда worker задается в `VOICE_WORKER_CMD`

Штатный пример: `docker/voice_worker_example.py`.
- В `DRY_RUN` режиме работает без реального входа в TS3.
- Для реального прод-потока подключите отдельный voice-sidecar (например, собственный TS3 клиент-бот или TS3AudioBot API).

## 8. Безопасность

- Секреты только в `.env`
- Проверка ролей на уровне handler/service
- Rate limit (глобальный и чувствительных команд)
- Audit trail для админ-действий
- Для опасных операций подтверждение через inline callback

## 9. Ограничения и TODO

- ServerQuery не является полноценным voice-клиентом TS3, поэтому voice-play вынесен в sidecar.
- `/reloadconfig` обновляет runtime-флаги; для полной перезагрузки `.env` требуется рестарт процесса.
- Модель “самый частый собеседник” пока эвристическая (по совместным пересечениям), без сложной overlap-математики.
- Для real production стоит добавить:
  - OpenTelemetry/Prometheus,
  - RBAC granular permissions,
  - Celery/RQ для масштабирования фоновых задач,
  - отдельный API-слой для admin UI,
  - полноценный TS3 voice-sidecar с SLA.

## 10. Тесты

Запуск:
- `pytest -q`

Покрыты ключевые элементы MVP:
- role/permission baseline
- rate limiter
- статистические утилиты
- TS3 query codec
