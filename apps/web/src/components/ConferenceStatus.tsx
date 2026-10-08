import React from "react";
import { Alert, Button, CircularProgress } from "@mui/material";
import { IconRefresh } from "@tabler/icons-react";
import styles from "./Conference.module.css";

export function ConferenceStatus({ loading, error, expired, retry, renew }: {
  loading: boolean; error: string; expired: boolean; retry: () => void; renew: () => void;
}) {
  return <>
    {loading && <div role="status" className={styles.loading}><CircularProgress size={28} /><div><strong>Проверяем научный снимок</strong><p>Dataset, artifacts и совместимость outer folds. Эксперименты не запускаются.</p></div></div>}
    {error && <Alert severity="error" action={<Button onClick={retry}>Повторить</Button>}>{error}</Alert>}
    {expired && <Alert severity="warning" action={<Button onClick={renew} startIcon={<IconRefresh size={16} />}>Новый снимок</Button>}>Срок снимка истёк. На экране остаётся прежнее свидетельство; для PDF создайте новый проверенный снимок. Текущий шаг сохранится.</Alert>}
  </>;
}
