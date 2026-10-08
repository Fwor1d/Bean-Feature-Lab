"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Box, Button, CssBaseline, Divider, Drawer, IconButton, List, ListItemButton,
  ListItemIcon, ListItemText, ThemeProvider, Typography,
} from "@mui/material";
import {
  IconAdjustments, IconChartBar, IconChartDots, IconClipboardList, IconDatabase,
  IconFlask, IconHelpCircle, IconMenu2, IconPlayerPlay, IconSettings, IconTable,
  IconX,
} from "@tabler/icons-react";
import { theme } from "@/theme";
import type { Dataset, Run } from "@/lib/api/contracts";
import { ContextPanel } from "./ContextPanel";

const navGroups = [
  { label: "Исследование", items: [
    { href: "/feature-budget", label: "Бюджет признаков", icon: IconChartDots },
    { href: "/experiments", label: "Эксперименты", icon: IconClipboardList },
    { href: "/runs", label: "Запуски", icon: IconPlayerPlay },
  ] },
  { label: "Анализ", items: [
    { href: "/features", label: "Анализ признаков", icon: IconTable },
    { href: "/compare", label: "Сравнение", icon: IconChartBar },
    { href: "/conference", label: "Научный доклад", icon: IconPlayerPlay },
  ] },
  { label: "Применение", items: [
    { href: "/classifier", label: "Классификатор", icon: IconFlask },
  ] },
];

function Navigation({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <nav className="app-nav" aria-label="Основная навигация" style={onNavigate ? { display: "flex", minHeight: "100%" } : undefined}>
      {navGroups.map(group => (
        <Box key={group.label}>
          <div className="nav-group-label">{group.label}</div>
          <List disablePadding dense>
            {group.items.map(item => (
              <ListItemButton key={item.href} component={Link} href={item.href} onClick={onNavigate}
                selected={pathname === item.href || (item.href === "/runs" && pathname.startsWith("/runs/"))} sx={{ mx: .75, my: .3, borderRadius: .5, color: "#e6edf3", minHeight: 42,
                  "&.Mui-selected": { bgcolor: "#304b67", color: "#fff" },
                  "&:hover": { bgcolor: "#384652" }, "&.Mui-selected:hover": { bgcolor: "#3b5875" } }}>
                <ListItemIcon sx={{ color: "inherit", minWidth: 31 }}><item.icon size={18} stroke={1.7} /></ListItemIcon>
                <ListItemText primary={item.label} slotProps={{ primary: { sx: { fontSize: 13 } } }} />
              </ListItemButton>
            ))}
          </List>
          <Divider sx={{ borderColor: "#46515c", mx: 1.5, my: 1 }} />
        </Box>
      ))}
      <Box className="nav-bottom">
        <List disablePadding dense>
          <ListItemButton component={Link} href="/settings" onClick={onNavigate} selected={pathname === "/settings"}
            sx={{ mx: .75, color: "#e6edf3", minHeight: 42 }}>
            <ListItemIcon sx={{ color: "inherit", minWidth: 31 }}><IconSettings size={18} /></ListItemIcon>
            <ListItemText primary="Настройки проекта" slotProps={{ primary: { sx: { fontSize: 13 } } }} />
          </ListItemButton>
          <ListItemButton component="a" href="https://archive.ics.uci.edu/dataset/602/dry+bean+dataset" target="_blank" rel="noreferrer"
            sx={{ mx: .75, color: "#e6edf3", minHeight: 42 }}>
            <ListItemIcon sx={{ color: "inherit", minWidth: 31 }}><IconHelpCircle size={18} /></ListItemIcon>
            <ListItemText primary="Источник данных" slotProps={{ primary: { sx: { fontSize: 13 } } }} />
          </ListItemButton>
        </List>
      </Box>
    </nav>
  );
}

export function AppShell({ children, datasets, runs }: { children: React.ReactNode; datasets: Dataset[] | null; runs: Run[] | null }) {
  const [navOpen, setNavOpen] = useState(false);
  const [contextOpen, setContextOpen] = useState(false);
  const pathname = usePathname();
  const selectedRun = runs?.find(run => pathname === `/runs/${run.id}`);
  const detailId = pathname.match(/^\/runs\/(\d+)$/)?.[1];
  if (pathname === "/conference") return <ThemeProvider theme={theme}><CssBaseline />{children}</ThemeProvider>;
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <div className="app-frame">
        <header className="app-top">
          <IconButton className="nav-toggle" aria-label="Открыть навигацию" onClick={() => setNavOpen(true)} sx={{ color: "#fff" }}><IconMenu2 size={20} /></IconButton>
          <Link className="brand" href="/">BeanFeature Lab</Link>
          <span className="brand-sub">Исследование. Признаки. Модели.</span>
          <div className="top-context" aria-label="Текущий контекст">
            <div className="top-context-item"><div className="top-context-label">Исследование</div><div className="top-context-value">Dry Bean · 602</div></div>
            <div className="top-context-item"><div className="top-context-label">Датасет</div><div className="top-context-value">{datasets === null ? "API недоступен" : datasets[0]?.validated ? "UCI · проверен" : "Не загружен"}</div></div>
            <div className="top-context-item"><div className="top-context-label">Запуск</div><div className="top-context-value">{selectedRun?.display_id ?? (detailId ? `#${detailId}` : "Не выбран")}</div></div>
          </div>
          <Button component={Link} href="/experiments" variant="contained" size="small" startIcon={<IconAdjustments size={16} />}
            sx={{ whiteSpace: "nowrap", display: { xs: "none", sm: "inline-flex" } }}>Конфигурации</Button>
          <IconButton className="context-toggle" aria-label="Открыть контекст и параметры" onClick={() => setContextOpen(true)} sx={{ color: "#fff" }}><IconDatabase size={20} /></IconButton>
        </header>
        <div className="app-body">
          <Navigation />
          <main className="workspace" id="main-content">{children}</main>
          <aside className="context-panel" aria-label="Контекст и параметры"><Suspense fallback={<Typography sx={{ color: "#c4cdd5", fontSize: 12 }}>Загрузка контекста…</Typography>}><ContextPanel runs={runs} /></Suspense></aside>
        </div>
        <Drawer open={navOpen} onClose={() => setNavOpen(false)} aria-label="Навигация" slotProps={{ paper: { sx: { width: 240, bgcolor: "#20272e" } } }}>
          <Box sx={{ display: "flex", justifyContent: "flex-end", p: 1 }}><IconButton aria-label="Закрыть навигацию" onClick={() => setNavOpen(false)} sx={{ color: "#fff" }}><IconX /></IconButton></Box>
          <Navigation onNavigate={() => setNavOpen(false)} />
        </Drawer>
        <Drawer anchor="right" open={contextOpen} onClose={() => setContextOpen(false)} aria-label="Контекст" slotProps={{ paper: { sx: { width: 300, bgcolor: "#252d35" } } }}>
          <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", p: 1.5, color: "#fff" }}><Typography sx={{ fontWeight: 700 }}>Контекст</Typography><IconButton aria-label="Закрыть контекст" onClick={() => setContextOpen(false)} sx={{ color: "#fff" }}><IconX /></IconButton></Box>
          <Box className="context-panel" sx={{ display: "block !important", border: 0 }}>
            <div className="context-mobile-state">Dry Bean · UCI 602<br />Датасет: {datasets === null ? "API недоступен" : datasets[0]?.validated ? "Проверен" : "Не загружен"}<br />Запуск: {selectedRun?.display_id ?? "Не выбран"}</div>
            <Suspense fallback={<Typography sx={{ color: "#c4cdd5", fontSize: 12 }}>Загрузка контекста…</Typography>}><ContextPanel runs={runs} /></Suspense>
          </Box>
        </Drawer>
      </div>
    </ThemeProvider>
  );
}
