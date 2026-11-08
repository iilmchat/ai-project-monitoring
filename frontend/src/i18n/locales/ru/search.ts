export const search = {
  'search.title': 'Поиск по коду',
  'search.subtitle':
    'Семантический поиск по README, docs и исходникам tracked-репозиториев.',
  'search.placeholder': 'Поиск по коду (RAG)…',
  'search.submit': 'Найти',
  'search.searching': 'Поиск…',
  'search.results': 'Результаты',
  'search.empty': 'Ничего не найдено. Измените запрос или порог похожести.',
  'search.noIndex': 'Индекс ещё не построен. Запустите индексацию.',
  'search.index': 'Индексировать',
  'search.indexing': 'Индексация…',
  'search.indexStarted':
    'Индексация запущена. Обновите статус через несколько секунд.',
  'search.refreshStatus': 'Обновить статус',
  'search.status':
    'Проиндексировано: {chunks} чанков в {repos} репозиториях.',
  'search.unavailable':
    'RAG недоступен: нужен PostgreSQL + pgvector и модель эмбеддингов.',
  'search.embeddingUnavailable':
    'Модель эмбеддингов недоступна. Проверьте EMBEDDING_* настройки.',
  'search.error': 'Не удалось выполнить поиск.',
  'search.stale': 'Индекс устарел — рекомендуем переиндексацию.',
  'search.copyPath': 'Копировать путь',
  'search.copied': 'Путь скопирован.',
  'search.openProject': 'Открыть проект',
  'search.openGithub': 'Открыть на GitHub',
  'search.lines': 'строки {start}–{end}',
  'search.score': 'релевантность {score}',
  'search.language': 'Язык',
  'search.languageAll': 'Все языки',
  'search.queryHint': 'Например: «где у меня настроен Redis?»',
} as const
