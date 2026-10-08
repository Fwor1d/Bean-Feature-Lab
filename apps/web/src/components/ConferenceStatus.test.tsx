import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import { ConferenceStatus } from "./ConferenceStatus";
const render = (props: { loading?: boolean; error?: string; expired?: boolean }) => renderToStaticMarkup(<ConferenceStatus loading={false} error="" expired={false} retry={() => {}} renew={() => {}} {...props} />);
it("announces verification/loading without placeholder results", () => {
  const markup = render({ loading: true });
  expect(markup).toContain('role="status"');
  expect(markup).toContain("Проверяем научный снимок");
  expect(markup).toContain("Эксперименты не запускаются");
});
it("shows API and missing/failed evidence with recovery", () => {
  for (const error of ["API недоступен", "Результаты не рассчитаны", "Проверка artifact не пройдена"]) {
    const markup = render({ error });
    expect(markup).toContain(error);
    expect(markup).toContain("Повторить");
  }
});
it("expired evidence is never silently replaced", () => {
  const markup = render({ expired: true });
  expect(markup).toContain("прежнее свидетельство");
  expect(markup).toContain("Новый снимок");
  expect(markup).toContain("Текущий шаг сохранится");
});
