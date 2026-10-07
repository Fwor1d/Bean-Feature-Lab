# Архитектура BeanFeature Lab

Статус: production-oriented локальная архитектура реализована. Leakage-safe engine, application/infrastructure boundaries, SQLite queue, filesystem artifacts, API/CLI/worker, deployment registry и Instrument Workstation UI работают на официальном UCI 602. Источники продуктовых ограничений — [`PRODUCT.md`](../../PRODUCT.md), [`EXPERIMENT_PROTOCOL.md`](../research/EXPERIMENT_PROTOCOL.md) и [исходный научный доклад](../research/Влияние_количества_признаков_семян_фасоли_на_точность_их_классификации.docx). Числовые выводы не фиксируются в этом документе: они читаются из hash-verified runtime artifacts.

## Границы системы

```mermaid
flowchart LR
    Web[Next.js frontend] -->|HTTP, типизированные DTO| API[FastAPI adapter]
    API --> App[Application layer]
    CLI[Python CLI] --> App
    Worker[Один локальный worker] --> App
    App --> Research[Независимое ML/research ядро]
    App --> Ports[Интерфейсы хранения и заданий]
    Infra[SQLite и файловые адаптеры] -. реализуют .-> Ports
    Infra --> DB[(SQLite)]
    Infra --> FS[(datasets и артефакты)]
```

- **Research** принимает данные и явные конфигурации, строит экспериментальные процедуры, возвращает типизированные результаты. Он не импортирует FastAPI, SQLite, Next.js и HTTP-схемы.
- **Application** задаёт команды `create/run/cancel/resume experiment`, запросы результатов и правила жизненного цикла; вызывает research и абстрактные порты хранения. Он не вычисляет научные метрики самостоятельно.
- **Infrastructure** реализует порты SQLite и файловой системы. Тяжёлые модели, fold-predictions и другие большие объекты остаются файлами, а SQLite хранит метаданные, конфигурации, статусы и числовые результаты.
- **FastAPI** валидирует запрос, переводит его в application-команду и возвращает DTO. Долгое обучение не выполняется в процессе обработки HTTP-запроса.
- **CLI и worker** используют те же application-команды, что и API. Experiment runner запускается без браузера и без работающего FastAPI.
- **Frontend** отображает сохранённые результаты и состояния `not run` / `not calculated`; не пересчитывает macro-F1, интервалы, stability или другие научные показатели. Plotly получает подготовленные сервером серии с их семантикой и единицами.

Первая версия использует **один локальный worker** с последовательным или явно ограниченным выполнением тяжёлых experiment jobs. Очередь и статус run сохраняются устойчиво через application/infrastructure; отмена и ошибка фиксируются как переходы состояния. Worker проверяет отмену между безопасными этапами, например между folds, и завершает активный процесс контролируемо. FastAPI только ставит задание и читает статус — nested CV не выполняется внутри HTTP request. Redis, Celery и иная распределённая инфраструктура в первую версию не входят. Порт исполнения заданий позволяет позднее заменить локальный backend без изменения ML/research ядра.

## Реализованные границы репозитория

```text
BeanFeatureLab/
├── PRODUCT.md
├── apps/
│   ├── web/                         # Next.js, TypeScript, Node.js 24 LTS
│   │   ├── src/app/                 # маршруты страниц
│   │   ├── src/features/            # сценарии страниц и запросы к API
│   │   ├── src/components/          # композиция готовых UI-компонентов
│   │   ├── src/lib/api/             # типизированный HTTP-клиент и DTO
│   │   └── src/lib/plots/           # адаптация готовых серий к Plotly
│   ├── api/                         # FastAPI, Python 3.11
│   │   └── src/beanfeature_api/
│   │       ├── main.py              # сборка приложения и DI
│   │       ├── routers/             # тонкие HTTP-адаптеры по доменам
│   │       └── schemas/             # внешние request/response DTO
│   └── worker/                      # один локальный исполнитель долгих runs
├── packages/
│   ├── research/                    # научное ядро, без API/UI/SQLite
│   │   └── src/beanfeature_research/
│   │       ├── datasets/            # схема, загрузка и научная валидация
│   │       ├── splits/              # outer/inner CV и split manifests
│   │       ├── preprocessing/       # fold-local pipeline builders
│   │       ├── selection/           # фильтры, RFE, embedded, PCA
│   │       ├── models/              # фабрики классификаторов и search spaces
│   │       ├── evaluation/          # predictions, метрики, агрегация
│   │       ├── stability/           # частоты выбора и Jaccard
│   │       └── resources/           # измерение wall time, RSS, размера
│   ├── application/
│   │   └── src/beanfeature_application/
│   │       ├── commands/            # запуск, отмена, регистрация модели
│   │       ├── queries/             # чтение сохранённых сравнений
│   │       ├── ports/               # интерфейсы repo/artifact/job
│   │       └── policies/            # статусы, идентичность, права операций
│   └── infrastructure/
│       └── src/beanfeature_infrastructure/
│           ├── sqlite/              # репозитории и миграции
│           ├── files/               # manifests, datasets, model artifacts
│           └── jobs/                # сменяемый адаптер локального worker
├── tools/cli/                      # воспроизводимые команды поверх application
├── configs/experiments/            # версионируемые шаблоны протокола
├── data/
│   ├── raw/                        # неизменяемые копии источников и hashes
│   └── processed/                  # проверенные версии данных и manifests
├── storage/sqlite/                 # локальная metadata/results DB (runtime, ignored)
├── artifacts/
│   ├── runs/                       # snapshots, predictions, logs по run ID
│   └── models/                     # доверенные обученные модели
├── tests/
│   ├── research/                   # leakage, CV, метрики, устойчивость
│   ├── application/                # lifecycle и идемпотентность
│   ├── api/                        # HTTP-контракты
│   ├── cli/                        # запуск без UI
│   └── web/                        # доступность и сценарии страниц
└── docs/
    ├── architecture/ARCHITECTURE.md
    └── research/
        ├── EXPERIMENT_PROTOCOL.md
        └── Влияние_количества_признаков_семян_фасоли_на_точность_их_классификации.docx
```

`data/processed` содержит воспроизводимый manifest проверки официального ARFF, но не обучаемые на всей выборке preprocessing statistics. Масштабирование, feature selection, PCA и любая статистика, зависящая от training data, создаются внутри CV pipeline. Raw/processed dataset files, runtime SQLite и generated artifacts исключены из Git; hashes и provenance сохраняются рядом с научным результатом.

## Запуск, идентичность и хранение

**Experiment definition** — неизменяемый снимок протокола: версия схемы, dataset version, модель/матрица условий, сетки настройки, CV, seed, метрики и ресурсный режим. **Run** — конкретное исполнение этого снимка. Пользовательский `RUN-{sequence:06d}` выдаётся атомарным счётчиком SQLite; он не является hash и никогда не переиспользуется. Отдельный SHA-256 fingerprint от канонизированной конфигурации, dataset hash, Git state и версий ПО позволяет находить повторные исполнения. Повтор запуска получает новый run ID и тот же fingerprint при неизменном окружении.

Для официально воспроизводимого запуска требуется Git commit. Исследовательский запуск при незакоммиченном состоянии допускается только с явной пометкой `dirty`, hash снимка изменений и неизменяемой копией конфигурации; пустой Git SHA нельзя подменять вымышленным. Timestamp хранится в UTC. Все артефакты получают относительный путь внутри проекта, размер и SHA-256; API не принимает произвольные пути к файлам и не загружает присланные пользователем сериализованные модели.

Реализованные SQLite metadata entities и файловые companions:

| Сущность | Ответственность и ключевые поля |
|---|---|
| `dataset_versions` | Источник `UCI Machine Learning Repository — Dry Bean Dataset — Dataset ID 602`, версия/дата получения, raw и processed hashes, схема 16 признаков, путь к manifest. |
| `experiments` | ID, immutable configuration JSON, model/selector/budget/search-space/seed/dataset version, UTC timestamps. |
| `runs` | Atomic integer key → `RUN-000001`, experiment ID, status/timestamps/error, summary JSON, dataset/fingerprint/artifact hashes and relative references. |
| `run_events` | Переходы статуса, ошибки с этапом и временем, предупреждения, попытки возобновления. |
| `worker_heartbeat` | Последний heartbeat единственного локального worker для operational status. |
| `artifacts/runs/RUN-*/` | Fold JSON, complete result, splits, predictions, selected features, confusion matrices, provenance и derived comparisons. |
| `artifacts/models/registry.json` | Versioned deployment entries: active status, source run/config, feature schema, model/artifact hashes and timestamps. |

Для condition обязателен явный `budget_kind`: `original_features`, `pca_components` или `sparse_original_features`. При **фиксированном** бюджете `original_features` запрошенное `k` — точное число исходных колонок. При `pca_components` хранится `n_components`, а `required_raw_feature_count` остаётся 16 и никогда не выводится из числа компонент. Для L1-path `k_original_features=null`, selector `C` зафиксирован в config, а `observed_nonzero_count` сохраняется по каждому fold; его нельзя выдавать за заранее заданное `k`. Выбранные признаки в PCA-ветви — `null`, а не вымышленный список физических измерений.

Run проходит состояния `DRAFT/QUEUED → RUNNING → COMPLETED`, либо `FAILED/CANCELLED`. Статус сохраняется до ответа API; после сбоя локальный worker переводит незавершённый `RUNNING` в failure и не выдаёт его за успешный. Partial fold files могут остаться для диагностики, но final metrics публикуются только после всех outer folds, записи result artifact и проверки SHA-256. Неполученные значения — `null` с явным `NOT_CALCULATED`; ноль означает реально измеренный ноль. Краткие SQLite-транзакции и один последовательный writer предотвращают длительную блокировку БД.

## API boundaries

Реализованные группы `/api/v1` endpoint'ов и их роль:

| Группа | Возможные операции | Источник ответа |
|---|---|---|
| `datasets` | список версий, manifest, валидация доступного файла | SQLite metadata и файловый manifest; не передавать весь датасет по умолчанию |
| `experiments` | шаблоны/definitions, просмотр конфигурации | SQLite, immutable config snapshot |
| `runs` | создать, статус, отменить, folds, результаты, ошибки | application service и сохранённые данные |
| `classifier` | active deployment model, benchmark, real UCI example, prediction | versioned model registry и полный fitted pipeline |
| `features` | budgets, selection frequency, stability, PCA variance | заранее рассчитанные scientific aggregates |
| `core/sufficiency`, paired comparison | corrected paired decisions по общим folds | verified fold artifacts; отдельный derived analysis |
| `system/reproducibility` | Git/data/software provenance, состояние worker | сохранённый environment snapshot и статус |

Сервер заранее вычисляет и сохраняет fold-level метрики, confidence/uncertainty по утверждённой методике, confusion matrices, selection frequency/Jaccard и resource summaries. Запрос может дешёво фильтровать, сортировать, пагинировать, соединять записи и превращать сохранённые сводки в серии для Plotly; при смене **научной** формулы создаётся версия расчёта, а не скрытый пересчёт в браузере. Большие predictions и модели выдаются через управляемые ссылки/экспорт, а не в каждой выдаче списка. Для ошибок API различает `not_run`, `running`, `failed`, `not_calculated` и `completed`.

## Реализованные product surfaces

Маршруты `/`, `/experiments`, `/runs`, `/runs/[id]`, `/feature-budget`, `/features`, `/compare`, `/classifier` и `/settings` используют один typed client и сохранённые API-сущности. Feature Budget строит линии только для полностью рассчитанных `k=1…16` series; partial series остаются отдельными измеренными markers. Run detail является reproducibility report. Classifier применяет только active registered pipeline. При отсутствии результатов страницы показывают loading/error/partial/`not calculated`, а не случайные данные.

Поздние Experiment Registry, Pareto Analysis, Conference Mode, расширенные сравнения, ручная ablation и генерация отчёта добавляются как новые application queries/commands и UI-маршруты поверх сохранённых fold results и artifacts. Они не требуют переноса ML-логики в API или frontend. Ручная ablation создаёт новую версионируемую experiment definition и честный run, а не изменяет сохранённые научные результаты.

## Утверждённый React UI stack

Утверждены **MUI Core, MUI X Data Grid Community, Tabler Icons и Plotly**. Lucide, MUI X Pro/Premium, коммерческие возможности Data Grid и MUI Charts не входят в первую версию. Plotly используется для научных графиков. Собственный UI kit не создаётся: стандартные buttons, inputs, forms, dialogs, tabs, menus, tooltips, navigation, tables/data grids, pagination, alerts и progress/state indicators собираются из готовых MUI-компонентов там, где они подходят. Custom components допустимы только для специфических исследовательских представлений BeanFeature Lab, которые нельзя разумно собрать из готовых primitives.

Табличные сценарии проектируются в пределах лицензии Community: базовая сортировка и фильтрация по одному критерию, пагинация с ограничением размера страницы до 100 строк. Multi-sort, multi-filter, column pinning, row grouping и Excel export не предполагаются как возможности Data Grid первой версии. При потребности в иных сценариях сначала проверяется состав актуальной Community-версии и отдельно принимается продуктовое решение; скрытой зависимости от Pro/Premium быть не должно.

Сравнение, на основании которого выбран стек, сохранено для объяснения решения:

| Критерий | Mantine | Material UI (MUI) |
|---|---|---|
| Готовые компоненты, формы, навигация | Широкий набор, `AppShell`, поля, навигация и `@mantine/form` с валидацией. | Широкий Core-набор; формы и навигация готовы, сложная форма требует собственной orchestration или отдельной form-библиотеки. |
| Таблицы | Core `Table` хорошо подходит для небольших семантических таблиц; полноценный data grid находится в экосистеме extensions, не в Core. | Официальный `MUI X Data Grid` даёт сортировку, фильтрацию, пагинацию, виртуализацию и keyboard navigation. Community бесплатен; часть продвинутых функций платная. |
| Accessibility | Документация заявляет WAI-ARIA, keyboard/focus и тесты; доступность итогового приложения всё равно проверяется отдельно. | Data Grid документирует WAI-ARIA и навигацию с клавиатуры; кастомные ячейки и Plotly требуют отдельного аудита. |
| Responsive и theming | Готовый responsive `AppShell`, provider и Styles API; удобно уйти от шаблонного dashboard. | Breakpoints, theme/component overrides и CSS variables; исходный Material-облик потребует последовательной настройки позже. |
| Next.js | Официальная инструкция App Router; компоненты используют client boundary. | Официальная интеграция App Router с cache provider для SSR/streaming. |
| Объём собственного UI-кода | Меньше для форм и shell; больше интеграционной работы, если нужен сложный grid из extension. | Меньше для реестров и таблиц благодаря Data Grid; тема и композиция потребуют работы, но базовые элементы не переписываются. |
| Иконки и поддерживаемость | Совместим с `@tabler/icons-react`; Core и grid-extension обновляются отдельно. | Совместим с `@tabler/icons-react`; Core и X имеют официальную поддержку, но план функций X надо проверять до использования. |

**Причина утверждённого выбора:** реестры запусков и сравнения требуют готового доступного data grid с минимальным собственным кодом. Реализованный Instrument Workstation следует научным задачам и происхождению данных, а не типовому AI/SaaS dashboard template. Если возникнет потребность в функциях Pro/Premium, потребуется отдельное решение; текущая версия на них не опирается.

Основание сравнения: официальные документы [Mantine Next.js](https://mantine.dev/guides/next/), [Mantine AppShell](https://mantine.dev/core/app-shell/), [Mantine Table](https://mantine.dev/core/table/), [Mantine Forms](https://mantine.dev/form/validation/), [Mantine accessibility](https://help.mantine.dev/q/are-mantine-components-accessible), [MUI Next.js](https://mui.com/material-ui/integrations/nextjs/), [MUI Data Grid](https://mui.com/x/react-data-grid/), [MUI X licensing](https://mui.com/x/introduction/licensing/), [Data Grid filtering](https://mui.com/x/react-data-grid/filtering/), [Data Grid sorting](https://mui.com/x/react-data-grid/sorting/), [Data Grid pagination](https://mui.com/x/react-data-grid/pagination/), [MUI Data Grid accessibility](https://mui.com/x/react-data-grid/accessibility/), [Tabler React icons](https://tabler.io/icons/packages). Сведения о возможностях библиотек проверены на этапе проектирования; совместимость конкретных версий следует повторно проверить перед установкой.

## Зафиксированные решения и открытые границы

Метод corrected repeated-CV interval, Bonferroni family, margin `0.01`, search spaces, comparator points, resource measurement profile и classifier deployment boundary зафиксированы до соответствующих вычислений. Public hosting работает как локальный Mac-hosted read-only surface: classifier prediction разрешён как bounded side-effect-free inference, scientific writes заблокированы. Независимый подтверждающий dataset, отдельная честная процедура выбора «лучшей» model/selector family, calibration research, Pareto analysis и Conference Mode остаются явно вне текущего Core; их отсутствие не подменяется выводами из уже просмотренных outer-CV curves.
