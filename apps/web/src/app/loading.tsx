import { Box, Skeleton } from "@mui/material";

export default function Loading() {
  return <section className="section-surface" aria-busy="true" role="status" aria-label="Загрузка научных данных">
    <Box sx={{ maxWidth: 760 }}><Skeleton variant="text" width="46%" height={38} /><Skeleton variant="text" width="85%" height={22} /><Skeleton variant="text" width="70%" height={22} /></Box>
    <Skeleton variant="rectangular" height={240} sx={{ mt: 3, bgcolor: "#e4e9ee" }} />
    <p className="table-note">Загрузка данных API…</p>
  </section>;
}
