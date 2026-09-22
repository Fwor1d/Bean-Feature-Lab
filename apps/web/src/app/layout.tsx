import type { Metadata } from "next";
import { AppRouterCacheProvider } from "@mui/material-nextjs/v16-appRouter";
import { AppShell } from "@/components/AppShell";
import { api } from "@/lib/api/client";
import "@fontsource/golos-text/400.css";
import "@fontsource/golos-text/500.css";
import "@fontsource/golos-text/600.css";
import "@fontsource/golos-text/700.css";
import "./globals.css";

export const metadata: Metadata = { title: "BeanFeature Lab", description: "Рабочая станция исследования бюджета признаков" };

export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const [datasets, runs] = await Promise.all([api.datasets().catch(() => null), api.runs().catch(() => null)]);
  return (
    <html lang="ru">
      <body>
        <AppRouterCacheProvider>
          <AppShell datasets={datasets} runs={runs}>{children}</AppShell>
        </AppRouterCacheProvider>
      </body>
    </html>
  );
}
