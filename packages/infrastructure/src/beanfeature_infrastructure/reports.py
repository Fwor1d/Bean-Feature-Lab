"""A bounded, offline PDF adapter. It renders verified DTOs; it never trains or writes DB."""

import io
import json
import os
import time
from concurrent.futures import Future, TimeoutError
from datetime import UTC, datetime
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock, Semaphore
from xml.sax.saxutils import escape

from beanfeature_application.reporting import ReportError, canonical, digest, report_protocol

MODEL_NAMES = {
    "logistic_regression": "Logistic Regression",
    "svm_rbf": "SVM RBF",
    "random_forest": "Random Forest",
    "xgboost": "XGBoost",
    "lightgbm": "LightGBM",
    "mlp": "MLP",
}
SELECTOR_NAMES = {
    "none": "Без отбора",
    "mutual_information": "Mutual Information",
    "anova": "ANOVA",
    "rfe": "RFE",
    "l1_logistic": "L1 Logistic",
    "tree_importance": "Tree importance",
    "pca": "PCA",
}
MAX_PDF_BYTES = 10 * 1024 * 1024


def number(value, digits=4):
    return "Не рассчитано" if value is None else f"{value:.{digits}f}"


class PDFReports:
    """One render at a time, coalesced requests, two bounded cached PDFs."""

    def __init__(self):
        self.lock, self.renderer = Lock(), Semaphore(1)
        self.pending: dict[str, Future] = {}
        self.outputs: dict[str, tuple[float, bytes]] = {}
        self.cache_directory = TemporaryDirectory(prefix="beanfeature-pdf-")
        # Matplotlib's font cache stays transient; the application does not need system fonts.
        self.cache_environment = {}
        for key in ("MPLCONFIGDIR", "XDG_CACHE_HOME"):
            if key not in os.environ:
                os.environ[key] = self.cache_directory.name
                self.cache_environment[key] = self.cache_directory.name

    def close(self):
        for key, value in self.cache_environment.items():
            if os.environ.get(key) == value:
                del os.environ[key]
        self.cache_directory.cleanup()

    def render(self, snapshot: dict) -> bytes:
        identifier = snapshot["snapshot_id"]
        with self.lock:
            cached = self.outputs.get(identifier)
            if cached:
                self.outputs[identifier] = (time.monotonic(), cached[1])
                return cached[1]
            future = self.pending.get(identifier)
            owner = future is None
            if owner:
                if not self.renderer.acquire(blocking=False):
                    raise ReportError("pdf_busy", "Другой PDF формируется. Повторите запрос.", 503)
                future = Future()
                self.pending[identifier] = future
        if not owner:
            try:
                return future.result(timeout=60)
            except TimeoutError as exc:
                raise ReportError(
                    "pdf_busy", "PDF ещё формируется. Повторите запрос.", 503
                ) from exc
        try:
            output = render_pdf(snapshot)
            if not output.startswith(b"%PDF-") or len(output) > MAX_PDF_BYTES:
                raise ReportError("pdf_size", "PDF превышает допустимый размер.", 422)
            with self.lock:
                if len(self.outputs) >= 2:
                    oldest = min(self.outputs, key=lambda key: self.outputs[key][0])
                    del self.outputs[oldest]
                self.outputs[identifier] = (time.monotonic(), output)
            future.set_result(output)
            return output
        except BaseException as exc:
            future.set_exception(exc)
            raise
        finally:
            with self.lock:
                del self.pending[identifier]
            self.renderer.release()


def render_pdf(snapshot: dict) -> bytes:
    # Validate evidence identity before rendering, including a DTO passed outside the API.
    if snapshot.get("format_version") != "core-report-v1":
        raise ReportError("unsupported_evidence", "Неподдерживаемый формат снимка.", 422)
    if any(
        snapshot.get("protocol", {}).get(key) != value
        for key, value in report_protocol().items()
        if key != "reference"
    ):
        raise ReportError("unsupported_protocol", "Неподдерживаемый протокол снимка.", 422)
    context_fields = {
        "evidence_sha256",
        "verified_at_utc",
        "generation_context",
        "snapshot_id",
        "expires_at_utc",
    }
    evidence = {k: v for k, v in snapshot.items() if k not in context_fields}
    if digest(evidence) != snapshot["evidence_sha256"] or not snapshot.get("runs"):
        raise ReportError("invalid_evidence", "Снимок повреждён или не содержит результатов.")
    if len(snapshot["runs"]) > 512 or len(canonical(snapshot)) > 8 * 1024 * 1024:
        raise ReportError("evidence_size", "Снимок превышает допустимый размер.", 422)
    import matplotlib
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from matplotlib.font_manager import FontProperties
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (
        Image,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Table,
        TableStyle,
    )

    fonts = Path(matplotlib.get_data_path()) / "fonts/ttf"
    for name, filename in [
        ("ReportSans", "DejaVuSans.ttf"),
        ("ReportBold", "DejaVuSans-Bold.ttf"),
        ("ReportMono", "DejaVuSansMono.ttf"),
    ]:
        if not (fonts / filename).is_file():
            raise ReportError(
                "fonts_unavailable", "Встроенные кириллические fonts недоступны.", 503
            )
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(fonts / filename)))
    pdfmetrics.registerFontFamily(
        "ReportSans",
        normal="ReportSans",
        bold="ReportBold",
        italic="ReportSans",
        boldItalic="ReportBold",
    )
    plot_font = FontProperties(fname=str(fonts / "DejaVuSans.ttf"), size=10)
    output = io.BytesIO()
    width = A4[0] - 88
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            "BodyRU",
            fontName="ReportSans",
            fontSize=10,
            leading=15,
            textColor=colors.HexColor("#263c53"),
            spaceAfter=10,
        )
    )
    styles.add(
        ParagraphStyle(
            "TitleRU",
            parent=styles["BodyRU"],
            fontName="ReportBold",
            fontSize=26,
            leading=32,
            spaceAfter=22,
        )
    )
    styles.add(
        ParagraphStyle(
            "HeadingRU",
            parent=styles["BodyRU"],
            fontName="ReportBold",
            fontSize=17,
            leading=22,
            spaceAfter=16,
        )
    )
    styles.add(
        ParagraphStyle("CellRU", parent=styles["BodyRU"], fontSize=8.5, leading=11, spaceAfter=0)
    )
    styles.add(ParagraphStyle("HeaderRU", parent=styles["CellRU"], fontSize=7, leading=10))
    styles.add(ParagraphStyle("SmallRU", parent=styles["BodyRU"], fontSize=8, leading=11))
    styles.add(
        ParagraphStyle(
            "HashRU",
            parent=styles["SmallRU"],
            fontName="ReportMono",
            fontSize=7,
            leading=10,
            wordWrap="CJK",
        )
    )
    story = []
    generated = datetime.now(UTC).isoformat()

    def paragraph(text, style="BodyRU"):
        return Paragraph(escape(str(text)).replace("\n", "<br/>"), styles[style])

    def add(text, style="BodyRU"):
        story.append(paragraph(text, style))

    def section(title):
        if story:
            story.append(PageBreak())
        add(title, "HeadingRU")

    def table(headers, rows, widths=None, hash_column=None):
        if not rows:
            add("Не рассчитано: совместимые проверенные результаты отсутствуют.")
            return
        data = [[paragraph(x, "HeaderRU") for x in headers]]
        data += [
            [
                paragraph(cell, "HashRU" if i == hash_column else "CellRU")
                for i, cell in enumerate(row)
            ]
            for row in rows
        ]
        item = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
        item.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9eef4")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.35, colors.HexColor("#cad4df")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        item.spaceAfter = 10
        story.append(item)

    def figure(selector, *, loss=False):
        fig = Figure(figsize=(7.05, 3.4), dpi=170, layout="constrained")
        FigureCanvasAgg(fig)
        ax = fig.add_subplot()
        markers = ["o", "s", "^", "D", "+", "*"]
        line_styles = ["-", "--", ":", "-.", (0, (5, 2, 1, 2)), "-"]
        palette = ["#255a91", "#9a5a1c", "#2e735f", "#785391", "#a5414b", "#263c53"]
        shown = 0
        for i, model in enumerate(MODEL_NAMES):
            if loss:
                family = next((f for f in snapshot["sufficiency"] if f["model"] == model), None)
                values = [
                    (c["k_original_features"], c["one_sided_upper_confidence_bound"])
                    for c in (family or {}).get("comparisons", [])
                    if c.get("one_sided_upper_confidence_bound") is not None
                    and c["k_original_features"] >= 10
                ]
            else:
                values = [
                    (
                        r["summary"]["n_components"]
                        if selector == "pca"
                        else r["summary"]["k_original_features"],
                        r["summary"]["macro_f1_mean"],
                    )
                    for r in snapshot["runs"]
                    if r["summary"]["model"] == model and r["summary"]["selector"] == selector
                ]
            if not values:
                continue
            values.sort()
            complete = len(values) == (6 if loss else 16) and [v[0] for v in values] == list(
                range(10, 16) if loss else range(1, 17)
            )
            ax.plot(
                [v[0] for v in values],
                [v[1] for v in values],
                marker=markers[i],
                linestyle=line_styles[i] if complete else "None",
                color=palette[i],
                markersize=4,
                linewidth=1.4,
                label=MODEL_NAMES[model],
            )
            shown += 1
        if not shown:
            add("Фигура не рассчитана: проверенные наблюдения отсутствуют.")
            return
        if loss:
            ax.axhline(
                snapshot["protocol"]["margin"],
                linestyle="--",
                color="#a5414b",
                linewidth=1,
                label="δ = " + str(snapshot["protocol"]["margin"]),
            )
        elif selector == "mutual_information":
            for run in snapshot["runs"]:
                if run["configuration"]["selector"] == "none":
                    ax.scatter(
                        [16],
                        [run["summary"]["macro_f1_mean"]],
                        marker="D",
                        color="#263c53",
                        s=30,
                        zorder=4,
                    )
        ax.set_xlabel(
            "Исходные признаки k" if selector != "pca" else "Число PCA components",
            fontproperties=plot_font,
        )
        ax.set_ylabel(
            "Upper loss bound · Macro-F1" if loss else "Macro-F1", fontproperties=plot_font
        )
        ax.set_xticks([10, 11, 12, 13, 14, 15] if loss else [1, 4, 8, 12, 16])
        ax.grid(alpha=0.2)
        for label in [*ax.get_xticklabels(), *ax.get_yticklabels()]:
            label.set_fontproperties(plot_font)
        ax.legend(
            prop=FontProperties(fname=str(fonts / "DejaVuSans.ttf"), size=8),
            loc="upper center",
            bbox_to_anchor=(0.5, -0.2),
            ncol=2,
            frameon=False,
        )
        stream = io.BytesIO()
        fig.savefig(stream, format="png", dpi=170)
        stream.seek(0)
        image = Image(stream, width=width, height=width / 7.05 * 3.4)
        image.spaceAfter = 12
        story.append(image)

    runs = snapshot["runs"]
    dataset, protocol = snapshot["dataset"], snapshot["protocol"]
    baselines = sorted(
        (r for r in runs if r["configuration"]["selector"] == "none"),
        key=lambda r: list(MODEL_NAMES).index(r["configuration"]["model"]),
    )
    partial = any(f["status"] != "CALCULATED" for f in snapshot["sufficiency"])
    add("BeanFeature Lab", "TitleRU")
    add("Число исходных признаков и качество классификации Dry Bean", "HeadingRU")
    add("Научный отчёт · " + ("частичные результаты" if partial else "проверенный Core snapshot"))
    add(
        "Цель: исследовать зависимость multiclass classification quality от числа исходных "
        "морфологических признаков и проверить заранее заданный предел потери Macro-F1."
    )
    add(
        "Отчёт использует сохранённые проверенные эксперименты. Обучение при его "
        "создании не выполнялось."
    )
    add(
        "Экономическая выгода сокращения измерений не измерялась. PCA components не означают "
        "сокращение исходных физических измерений."
    )
    add(
        f"Проверенных условий: {len(runs)}. Selection: самый ранний COMPLETED run каждого условия; "
        "full protocol; без отбора по лучшей метрике."
    )
    add("Evidence SHA-256", "SmallRU")
    add(snapshot["evidence_sha256"], "HashRU")
    add("Снимок проверен: " + snapshot["verified_at_utc"], "SmallRU")
    add("PDF сформирован: " + generated, "SmallRU")
    add(
        "Читать: dataset и протокол → curves и baselines → sufficient-k → comparators/PCA → "
        "ограничения → полный индекс источников."
    )

    section("Dataset и происхождение")
    add(
        f"UCI Dry Bean Dataset · ID {dataset['source_id']}: {dataset['rows']} observations, "
        f"{dataset['feature_count']} original features, {len(dataset['classes'])} classes. "
        f"Missing values: {snapshot['quality']['missing_values']}."
    )
    table(
        ["Класс", "Объекты", "Доля"],
        [
            [label, entry["count"], f"{entry['fraction']:.2%}"]
            for label, entry in snapshot["quality"]["class_balance"].items()
        ],
        [240, 100, width - 340],
    )
    add("Canonical ARFF schema: " + ", ".join(dataset["features"]))
    add("Официальные spellings AspectRation, roundness и DERMASON сохранены.")
    for label, field in [
        ("Dataset version", "dataset_version"),
        ("ARFF SHA-256", "arff_sha256"),
        ("ZIP SHA-256", "archive_sha256"),
        ("Retrieved UTC", "retrieved_at_utc"),
    ]:
        add(label + ": " + str(dataset[field]), "HashRU" if "SHA" in label else "SmallRU")
    add("Источник: https://archive.ics.uci.edu/dataset/602/dry+bean+dataset", "SmallRU")
    add("Downloaded archive: " + dataset["source_url"], "SmallRU")

    section("Frozen экспериментальный дизайн")
    add(
        f"Outer CV: RepeatedStratifiedKFold(n_splits={protocol['outer_splits']}, "
        f"n_repeats={protocol['outer_repeats']}). Inner CV: StratifiedKFold(n_splits="
        f"{protocol['inner_splits']}, shuffle=True). Seed: {snapshot['cohort']['seed']}."
    )
    add(
        "В каждом outer training fold отдельно обучаются scaling, feature selection/PCA "
        "и подбор hyperparameters по inner Macro-F1. Outer test fold не участвует в подборе. "
        "Сравнимые условия используют одинаковые frozen outer splits."
    )
    add(
        "Macro-F1 — среднее F1 классов с равным весом. Accuracy — доля корректных predictions. "
        "Средние ниже описывают результаты outer folds, а не независимое внешнее испытание."
    )
    add(
        "Fold SD является описательной дисперсией зависимых repeated-CV folds; она не используется "
        "как независимый standard error или доверительный интервал."
    )
    table(
        ["Модель", "Доступные методы"],
        [
            [
                name,
                ", ".join(
                    SELECTOR_NAMES[s]
                    for s in sorted(
                        {
                            r["configuration"]["selector"]
                            for r in runs
                            if r["configuration"]["model"] == model
                        }
                    )
                ),
            ]
            for model, name in MODEL_NAMES.items()
            if any(r["configuration"]["model"] == model for r in runs)
        ],
        [160, width - 160],
    )
    add("Protocol version: " + protocol["version"], "HashRU")
    add("Outer splits SHA-256: " + snapshot["cohort"]["outer_split_set_sha256"], "HashRU")
    add("MLP — только full-feature baseline. Extended selectors не входят в этот отчёт.")

    section("Primary результаты: Mutual Information")
    figure("mutual_information")
    add(
        "Средний Macro-F1 по outer folds. Ромбы при k=16 — baselines без отбора. "
        "Линия только для полного ряда 1…16; неполные ряды показаны точками. "
        "Форма marker и line style различают модели независимо от цвета."
    )
    models = [
        model
        for model in MODEL_NAMES
        if any(
            r["summary"]["model"] == model and r["summary"]["selector"] == "mutual_information"
            for r in runs
        )
    ]
    mi = {
        (r["summary"]["model"], r["summary"]["k_original_features"]): r["summary"]["macro_f1_mean"]
        for r in runs
        if r["summary"]["selector"] == "mutual_information"
    }
    table(
        ["k", *[MODEL_NAMES[m] for m in models]],
        [[k, *[number(mi.get((m, k))) for m in models]] for k in range(1, 17)],
        [25, *[(width - 25) / max(1, len(models))] * len(models)],
    )

    section("Baselines: 16 исходных признаков")
    table(
        ["Модель", "Macro-F1", "Accuracy", "Run"],
        [
            [
                MODEL_NAMES[r["configuration"]["model"]],
                number(r["summary"]["macro_f1_mean"]),
                number(r["summary"]["accuracy_mean"]),
                r["run_id"],
            ]
            for r in baselines
        ],
        [175, 90, 90, width - 355],
    )
    add(
        "Все baselines используют оригинальные признаки без selector; preprocessing и "
        "hyperparameter tuning остаются внутри CV. Deployment classifier, refitted на всех "
        "данных для inference, не служит независимой оценкой качества."
    )
    diagnostics = snapshot.get("baseline_diagnostics", {})
    labels = sorted(dataset["classes"])
    table(
        ["Модель", *labels],
        [
            [
                MODEL_NAMES[r["configuration"]["model"]],
                *[
                    number(
                        diagnostics.get(r["run_id"], {})
                        .get("per_class_recall_fold_mean", {})
                        .get(label),
                        3,
                    )
                    for label in labels
                ],
            ]
            for r in baselines
        ],
        [120, *[(width - 120) / len(labels)] * len(labels)],
    )
    add(
        "Recall по классам: описательное среднее записанных значений 15 outer folds. "
        "Отсутствующие записи остаются не рассчитанными.",
        "SmallRU",
    )
    if baselines:
        chosen = baselines[0]
        diagnostic = diagnostics.get(chosen["run_id"], {})
        if diagnostic.get("status") == "CALCULATED":
            add(
                "Confusion matrix: "
                + MODEL_NAMES[chosen["configuration"]["model"]]
                + " · "
                + chosen["run_id"]
            )
            table(
                ["True / predicted", *labels],
                [
                    [label, *row]
                    for label, row in zip(labels, diagnostic["confusion_matrix_sum"], strict=True)
                ],
                [120, *[(width - 120) / len(labels)] * len(labels)],
            )
            add(
                "Сумма сохранённых confusion matrices 15 folds: каждый объект предсказывается "
                "в трёх repeats. Counts не являются числом различных независимых объектов. "
                "Baseline выбран первым в фиксированном порядке моделей, не по лучшей метрике.",
                "SmallRU",
            )

        else:
            add("Confusion matrix не рассчитана: полные совместимые записи folds отсутствуют.")

    section("Sufficient-k: corrected paired анализ")
    add(
        f"D = MacroF1_baseline16 − MacroF1_MI,k на одинаковых outer folds. Margin δ="
        f"{protocol['margin']}; one-sided Nadeau–Bengio correction, Bonferroni α="
        f"{protocol['family_alpha']}/{protocol['comparisons_per_model']} внутри каждой модели."
    )
    add(
        "Corrected SE = sqrt((1/15 + 1/4) × sample variance(D)); upper bound = mean(D) + "
        "t(1 − α, df=14) × corrected SE. Формальное решение требует upper bound ≤ δ. "
        "Формула и константы зафиксированы протоколом, не подобраны по результатам."
    )
    add(
        "Минимальный sufficient-k публикуется только для полной семьи из 15 сравнений. "
        "Not sufficient означает, что достаточность не установлена этим критерием; "
        "это не доказательство непригодности модели."
    )
    table(
        ["Модель", "k", "Upper loss bound", "Сравнения"],
        [
            [
                MODEL_NAMES[f["model"]],
                f["minimal_sufficient_k"]
                if f["minimal_sufficient_k"] is not None
                else ("Не установлен" if f["status"] == "CALCULATED" else "Не рассчитано"),
                number(
                    next(
                        (
                            c.get("one_sided_upper_confidence_bound")
                            for c in f["comparisons"]
                            if c["k_original_features"] == f["minimal_sufficient_k"]
                        ),
                        None,
                    ),
                    6,
                ),
                str(f["calculated_comparisons"]) + "/15",
            ]
            for f in snapshot["sufficiency"]
        ],
        [175, 70, 130, width - 375],
    )
    figure("mutual_information", loss=True)
    add(
        "Детальный вид k=10…15 из полной семьи 1…15. Полные upper bounds приведены ниже. "
        "Sufficient-k относится только к этой модели, MI и frozen protocol.",
        "SmallRU",
    )
    section("Полная семья corrected upper loss bounds")
    families = snapshot["sufficiency"]
    table(
        ["k", *[MODEL_NAMES[f["model"]] for f in families]],
        [
            [
                k,
                *[
                    number(
                        next(
                            (
                                c.get("one_sided_upper_confidence_bound")
                                for c in f["comparisons"]
                                if c["k_original_features"] == k
                            ),
                            None,
                        ),
                        6,
                    )
                    for f in families
                ],
            ]
            for k in range(1, 16)
        ],
        [25, *[(width - 25) / len(families)] * len(families)],
    )
    add(
        "Предел сравнения — δ=" + str(protocol["margin"]) + ". Multiplicity correction "
        "применена к 15 бюджетам внутри модели; это не тест превосходства между моделями."
    )

    section("Selectors: описательные comparator результаты")
    for model in MODEL_NAMES:
        selected = [
            r
            for r in runs
            if r["configuration"]["model"] == model
            and r["configuration"]["selector"] in {"anova", "rfe", "tree_importance"}
        ]
        if not selected:
            continue
        add(MODEL_NAMES[model])
        selectors = sorted({r["configuration"]["selector"] for r in selected})
        table(
            ["Метод / k", "1", "2", "4", "8", "12", "16"],
            [
                [
                    SELECTOR_NAMES[s],
                    *[
                        number(
                            next(
                                (
                                    r["summary"]["macro_f1_mean"]
                                    for r in selected
                                    if r["configuration"]["selector"] == s
                                    and r["configuration"]["k_original_features"] == k
                                ),
                                None,
                            )
                        )
                        for k in [1, 2, 4, 8, 12, 16]
                    ],
                ]
                for s in selectors
            ],
            [125, *[(width - 125) / 6] * 6],
        )
    add(
        "Средний Macro-F1 на frozen comparator budgets. Разность средних не объявляется "
        "статистическим превосходством. Неизмеренные условия не интерполируются."
    )
    sparse = [r for r in runs if r["configuration"]["selector"] == "l1_logistic"]
    table(
        ["L1 C", "Macro-F1", "Accuracy", "Ненулевые признаки в folds"],
        [
            [
                str(r["configuration"].get("selector_configuration", {}).get("C")),
                number(r["summary"]["macro_f1_mean"]),
                number(r["summary"]["accuracy_mean"]),
                ", ".join(map(str, r["summary"].get("observed_nonzero_feature_counts") or []))
                or "Недоступно",
            ]
            for r in sparse
        ],
        [55, 80, 80, width - 215],
    )
    add(
        "L1 C задаёт регуляризацию, не фиксированный feature budget. Сохранены "
        "observed fold counts."
    )

    section("PCA: отдельная dimensionality branch")
    add(
        "n_components — число компонент. Для вычисления PCA требуются все 16 исходных признаков. "
        "PCA не участвует в выборе минимального числа физических измерений."
    )
    figure("pca")
    pca_models = [
        m
        for m in MODEL_NAMES
        if any(
            r["configuration"]["model"] == m and r["configuration"]["selector"] == "pca"
            for r in runs
        )
    ]
    table(
        ["Components", *[MODEL_NAMES[m] for m in pca_models]],
        [
            [
                k,
                *[
                    number(
                        next(
                            (
                                r["summary"]["macro_f1_mean"]
                                for r in runs
                                if r["configuration"]["model"] == m
                                and r["configuration"]["selector"] == "pca"
                                and r["configuration"]["n_components"] == k
                            ),
                            None,
                        )
                    )
                    for m in pca_models
                ],
            ]
            for k in range(1, 17)
        ]
        if pca_models
        else [],
        [80, *[(width - 80) / max(1, len(pca_models))] * len(pca_models)],
    )

    section("Интерпретация и ограничения")
    add(
        "Результаты описывают зависимость качества от model/selector/budget в данном dataset. "
        "Монотонность не предполагается; universally optimal feature set не объявляется."
    )
    add(
        "Sufficient-k — non-inferiority-style решение относительно same-model baseline "
        "при fixed margin. Оно не доказывает равенство качества и не переносится автоматически "
        "на другие cameras, batches, populations или datasets."
    )
    for limitation in [
        "Проведена internal repeated cross-validation; external validation отсутствует.",
        "Outer folds зависимы; corrected statistical method учитывает их перекрытие приближённо.",
        "Selection может различаться между folds. Полные исторические rank "
        "distributions отсутствуют.",
        "Исторические memory measurements не реконструировались; экономическая "
        "стоимость не измерялась.",
        "MLP имеет Core baseline; Extended selectors и новые experiments в отчёт не добавлялись.",
    ]:
        add("• " + limitation)
    if snapshot["excluded"]:
        add(
            "Исключённые runs: "
            + "; ".join(r["run_id"] + ": " + r["reason"] for r in snapshot["excluded"]),
            "SmallRU",
        )

    section("Воспроизводимость и ссылки")
    add(
        "Scientific evidence можно идентифицировать по dataset/split hashes, "
        "immutable configuration "
        "fingerprints и result artifact hashes. PDF фиксирует один проверенный snapshot. "
        "Generation timestamps и PDF metadata могут различаться: byte-identical PDF не заявляется."
    )
    add("Evidence SHA-256: " + snapshot["evidence_sha256"], "HashRU")
    add("Snapshot ID: " + snapshot["snapshot_id"], "HashRU")
    add("Protocol: " + protocol["reference"] + " · " + protocol["version"], "SmallRU")
    add("Statistical method: " + protocol["method"], "SmallRU")
    add(
        "Snapshot verification context: "
        + json.dumps(snapshot["generation_context"], ensure_ascii=False, sort_keys=True),
        "SmallRU",
    )
    add("Renderer source SHA-256: " + sha256(Path(__file__).read_bytes()).hexdigest(), "HashRU")
    add(
        "Renderer: core-pdf-v1; ReportLab "
        + version("reportlab")
        + "; Matplotlib "
        + version("matplotlib")
        + ". Embedded DejaVu fonts from Matplotlib package; license LICENSE_DEJAVU.",
        "SmallRU",
    )
    add(
        "Источники: UCI Dataset 602 (https://archive.ics.uci.edu/dataset/602/dry+bean+dataset); "
        "repository PRODUCT.md; docs/research/EXPERIMENT_PROTOCOL.md; "
        "docs/architecture/ARCHITECTURE.md.",
        "SmallRU",
    )
    add(
        "Полный configuration/provenance доступен в result.json/config.json через /runs/{id}. "
        "Этот документ остаётся читаемым offline; ссылки нужны только для "
        "получения исходных artifacts."
    )
    provenances, environments = {}, {}
    for r in runs:
        provenance = r["provenance"]
        env = {k: provenance.get(k) for k in ("python_version", "platform", "package_versions")}
        env_id = digest(env)
        environments.setdefault(env_id, env)
        provenances.setdefault(digest(provenance), (provenance, env_id))
    for env_id, environment in environments.items():
        add(
            "Environment " + env_id[:12] + ": " + json.dumps(environment, sort_keys=True), "SmallRU"
        )
    table(
        ["Group / environment", "Git / source tree SHA-256"],
        [
            [
                key[:12] + " / " + env_id[:12],
                str(provenance.get("git_commit", "unavailable"))
                + " · dirty="
                + str(provenance.get("git_dirty"))
                + "\n"
                + str(provenance.get("source_tree_sha256", "unavailable")),
            ]
            for key, (provenance, env_id) in provenances.items()
        ],
        [180, width - 180],
        hash_column=1,
    )
    add(
        "Group — первые 12 знаков SHA-256 полного provenance; точный provenance связан с "
        "immutable artifact. Различия Git отражены, а не трактуются как несовместимость.",
        "SmallRU",
    )
    section("Индекс научных источников")
    add(
        "Каждый run связан с точными result SHA-256 и configuration/provenance fingerprint. "
        "Snapshot не изменяет completed artifacts. Group соответствует таблице выше."
    )
    short_models = dict(zip(MODEL_NAMES, ["LR", "SVM", "RF", "XGB", "LGB", "MLP"], strict=True))
    short_selectors = dict(
        zip(SELECTOR_NAMES, ["None", "MI", "ANOVA", "RFE", "L1", "Tree", "PCA"], strict=True)
    )
    add(
        "LR = Logistic Regression; SVM = SVM RBF; RF = Random Forest; XGB = XGBoost; "
        "LGB = LightGBM. MI = Mutual Information; Tree = tree importance. "
        "Бюджет: k для original features, n для PCA, C для L1.",
        "SmallRU",
    )
    table(
        ["Run / group", "Условие", "Result SHA-256 / fingerprint"],
        [
            [
                r["run_id"] + "\n" + digest(r["provenance"])[:12],
                short_models[r["configuration"]["model"]]
                + " / "
                + short_selectors[r["configuration"]["selector"]]
                + " / "
                + (
                    "n="
                    if r["configuration"]["selector"] == "pca"
                    else "C="
                    if r["configuration"]["selector"] == "l1_logistic"
                    else "k="
                )
                + str(
                    r["configuration"].get("k_original_features")
                    or r["configuration"].get("n_components")
                    or r["configuration"].get("selector_configuration", {}).get("C")
                ),
                r["result_sha256"] + "\n" + str(r["fingerprint"]),
            ]
            for r in runs
        ],
        [85, 105, width - 190],
        hash_column=2,
    )

    def footer(canvas, doc):
        if doc.page > 40:
            raise ReportError("pdf_size", "PDF превышает допустимое число страниц.", 422)
        canvas.saveState()
        canvas.setFont("ReportSans", 8)
        canvas.setFillColor(colors.HexColor("#506177"))
        canvas.drawString(44, 26, "BeanFeature Lab · " + snapshot["evidence_sha256"][:16])
        canvas.drawRightString(A4[0] - 44, 26, str(doc.page))
        canvas.restoreState()

    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        leftMargin=44,
        rightMargin=44,
        topMargin=44,
        bottomMargin=44,
        title="BeanFeature Lab — научный отчёт",
        author="BeanFeature Lab",
    )
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
