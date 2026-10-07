# Экспериментальный протокол BeanFeature Lab

Статус: Core-модели, матрица методов, margin, метрики, search budget, comparator-точки и corrected interval утверждены до соответствующих вычислений. Основание — [`PRODUCT.md`](../../PRODUCT.md) и [исходный научный доклад](./Влияние_количества_признаков_семян_фасоли_на_точность_их_классификации.docx). Числовые результаты хранятся только в проверяемых runtime-artifacts; этот документ фиксирует метод, а не подменяет result artifact.

## Вопрос и единица сравнения

Главный вопрос: как меняется качество классификации семи сортов **UCI Machine Learning Repository — Dry Bean Dataset — Dataset ID 602** при `k = 1…16` исходных морфологических признаков, и какова цена сокращения в качестве, времени, памяти и устойчивости выбора признаков? Официальный ARFF валидируется строго: 13 611 объектов, 16 численных признаков, семь классов, canonical spelling и pinned hashes; любое расхождение останавливает run.

Единица научного сравнения — условие `(dataset_version, model, selector, budget_kind, k, search_space_version, CV_protocol_version)`. Все сравниваемые условия используют **одни и те же заранее сохранённые outer splits** и одинаковое правило выбора лучшей inner-конфигурации по macro-F1. Результат на внешнем test fold — оценка всей процедуры выбора параметров, а не отдельной уже подобранной модели.

## Семантика feature budget

| Ветвь | Значение `k` | Что физически измеряется |
|---|---|---|
| ANOVA, Mutual Information, RFE, L1/деревья при точном top-k | Ровно `k` исходных колонок | Только выбранные исходные параметры. |
| L1 sparse path | `k` не задано как условие; хранится фактическое число ненулевых исходных признаков в каждом fold | Фактический набор может различаться между folds; нельзя подписать кривую как фиксированное `k`. |
| PCA | Ровно `k` главных компонент | Для вычисления компонент обычно нужны все 16 исходных признаков; `k` не является бюджетом физических измерений. |

В модели данных application/backend и API DTO обязательны `budget_kind = original_features | pca_components | sparse_original_features`, `k_original_features`, `n_components`, observed non-zero count при variable sparsity, `required_raw_feature_count` и `selected_original_features` только для применимых ветвей. UI показывает «исходных признаков», L1 variable sparsity и «компонент PCA» раздельно; PCA не может выигрывать конкурс минимального **измеряемого** feature budget.

## Статус моделей и методов по исходному DOCX

| Модель | Статус предложения | Причина |
|---|---|---|
| Logistic Regression | Core: 16-feature baseline и обязательная MI-кривая; также RFE/L1 и PCA comparator | Утверждена как одна из пяти моделей основной feature-budget кривой и интерпретируемый ориентир. |
| SVM RBF | Core | Главный нелинейный baseline; масштабирование внутри fold обязательно. Для RFE нужен отдельный линейный estimator. |
| Random Forest | Core | Нелинейная модель и источник tree ranking. |
| XGBoost | Core | Boosting baseline из доклада. |
| LightGBM | Core для baseline и общей MI-кривой | Проверяет переносимость зависимости `F1(k)` на другой boosting алгоритм; расширять на все selectors не требуется. |
| Небольшая MLP | Core только для baseline при `k=16`; полная кривая — Extended | Сохраняется в протоколе как независимый нелинейный baseline с fold-local scaling, но не входит в обязательную полную кривую первой версии. |

| Метод | Статус предложения | Что именно говорит DOCX |
|---|---|---|
| Mutual Information | Core | Полная кривая `k=1…16` с пятью моделями в утверждённой матрице. |
| ANOVA F-score | Core, контрольный filter comparator | Предложен для сравнения фильтров; матрица DOCX ограничивает модели SVM/RF/XGB. |
| RFE | Core, ограниченное сравнение | Главный wrapper; DOCX предлагает линейный SVM и логистическую регрессию как base estimators, избегая тяжёлого estimator на каждом шаге. |
| L1 Logistic Regression | Core, sparse embedded control | Доклад предлагает менять `C` и фиксировать фактическое число ненулевых исходных признаков; это отдельная кривая с переменным `k`. |
| Tree-based importance | Core, ограниченное embedded сравнение | Предложены RF/XGB/LGBM ranking и осторожная интерпретация коррелированных признаков. |
| PCA | Core как отдельная контрольная ветвь | Исследует информационную размерность, **не** сокращение исходных физических измерений. |
| Correlation pruning | Extended | Упомянут в рекомендуемом перечне фильтров, но **отсутствует в таблице основной матрицы экспериментов DOCX**. Поэтому не делаем его обязательной полной кривой. |
| Sequential Feature Selection | Extended | DOCX говорит «также можно использовать»; метод дорогой и **отсутствует в основной матрице**. |

В докладе есть разные уровни объёма: executive summary рекомендует SVM/RF/XGB/LGBM/MLP, а ограниченная версия по срокам — три модели. Утверждённая для BeanFeature Lab первая версия заменяет MLP на Logistic Regression в **обязательной MI-кривой**: LR, SVM RBF, RF, XGB и LGBM. MLP сохраняется в baseline и Extended. Полный Cartesian product всех моделей, selectors и `k` не требуется.

## Утверждённая матрица Core

Контрольные точки comparator-ветвей **зафиксированы до их первого запуска** в [`configs/experiments/core-comparators-v1.json`](../../configs/experiments/core-comparators-v1.json): `k ∈ {1, 2, 4, 8, 12, 16}`. Этот набор применяется к ANOVA, RFE и tree-importance и не меняется после просмотра результатов. Точки не заменяют полную главную MI-кривую. Условие `k=16` без отбора переиспользует baseline, если pipeline действительно эквивалентен; для PCA `n_components=16` остаётся отдельным условием.

Зафиксированные границы: ANOVA — SVM RBF/RF/XGBoost; RFE — LR с logistic estimator и SVM RBF с **linear SVM estimator только внутри selector**; tree importance — RF/XGBoost/LightGBM с ranking соответствующей семьи; PCA — LR/SVM RBF, `n_components=1…16`, отдельно от physical feature budget. L1 — sparse path LR по `C ∈ {0.01, 0.1, 1, 10}` с фактическим числом non-zero признаков, а не как fixed-k curve.

| Блок | Условия | Научная роль |
|---|---|---|
| C0 — 16-feature baseline | `k=16`, без selector; LR, SVM RBF, RF, XGB, LGBM, MLP | Общая точка сравнения качества и стоимости. |
| C1 — главная кривая | MI, `k=1…16`; LR, SVM RBF, RF, XGB, LGBM | Утверждённая полная зависимость `F1(k)` на одинаковых внешних folds для пяти моделей. MLP здесь не требуется. |
| C2 — второй filter | ANOVA, заранее заданные контрольные точки; SVM RBF, RF, XGB | Проверка, зависит ли картина от фильтра, без пятикратного размножения всей матрицы. |
| C3 — wrapper | RFE с LR и linear SVM, контрольные точки | Проверка model-aware отбора; SVM RBF не используется как RFE base estimator. |
| C4 — embedded | L1 logistic sparse path по заранее заданной сетке `C`; RF/XGB importance top-k на контрольных точках | Сопоставить разреженный линейный и нелинейный ranking с фильтрами; для L1 фиксировать фактический `k` по каждому fold. |
| C5 — PCA | `k_components=1…16`; SVM RBF и LR | Контроль информационной размерности при сохранении полной потребности в исходных измерениях. |

Hyperparameter search spaces и число испытаний фиксируются для каждого семейства до запуска и сохраняются в config snapshot. По возможности одинаковый вычислительный бюджет настройки внутри сравнимых семейств; различия фиксируются в отчёте. Предварительный **технический** прогон для оценки времени допускается только без просмотра качества и без изменения научной матрицы на основании результатов. Если бюджет вычислений недостаточен, матрица сужается и заново утверждается до сбора outer-test результатов.

## Extended после основной матрицы

| Ветвь | Польза и граница |
|---|---|
| MLP feature-budget curve и полные ANOVA/RFE/tree curves для дополнительных моделей | Уточнить взаимодействие model × selector × `k`; MLP остаётся в проекте, но её полная кривая не обязательна в первой версии. Результаты маркировать exploratory, если ветвь выбрана после просмотра Core. |
| Correlation pruning и Sequential Feature Selection | Проверить redundancy-aware и forward wrapper, которых нет в основной таблице DOCX. |
| PCA для XGBoost/MLP и thresholds explained variance | Проверить, зависит ли поведение компонент от модели и совпадает ли retained variance с полезной классификационной информацией. |
| Reverse ablation, permutation importance, расширенный L1 path | Изучить взаимозаменяемость признаков; не подменять этим primary feature-budget estimate. |
| Probability calibration, log loss, Brier/reliability diagrams | Важны перед демонстрацией вероятностей classifier; калибровать только внутри training folds. |
| Rice/Raisin, RGB/texture/HSI | Внешние исследования и другие постановки. Не объединять их scores с Dry Bean и не загружать сейчас. |
| Repeated/confirmatory validation сверх Core | Укрепить вывод о минимальном `k`, если заявляется практическая эквивалентность, особенно при широкой неопределённости. |

## Жизненный цикл одного run

1. **Config и identity.** Проверить schema version, допустимые `budget_kind/k`, search space, seed и измерительные условия. Сохранить immutable snapshot, hash и новый `RUN-{sequence:06d}`; зафиксировать Git commit или явный dirty state, software versions, dataset manifest.
2. **Dataset loading/validation.** Проверить source/version/hash, 16 ожидаемых численных колонок, target, классы, типы, пропуски/NaN/Inf, дубли и порядок колонок. Любые действия с подозрительными строками документируются заранее. Научное преобразование, оценивающее распределение, здесь не выполняется.
3. **Split manifest.** Один раз построить и сохранить индексы `RepeatedStratifiedKFold(5 splits × 3 repeats)` для данного dataset version и seed; одни и те же индексы применить ко всем Core-условиям. Inner `StratifiedKFold(4 splits, shuffle=True)` создаётся только на outer-train; seeds и индексы сохраняются. При наличии групп партия/камера протокол пересматривается в пользу group-aware split **до** оценки.
4. **Outer fold.** Изолировать outer-test. Никакое решение по признакам, масштабу, моделям, порогам или вероятностям не смотрит на него до единственного evaluation вызова для данного условия.
5. **Inner search.** На каждом inner-train заново обучить весь pipeline: допустимые train-only preprocessing/imputer при необходимости → StandardScaler там, где требуется → selector **или** PCA → estimator; подобрать разрешённые параметры по inner macro-F1. На inner-validation pipeline делает только `transform/predict`. `k` для научной кривой фиксирован; параметры selector и модели ищутся только здесь.
6. **Outer refit и evaluation.** Лучшую inner-конфигурацию заново обучить на полном outer-train, применить к outer-test и один раз вычислить fold-level метрики. Сохранить selected original features или PCA metadata, параметры и predictions; calibration, если включена, тоже обучается без outer-test.
7. **Resources.** Отдельно записать wall time всей inner-search+outer-refit процедуры, время финального refit, end-to-end inference latency pipeline для одной строки и пакета, peak process-tree RSS и размер сериализованного pipeline. Latency и память требуют warm-up, повторов и сохранения hardware/software условий.
8. **Aggregation и stability.** Только после завершения всех обязательных folds агрегировать scores, paired differences от `k=16`, неопределённость, confusion matrices, частоты выбора и Jaccard для исходных feature subsets. Для PCA stability физических subsets неприменима.
9. **Persistence.** Атомарно сохранить валидированные artifacts и hashes, fold records, aggregate version, status/error events. Один локальный worker выполняет тяжёлые задания последовательно или с явно ограниченной параллельностью; отмена и ошибка сохраняются, частичный run остаётся помеченным как таковой. FastAPI не выполняет nested CV внутри HTTP request; смена execution backend позднее не меняет research core. Redis/Celery в первой версии не требуются.
10. **API/UI.** FastAPI читает application queries; frontend отображает сохранённые значения и явный тип budget. Отсутствие расчёта показывается как `not calculated`, а не `0` или placeholder-метрика.

Нельзя заранее запускать `selector.fit(X_all, y_all)`, `scaler.fit(X_all)`, `PCA.fit(X_all)` или глобальную импутацию и затем делать CV. Даже если selector использует только `X`, его fit до CV сообщает модели структуру test fold. Ранжирование дерева/RFE/L1, подбор explained-variance threshold, выбор модели и `k` для конечной системы должны оставаться внутри соответствующего training fold. Официальный [пример scikit-learn по nested CV](https://scikit-learn.org/stable/auto_examples/model_selection/plot_nested_cross_validation_iris.html) описывает оптимистическое смещение при подборе и оценке на одних данных.

Отдельная задача **автоматического выбора конечной системы** рассматривает `model`, `selector`, `k` как совместно подбираемые параметры inner loop и оценивает эту процедуру на outer folds. Её score нельзя подменять максимумом по уже построенным outer-CV кривым. После честной оценки можно обучить финальный pipeline на всех доступных данных для classifier demo; это уже deployment artifact, а не независимый test result.

## Метрики и отчётность

| Роль | Показатели | Зачем |
|---|---|---|
| Primary | Macro-F1 по outer fold | Каждому из семи сортов одинаковый вес. |
| Required | Accuracy, recall по каждому классу и confusion matrix по outer fold | Показывают общее качество и конкретные смешения сортов; accuracy не является единственным основанием выбора. |
| Diagnostic | Multiclass macro ROC AUC OvR при корректной основе для расчёта | Показывает ранжирование классов; неприменимость отражается явно, AUC не заменяет F1. |
| Extended probability quality | Calibration, log loss, multiclass Brier/reliability | Включаются при конкретном анализе вероятностей, а не автоматически в обязательную первую матрицу. |
| Обязательные инженерные | Fit/search wall-clock time, финальный fit, latency полного preprocessing + model pipeline для одной строки и пакета, peak memory, размер сериализованного pipeline, Jaccard/selection frequency | Позволяют оценить стоимость сокращения и стабильность исходных признаков; latency и memory измеряются с повторами и сохранением условий. |

Macro precision/recall, balanced accuracy и weighted-F1 из DOCX можно сохранять как дополнительные диагностические поля при необходимости, но не объявлять равноправными критериями выбора без отдельной причины. Если ROC AUC или probability-метрика неприменима к конкретной модели/оценке, хранить `not_calculated` с причиной, а не искусственно создавать probabilities. Confusion matrix для повторов хранится по fold; при объединении учитывать, что один объект предсказывается в каждом повторе, и явно описывать нормировку. Не трактовать 15 коррелированных outer-fold оценок как 15 независимых выборок.

## Минимально достаточное `k`: утверждённый критерий и дополнительные анализы

| Подход DOCX | Достоинство для Dry Bean | Ограничение |
|---|---|---|
| One-standard-error rule | Простое консервативное предпочтение меньшего `k` возле максимума CV. | Standard error по повторным, зависимым folds нельзя наивно считать как по независимым наблюдениям; правило зависит от шумной оценки «лучшего» результата и не задаёт прикладную допустимую потерю. |
| Заранее заданная допустимая потеря macro-F1 от `k=16` | Напрямую отвечает на исследовательский вопрос о цене сокращения исходных измерений; margin `δ = 0.01` утверждён до запуска. | Метод оценки неопределённости ещё нужно зафиксировать до анализа; средняя разница сама по себе не доказывает достаточность меньшего `k`. |
| Pareto по F1, `k`, latency/памяти | Показывает несколько инженерно разумных компромиссов вместо одной «лучшей» модели. | Не даёт единственного минимального `k` без дополнительных предпочтений; resource noise может менять границу. |

**Основное заранее заданное non-inferiority-style правило:** для каждой из пяти моделей главной MI-кривой сравнивать `k < 16` с сопоставимым baseline той же модели на всех 16 исходных признаках при одинаковых outer folds. На каждом paired fold определять потерю `D_k = MacroF1_16 − MacroF1_k`. Наименьшее `k` исходных признаков считается достаточным, только если односторонняя верхняя граница интервала потери не превышает утверждённый абсолютный margin `δ = 0.01`.

**Зафиксированный метод `nadeau-bengio-corrected-resampled-t-v1`.** Для 15 paired differences (`n=15`) используется sample variance `s_D²` с `ddof=1` и corrected standard error `SE_corr = sqrt((1/n + n_test/n_train) × s_D²)`. Для 5-fold outer CV `n_test/n_train = 1/4`. Верхняя граница равна `mean(D_k) + t_(1−α*,14) × SE_corr`. Наивное `s_D/sqrt(15)` не вычисляется и не используется. Семейство — 15 сравнений `k=1…15` внутри одной модели; family-wise `α=0.05`, Bonferroni `α*=0.05/15`, односторонний критический уровень. Решение `sufficient` принимается только при `upper_bound <= 0.01`; иначе `not_sufficient`. При отсутствующем baseline/condition или несовпадающих fold identities решение `not_calculated` либо сравнение отклоняется. `k=16` не является compact candidate. Минимальный `k` определяется только среди `sufficient`; если таких нет, `minimal_sufficient_k = not established`.

Правило применяется отдельно к каждой модели; общий «лучший» вариант нельзя выбирать по максимуму просмотренных outer-test результатов без отдельной честной оценки процедуры выбора. Fold overlap учитывается correction factor, однако t-style interval остаётся приближением, а не независимым подтверждением на внешнем наборе. Margin и multiplicity correction не меняются после просмотра результатов. One-standard-error rule остаётся sensitivity analysis, Pareto — дополнительной инженерной интерпретацией.

## Честное измерение ресурсов на Apple Silicon/macOS

- Измерять на зафиксированном CPU-профиле; записывать модель Apple Silicon, число ядер, RAM, macOS, Python, версии NumPy/BLAS/scikit-learn/XGBoost/LightGBM, число потоков и `n_jobs`, питание, энергосбережение и условия фоновой нагрузки. Не смешивать CPU и GPU результаты. Порядок условий чередовать или рандомизировать по заранее заданному seed, чтобы нагрев/thermal throttling не всегда ухудшал один и тот же `k`.
- Для wall time использовать монотонный высокоточный счётчик, например Python [`time.perf_counter_ns`](https://docs.python.org/3.11/library/time.html#time.perf_counter_ns). Раздельно измерять весь inner search + refit и стоимость финального `fit` на outer-train; оба определения публиковать явно. Loading, запись SQLite и HTTP не входят в научное `fit`/inference измерение.
- Inference — сохранённый полный pipeline (валидные исходные колонки → preprocessing/selector или PCA → classifier), а не один `estimator.predict`. Отдельно измерять batch=1 и batch=1000 на допустимых test features после warm-up, много повторов, медиану и разброс/p95. Нормировать единицы как мс на 1 семя и мс на 1000 семян; не делить время одиночного вызова на 1000.
- Память: supervisor запускает каждое условие в отдельном spawned run process. До dataset load фиксируется baseline RSS; process и доступные descendants опрашиваются каждые 0,01 с до завершения evaluation, сохраняются absolute peak, incremental peak, число samples/children и hardware profile. Для отдельного deployment latency benchmark используется ещё один fresh process с warm-up и повторениями. RSS — операционная оценка, а не точное потребление общей памяти Apple Silicon; короткие пики sampler может пропустить. Если macOS запрещает child enumeration, сохраняется собственный RSS и ограничение measurement явно видно из metadata.
- Размер модели — фактический размер сериализованного **полного** pipeline и необходимых для инференса metadata на диске в байтах, с hash и форматом. Не подменять его размером Python-объекта в RAM.
- Ресурсные измерения повторять отдельно от случайности CV, хранить сырые замеры и медианы. Сопоставлять только условия одного hardware/software профиля и одинаковой параллельности; отчёт обязан указать шум и ограничения измерения.

## Воспроизводимость и научная честность

Каждый run сохраняет ID и UTC timestamp; Git SHA/dirty state; dataset source/version/SHA-256; seed и manifests outer/inner splits; модель, selector, `budget_kind`, `k`; search space и выбранные inner-гиперпараметры по fold; selected original features или PCA metadata; fold-level и агрегированные метрики с версией расчёта; fit/inference/memory измерения и их условия; пути/hashes model artifacts; версии зависимостей; status и ошибки. Для повторного запуска immutable config и dataset hashes должны совпадать, а несовпадение отмечаться как новый fingerprint.

Результаты других авторов и числовые примеры в DOCX служат контекстом и не попадают в результаты BeanFeature Lab. До реального эксперимента API и UI показывают `not run` / `not calculated`. Запрещены fake metrics, hardcoded best model/optimal `k`, фиктивные confusion matrices и случайные точки для графиков. Даже реальный результат одного Dry Bean набора нельзя автоматически обобщать на другую камеру, партию или регион.

## Решения до экспериментальных запусков

Основная матрица, margin `δ = 0.01`, corrected interval, multiplicity correction, comparator-точки, L1 path и обязательные метрики зафиксированы. Независимый подтверждающий dataset не входит в Core и по-прежнему не имитируется. Ресурсные benchmarks требуют сопоставимого hardware/software profile; classifier deployment отделён от independent CV evaluation.
