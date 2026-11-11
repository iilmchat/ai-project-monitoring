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
  'search.index': 'Запустить индексацию (RAG)',
  'search.indexing': 'Индексация…',
  'search.indexStarted':
    'Индексация запущена. Обновите статус через несколько секунд.',
  'search.refreshStatus': 'Обновить статус',
  'search.status':
    'Проиндексировано: {chunks} чанков в {repos} репозиториях.',
  'search.unavailable':
    'RAG недоступен. Проверьте настройки базы данных и модели эмбеддингов.',
  'search.ragUnavailable': 'Поиск по коду недоступен. Проверьте настройки БД',
  'search.embeddingUnavailable':
    'Ошибка: Модель эмбеддингов недоступна. Зайдите в Настройки → AI Провайдеры и укажите embedding-модель (например, nomic-embed-text).',
  'search.embeddingNotConfigured':
    'Ошибка: Модель эмбеддингов не настроена. Зайдите в Настройки → AI Провайдеры и укажите embedding-модель (например, nomic-embed-text).',
  'search.embeddingDimensionMismatch':
    'Размерность эмбеддингов не совпадает с индексом. Для nomic-embed-text задайте EMBEDDING_DIMENSIONS=768 и переиндексируйте код.',
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
  'search.modeSearch': 'Поиск',
  'search.modeChat': 'Чат с кодом',
  'search.chatTitle': 'Чат с базой знаний',
  'search.chatHint':
    'Вопросы по README, docs и коду tracked-репозиториев. Ответы — только по найденным фрагментам.',
  'search.chatEmpty':
    'Задайте вопрос, например: «В каких проектах я использую Redis?».',
  'search.chatPlaceholder': 'Спросите о кодовой базе…',
  'search.chatSend': 'Отправить',
  'search.chatSending': 'Отправка…',
  'search.chatThinking': 'Ищу в базе знаний и формулирую ответ…',
  'search.chatClear': 'Очистить',
  'search.chatError': 'Не удалось получить ответ.',
  'search.chatLlmUnavailable':
    'LLM недоступна. Проверьте настройки AI-провайдера.',
} as const
