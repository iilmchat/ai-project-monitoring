# ADR-0022: sqlite-vec для RAG в desktop-сборке

**Дата:** 2026-11-11 · **Статус:** принято · **Спринт:** S61-001/S61-002

## Контекст

ADR-0015 закрепил RAG на PostgreSQL + `pgvector`. Desktop-версия работает на
SQLite, поэтому на ней `/search/code` всегда отвечал `503 rag_unavailable`, а
основная функция «поиск по коду» в приложении была недоступна.

Нужен локальный векторный поиск без внешней БД и без тяжёлых сервисов.

## Решение

Использовать расширение [`sqlite-vec`](https://github.com/asg017/sqlite-vec)
(`vec0`) — компактное C-расширение к SQLite, поставляемое wheel-пакетом.

- Зависимость: `sqlite-vec==0.1.9` (`backend/requirements.txt`).
- Метаданные чанков — обычная таблица `code_chunks` (миграция `015`), эмбеддинг
  хранится как JSON-текст. Это позволяет пересчитать близость без расширения.
- Векторный индекс — виртуальная таблица
  `vec_chunks USING vec0(embedding float[1536] distance_metric=cosine,
  repository_id integer, language text)`; `repository_id`/`language` — partition
  keys, поэтому фильтры по проекту и языку работают внутри KNN-запроса.
- Поиск: `ORDER`/`k` через `WHERE embedding MATCH ? AND k = ?`; итоговый score
  считается как `1 - distance` (та же семантика, что у pgvector).
- PostgreSQL-путь (`<=>`, HNSW) не меняется.

### Fallback

`sqlite_vec` — нативное расширение, и его можно не собрать в PyInstaller.
Поэтому в `SqliteVecStore` есть двухуровневая деградация:

1. Если расширение не загрузилось, сервис логирует
   `sqlite_vec_unavailable_fallback_to_python` и считает косинусную близость в
   чистом Python по JSON-эмбеддингам из `code_chunks`.
2. Если расширение есть, но конкретный KNN-запрос падает, поиск также
   повторяется через Python-fallback.

Данные при этом не теряются: `code_chunks` — источник истины, `vec_chunks` можно
пересоздать повторной индексацией.

### Упаковка

`backend/build_sidecar.py` находит `vec0.dll`/`vec0.so`/`vec0.dylib` в пакете и
передаёт `--add-binary …;sqlite_vec`. При старте `sqlite_vec.loadable_path()`
указывает на `_MEIPASS/sqlite_vec/vec0`, поэтому SQLite находит библиотеку.

## Последствия

- Desktop RAG работает без PostgreSQL; веб/серверная сборка продолжает
  использовать pgvector.
- Добавлена нативная зависимость (wheel содержит готовые бинарники для
  Windows/macOS/Linux); при отсутствии — graceful fallback.
- Векторные записи пишутся отдельным синхронным `sqlite3`-соединением после
  коммита метаданных: aiosqlite не умеет синхронно загружать расширения, а
  второй писатель не должен конфликтовать с транзакцией SQLAlchemy.
